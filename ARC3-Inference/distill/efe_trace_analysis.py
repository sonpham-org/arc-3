#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Offline, free-energy-principle-inspired scoring of recorded ARC-3 agent/environment
#   traces (the harness's artifacts/*_events.jsonl). Requested by OpenMind in #arc-3 on
#   23-Sep-2026 after the Boss's go-ahead; first cut runs on the first three traces with actions.
#   It replays each trace step by step and, WITHOUT changing what the agent did, asks at every
#   step: under a simple Dirichlet-categorical model of "what does action-in-context c do to the
#   board", how much information about that model did each available action promise (epistemic
#   value / novelty, Parr, Pezzulo & Friston ch. 7.5), which one did the agent pick, and how
#   surprising was the result. Per step it reports: expected information gain (EIG) of the chosen
#   context, the best EIG among the candidates available at that step, the chosen action's EIG tier
#   (tie-aware: 1 = among the most informative candidates),
#   the observed outcome class, its surprisal (-ln p) and the Bayesian surprise
#   KL[posterior || prior] of the updated Dirichlet. The pragmatic term is reported only as the
#   model's current p(level clear | context), since the goal is hidden.
#   Model:
#   - Context: button actions -> the action id (ACTION1..5, 7); clicks (ACTION6) -> the TYPE of
#     the 4-connected object under the click on the PRE-click board: its normalised shape, with
#     position and colour dropped. Identical pieces share one context, a moved object keeps its
#     context, and re-clicking a recoloured object is still a repeat. Background clicks share one.
#   - Candidates at a step: every valid button action (from the harness's "Valid actions right
#     now" line) plus, if clicking is valid, every non-background object on the pre-action board.
#   - Outcome class: level_clear | game_over | nothing | changed~2^k (log2 count of changed
#     cells; --outcome fine also keys on the colour-transition set). Cells that change on most steps of the trace (step counters, timer bars) are masked
#     as HUD first, so a ticking counter does not make every action look informative.
#   - Per context a Dirichlet over the outcome classes plus one "unseen outcome" slot, symmetric
#     prior ALPHA_PRIOR. EIG = mutual information between the next outcome and the Dirichlet
#     parameters = H[E p] - E[H p] (closed form with digamma).
#   - Optional back-off prior (added 23-Sep-2026, round three, --prior backoff / analyse(prior=)):
#     alpha_c(o) = count_c(o) + BACKOFF_BETA * p_global(o), with p_global the trace's pooled,
#     ALPHA_PRIOR-smoothed outcome distribution so far. It removes the ~ln K nats every fresh context
#     paid under the flat prior. Default stays flat, which reproduces all earlier outputs exactly;
#     EIG, surprisal and Bayesian surprise use the same formulas on whichever alpha is active.
#   Known limits: with a fixed support and symmetric prior, EIG is a decreasing function of how often
#   a context was tried, so the "chosen vs best EIG" side restates count-based novelty (already
#   measured by novelty_vs_solves.py); the new signal is the realised side (surprisal, Bayesian
#   surprise). Button contexts ignore where the avatar is. HUD masking removes whole edge lines
#   that change on most steps; check it does not eat a meaningful edge strip (the Skewer Kebabs
#   answer key) before widening the trace set.
#   Dependencies: scipy (digamma, gammaln); novelty_vs_solves.py in the same folder for
#   BACKGROUND_AREA, the regexes and the nickname loader. Reads files only; launches nothing.
# SRP/DRY check: Pass -- novelty_vs_solves.py measures first-time-in-context fractions over
#   windows; nothing in distill/ computes Dirichlet information gain or Bayesian surprise.
#   Trace parsing primitives are imported from it rather than copied.
"""FEP-style epistemic scoring of recorded ARC-3 traces.

Usage:
    python distill/efe_trace_analysis.py                     # first 3 traces of the 7.36 run
    python distill/efe_trace_analysis.py --n 3 --steps 40 path/to/*_events.jsonl
    python distill/efe_trace_analysis.py --out results/efe_trace_analysis
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scipy.special import digamma, gammaln

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novelty_vs_solves import (BACKGROUND_AREA, MOUSE_RE, NAME_TO_ID, VALID_RE,  # noqa: E402
                               load_nicknames)

HOME = Path.home()
DEFAULT_GLOB = str(HOME / "bubba-workspace/arc3-kaggle/best-7.36/output/artifacts/*_events.jsonl")
ALPHA_PRIOR = 1.0      # symmetric Dirichlet concentration per outcome class
HUD_SHARE = 0.6        # an edge line changing on more than this share of steps is treated as HUD
HUD_EDGE = 2           # only rows/columns this close to the border can be HUD
BASE_OUTCOMES = ["nothing", "level_clear", "game_over"]   # always in the support from step one
# Outcome granularity. "coarse" (default): changed cells bucketed by log2 count only, so the support
# is fixed from step one and EIG of an untried context is constant. "fine": also keys on the set of
# colour transitions; the support grows as new classes appear, which makes every untried context
# look more informative over time and fragments outcomes (most steps become a new class).
OUTCOME_MODE = "coarse"
SIZE_BUCKETS = 13      # log2 buckets 0..12 cover 1..4096 changed cells on a 64x64 board
BACKOFF_BETA = 2.0     # prior="backoff": total prior pseudo-count a fresh context borrows from the trace


# ---------------------------------------------------------------- Dirichlet quantities

def eig(alpha: list[float]) -> float:
    """Mutual information I(o; theta) for one draw from Dirichlet-categorical(alpha), in nats.
    = H[p_bar] - E_theta H[theta], with E H = psi(a0+1) - sum p_k psi(a_k+1)."""
    a0 = sum(alpha)
    p = [a / a0 for a in alpha]
    h_mean = -sum(pk * math.log(pk) for pk in p if pk > 0)
    exp_h = float(digamma(a0 + 1)) - sum(pk * float(digamma(ak + 1)) for pk, ak in zip(p, alpha))
    return max(h_mean - exp_h, 0.0)


def kl_dirichlet(post: list[float], prior: list[float]) -> float:
    """KL[Dir(post) || Dir(prior)] in nats (Bayesian surprise of one update)."""
    p0, q0 = sum(post), sum(prior)
    out = float(gammaln(p0)) - sum(float(gammaln(a)) for a in post)
    out -= float(gammaln(q0)) - sum(float(gammaln(a)) for a in prior)
    out += sum((a - b) * (float(digamma(a)) - float(digamma(p0))) for a, b in zip(post, prior))
    return out


class Beliefs:
    """Per-context Dirichlet counts over a trace-wide, growing outcome vocabulary.
    prior="flat" (default): alpha_c(o) = ALPHA_PRIOR + count_c(o), symmetric, as in all earlier results.
    prior="backoff": alpha_c(o) = count_c(o) + beta * p_global(o), a hierarchical back-off prior where
    p_global(o) = (G(o) + ALPHA_PRIOR) / (N + ALPHA_PRIOR * K) is the smoothed outcome distribution
    pooled over every context of this trace so far (G = global counts, N = their total, K = support
    size including the unseen slot). A fresh context then predicts the trace's usual outcomes instead
    of a uniform spread over the whole alphabet, so splitting contexts no longer pays ln K per split."""

    def __init__(self, vocab=None, prior: str = "flat", beta: float = BACKOFF_BETA):
        if prior not in ("flat", "backoff"):
            raise ValueError(f"unknown prior {prior!r}")
        self.vocab: list[str] = list(BASE_OUTCOMES)
        if vocab is not None:                      # caller-supplied fixed support (learned outcome codes)
            self.vocab += [v for v in vocab if v not in self.vocab]
        elif OUTCOME_MODE == "coarse":
            self.vocab += [f"changed~2^{k}" for k in range(SIZE_BUCKETS)]
        self.counts: dict[tuple, Counter] = defaultdict(Counter)
        self.prior, self.beta = prior, beta
        self.global_counts: Counter = Counter()
        self.global_n = 0

    def base(self) -> list[float]:
        """Per-class prior pseudo-counts (vocab order, unseen slot last)."""
        if self.prior == "flat":
            return [ALPHA_PRIOR] * (len(self.vocab) + 1)
        k = len(self.vocab) + 1                    # recomputed per call: the vocab can grow mid-trace
        z = self.global_n + ALPHA_PRIOR * k
        g = self.global_counts
        return [self.beta * (g[o] + ALPHA_PRIOR) / z for o in self.vocab] + [self.beta * ALPHA_PRIOR / z]

    def alpha(self, ctx) -> list[float]:
        c = self.counts[ctx]
        if self.prior == "flat":
            return [ALPHA_PRIOR + c[o] for o in self.vocab] + [ALPHA_PRIOR]   # last slot = unseen
        base = self.base()
        return [b + c[o] for b, o in zip(base, self.vocab)] + [base[-1]]

    def p(self, ctx, outcome) -> float:
        a = self.alpha(ctx)
        idx = self.vocab.index(outcome) if outcome in self.vocab else len(a) - 1
        return a[idx] / sum(a)

    def update(self, ctx, outcome) -> float:
        """Add one observation; return Bayesian surprise KL[post || prior] over the same support."""
        if outcome not in self.vocab:
            # A new class: the prior mass it had sat in the unseen slot. Grow the support first,
            # giving the new class the unseen slot's prior, so prior and posterior share support.
            self.vocab.append(outcome)
        prior = self.alpha(ctx)
        self.counts[ctx][outcome] += 1
        if self.prior == "flat":
            post = self.alpha(ctx)
        else:
            # Conjugate update against the SAME base measure; the global distribution moves only
            # after the KL is taken, so Bayesian surprise measures this context's update alone.
            post = list(prior)
            post[self.vocab.index(outcome)] += 1
            self.global_counts[outcome] += 1
            self.global_n += 1
        return kl_dirichlet(post, prior)


# ---------------------------------------------------------------- trace reading

def load_trace(path: str):
    rows = []
    with open(path) as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    valid = None
    for r in rows:
        if r.get("type") == "analysis":
            m = VALID_RE.search(r.get("transcript") or "")
            if m:
                valid = [NAME_TO_ID.get(t.strip(), t.strip()) for t in m.group(1).split(",") if t.strip()]
                break
    initial = next((r for r in rows if r.get("type") == "initial"), None)
    actions = [r for r in rows if r.get("type") == "action"]
    return valid or [], (initial or {}).get("board"), actions


def hud_mask(boards: list) -> set:
    """Cells of HUD lines: whole rows/columns within HUD_EDGE of the border that change on more
    than HUD_SHARE of consecutive board pairs. Masking whole lines (not single cells) is needed
    because a step bar fills one new cell per action, so no single cell changes often."""
    boards = [b for b in boards if b]
    if len(boards) < 3:
        return set()
    h, w = len(boards[0]), len(boards[0][0])
    rows, cols = Counter(), Counter()
    for a, b in zip(boards, boards[1:]):
        rs, cs = set(), set()
        for y, (ra, rb) in enumerate(zip(a, b)):
            for x, (ca, cb) in enumerate(zip(ra, rb)):
                if ca != cb:
                    rs.add(y)
                    cs.add(x)
        rows.update(rs)
        cols.update(cs)
    n = len(boards) - 1
    edge = lambda i, size: i < HUD_EDGE or i >= size - HUD_EDGE  # noqa: E731
    mask = set()
    for y, k in rows.items():
        if edge(y, h) and k / n > HUD_SHARE:
            mask.update((y, x) for x in range(w))
    for x, k in cols.items():
        if edge(x, w) and k / n > HUD_SHARE:
            mask.update((y, x) for y in range(h))
    return mask


def outcome_class(pre, post, row, mask) -> str:
    if row.get("level_completed"):
        return "level_clear"
    if row.get("game_over"):
        return "game_over"
    if not pre or not post:
        return "unknown"
    trans = set()
    n = 0
    for y, (ra, rb) in enumerate(zip(pre, post)):
        for x, (ca, cb) in enumerate(zip(ra, rb)):
            if ca != cb and (y, x) not in mask:
                trans.add((ca, cb))
                n += 1
    if n == 0:
        return "nothing"
    bucket = min(round(math.log2(n)), SIZE_BUCKETS - 1)
    if OUTCOME_MODE == "coarse":
        return f"changed~2^{bucket}"
    return f"changed{sorted(trans)}~2^{bucket}"


def component_cells(board, r, c):
    """4-connected same-colour cells under (r, c); None if it is background (too big)."""
    h, w = len(board), len(board[0])
    colour, seen, stack = board[r][c], {(r, c)}, [(r, c)]
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and board[ny][nx] == colour:
                seen.add((ny, nx))
                stack.append((ny, nx))
                if len(seen) > BACKGROUND_AREA:
                    return None
    return seen


def object_type(cells) -> tuple:
    """Position- and colour-free type key: the normalised shape of the component. Identical pieces
    anywhere on the board share one context (a grid of identical pontoons is ONE thing to learn
    about), a moved object keeps its key, and a toggle that recolours it keeps its key too."""
    y0 = min(y for y, _ in cells)
    x0 = min(x for _, x in cells)
    shape = tuple(sorted((y - y0, x - x0) for y, x in cells))
    return ("M", "type", len(cells), hash(shape) & 0xFFFFFF)


def objects_on(board) -> set:
    """Every distinct non-background object type on the board."""
    if not board:
        return set()
    h, w = len(board), len(board[0])
    seen, keys = set(), set()
    for y in range(h):
        for x in range(w):
            if (y, x) in seen:
                continue
            cells = component_cells(board, y, x)
            if cells is None:
                # background: mark its cells so we do not flood it again from every pixel
                colour, stack = board[y][x], [(y, x)]
                seen.add((y, x))
                while stack:
                    cy, cx = stack.pop()
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and board[ny][nx] == colour:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                continue
            seen |= cells
            keys.add(object_type(cells))
    return keys


def context_of(row, pre):
    name = row.get("action_name")
    if name == "ACTION6":
        m = MOUSE_RE.search(row.get("action_display", ""))
        r, c = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
        if not pre or not (0 <= r < len(pre) and 0 <= c < len(pre[0])):
            return ("M", "off")
        cells = component_cells(pre, r, c)
        return ("M", "bg") if cells is None else object_type(cells)
    return (name,)


def ctx_label(ctx) -> str:
    if ctx[0] == "M":
        if ctx[1] == "type":
            return "click %d-cell obj #%06x" % (ctx[2], ctx[3])
        return "click " + ctx[1]
    return {"ACTION1": "up", "ACTION2": "down", "ACTION3": "left", "ACTION4": "right",
            "ACTION5": "space", "ACTION7": "undo"}.get(ctx[0], ctx[0])


class HandmadePerception:
    """Default perception: button -> action id; click -> object type (normalised shape)."""
    name = "handmade"

    def context(self, row, pre):
        return context_of(row, pre)

    def candidates(self, pre, buttons, clicking):
        return set(buttons) | (objects_on(pre) if clicking else set())


# ---------------------------------------------------------------- analysis

def analyse(path: str, max_steps: int | None, perception=None, outcome_fn=None, outcome_vocab=None,
            prior: str = "flat", beta: float = BACKOFF_BETA):
    """outcome_fn(pre, post, row, mask) -> class label replaces outcome_class when given;
    outcome_vocab is then the fixed support of the Dirichlet (plus the base classes).
    prior: "flat" (symmetric, default, reproduces earlier results) or "backoff" (see Beliefs)."""
    perception = perception or HandmadePerception()
    outcome_fn = outcome_fn or outcome_class
    valid, board, actions = load_trace(path)
    boards = [board] + [a.get("board") for a in actions]
    mask = hud_mask(boards)
    beliefs = Beliefs(outcome_vocab, prior, beta)
    buttons = [v for v in valid if v not in ("ACTION6", "RESET")]
    clicking = "ACTION6" in valid
    steps = []
    pre = board
    for i, row in enumerate(actions):
        if max_steps and i >= max_steps:
            break
        post = row.get("board")
        if row.get("action_name") == "RESET":
            pre = post
            steps.append({"step": i + 1, "level": row.get("level"), "reset": True})
            continue
        ctx = perception.context(row, pre)
        cands = perception.candidates(pre, [(b,) for b in buttons], clicking)
        cands.add(ctx)
        scored = {c: eig(beliefs.alpha(c)) for c in cands}
        eig_first = eig(beliefs.base())                            # EIG of a never-tried context
        chosen = scored[ctx]
        best = max(scored.values())
        better = sum(1 for v in scored.values() if v > chosen + 1e-9)
        levels = sorted({round(v, 9) for v in scored.values()}, reverse=True)
        tier = levels.index(round(chosen, 9)) + 1          # 1 = in the top EIG tier
        out = outcome_fn(pre, post, row, mask)
        p_o = beliefs.p(ctx, out)
        p_clear = beliefs.p(ctx, "level_clear")
        bs = beliefs.update(ctx, out)
        steps.append({
            "step": i + 1, "level": row.get("level"), "action": ctx_label(ctx) if len(ctx) < 3 or ctx[1] == "type" else str(ctx)[:26],
            "n_cands": len(cands), "eig_chosen": chosen, "eig_best": best,
            "n_better": better, "tier": tier, "tiers": len(levels), "top": better == 0,
            "outcome": out, "surprisal": -math.log(p_o), "bayes_surprise": bs,
            "p_clear_before": p_clear, "eig_first": eig_first,
        })
        # Advance the board. Before 23-Sep-2026 ~19:45 ET this line was missing, so every step was
        # compared with the board the play (or last RESET) started from: rounds one to three and the
        # first-3 / next-30 / next-20 tables used a stale "before" board. Found by the round-four agent.
        pre = post
    return {"file": path, "valid": valid, "hud_cells": len(mask), "steps": steps,
            "vocab_size": len({x["outcome"] for x in steps if not x.get("reset")})}


def summary(res) -> dict:
    s = [x for x in res["steps"] if not x.get("reset")]
    if not s:
        return {}
    return {
        "steps": len(s),
        "chose_top_eig_share": sum(x["top"] for x in s) / len(s),
        "mean_eig_chosen": sum(x["eig_chosen"] for x in s) / len(s),
        "mean_eig_best": sum(x["eig_best"] for x in s) / len(s),
        "epistemic_regret_per_step": sum(x["eig_best"] - x["eig_chosen"] for x in s) / len(s),
        "bayes_surprise_per_step": sum(x["bayes_surprise"] for x in s) / len(s),
        "surprisal_per_step": sum(x["surprisal"] for x in s) / len(s),   # prequential code length
        "repeat_share": sum(x["eig_chosen"] < x["eig_first"] - 1e-9 for x in s) / len(s),
        "max_p_clear_before": max(x["p_clear_before"] for x in s),
        "nothing_share": sum(x["outcome"] == "nothing" for x in s) / len(s),
        "outcome_classes_seen": res["vocab_size"],
        "levels_cleared": sum(x["outcome"] == "level_clear" for x in s),
    }


def run_name(path: str) -> str:
    """Folder that identifies the run: the parent of artifacts/, or its parent if that is output/."""
    parts = Path(path).parts
    name = parts[-3]
    return parts[-4] if name == "output" else name


def short_outcome(o: str) -> str:
    return o if len(o) <= 28 else o[:25] + "..."


def print_trace(res, nick):
    game = Path(res["file"]).name.split("-")[0]
    name = nick.get(game, game)
    print(f"\n=== {name} ({run_name(res['file'])}/{Path(res['file']).name}) | valid: {', '.join(res['valid'])} | "
          f"HUD cells masked: {res['hud_cells']}")
    print(f"{'step':>4} {'lvl':>3} {'action':<26} {'cands':>5} {'EIG':>6} {'best':>6} {'tier':>7} "
          f"{'surpr':>6} {'BayesS':>6}  outcome")
    for x in res["steps"]:
        if x.get("reset"):
            print(f"{x['step']:>4} {x['level']:>3} RESET")
            continue
        print(f"{x['step']:>4} {x['level']:>3} {x['action']:<26} {x['n_cands']:>5} "
              f"{x['eig_chosen']:>6.3f} {x['eig_best']:>6.3f} {str(x['tier']) + '/' + str(x['tiers']):>7} "
              f"{x['surprisal']:>6.2f} {x['bayes_surprise']:>6.3f}  {short_outcome(x['outcome'])}")
    sm = summary(res)
    print("summary:", json.dumps({k: round(v, 3) if isinstance(v, float) else v for k, v in sm.items()}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="events.jsonl files (default: the 7.36 run)")
    ap.add_argument("--n", type=int, default=3, help="number of traces with actions to analyse")
    ap.add_argument("--skip", type=int, default=0, help="skip this many traces with actions first")
    ap.add_argument("--steps", type=int, default=None, help="cap steps printed per trace")
    ap.add_argument("--out", default=None, help="write per-trace JSON here")
    ap.add_argument("--outcome", choices=("coarse", "fine"), default="coarse",
                    help="outcome granularity (see OUTCOME_MODE)")
    ap.add_argument("--prior", choices=("flat", "backoff"), default="flat",
                    help="per-context Dirichlet prior: flat symmetric (default) or back-off to the trace's "
                         "global outcome distribution (see Beliefs)")
    ap.add_argument("--beta", type=float, default=BACKOFF_BETA, help="back-off prior strength")
    args = ap.parse_args()
    global OUTCOME_MODE
    OUTCOME_MODE = args.outcome
    paths = args.paths or sorted(glob.glob(DEFAULT_GLOB))
    nick = load_nicknames()
    done = []
    skipped = 0
    for p in paths:
        if len(done) >= args.n:
            break
        res = analyse(p, args.steps, prior=args.prior, beta=args.beta)
        if not [x for x in res["steps"] if not x.get("reset")]:
            continue
        if skipped < args.skip:
            skipped += 1
            continue
        print_trace(res, nick)
        done.append(res)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for res in done:
            run = run_name(res["file"])   # e.g. best-7.36 / armA / arc3-job1-control; stems repeat
            (out / (run + "__" + Path(res["file"]).stem + ".efe.json")).write_text(
                json.dumps({"summary": summary(res), **res}, indent=1, default=str))


if __name__ == "__main__":
    main()
