"""Fine-tune the MTP draft's dense layers on the target's own ARC play (stitched V4 capture), step 1.

  python train_draft.py --cap DIR [--cap DIR ...] --ckpt MODEL_DIR --mask MASK.pt --hot HOT.pt --out OUT_DIR
                        [--steps 2000 --lr 2e-5 --rows 768 --holdout 0.2 --eval-every 200]

Objective: at every generated position p (row = target hc at p + token p+1), the draft's distribution over the
hot-token map should match the TARGET's distribution for token p+2, i.e. softmax(lm_head(target_mixer(hc_{p+1}))),
recomputed exactly from the captured hc (KL, target -> draft). A draft token is accepted with the target's probability
of it, so matching the target's argmax is what raises acceptance.
Trainable: the dense draft parameters (fusion, hyper-connections, attention incl. the QSA indexer, router, shared
expert, norms). Frozen: routed experts, embed_tokens, lm_head. Context keys/values (all positions before a query) are
computed with the current weights but without gradient; gradients flow through the query rows.
Held out: whole conversation chains (a request and every request that continues it), --holdout of them. With
--split game, whole GAMES instead: chains are keyed by the game's opening frame (first board image hash after the
shared system prompt), so the other capture run's session of a held-out game (and any fragment of it) stays out of
training too; that is the honest "never-seen game" number.
Eval (before training and every --eval-every steps, held-out chains): step-1 agreement with the target argmax and
accuracy against the token that was really sampled, for the fine-tuned draft (base numbers at step 0); expected tokens
per verify step, and its ceiling for a chain draft that always proposes the target's argmax (1 + m1 + m1m2 + m1m2m3,
m_s = the target's top probability at step s, teacher-forced).
Writes OUT_DIR/draft_ft.pt (dense mtp.* tensors, checkpoint names, bf16) and OUT_DIR/log.jsonl.
"""
import argparse
import gc
import json
import os
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_io import emb_plan, IMAGE_PAD_ID, load_capture, read_tensor, rope_positions, stitch  # noqa: E402
from draft_torch import EXPERTS, MAP, GatedResidual, gemma_rms, load_draft, read_tensors  # noqa: E402

EXPERT_PARAMS = {EXPERTS[0]: "gate_up", EXPERTS[1]: "down"}  # checkpoint name -> Draft attribute (kept experts)
ADAPTER = "mtp.step_adapter."  # saved per-guess adapter tensors (--step-adapter): ADAPTER + Draft attribute
AUX = "mtp.aux."  # saved multi-layer input tensors (--aux-layers): AUX + Draft attribute (aux_norm, aux_fc)
HC_W = 10240  # the layer-47 stream: the first HC_W columns of every captured hc row (aux captures append more)
SHX = "mtp.sh_extra."  # saved extra shared-expert columns (--sh-extra): SHX + Draft attribute (shx_gate/up/down)
UNTIE = "mtp.untie."  # saved untied copies for guesses >= 2 (--untie): UNTIE + c<copy>__<Draft attribute, . -> __>
_HCP = ("hc_norm", "down", "up")
UNTIE_SETS = {  # --untie presets (Draft attribute paths); the QSA indexer is left out: only guess 1 picks the tokens
    "fuse": ("pre_fc_norm_embedding", "pre_fc_norm_hidden", "fc_embedding", "fc_hidden"),
    "hc": tuple(f"{m}.{p}" for m in ("attn_hc", "mlp_hc") for p in _HCP + ("inject",)) + tuple(f"mixer.{p}" for p in _HCP),
    "attn": ("q_proj", "k_proj", "v_proj", "o_proj", "q_norm", "k_norm"),
    "ffn": ("router", "sh_gate", "sh_up", "sh_down", "sh_expert_gate"),
}
UNTIE_SETS["all"] = sum(UNTIE_SETS.values(), ())


class DiskStore:
    """--disk: HcStore's interface, reading hc rows from the capture files on demand (data bigger than host RAM)."""

    def __init__(self, reqs):
        self.files = {}

    def vec(self, path, head, row, n):
        return read_tensor(path, head, "mm_embeds", rows=(row, row + n))

    def context(self, r, end):
        parts, pos = [], 0
        for s, e, path, head, row in r.segments:
            if s >= end:
                break
            e2 = min(e, end)
            parts.append(read_tensor(path, head, "hc", rows=(row, row + e2 - s)))
            pos = e2
        assert pos == end
        return torch.cat(parts)


class HcStore:
    """Every captured hc row in host RAM, addressed by (file, row)."""

    def __init__(self, reqs):
        self.files = {}
        for r in reqs:
            for s, e, path, head, row in r.segments:
                if path not in self.files:
                    self.files[path] = read_tensor(path, head, "hc")

    def vec(self, path, head, row, n):
        key = (path, "mm_embeds")
        if key not in self.files:
            self.files[key] = read_tensor(path, head, "mm_embeds")
        return self.files[key][row:row + n]

    def context(self, r, end):
        parts, pos = [], 0
        for s, e, path, head, row in r.segments:
            if s >= end:
                break
            e2 = min(e, end)
            parts.append(self.files[path][row:row + e2 - s])
            pos = e2
        assert pos == end
        return torch.cat(parts)


def system_prefix(reqs):
    """The shared system prompt: the most common short cached prefix."""
    shorts = [r.prefix for r in reqs if r.prefix is not None and 0 < r.prefix < 16384]
    return max(set(shorts), key=shorts.count) if shorts else 0


def game_key(g, system, vocab=248320):
    """A chain's game: the first image (hash id, deterministic in the pixels) after the system prompt in its earliest
    request = the opening frame. Chains without one key to themselves."""
    root = min(g, key=lambda r: r.first_seq)
    img = next((int(t) for t in root.prompt[system:] if t >= vocab), None)
    return img if img is not None else ("chain", root.rid)


def chains(reqs):
    """Group stitched requests into conversations (ancestor links, union-find): hold-out splits whole games."""
    parent = {r.rid: r.rid for r in reqs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    # Every game's first request reuses the cached SYSTEM prompt, so a link through that shared prefix would merge all
    # games into one chain. The shared system prompt is the most common short prefix; link only past it.
    system = system_prefix(reqs)
    for r in reqs:
        if r.ancestor in parent and (r.prefix or 0) > system + 64:
            parent[find(r.rid)] = find(r.ancestor)
    groups = {}
    for r in reqs:
        groups.setdefault(find(r.rid), []).append(r)
    return list(groups.values())


MSTEPS = 3  # served draft steps trained and evaluated (--msteps)


def int4_rtn(w, group=32):
    """Daniel's drafter expert format (compressed-tensors pack-quantized): symmetric INT4 in [-8, 7], groups of 32 along
    the input (last) dim, scale = amax / 7.5 stored in bf16; returns the dequantized weights."""
    shp = w.shape
    g = w.float().reshape(*shp[:-1], shp[-1] // group, group)
    scale = (g.abs().amax(-1, keepdim=True) / 7.5).clamp_min(1e-12).to(torch.bfloat16).float()
    return ((g / scale).round().clamp(-8, 7) * scale).reshape(shp).to(w.dtype)


def query_rows(r):
    """Generated positions p whose steps 1..MSTEPS are all checkable: target hc up to p+MSTEPS, tokens to p+MSTEPS+1."""
    if getattr(r, "qrows", None) is not None:  # --span-rows (replay capture): rows set by replay_rows.assign
        return r.qrows
    L = min(r.segments[-1][1], len(r.tokens) - 1)
    start = len(r.prompt) - 1
    return list(range(start, L - MSTEPS)) if L - MSTEPS > start else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", action="append", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--mask", required=True)
    ap.add_argument("--hot", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--rows", type=int, default=768)
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--eval-every", type=int, default=200)
    ap.add_argument("--eval-rows", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--msteps", type=int, default=3, help="draft steps in the loss/eval (served: 3)")
    ap.add_argument("--step-weights", default="1,1,1")
    ap.add_argument("--split", choices=["chain", "game", "ttt", "named"], default="chain",
                    help="hold out whole chains or whole games; ttt = simulated test-time training: the held-out games "
                    "(as --split game) are cut in time, each game's earlier requests (--ttt-frac of its rows) train, "
                    "its later requests evaluate (start from --init: the draft tuned on the other games); named = "
                    "replay captures: --hold-games never train, and evaluate from the --eval-cap dirs (all --cap "
                    "dirs without --eval-cap)")
    ap.add_argument("--hold-games", default="", help="--split named: comma list of game ids (e.g. ar25,ft09)")
    ap.add_argument("--eval-cap", action="append", default=[],
                    help="--split named: capture dirs that only evaluate (their other games are dropped)")
    ap.add_argument("--span-rows", action="store_true",
                    help="replay captures (daniel-draft/replay): rows = the assistant turns re-rendered inside later "
                    "prompts (replay_rows.py), each turn once; the draft's input embedding at those rows is the "
                    "shifted token, as the served decode embedded it")
    ap.add_argument("--disk", action="store_true",
                    help="read hc rows from the capture files on demand instead of holding them in RAM")
    ap.add_argument("--hc-fp8", action="store_true",
                    help="storage study: TRAIN on hc rounded to fp8 e4m3 (one scale per row and stream), as if the "
                    "capture were stored in fp8 (half the bytes); eval keeps bf16 hc and also reports how far the "
                    "target's own distribution moves (fp8_target_agree / fp8_target_kl)")
    ap.add_argument("--ttt-frac", type=float, default=0.5)
    ap.add_argument("--int4-experts", action="store_true",
                    help="with --train-experts: after training, snap the experts to Daniel's drafter format (symmetric "
                    "INT4, groups of 32 along the input dim, bf16 scale = amax / 7.5) and evaluate again (step = steps+1)")
    ap.add_argument("--init", help="start from this draft_ft.pt (with --steps 0: evaluate it)")
    ap.add_argument("--loss", choices=["kl", "tvd", "rkl", "kl_tvd"], default="kl",
                    help="per-row divergence target -> draft over the hot map (tvd = 1 - acceptance of a draft sample)")
    ap.add_argument("--chain-weight", action="store_true",
                    help="weight step s rows by the (detached) chance steps < s were accepted, as in the served chain")
    ap.add_argument("--train-experts", action="store_true",
                    help="also train the routed experts (saved as the pruned [kept, ...] bf16 tensors; the server "
                    "re-quantizes them to NVFP4 online)")
    ap.add_argument("--expert-lr-scale", type=float, default=0.3, help="expert lr = --lr x this")
    ap.add_argument("--eval-temp", type=float, default=1.0,
                    help="eval also scores acceptance under the served sampling: target probs at this temperature, "
                    "then top-k / top-p renormalized as SGLang's verify does (served_* fields; 1.0 / 0 / 1.0 = off)")
    ap.add_argument("--eval-top-k", type=int, default=0)
    ap.add_argument("--eval-top-p", type=float, default=1.0)
    ap.add_argument("--eval-rs", action="store_true",
                    help="with the served sampling: also score rejection sampling (draft samples from q = its own "
                    "distribution under the same temperature / top-k / top-p, accepted with min(1, p/q): per-step "
                    "acceptance sum_x min(p, q)), as served by patch 0008 v2 (served_rs_* fields)")
    ap.add_argument("--fp8-kv", action="store_true",
                    help="round the draft's K/V through fp8 e4m3 (an fp8 draft KV cache) in eval and training "
                    "(straight-through gradient)")
    ap.add_argument("--step-adapter", type=int, default=0, metavar="RANK",
                    help="per-guess adapter of this rank on the fused input of guesses 2..--msteps (draft_torch "
                    "add_step_adapter; zero-initialized, so step 0 = the plain drafter); saved as mtp.step_adapter.*")
    ap.add_argument("--adapter-lr-scale", type=float, default=10.0, help="adapter lr = --lr x this")
    ap.add_argument("--aux-layers", type=int, default=0, metavar="N",
                    help="multi-layer input (drafter idea 2): the capture's hc rows carry N earlier-layer streams after "
                    "the layer-47 block (replay make_replay_notebook.py --aux-layers); the drafter reads them through a "
                    "zero-initialized aux path (draft_torch add_aux) for context rows and guess 1; saved as mtp.aux.*. "
                    "Without it an aux capture is read as layer 47 only")
    ap.add_argument("--aux-lr-scale", type=float, default=10.0, help="aux path lr = --lr x this")
    # drafter autoresearch (4-Oct): training-only knobs and one architecture option, all off by default
    ap.add_argument("--train-seed", type=int, default=None,
                    help="seed of the training data order only (default: --seed, which also picks the held-out split): "
                    "a seed-noise replica on the SAME held-out games")
    ap.add_argument("--loss-temp", type=float, default=1.0,
                    help="divergence between target and draft both at this temperature (served sampling is T 0.6)")
    ap.add_argument("--batch-reqs", type=int, default=1,
                    help="requests per optimizer step (--rows rows from each, gradients accumulated)")
    ap.add_argument("--sched", choices=["linear", "cosine", "plateau"], default="linear",
                    help="lr decay after warmup, down to --lr-floor x lr at --steps (or --time-budget); plateau = "
                    "adaptive: constant lr, x --plateau-factor when an internal validation loss stops improving")
    ap.add_argument("--warmup", type=int, default=100, help="linear warmup steps")
    ap.add_argument("--lr-floor", type=float, default=0.1, help="final lr as a share of --lr")
    ap.add_argument("--decay-frac", type=float, default=None,
                    help="earlier taper: linear/cosine decay reaches --lr-floor at this share of the run, then holds")
    ap.add_argument("--plateau-every", type=int, default=250,
                    help="--sched plateau: check the internal validation loss every N steps (counted in the budget)")
    ap.add_argument("--plateau-patience", type=int, default=2, help="--sched plateau: checks without improvement")
    ap.add_argument("--plateau-factor", type=float, default=0.5, help="--sched plateau: lr multiplier per cut")
    ap.add_argument("--plateau-min", type=float, default=0.05, help="--sched plateau: lowest lr multiplier")
    ap.add_argument("--plateau-tol", type=float, default=0.002, help="--sched plateau: relative improvement needed")
    ap.add_argument("--val-rows", type=int, default=4096,
                    help="--sched plateau: internal validation rows (256-row windows from held-back TRAINING requests)")
    ap.add_argument("--sh-extra", type=int, default=0, metavar="N",
                    help="architecture: N more shared-expert columns (draft_torch add_sh_extra, zero-init down "
                    "projection); saved as mtp.sh_extra.*")
    ap.add_argument("--sh-extra-lr-scale", type=float, default=10.0, help="extra shared-expert lr = --lr x this")
    ap.add_argument("--untie", default="",
                    help="architecture: guesses >= 2 get their own copies of these dense parameters (draft_torch "
                    "add_untie; comma list of presets fuse,hc,attn,ffn,all or Draft attribute paths), copied from the "
                    "shared ones; saved as mtp.untie.*")
    ap.add_argument("--untie-groups", type=int, default=1,
                    help="copies for guesses >= 2: guess s uses copy min(K - 1, s - 2) (1 = one shared copy)")
    ap.add_argument("--time-budget", type=float, default=0.0, metavar="SECONDS",
                    help="autoresearch: stop training after this much training time (evals excluded), then evaluate; "
                    "the lr decays on time progress (elapsed / budget) instead of --steps (warmup stays in steps); "
                    "set --steps above what fits. No step-0 eval unless the queue spec sets eval0")
    ap.add_argument("--resume-state", metavar="PATH",
                    help="continue a run from its train_state.pt (weights + AdamW memory + step + rng): resumes at the "
                    "lr it ended on, no second warmup, then tapers to --lr-floor x that lr by --steps (total steps)")
    ap.add_argument("--no-save-state", action="store_true",
                    help="skip OUT/train_state.pt (saved by default at every eval: ~4x the trainable weights in fp32)")
    ap.add_argument("--train-frac", type=float, default=1.0,
                    help="data-scaling curve: train on this share of the training chains (by rows; a fixed shuffle, so "
                    "a smaller share is a subset of a larger one); the held-out set is unchanged")
    ap.add_argument("--queue", help="autoresearch worker: load the data once, then run every trial spec <name>.json "
                    "that appears in this dir (keys: lr steps rows loss chain_weight step_weights seed init), each "
                    "from the base draft, into OUT/<name>/; a file named STOP ends the worker")
    ap.add_argument("--queue-rebuild", action="store_true",
                    help="with --queue: build a fresh drafter for every trial, so a spec may also set architecture "
                    "options (step_adapter, sh_extra, untie, untie_groups) and msteps (e.g. a 3-step guard eval: "
                    "{init, steps: 0, msteps: 3}); a spec {bench: [variants]} runs bench_draft_cost.py instead")
    a = ap.parse_args()
    # multi-GPU (Son 5-Oct): launched by torchrun -> RANK/WORLD_SIZE/LOCAL_RANK set; data-parallel by hand: every rank
    # loads the same data and model (same seeds -> same split and init), draws its own batches, gradients averaged
    # with one all-reduce per step; rank 0 alone evaluates, logs and saves. WORLD_SIZE 1 = the old single-GPU path.
    rank, world = int(os.environ.get("RANK", 0)), int(os.environ.get("WORLD_SIZE", 1))
    if world > 1:
        import datetime
        import torch.distributed as dist
        torch.cuda.set_device(int(os.environ.get("LOCAL_RANK", 0)))
        dist.init_process_group("nccl", timeout=datetime.timedelta(hours=2))
        assert not a.queue, "multi-GPU: no --queue (one run per launch)"
        assert not getattr(a, "time_budget", 0), "multi-GPU: no --time-budget (ranks would stop at different steps)"
    global MSTEPS
    MSTEPS = a.msteps
    import draft_torch
    draft_torch.FAKE_FP8_KV = a.fp8_kv
    sw = [float(x) for x in a.step_weights.split(",")][:MSTEPS]
    a.out.mkdir(parents=True, exist_ok=True)
    random.seed(a.seed)
    torch.manual_seed(a.seed)
    log = open(a.out / "log.jsonl", "a")

    sink = {"trial": None, "log": None}  # worker mode: the running trial and its own log

    def emit(**kw):
        if rank != 0:
            return
        if sink["trial"]:
            kw = {"trial": sink["trial"], **kw}
        kw["t"] = round(time.time(), 1)
        print(json.dumps(kw), flush=True)
        for f in (log, sink["log"]):
            if f is not None:
                f.write(json.dumps(kw) + "\n")
                f.flush()

    reqs, loaded = [], []
    eval_only, span_stats = set(), {}
    for cap in a.cap + a.eval_cap:
        rq = load_capture(cap)
        stitch(rq)
        if a.span_rows:
            import replay_rows
            span_stats[cap] = replay_rows.assign(rq, MSTEPS)
        loaded.append(rq)
        got = [r for r in rq.values() if r.segments and query_rows(r)]
        if cap in a.eval_cap:
            eval_only.update(id(r) for r in got)
        reqs += got
    import capture_io  # exact MRoPE positions everywhere: shapes learned from captures that recorded them (V6)
    for rq in loaded:
        capture_io.MROPE_SHAPES.update(capture_io.learn_mrope_shapes(rq))
    groups = chains(reqs)
    size = lambda g: sum(len(query_rows(r)) for r in g)  # noqa: E731
    big = sorted((g for g in groups if size(g) >= 5000), key=size, reverse=True)  # real games; the rest are
    random.shuffle(big)                                                            # warmups, canaries, probes
    games = None
    if a.split == "chain":
        n_hold = max(2, int(round(len(big) * a.holdout)))
        hold_ids = {id(g) for g in big[:n_hold]}
        hold = [r for g in big[:n_hold] for r in g]
        train = [r for g in groups if id(g) not in hold_ids for r in g]
    elif a.split == "named":  # replay captures: games held out by name, evaluated from runs that never train
        import replay_rows
        held = {g for g in a.hold_games.split(",") if g}
        n_hold = len(held)
        hold = [r for r in reqs if replay_rows.game_of(r.rid) in held and (id(r) in eval_only or not a.eval_cap)]
        train = [r for r in reqs if replay_rows.game_of(r.rid) not in held and id(r) not in eval_only]
        random.Random(7).shuffle(hold)  # evaluate() stops at --eval-rows: sample every held game, not the first
        games = {"held_games": sorted(held), "span_stats": span_stats,
                 "held_rows_by_game": {g: sum(len(query_rows(r)) for r in hold if replay_rows.game_of(r.rid) == g)
                                       for g in sorted(held)},
                 "train_games": len({replay_rows.game_of(r.rid) for r in train})}
    else:
        system = system_prefix(reqs)
        keys = list(dict.fromkeys(game_key(g, system) for g in big))  # shuffled order
        n_hold = max(2, int(round(len(keys) * a.holdout)))
        held = set(keys[:n_hold])
        hold = [r for g in big if game_key(g, system) in held for r in g]
        train = [r for g in groups if game_key(g, system) not in held for r in g]
        games = {"games": len(keys), "held_games": n_hold,
                 "held_chains": sum(1 for g in big if game_key(g, system) in held)}
        if a.split == "ttt":  # each held-out game: earlier requests train, later requests evaluate
            by_game = {}
            for g in big:
                if game_key(g, system) in held:
                    by_game.setdefault(game_key(g, system), []).extend(g)
            train, hold = [], []
            for rs in by_game.values():
                rs = sorted(rs, key=lambda r: r.first_seq)
                total, acc, cut = sum(len(query_rows(r)) for r in rs), 0, 0
                while cut < len(rs) and acc < a.ttt_frac * total:
                    acc += len(query_rows(rs[cut])); cut += 1
                train += rs[:cut]
                hold += rs[cut:]
            games["ttt_games"] = len(by_game)
    if a.train_frac < 1:  # Son 4-Oct: does the drafter keep improving with more data? same held-out set, less train
        tg = chains(train)
        random.Random(1234).shuffle(tg)
        total, acc, keep = sum(size(g) for g in tg), 0, []
        for g in tg:
            if acc >= a.train_frac * total:
                break
            keep.append(g)
            acc += size(g)
        train = [r for g in keep for r in g]
    store = DiskStore(reqs) if a.disk else HcStore(reqs)
    emit(event="data", config={k: str(v) for k, v in vars(a).items() if k != "cap"}, split=a.split, games=games, requests=len(reqs), chains=len(groups), game_chains=len(big),
         holdout_chains=n_hold,
         train_rows=sum(len(query_rows(r)) for r in train), holdout_rows=sum(len(query_rows(r)) for r in hold),
         ram_gb=round(sum(t.numel() * 2 for t in store.files.values()) / 2 ** 30, 1),
         mrope_shapes={str(k): v for k, v in capture_io.MROPE_SHAPES.items()})

    hot = torch.load(a.hot) if a.hot.endswith(".pt") else json.load(open(a.hot))
    dev = torch.device("cuda")
    def untie_names(spec):
        names = []
        for tok in str(spec).split(","):
            for n in UNTIE_SETS.get(tok.strip(), (tok.strip(),) if tok.strip() else ()):
                if n not in names:
                    names.append(n)
        return names

    def build_draft():  # the base drafter + the architecture options in `a` (queue mode: rebuilt for every trial)
        d = load_draft(a.ckpt, a.mask, hot, dtype=torch.float32, device=dev)
        for attr in EXPERT_PARAMS.values():  # buffers -> fp32 Parameters, frozen unless a trial trains them
            w = getattr(d, attr)
            del d._buffers[attr]
            setattr(d, attr, torch.nn.Parameter(w.float(), requires_grad=False))
        if a.step_adapter:
            d.add_step_adapter(MSTEPS, a.step_adapter)
        if a.aux_layers:
            d.add_aux(a.aux_layers)
        if a.sh_extra:
            d.add_sh_extra(a.sh_extra)
        if a.untie:
            d.add_untie(untie_names(a.untie), a.untie_groups)
        return d

    draft = build_draft()

    def load_init(path):  # a previous fine-tune (checkpoint names, as saved below)
        init = torch.load(path)
        if any(ck.startswith(ADAPTER) for ck in init) and not hasattr(draft, "step_A"):
            A = init[ADAPTER + "step_A"]  # a saved adapter: build it with the saved shape (guesses 2..n+1, rank)
            draft.add_step_adapter(A.shape[0] + 1, A.shape[1])
        if any(ck.startswith(AUX) for ck in init) and not hasattr(draft, "aux_fc"):
            draft.add_aux(init[AUX + "aux_fc"].shape[1] // 2560)  # a saved aux path: same number of layers
        if any(ck.startswith(SHX) for ck in init) and not hasattr(draft, "shx_down"):
            draft.add_sh_extra(init[SHX + "shx_down"].shape[1])  # saved extra shared-expert columns: same width
        ukeys = [ck[len(UNTIE):] for ck in init if ck.startswith(UNTIE)]
        if ukeys and not hasattr(draft, "untie"):  # saved untied copies: same parameters, same number of copies
            unames = list(dict.fromkeys(k.split("__", 1)[1].replace("__", ".") for k in ukeys))
            draft.add_untie(unames, 1 + max(int(k.split("__", 1)[0][1:]) for k in ukeys))
        own = dict(draft.named_parameters())
        with torch.no_grad():
            for ck, v in init.items():
                if ck.startswith(ADAPTER):
                    dst = own[ck[len(ADAPTER):]]
                    n = min(dst.shape[0], v.shape[0])  # an adapter trained for fewer/more guesses: the shared ones
                    dst[:n].copy_(v[:n].to(torch.float32))
                    continue
                if ck.startswith(AUX):
                    own[ck[len(AUX):]].copy_(v.to(torch.float32))
                    continue
                if ck.startswith(SHX):
                    own[ck[len(SHX):]].copy_(v.to(torch.float32))
                    continue
                if ck.startswith(UNTIE):
                    own["untie." + ck[len(UNTIE):]].copy_(v.to(torch.float32))
                    continue
                own[MAP.get(ck) or EXPERT_PARAMS[ck]].copy_(v.to(torch.float32))
        if hasattr(draft, "untie") and not ukeys:  # --untie on a checkpoint without copies: copy what was loaded
            draft.untie_sync()
        emit(event="init", path=path, tensors=len(init))

    if a.init and not a.queue:
        load_init(a.init)
    base_state = {k: v.detach().clone() for k, v in draft.named_parameters()}
    tm = GatedResidual(combine=False).to(dev)  # the TARGET's final mixer (frozen): target logits from captured hc
    names = {"hc_norm": "model.language_model.hyper_connection_mixer.hc_norm.weight",
             "down": "model.language_model.hyper_connection_mixer.input_mix_weight_down.weight",
             "up": "model.language_model.hyper_connection_mixer.input_mix_weight_up.weight"}
    got = read_tensors(a.ckpt, list(names.values()))
    for attr, n in names.items():
        getattr(tm, attr).data = got[n].float().to(dev)
    tm.requires_grad_(False)
    W_hot = draft.lm_head[draft.hot]  # [65536, 2560] bf16

    def target_logp(hc_next):
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            m = tm.mix(hc_next)[0]
            return F.log_softmax(F.linear(m, W_hot).float(), -1)

    hot_index = torch.full((draft.lm_head.shape[0],), -1, dtype=torch.long, device=dev)
    hot_index[draft.hot] = torch.arange(draft.hot.numel(), device=dev)

    io_pool = None
    if a.disk:
        from concurrent.futures import ThreadPoolExecutor
        io_pool = ThreadPoolExecutor(4)

    def ahead(items, depth=3):
        """--disk: (r, rows) -> (r, rows, hc on host), reading the next `depth` contexts while the GPU works."""
        q = []
        for r, rows in items:
            q.append((r, rows, io_pool.submit(store.context, r, rows[-1] + MSTEPS + 1)))
            if len(q) > depth:
                r0, rows0, f0 = q.pop(0)
                yield r0, rows0, f0.result()
        for r0, rows0, f0 in q:
            yield r0, rows0, f0.result()

    def fp8_store(h):
        """--hc-fp8: hc as an fp8 capture would hold it: e4m3 with one scale per (row, 2560-wide stream)."""
        x = h.float().unflatten(-1, (4, -1))
        s = x.abs().amax(-1, keepdim=True).clamp_min(1e-12) / 448.0
        return ((x / s).to(torch.float8_e4m3fn).float() * s).flatten(-2).to(h.dtype)

    def batch(r, rows, hc=None, fp8=False):
        end = rows[-1] + MSTEPS + 1
        hc = store.context(r, end) if hc is None else hc
        aux = None
        if hc.shape[-1] > HC_W:  # an aux capture: [layer 47 | earlier layers]; only the drafter's aux path reads the rest
            if hasattr(draft, "aux_fc"):
                aux = hc[:, HC_W:HC_W + draft.aux_fc.shape[1] * 4].to(dev, non_blocking=True)
            hc = hc[:, :HC_W].contiguous()
        hc = hc.to(dev, non_blocking=True)
        if fp8:
            hc = fp8_store(hc)
        toks = torch.as_tensor(r.tokens[: end + 1], device=dev)
        rows_t = torch.as_tensor(rows, device=dev)
        tok, vecs = emb_plan(r, end)  # what the served draft embedded at each context row (image chunks differ)
        t = torch.as_tensor(tok, device=dev)
        t = torch.where(t >= draft.embed.shape[0], torch.full_like(t, IMAGE_PAD_ID), t).clamp_min(0)
        e_in = draft.embed[t]
        for s0, n, path, head, row in vecs:
            e_in[s0:s0 + n] = store.vec(path, head, row, n).to(dev, e_in.dtype)
        if a.span_rows and getattr(r, "gen_spans", None):  # replayed turns were decoded when served: shifted token
            for g0, g1 in r.gen_spans:
                lo, hi = g0 - 1, min(g1 - 1, end)
                if lo < hi:
                    e_in[lo:hi] = draft.embed[toks[lo + 1:hi + 1]]
        rpos = rope_positions(r, end).to(dev)  # MRoPE (V6 capture) or logical positions
        return hc, toks, rows_t, e_in, rpos, aux

    def forward(hc, toks, rows_t, e_in, rpos, grad, aux=None):
        """log-probs over the hot map for steps 1..MSTEPS (draft_torch.forward_steps, teacher-forced)."""
        with torch.autocast("cuda", dtype=torch.bfloat16):
            n_ctx = int(rows_t[-1]) + 1
            ctx_hc, ctx_e = hc[:n_ctx], e_in[:n_ctx]
            ctx_aux = None if aux is None else aux[:n_ctx]
            if grad:
                with torch.no_grad():
                    y_all, (x0, xn) = draft.attn_hc.mix(draft.fuse(None, ctx_hc, ctx_e, ctx_aux))
                    ck, cv, kc = draft.ctx_keys(y_all, rpos)
                mixed = draft.forward_steps(ctx_hc, ctx_e, rows_t, toks, MSTEPS, ctx=(y_all, x0, xn, ck, cv, kc),
                                            rows_grad=True, rpos=rpos, aux=ctx_aux)
            else:
                mixed = draft.forward_steps(ctx_hc, ctx_e, rows_t, toks, MSTEPS, rpos=rpos, aux=ctx_aux)
            return [F.log_softmax(draft.logits(m).float(), -1) for m in mixed]

    served = a.eval_temp != 1.0 or a.eval_top_k > 0 or a.eval_top_p < 1.0

    def served_logp(tl):
        """Target log-probs (T=1, hot map) -> the served verify distribution: temperature, top-k, then top-p."""
        lp = F.log_softmax(tl / a.eval_temp, -1)
        if a.eval_top_k > 0:
            kth = lp.topk(a.eval_top_k, -1).values[:, -1:]
            lp = F.log_softmax(lp.masked_fill(lp < kth, float("-inf")), -1)
        if a.eval_top_p < 1.0:
            srt, idx = lp.exp().sort(-1, descending=True)
            drop = (srt.cumsum(-1) - srt) >= a.eval_top_p  # keep the smallest prefix reaching top_p
            lp = F.log_softmax(lp.masked_fill(torch.zeros_like(drop).scatter(1, idx, drop), float("-inf")), -1)
        return lp

    def evaluate(step):
        """Held-out games: per step, agreement with the target argmax, accuracy vs the sampled token and KL; plus the
        expected tokens per verify step 1 + a1 + a1a2 + a1a2a3 (a_s = target probability of the step-s proposal,
        teacher-forced chain), comparable to sglang:spec_accept_length; with --eval-temp/top-k/top-p, the same under
        the served sampling (served_*)."""
        rng = random.Random(1234)
        n = 0
        agree, acc, kl = [0] * MSTEPS, [0] * MSTEPS, [0.0] * MSTEPS
        exp_len = oracle_len = 0.0
        s_exp_len = s_oracle_len = rs_exp_len = 0.0
        rs_acc = [0.0] * MSTEPS
        fp8_cmp = [0, 0.0]
        draft.eval()

        def picks():
            for r in (hold if a.split == "named" else sorted(hold, key=lambda r: r.rid)):
                rows = query_rows(r)
                if len(rows) > 384:
                    i = rng.randrange(0, len(rows) - 384)
                    rows = rows[i:i + 384]
                yield r, rows
        for r, rows, hc_pre in (ahead(picks()) if a.disk else ((r, rows, None) for r, rows in picks())):
            hc, toks, rows_t, e_in, rpos, aux = batch(r, rows, hc_pre)
            with torch.no_grad():
                lps = forward(hc, toks, rows_t, e_in, rpos, grad=False, aux=aux)
                chain = torch.ones(len(rows), device=dev)
                total = torch.ones(len(rows), device=dev)
                o_chain = torch.ones(len(rows), device=dev)  # ceiling: a draft that always proposes the target argmax
                o_total = torch.ones(len(rows), device=dev)
                s_chain, s_total = torch.ones(len(rows), device=dev), torch.ones(len(rows), device=dev)
                so_chain, so_total = torch.ones(len(rows), device=dev), torch.ones(len(rows), device=dev)
                rs_chain, rs_total = torch.ones(len(rows), device=dev), torch.ones(len(rows), device=dev)
                for s_, lp in enumerate(lps):
                    tl = target_logp(hc[rows_t + s_ + 1])
                    if a.hc_fp8 and s_ == 0:  # how far fp8 storage moves the target's own next-token distribution
                        tq = target_logp(fp8_store(hc[rows_t + 1]))
                        fp8_cmp[0] += int((tq.argmax(-1) == tl.argmax(-1)).sum())
                        fp8_cmp[1] += float((tl.exp() * (tl - tq)).sum(-1).sum())
                    prop = lp.argmax(-1)
                    agree[s_] += int((prop == tl.argmax(-1)).sum())
                    acc[s_] += int((prop == hot_index[toks[rows_t + s_ + 2]]).sum())
                    kl[s_] += float((tl.exp() * (tl - lp)).sum(-1).sum())
                    chain = chain * tl.gather(1, prop[:, None]).squeeze(1).exp()
                    total = total + chain
                    o_chain = o_chain * tl.max(-1).values.exp()
                    o_total = o_total + o_chain
                    if served:
                        sl = served_logp(tl)
                        s_chain = s_chain * sl.gather(1, prop[:, None]).squeeze(1).exp()
                        s_total = s_total + s_chain
                        so_chain = so_chain * sl.max(-1).values.exp()
                        so_total = so_total + so_chain
                        if a.eval_rs:  # q = the draft's distribution under the same sampling transform as p
                            a_rs = torch.minimum(sl.exp(), served_logp(lp).exp()).sum(-1)
                            rs_acc[s_] += float(a_rs.sum())
                            rs_chain = rs_chain * a_rs
                            rs_total = rs_total + rs_chain
                exp_len += float(total.sum())
                oracle_len += float(o_total.sum())
                s_exp_len += float(s_total.sum())
                s_oracle_len += float(so_total.sum())
                rs_exp_len += float(rs_total.sum())
            n += len(rows)
            del hc
            if n >= a.eval_rows:
                break
        draft.train()
        extra = {}
        if served:
            extra = {"served_sampling": f"T{a.eval_temp} top_k {a.eval_top_k} top_p {a.eval_top_p}",
                     "served_expected_tokens_per_step": round(s_exp_len / n, 4),
                     "served_ceiling_tokens_per_step": round(s_oracle_len / n, 4)}
            if a.eval_rs:
                extra.update(served_rs_expected_tokens_per_step=round(rs_exp_len / n, 4),
                             served_rs_accept=[round(x / n, 4) for x in rs_acc])
        if a.hc_fp8:
            extra.update(fp8_target_agree=round(fp8_cmp[0] / n, 5), fp8_target_kl=round(fp8_cmp[1] / n, 6))
        emit(event="eval", step=step, rows=n, expected_tokens_per_step=round(exp_len / n, 4),
             ceiling_tokens_per_step=round(oracle_len / n, 4),
             agree_target_argmax=[round(x / n, 4) for x in agree], acc_sampled_token=[round(x / n, 4) for x in acc],
             kl=[round(x / n, 4) for x in kl], **extra)

    def divergence(tl, lp):
        """Per-row divergence between the target (tl) and the draft (lp) log-probs over the hot map."""
        if a.loss == "kl":
            return (tl.exp() * (tl - lp)).sum(-1)
        if a.loss == "rkl":
            return (lp.exp() * (lp - tl)).sum(-1)
        tvd = 0.5 * (tl.exp() - lp.exp()).abs().sum(-1)
        return tvd if a.loss == "tvd" else tvd + (tl.exp() * (tl - lp)).sum(-1)

    def weighted(per_row, w):
        return (per_row * w).sum() / w.sum().clamp_min(1e-6) if a.chain_weight else per_row.mean()

    def train_once(out):
        sw = [float(x) for x in str(a.step_weights).split(",")][:MSTEPS]
        tseed = a.seed if getattr(a, "train_seed", None) is None else int(a.train_seed)
        random.seed(tseed + 7919 * rank)  # each rank draws its own batches (rank 0 = the single-GPU stream)
        torch.manual_seed(tseed)
        experts = [getattr(draft, attr) for attr in EXPERT_PARAMS.values()]
        for w in experts:
            w.requires_grad_(bool(a.train_experts))
        ex_ids = {id(w) for w in experts}
        ad = [p for k, p in draft.named_parameters() if k.startswith("step_")]
        ax = [p for k, p in draft.named_parameters() if k.startswith("aux_")]
        sx = [p for k, p in draft.named_parameters() if k.startswith("shx_")]
        ad_ids = {id(p) for p in ad + ax + sx}
        dense = [p for p in draft.parameters() if p.requires_grad and id(p) not in ex_ids and id(p) not in ad_ids]
        groups = [{"params": dense, "lr": a.lr}]
        if ad:  # zero-initialized adapter: it starts from nothing, so it gets a larger step than the pretrained layer
            groups.append({"params": ad, "lr": a.lr * float(a.adapter_lr_scale)})
        if ax:  # zero-initialized aux path (--aux-layers): same reasoning as the adapter
            groups.append({"params": ax, "lr": a.lr * float(a.aux_lr_scale)})
        if sx:  # extra shared-expert columns (--sh-extra), zero-initialized down projection: same reasoning
            groups.append({"params": sx, "lr": a.lr * float(a.sh_extra_lr_scale)})
        if a.train_experts:
            groups.append({"params": experts, "lr": a.lr * float(a.expert_lr_scale)})
        params = [p for g in groups for p in g["params"]]
        opt = torch.optim.AdamW(groups, lr=a.lr, weight_decay=0.0, betas=(0.9, 0.98))
        warm, floor = max(1, int(getattr(a, "warmup", 100))), float(getattr(a, "lr_floor", 0.1))
        budget = float(getattr(a, "time_budget", 0) or 0)
        clock = [0.0]  # --time-budget: training seconds so far (evals excluded)
        prog = (lambda s: min(1.0, clock[0] / budget)) if budget else (lambda s: s / max(1, a.steps))  # noqa: E731
        mode = getattr(a, "sched", "linear")
        dfrac = getattr(a, "decay_frac", None)
        pmult = [1.0]  # --sched plateau: the current lr multiplier
        if mode == "plateau":
            lr_fn = lambda s: min(1.0, (s + 1) / warm) * pmult[0]  # noqa: E731
        elif dfrac:  # --decay-frac: reach the floor at this share of the run, then hold it
            import math
            pd = lambda s: min(1.0, prog(s) / float(dfrac))  # noqa: E731
            if mode == "cosine":
                lr_fn = lambda s: min(1.0, (s + 1) / warm) * (floor + (1 - floor) * 0.5 * (1 + math.cos(  # noqa: E731
                    math.pi * pd(s))))
            else:
                lr_fn = lambda s: min(1.0, (s + 1) / warm) * (1 - (1 - floor) * pd(s))  # noqa: E731
        elif mode == "cosine":
            import math
            lr_fn = lambda s: min(1.0, (s + 1) / warm) * (floor + (1 - floor) * 0.5 * (1 + math.cos(  # noqa: E731
                math.pi * min(1.0, prog(s)))))
        else:  # the default (100 steps warmup, linear to 0.1x): min(1, (s+1)/100) * max(0.1, 1 - s/steps)
            lr_fn = lambda s: min(1.0, (s + 1) / warm) * max(floor, 1 - prog(s))  # noqa: E731
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_fn)
        n_req = max(1, int(getattr(a, "batch_reqs", 1) or 1))
        ltemp = float(getattr(a, "loss_temp", 1.0) or 1.0)
        pool, val_win = train, []
        if mode == "plateau":  # internal validation slice: whole training REQUESTS (their generated rows) held out of
            # training, one 256-row window each; never the locked eval games or the fixed 5-game eval set
            cand = sorted((r for r in train if len(query_rows(r)) >= 256), key=lambda r: str(r.rid))
            random.Random(4321).shuffle(cand)
            vr = cand[:max(1, int(getattr(a, "val_rows", 4096)) // 256)]
            vids = {id(r) for r in vr}
            for j, r in enumerate(vr):
                rows = query_rows(r)
                i = random.Random(j).randrange(0, len(rows) - 256 + 1)
                val_win.append((r, rows[i:i + 256]))
            pool = [r for r in train if id(r) not in vids]
            emit(event="plateau_val", windows=len(val_win), rows=256 * len(val_win))

        def val_loss():
            tot = 0.0
            for r, rows in val_win:
                hc, toks, rows_t, e_in, rpos, aux = batch(r, rows)
                with torch.no_grad():
                    lps = forward(hc, toks, rows_t, e_in, rpos, grad=False, aux=aux)
                    ls = []
                    for s_, lp in enumerate(lps):
                        tl = target_logp(hc[rows_t + s_ + 1])
                        if ltemp != 1.0:
                            tl, lp = F.log_softmax(tl / ltemp, -1), F.log_softmax(lp / ltemp, -1)
                        ls.append(float(divergence(tl, lp).mean()))
                tot += sum(w * l for w, l in zip(sw, ls)) / sum(sw)
                del hc, lps
            draft.train()
            return tot / len(val_win)
        pstate = {"best": float("inf"), "bad": 0}
        weights = [len(query_rows(r)) for r in pool]
        if a.int4_experts and a.train_experts:  # baseline: how far re-quantizing the untrained experts moves them
            with torch.no_grad():
                rel = [float((int4_rtn(w) - w).norm() / w.norm()) for w in experts]
            emit(event="int4_check", requant_rel_change_before_training=[round(x, 4) for x in rel])
        want0 = not a.queue or a.init or a.steps == 0 or getattr(a, 'eval0', False)  # worker: base eval once, by spec
        if budget and a.steps > 0 and not getattr(a, 'eval0', False):  # --time-budget: the base is already known
            want0 = False
        s0 = 0
        if getattr(a, "resume_state", None):  # Son 5-Oct: continue a run exactly where it stopped (optimizer memory kept)
            st = torch.load(a.resume_state, map_location="cpu", weights_only=False)
            own = dict(draft.named_parameters())
            with torch.no_grad():
                for k, v in st["params"].items():
                    own[k].copy_(v.to(own[k].device, own[k].dtype))
            opt.load_state_dict(st["opt"])
            s0, m_end = int(st["step"]), float(st["lr_mult"])
            pmult[0] = float(st.get("pmult", 1.0))
            pstate.update(st.get("pstate", {}))
            random.setstate(st["rng"]["py"])
            torch.set_rng_state(st["rng"]["torch"])
            torch.cuda.set_rng_state_all(st["rng"]["cuda"])
            if world > 1:  # the saved python rng is rank 0's: give the other ranks their own streams again
                random.seed(int(st["args"].get("seed", 0)) + 7919 * rank + s0)
            rem = max(1, a.steps - s0)  # resume at the lr the run ended on (no second warmup), taper to floor x that
            sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda e: m_end * max(floor, 1 - e / rem))
            emit(event="resume", path=a.resume_state, step=s0, lr_mult=m_end, lr=opt.param_groups[0]["lr"],
                 to_steps=a.steps)
            want0 = True

        def save_state(step):  # Son 5-Oct: every run keeps a resumable state (weights + optimizer + schedule + rng)
            if getattr(a, "no_save_state", False):
                return
            st = {"step": step, "params": {k: v.detach().float().cpu() for k, v in draft.named_parameters()
                                           if v.requires_grad},
                  "opt": opt.state_dict(), "lr_mult": opt.param_groups[0]["lr"] / opt.param_groups[0]["initial_lr"],
                  "pmult": pmult[0], "pstate": dict(pstate),
                  "rng": {"py": random.getstate(), "torch": torch.get_rng_state(),
                          "cuda": torch.cuda.get_rng_state_all()},
                  "args": {k: str(v) for k, v in vars(a).items()}}
            torch.save(st, out / "train_state.pt.tmp")
            (out / "train_state.pt.tmp").replace(out / "train_state.pt")

        if want0 and rank == 0:
            evaluate(s0)
        if world > 1:
            dist.barrier()
        t0 = time.time()

        def picks():
            while True:
                r = random.choices(pool, weights=weights)[0]
                rows = query_rows(r)
                if len(rows) > a.rows:
                    i = random.randrange(0, len(rows) - a.rows)
                    rows = rows[i:i + a.rows]
                yield r, rows
        stream = ahead(picks()) if a.disk else ((r, rows, None) for r, rows in picks())
        for step in range(s0 + 1, a.steps + 1):
            t_step = time.time()
            prof = step % 50 == 1 and n_req == 1  # per-step time split every 50 steps (Son 5-Oct: where does it go?)
            tp = [time.time()]
            opt.zero_grad(set_to_none=True)
            parts = []
            for _micro in range(n_req):  # --batch-reqs: one request per micro-batch, gradients summed (mean)
                r, rows, hc_pre = next(stream)
                hc, toks, rows_t, e_in, rpos, aux = batch(r, rows, hc_pre, fp8=a.hc_fp8)
                if prof:
                    torch.cuda.synchronize()
                    tp.append(time.time())
                lps = forward(hc, toks, rows_t, e_in, rpos, grad=True, aux=aux)
                losses = []
                reach = torch.ones(len(rows), device=dev)  # chance the served chain gets to step s (detached)
                for s_, lp in enumerate(lps):
                    tl = target_logp(hc[rows_t + s_ + 1])
                    if ltemp != 1.0:  # --loss-temp: both distributions at the served temperature
                        losses.append(weighted(divergence(F.log_softmax(tl / ltemp, -1), F.log_softmax(lp / ltemp, -1)),
                                               reach))
                    else:
                        losses.append(weighted(divergence(tl, lp), reach))
                    if a.chain_weight:
                        with torch.no_grad():
                            reach = reach * tl.gather(1, lp.argmax(-1)[:, None]).squeeze(1).exp()
                loss = sum(w * l for w, l in zip(sw, losses)) / sum(sw)
                if n_req == 1:
                    loss.backward()
                    if prof:
                        torch.cuda.synchronize()
                        tp.append(time.time())
                else:
                    (loss / n_req).backward()
                    parts.append((loss.detach(), [l.detach() for l in losses]))
                    ctx_len = int(hc.shape[0])
                    del hc, lps, toks, rows_t, e_in, rpos, aux
            if n_req > 1:  # what the log reports: the mean over the micro-batches
                loss = sum(p_[0] for p_ in parts) / n_req
                losses = [sum(p_[1][i] for p_ in parts) / n_req for i in range(len(parts[0][1]))]
                hc = torch.empty(ctx_len, 0)
            if world > 1:  # data parallel: average the gradients of all ranks (one flat all-reduce)
                from torch._utils import _flatten_dense_tensors, _unflatten_dense_tensors
                for p_ in params:
                    if p_.grad is None:
                        p_.grad = torch.zeros_like(p_)
                grads = [p_.grad for p_ in params]
                flat = _flatten_dense_tensors(grads)
                dist.all_reduce(flat)
                flat.div_(world)
                for g_, s_ in zip(grads, _unflatten_dense_tensors(flat, grads)):
                    g_.copy_(s_)
                del flat
            if prof:
                torch.cuda.synchronize()
                tp.append(time.time())
            gn = torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            if prof:
                torch.cuda.synchronize()
                tp.append(time.time())
                emit(event="prof", step=step, world=world, ms={k: round(1000 * (tp[i + 1] - tp[i]), 1) for i, k in
                                                               enumerate(("data", "fwd_bwd", "allreduce", "clip_opt"))})
            if mode == "plateau" and step % int(getattr(a, "plateau_every", 250)) == 0:  # adaptive lr
                v = val_loss()
                if v < pstate["best"] * (1 - float(getattr(a, "plateau_tol", 0.002))):
                    pstate["best"], pstate["bad"] = v, 0
                else:
                    pstate["bad"] += 1
                cut = pstate["bad"] >= int(getattr(a, "plateau_patience", 2)) and pmult[0] > float(
                    getattr(a, "plateau_min", 0.05))
                if cut:
                    pmult[0] = max(float(getattr(a, "plateau_min", 0.05)), pmult[0] * float(getattr(a, "plateau_factor", 0.5)))
                    pstate["bad"] = 0
                emit(event="plateau", step=step, val_loss=round(v, 5), best=round(pstate["best"], 5),
                     bad=pstate["bad"], lr_mult=pmult[0], cut=cut)
            clock[0] += time.time() - t_step
            sched.step()
            if step % 20 == 0:
                emit(event="train", step=step, loss=round(loss.item(), 4), per_step=[round(l.item(), 4) for l in losses],
                     grad_norm=round(float(gn), 3), lr=sched.get_last_lr()[0], ctx=int(hc.shape[0]),
                     sec_per_step=round((time.time() - t0) / (step - s0), 3))
            out_of_time = bool(budget) and clock[0] >= budget
            if step % a.eval_every == 0 or step == a.steps or out_of_time:
                if out_of_time:
                    emit(event="budget", steps_done=step, train_seconds=round(clock[0], 1))
                if rank == 0:
                    evaluate(step)
                    save_state(step)
                if world > 1:
                    dist.barrier()
            if out_of_time:
                break
        if rank != 0:  # only rank 0 saves; the others are done
            del opt, groups, params
            return
        if a.int4_experts and a.train_experts:  # what serving would load: experts back on his INT4 g32 grid
            with torch.no_grad():
                for attr in EXPERT_PARAMS.values():
                    w = getattr(draft, attr)
                    w.copy_(int4_rtn(w))
            evaluate(a.steps + 1)
        inv = {v: k for k, v in MAP.items()}
        state = {inv[k]: v.detach().to(torch.bfloat16).cpu() for k, v in draft.named_parameters() if k in inv}
        state.update({ADAPTER + k: v.detach().to(torch.bfloat16).cpu() for k, v in draft.named_parameters()
                      if k.startswith("step_")})
        state.update({AUX + k: v.detach().to(torch.bfloat16).cpu() for k, v in draft.named_parameters()
                      if k.startswith("aux_")})
        state.update({SHX + k: v.detach().to(torch.bfloat16).cpu() for k, v in draft.named_parameters()
                      if k.startswith("shx_")})
        state.update({UNTIE + k[len("untie."):]: v.detach().to(torch.bfloat16).cpu()
                      for k, v in draft.named_parameters() if k.startswith("untie.")})
        if a.train_experts:
            for ck, attr in EXPERT_PARAMS.items():
                state[ck] = getattr(draft, attr).detach().to(torch.bfloat16).cpu().contiguous()
        delta = {k: round(float((v - base_state[k]).norm() / base_state[k].norm().clamp_min(1e-9)), 5)
                 for k, v in draft.named_parameters()
                 if k in base_state and base_state[k].norm() > 0}  # zero-init adapter: no ratio
        torch.save(state, out / "draft_ft.pt")
        del opt, groups, params
        for w in experts:
            w.requires_grad_(False)
            w.grad = None
        torch.cuda.empty_cache()
        emit(event="saved", tensors=len(state), max_rel_change=max(delta.values()),
             biggest=sorted(delta.items(), key=lambda kv: -kv[1])[:5])

    if not a.queue:
        train_once(a.out)
        if world > 1:
            dist.barrier()
            dist.destroy_process_group()
        return
    defaults, qdir = dict(vars(a)), Path(a.queue)
    started = set()
    while True:
        specs = sorted(q for q in qdir.glob("*.json")
                       if q.stem not in started and not (a.out / q.stem / "DONE").exists())
        if not specs:
            if (qdir / "STOP").exists():
                break
            time.sleep(20)
            continue
        name = specs[0].stem
        started.add(name)
        out = a.out / name
        out.mkdir(parents=True, exist_ok=True)
        sink["trial"], sink["log"] = name, open(out / "log.jsonl", "a")
        try:
            spec = json.loads(specs[0].read_text())
            vars(a).clear()
            vars(a).update(defaults)
            for k, v in spec.items():
                setattr(a, k.replace("-", "_"), v)
            if a.queue_rebuild and spec.get("bench") is not None:  # measured serving cost of architecture options
                import bench_draft_cost
                emit(event="trial", spec=spec)
                vs = [dict(v, untie=untie_names(v["untie"])) if v.get("untie") else v for v in spec["bench"]]
                draft = base_state = None
                gc.collect()
                torch.cuda.empty_cache()
                emit(event="bench", **bench_draft_cost.run(vs, emit=lambda r: None))
                (out / "DONE").write_text("ok")
                sink["log"].close()
                sink["trial"], sink["log"] = None, None
                torch.cuda.empty_cache()
                continue
            if a.queue_rebuild:  # a fresh drafter per trial: its own architecture options and draft step count
                MSTEPS = int(a.msteps)
                draft = base_state = None
                gc.collect()
                torch.cuda.empty_cache()
                torch.manual_seed(a.seed)
                draft = build_draft()
                emit(event="trial", spec=spec)
                if spec.get("init"):
                    load_init(spec["init"])
                base_state = {k: v.detach().clone() for k, v in draft.named_parameters()  # no frozen-expert copy
                              if k not in EXPERT_PARAMS.values() or a.train_experts}
            else:
                with torch.no_grad():
                    for k, p_ in draft.named_parameters():
                        p_.copy_(base_state[k])
                emit(event="trial", spec=spec)
                if spec.get("init"):
                    load_init(spec["init"])
            train_once(out)
            (out / "DONE").write_text("ok")
        except Exception as e:  # noqa: BLE001 - one bad trial must not end the worker
            emit(event="trial_error", error=repr(e)[:800])
            (out / "DONE").write_text("error")
            torch.cuda.empty_cache()
        sink["log"].close()
        sink["trial"], sink["log"] = None, None
    emit(event="worker_stop", trials=sorted(started))

if __name__ == "__main__":
    main()
