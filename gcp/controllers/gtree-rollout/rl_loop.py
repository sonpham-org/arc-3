"""RL learner loop for the rollout server: master files -> sibling advantages -> AWR policy vN+1 -> new job round.

Author: Claude Opus 5.5 (3-Oct-2026, Son approved starting RL now: sibling rollouts in the notebook's 10 lanes).
Runs on the operator PC (or a CPU VM). After every round it publishes a status document for the site's RL2
"Training" view (--no-publish to skip; publish-status does only that, --dry-run writes it to a local file instead).

  C:/Python312/python.exe rl_loop.py init --campaign c1 [--K 5 --N 4 --limit 40 ...]   # policy v0 (stock) + round 1
  C:/Python312/python.exe rl_loop.py run  --campaign c1 [--every 15] [--once]           # the loop
  C:/Python312/python.exe rl_loop.py report --campaign c1                               # one screen, no writes
  C:/Python312/python.exe rl_loop.py publish-status --campaign c1 [--dry-run]           # the Training view's doc

Layout (--store, default gs://cellens-ai-artifacts/arc3-gtree/v1; a local directory works the same, tests use one):
  rollouts/<seed run>/...jsonl.gz            the seed tree (ingest.py)
  rollouts/gtr-<campaign>/...jsonl.gz        the campaign's tries (runner/rl_host_sync.py uploads them)
  rl/<campaign>/policy/current.json          what the VM syncs to /kaggle/rollout/policy/current.json
  rl/<campaign>/policy/v<N>.json             archive
  rl/<campaign>/jobs/round-NNNN/*.json       the job queue the VM stages
  rl/<campaign>/learner/state.json           round / version counters and history; report-v<N>.txt
Every iteration:
  1. gather every master file of the seed runs + the campaign (cached locally, only new files downloaded)
  2. reward per step: learn_awr.score_returns, speed reward k * (reference / level moves)^2, uncapped, reference =
     the fastest known clear of the level over ALL plays (or the human baseline when lower); not cleared = 0; a soft
     token charge (Son 3-Oct): a cleared step's score x (sibling median tokens to clear / its tokens)^--token-alpha
     (0.5; tokens from learn_awr.token_totals over EVERY step of the plays)
  3. training set = the campaign's branch steps (the first step of each try: the assigned action at the node) and,
     with --all-steps, the policy's later steps too; tries that ended by deadline / divergence are dropped
  4. advantage = G - the mean G of the other tries at the same t1 node, stratified per action (learn_awr.baselines),
     AWR (learn_awr.train) with the previous policy as the KL prior; floor keeps every mode sampleable
  5. write policy v<N+1> (seq N+1) to policy/v<N+1>.json and policy/current.json; print the report
  6. the queue (results/<vm>/summary.json): which jobs of the rounds the servers keep (the newest two) are still
     unstarted, and which restart points failed to restore (status 'diverged', or aborted with an origin mismatch /
     restore failure): those are blocked for the campaign (learner/state.json 'blocked', the report and the status
     doc say why), and a node whose restore failed from 2+ source plays is blocked outright
  7. refill, only when the queue runs low (fewer unstarted jobs than --refill-below, default 2 x the nodes a VM has in
     flight (lanes / K + 1) x the active VMs): pick_nodes.pick with the new counts and policy, least-sampled games
     first, the queued nodes and blocked restart points skipped, token cap per try (--token-cap) ->
     jobs/round-<N+1>/. (3-Oct pilot: a new round every 15 min while the VM finished 2-4 nodes, and the server dropped
     the older round's unstarted jobs: only ar25, bp35, cd82 and cn04 were ever played.)
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "rl2"))
import learn_awr  # noqa: E402
import pick_nodes  # noqa: E402
import rl_common as rc  # noqa: E402


def rl_store(store: str, campaign: str) -> rc.Store:
    return rc.Store(f"{store.rstrip('/')}/rl/{campaign}")


def read_json(store: rc.Store, name: str, default=None):
    raw = store.get(name)
    return json.loads(raw) if raw else default


def gather(store: str, campaign: str, seed_runs: list[str], cache: Path) -> list[dict]:
    return rc.load_plays(rc.sync_masters(store, list(seed_runs) + [rc.campaign_run(campaign)], cache))


def branch_steps(plays: list[dict], campaign: str, all_steps: bool = False) -> list[dict]:
    run = rc.campaign_run(campaign)
    out = []
    for p in plays:
        r = p["rollout"]
        if r.get("run") != run or not rc.is_rollout(p):
            continue
        for s in sorted(p["steps"], key=lambda s: s["seq"]):
            if s["seq"] == 1 or all_steps:
                out.append(dict(s, _job=(r.get("result") or {}).get("job"), _try=(r.get("result") or {}).get("try")))
    return out


def node_report(steps: list[dict], G: list[float | None], top: int = 6) -> list[str]:
    by = defaultdict(list)
    for s, g in zip(steps, G):
        by[s["n1"]].append((s, g))
    lines = []
    for n1, rows in sorted(by.items(), key=lambda kv: -len(kv[1]))[:top]:
        acts = defaultdict(list)
        for s, g in rows:
            acts[s["action"]].append((s, g))
        s0 = rows[0][0]
        lines.append(f"  {n1}  (level {s0['level']}, moves {s0.get('moves')}, {len(rows)} tries)")
        for a, xs in sorted(acts.items(), key=lambda kv: -sum((g or 0) for _, g in kv[1]) / len(kv[1])):
            cl = [s for s, _ in xs if (s.get("outcome") or {}).get("cleared_level")]
            mv = [int(s["outcome"]["moves_to_clear"]) for s in cl]
            gs = [g for _, g in xs if g is not None]
            lines.append(f"      {a:<9} n={len(xs):<3} clear {len(cl) / len(xs):.0%}  "
                         f"moves {sum(mv) / len(mv):.0f}" if mv else f"      {a:<9} n={len(xs):<3} clear 0%  moves -")
            lines[-1] += f"   reward {sum(gs) / len(gs):.2f}" if gs else ""
    return lines


# ------------------------------------------------------------------------------------------------ the job queue
# Restore failures that block a restart point: a 'diverged' try (the replayed harness built another request than the
# log: deterministic for that source play and step), or an abort before the origin's first request.
RESTORE_ABORTS = ("origin_mismatch", "restore failed", "snapshot restore failed")
KEEP_ROUNDS = 2                                  # the server's default (rollout_driver.serve keep_rounds)


def job_id_of(name: str) -> str:
    """jobs/round-NNNN/RRRR-PPPPP-<job id>.json (or a bare file name) -> the job id."""
    base = name.rsplit("/", 1)[-1]
    base = base[:-5] if base.endswith(".json") else base
    parts = base.split("-", 2)
    return parts[2] if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() else base


def round_of_name(name: str) -> int:
    head = name.rsplit("/", 1)[-1].split("-", 1)[0]
    return int(head) if head.isdigit() else 0


def read_summaries(rls: rc.Store, files: list[str] | None = None) -> dict[str, dict]:
    """VM name -> the server's summary.json (results/<vm>/summary.json)."""
    out = {}
    for n in files if files is not None else rls.list("results/"):
        if n.startswith("results/") and n.count("/") == 2 and n.endswith("/summary.json"):
            try:
                out[n.split("/")[1]] = json.loads(rls.get(n) or b"{}")
            except ValueError:
                pass
    return out


def queue_state(names: list[str], summaries: dict[str, dict], keep_rounds: int = KEEP_ROUNDS,
                now: float | None = None) -> dict:
    """What the servers still have to play: the job files of the newest keep_rounds rounds that no server finished,
    has in flight or skipped (the same rule rl_host_sync uses when it stages jobs for a new VM)."""
    now = time.time() if now is None else now
    by_round: dict[int, list[str]] = defaultdict(list)
    for n in names:
        if n.endswith(".json"):
            by_round[round_of_name(n)].append(job_id_of(n))
    done, running, skipped = set(), set(), set()
    active = 0
    for s in summaries.values():
        done |= {str(r.get("job")) for r in s.get("results") or []}
        done |= {str(e.get("job")) for e in s.get("errors") or []}
        running |= {str(j) for j in (s.get("running") or {}).get("jobs") or []}
        skipped |= {job_id_of(n) for n in list(s.get("skipped_old_round") or []) + list(s.get("skipped_fenced") or [])}
        if not s.get("ended_at") and now - float(s.get("updated_at") or 0) < 1800:
            active += 1
    rounds = sorted(by_round)
    kept = rounds[-keep_rounds:] if keep_rounds and keep_rounds > 0 else rounds
    gone = done | running | skipped
    pending = [j for r in kept for j in sorted(by_round[r]) if j not in gone]
    return {"rounds": kept, "newest": rounds[-1] if rounds else 0, "pending": pending,
            "done": sum(j in done for r in kept for j in by_round[r]), "running": len(running), "vms_active": active}


def restore_failure(row: dict) -> str | None:
    """Why a summary row's try never reached its first live request through no fault of the play, else None."""
    if row.get("status") == "diverged":
        return "diverged"
    why = str(row.get("aborted") or row.get("stop") or "")
    if row.get("status") == "aborted" and why.startswith(RESTORE_ABORTS):
        return "aborted: " + why[:120]
    return None


def _brief(x, n: int = 160):
    """A small copy of a result's failure detail (long strings cut)."""
    if isinstance(x, dict):
        return {k: _brief(v, n) for k, v in list(x.items())[:12]}
    if isinstance(x, list):
        return [_brief(v, n) for v in x[:6]]
    if isinstance(x, str) and len(x) > n:
        return x[:n] + "..."
    return x


def failure_detail(rls: rc.Store | None, campaign: str, vm: str, row: dict) -> dict | None:
    """The diverged / aborted detail of one failed try: the summary row's own (new servers), else the try's
    result.json uploaded by the host sync (results/<vm>/<job>/k<k>/), else the final rsync of the run
    (runs/rl-<campaign>-<x>/gtree-rollout/<job>/k<k>/, the 3-Oct pilot's only copy)."""
    if row.get("diverged") or row.get("aborted"):
        return _brief({"diverged": row.get("diverged"), "aborted": row.get("aborted")})
    if rls is None:
        return None
    job, k = row.get("job"), row.get("try")
    run_id = f"rl-{campaign}-" + vm[len("arc3-rl-"):] if vm.startswith("arc3-rl-") else None
    for name in [f"results/{vm}/{job}/k{k}/result.json"] + \
            ([f"runs/{run_id}/gtree-rollout/{job}/k{k}/result.json"] if run_id else []):
        try:
            raw = rls.get(name)
        except Exception:                        # noqa: BLE001 - detail is optional
            raw = None
        if raw:
            r = json.loads(raw)
            return _brief({"diverged": r.get("diverged"), "aborted": r.get("aborted"),
                           "mismatch": (r.get("origin") or {}).get("mismatch") or None, "from": name})
    return None


def blocked_points(summaries: dict[str, dict], jobs: dict[str, dict], prev: dict | None, *, rls: rc.Store | None = None,
                   campaign: str = "", min_tries: int = 1, now: float | None = None) -> tuple[dict, dict, list[str]]:
    """(blocked restart points, blocked nodes, keys new this round). A restart point = (source play, step), keyed by
    pick_nodes.restart_key; blocked once min_tries of its tries failed to restore. jobs: job id -> the job index
    (source rollout id, origin seq, t1, game). A node (t1) whose restore failed from 2+ source plays is blocked."""
    now = time.time() if now is None else now
    out = {k: dict(v) for k, v in (prev or {}).items()}
    acc: dict[str, dict] = {}
    for vm, s in sorted(summaries.items()):
        for r in s.get("results") or []:
            why = restore_failure(r)
            if not why:
                continue
            j = jobs.get(str(r.get("job"))) or {}
            src, seq = r.get("source") or j.get("source"), r.get("seq") if r.get("seq") is not None else j.get("seq")
            if not src or seq is None:
                continue
            a = acc.setdefault(pick_nodes.restart_key(src, seq), {"tries": 0, "jobs": set(), "rows": [], "why": why,
                                                                 "t1": r.get("node") or j.get("t1"),
                                                                 "game": j.get("game")})
            a["tries"] += 1
            a["jobs"].add(str(r.get("job")))
            a["rows"].append((vm, r))
    new = []
    for key, a in acc.items():
        if a["tries"] < min_tries:
            continue
        old = out.get(key) or {}
        detail = old.get("detail")
        if detail is None and not old.get("detail_tried"):
            row = next((x for x in a["rows"] if x[1].get("diverged") or x[1].get("aborted")), a["rows"][0])
            detail = failure_detail(rls, campaign, *row)
        if not old:
            new.append(key)
        out[key] = {"source": key.rsplit("#", 1)[0], "seq": int(key.rsplit("#", 1)[1]), "t1": a["t1"],
                    "game": a["game"], "why": a["why"], "tries": a["tries"], "jobs": sorted(a["jobs"]),
                    "detail": detail, "detail_tried": True, "since": old.get("since") or now}
    by_node: dict[str, list[str]] = defaultdict(list)
    for key, b in out.items():
        if b.get("t1"):
            by_node[b["t1"]].append(key)
    nodes = {t1: f"restore failed from {len(keys)} source plays ({', '.join(sorted(keys))[:200]})"
             for t1, keys in by_node.items() if len({k.rsplit('#', 1)[0] for k in keys}) >= 2}
    return out, nodes, new


def describe_block(key: str, b: dict) -> str:
    d = b.get("detail") or {}
    dv = d.get("diverged") or {}
    why = b.get("why") or "?"
    if dv:
        first = dv.get("first") or {}
        why = f"diverged: {dv.get('kind')} at logged call {dv.get('call')}" + (
            f", message {first.get('message')}: sent {str(first.get('sent'))[:70]!r} vs logged "
            f"{str(first.get('logged'))[:70]!r}" if first else "")
    elif d.get("aborted"):
        why = f"aborted: {str(d['aborted'])[:140]}"
    return f"    {b.get('game') or '?'} {b.get('t1')} from {key}: {b.get('tries')} tries, {why}"


def mean_dist(pol: dict, steps: list[dict]) -> dict[str, float]:
    acc = Counter()
    n = 0
    for s in steps:
        d = rc.mode_dist(pol, s.get("features") or {})
        if d:
            acc.update(d)
            n += 1
    return {k: acc[k] / n for k in rc.MODES} if n else {}


def iterate(cfg: argparse.Namespace, *, write: bool = True) -> dict:
    """One learner round. Returns {version, report lines, policy, jobs}."""
    t0 = time.time()
    rls = rl_store(cfg.store, cfg.campaign)
    state = read_json(rls, "learner/state.json", {"version": 0, "round": 1, "history": []})
    prev = read_json(rls, "policy/current.json", {}) or {}
    plays = gather(cfg.store, cfg.campaign, cfg.seed_runs, Path(cfg.cache))
    all_steps = [s for p in plays for s in p["steps"]]
    best = learn_awr.best_known(all_steps)
    tok = learn_awr.token_totals(all_steps)          # every step: a training subset would cut the sums short
    alpha = float(getattr(cfg, "token_alpha", 0.0) or 0.0)
    human = learn_awr._human_baselines() if not getattr(cfg, "no_human", False) else {}
    train = branch_steps(plays, cfg.campaign, cfg.all_steps)
    G = learn_awr.score_returns(train, human, best, tok, alpha)
    tries = [p for p in plays if p["rollout"].get("run") == rc.campaign_run(cfg.campaign)]
    statuses = Counter((p["rollout"].get("result") or {}).get("stop_reason") for p in tries)
    cleared = sum(bool((p["rollout"].get("result") or {}).get("cleared")) for p in tries)
    lines = [f"RL learner {cfg.campaign}  {time.strftime('%Y-%m-%d %H:%M')}  policy {prev.get('version')} "
             f"(seq {prev.get('seq')})  round {state['round']}",
             f"  data: {len(plays)} plays ({len(tries)} campaign tries, {cleared} cleared the origin level; stops "
             f"{dict(statuses)}), {len(all_steps)} steps, {len(best)} levels with a known clear",
             f"  training set: {len(train)} branch steps at {len({s['n1'] for s in train})} nodes "
             f"(actions {dict(Counter(s['action'] for s in train))})",
             f"  reward: speed score x (sibling median tokens / tokens to clear)^{alpha:g} (token_alpha {alpha:g}, "
             f"{sum(1 for s in train if tok.get(s.get('id') or ''))} branch steps with tokens to clear); new jobs: "
             f"token_cap {getattr(cfg, 'token_cap', None) or 'none'} per try"]
    out = {"version": prev.get("version"), "policy": prev, "jobs": [], "trained": False}
    labels = pick_nodes.mode_set(getattr(cfg, "modes", "all")) if (getattr(cfg, "modes", "all") or "all") != "all" else None
    # the policy for real play: Stock unless a mode beats the same start state's Stock with confidence (no exploration)
    caut = learn_awr.cautious_table(train, G, labels, min_n=getattr(cfg, "cautious_min_n", 15), z=getattr(cfg, "cautious_z", 1.0), share=getattr(cfg, "cautious_share", 0.5),
                                    version=f"{cfg.campaign}-cautious-r{state['round']}")
    departs = {s: next(iter(d)) for s, d in caut["table"].items()}
    lines.append(f"  cautious policy (for real play): " + (", ".join(f"{s} -> {m}" for s, m in departs.items())
                 if departs else "Stock everywhere (no mode beats Stock with confidence yet)"))
    for sit, ev in caut["evidence"].items():
        top = sorted(ev.items(), key=lambda kv: -(kv[1]["lcb"] if kv[1]["lcb"] is not None else -9))[:3]
        lines.append(f"    {sit:12s} " + "  ".join(f"{m} n={v['n']} {v['mean']:+.2f}" + (f"±{v['se']:.2f}" if v['se'] is not None
                     else "") for m, v in top))
    if write:
        rc.write_json(rls, "policy/cautious.json", caut)
    out["cautious"] = caut
    nodes_multi = {n for n, c in Counter(s["n1"] for s in train).items() if c >= 2}
    if len(train) >= cfg.min_steps and nodes_multi:
        seq = int(prev.get("seq") or state["version"] or 0) + 1
        version = f"{cfg.campaign}-v{seq}"
        tmp = Path(tempfile.mkdtemp(prefix="rl-loop-"))
        prev_path = None
        if prev:
            prev_path = tmp / "prev.json"
            prev_path.write_text(json.dumps(prev), encoding="utf-8")
        pol = learn_awr.train(train, version, str(prev_path) if prev_path else None, tau=cfg.tau, beta=cfg.beta,
                              floor=cfg.floor, epochs=cfg.epochs, best=best, human=human, out_dir=tmp,
                              extra={"seq": seq, "campaign": cfg.campaign, "trained_at": time.time(),
                                     "data": {"train_steps": len(train), "tries": len(tries)}},
                              tok=tok, token_alpha=alpha, labels=labels, freq_correct=not getattr(cfg, "no_freq_correct", False))
        base = learn_awr.baselines([s for s, g in zip(train, G) if g is not None], [g for g in G if g is not None])
        before, after = mean_dist(prev, train), mean_dist(pol, train)
        lines.append(f"  trained {version}: used {pol['stats']['used']} steps, ESS {pol['stats']['ess']}, "
                     f"mean reward {pol['stats']['mean_G']}, baselines from siblings for "
                     f"{sum(b is not None for b in base)} steps")
        lines.append("  policy change (mean P(mode) at the training nodes):  " + "  ".join(
            f"{m} {before.get(m, 1.0 if m == 'stock' and not prev else 0):.2f}->{after.get(m, 0):.2f}"
            for m in rc.MODES if after.get(m, 0) >= 0.02 or before.get(m, 0) >= 0.02))
        out.update(version=version, policy=pol, trained=True)
        # deploy guard (3-Oct pilot: v1 from 10 steps, ESS 2.3 swung stock 1.00 -> 0.05): a policy goes live only when
        # its effective sample size says the data can carry it; otherwise it is archived for inspection only
        deploy = (pol["stats"].get("ess") or 0) >= cfg.min_ess
        if write:
            rc.write_json(rls, f"policy/{version}.json", pol)
            if deploy:
                rc.write_json(rls, "policy/current.json", pol)
        if not deploy:
            lines.append(f"  NOT deployed: ESS {pol['stats'].get('ess')} < {cfg.min_ess}; the machines keep "
                         f"{prev.get('version')}")
            out.update(version=prev.get("version"), policy=prev)
        state["version"] = seq
    else:
        lines.append(f"  not trained: {len(train)} branch steps (min {cfg.min_steps}), "
                     f"{len(nodes_multi)} nodes with 2+ tries")
    lines.append("  most-sampled nodes (clear rate and mean moves to clear per first action):")
    lines += node_report(train, G)
    q = None
    try:                                         # the queue and the restore failures, from the servers' summaries
        names = [n for n in rls.list("jobs/") if n.endswith(".json")]
        summaries = read_summaries(rls)
        jindex = _job_index(rls, names, Path(cfg.cache) / "rl-jobs" / cfg.campaign)
        q = queue_state(names, summaries, getattr(cfg, "keep_rounds", KEEP_ROUNDS))
        blocked, blocked_nodes, new = blocked_points(summaries, jindex, state.get("blocked"), rls=rls,
                                                     campaign=cfg.campaign, min_tries=getattr(cfg, "block_after", 1))
        state["blocked"], state["blocked_nodes"] = blocked, blocked_nodes
        if blocked:
            lines.append(f"  blocked restart points ({len(blocked)}, {len(new)} new; restore failed, the picker skips "
                         f"them for the campaign):")
            lines += [describe_block(k, b) for k, b in sorted(blocked.items())]
            lines += [f"    node {t1} blocked: {why}" for t1, why in sorted(blocked_nodes.items())]
    except Exception as exc:                     # noqa: BLE001 - no queue view: train, but do not refill blind
        lines.append(f"  queue unreadable ({type(exc).__name__}: {str(exc)[:200]}): no refill this round")
    if q is not None:
        per_vm = 2 * (max(1, int(cfg.lanes) // max(1, int(cfg.K))) + 1)
        below = cfg.refill_below if getattr(cfg, "refill_below", None) is not None else per_vm * max(1, q["vms_active"])
        lines.append(f"  queue: rounds {q['rounds']} kept by the servers: {len(q['pending'])} unstarted, {q['done']} "
                     f"played, {q['running']} running; {q['vms_active']} VM(s) reporting; refill below {below}")
        state["queue"] = {"rounds": q["rounds"], "pending": len(q["pending"]), "done": q["done"],
                          "running": q["running"], "vms_active": q["vms_active"], "refill_below": below,
                          "t": time.time()}
    if not getattr(cfg, "no_refill", False) and q is not None and len(q["pending"]) >= below:
        lines.append(f"  refill: not yet ({len(q['pending'])} unstarted jobs >= {below})")
    elif not getattr(cfg, "no_refill", False) and q is not None:
        state["round"] = max(int(state["round"]), int(q["newest"])) + 1
        pending = [jindex[j] for j in q["pending"] if j in jindex]
        jobs, rep = pick_nodes.pick(plays, campaign=cfg.campaign, round_=state["round"], seed_runs=set(cfg.seed_runs),
                                    build=cfg.build or None, pol=out["policy"], N=cfg.N, K=cfg.K, limit=cfg.limit,
                                    per_game=cfg.per_game, backward_depth=cfg.backward_depth,
                                    turn_cap=cfg.turn_cap, caps=cfg.caps.split(","),
                                    state_index=rc.load_state_index(cfg.store, Path(cfg.cache)), store=cfg.store,
                                    modes=cfg.modes, pending=pending, blocked=state.get("blocked"),
                                    blocked_nodes=state.get("blocked_nodes"), token_cap=cfg.token_cap or None,
                                    mix=parse_mix(cfg.mix), games=game_set(cfg) or set(state.get("games") or []) or None,
                                    stage_k=getattr(cfg, "stage_k", 0) or None, frontier=getattr(cfg, "frontier", 0) or None,
                                    level_counts=frontier_counts(cfg))
        out["jobs"] = jobs
        lines.append(f"  refill: round {state['round']}: {len(jobs)} jobs / {rep['tries']} tries "
                     f"{rep['by_class']} (skipped: {rep['skipped_full']} full, {rep['skipped_grid']} same t5 cell, "
                     f"{rep['skipped_pending']} queued, {rep['skipped_blocked']} blocked); games first: "
                     f"{' '.join(rep['game_order'][:8])}")
        if write and jobs:
            pick_nodes.write_jobs(jobs, queue=rls.root)
    lines.append(f"  ({time.time() - t0:.0f}s)")
    state["history"].append({"t": time.time(), "version": out["version"], "round": state["round"],
                             "train": len(train), "tries": len(tries), "trained": out["trained"],
                             "nodes_with_siblings": len(nodes_multi),
                             "ess": (out["policy"].get("stats") or {}).get("ess") if out["trained"] else None,
                             "jobs": len(out["jobs"]), "job_tries": sum(int(j.get("tries") or 0) for j in out["jobs"]),
                             "queued": len(q["pending"]) if q is not None else None, "token_alpha": alpha,
                             "token_cap": getattr(cfg, "token_cap", None) or None})
    if write:
        rc.write_json(rls, "learner/state.json", state)
        # one report per learner round (rounds of jobs are rarer now: the time keeps them apart)
        rls.put(f"learner/report-{out['version'] or 'v0'}-r{state['round']}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
                f".txt", "\n".join(lines).encode("utf-8"), once=False, content_type="text/plain")
    out["report"] = lines
    return out


# ------------------------------------------------------------------------------------------------ status publication
# One JSON document per campaign for the site's RL2 "Training" view (docs/static/js/rl2.js, arc-3 repo), PUT to
# /api/v1/rl2/publication/rl-campaign-<campaign>, and a small index rl-campaigns ({"campaigns": [{name, updated}]}).
# The site's machine token can write but not read documents, so the index's names are kept in the store
# (rl/published-campaigns.json) and merged there. Sources: master files (tries), learner/state.json (rounds),
# policy/current.json + archive (ESS), jobs/round-NNNN/*.json (class, restore kind; cached locally, write-once),
# results/<vm>/summary.json (the server's counters), runs/<run>/phases.tsv (the VM's phases), gcloud (VM status).
SITE = "https://arc3.sonpham.net"
RAILWAY_CWD = Path(r"D:\codex-work\arc3-game-evolution-20260918")
WIN_PY = r"C:\python312\python.exe"
GCLOUD_PY = r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"
HARNESS = "best combo (f40b168002b8) + coach + rollout server"
MAX_DOC = 5 * 1024 * 1024
NODES_CAP = 300
# a few feature points that stand for the situations the coach sees (arc3_coach.situation_key / linear_features)
POLICY_POINTS = [
    ("level start, level 1", {"level": 1, "actions_in_level": 0, "actions_total": 0, "elapsed_s": 300, "tokens": 20000}),
    ("level start, level 2+", {"level": 3, "actions_in_level": 0, "actions_total": 80, "elapsed_s": 1800,
                               "tokens": 120000, "pending_new_level": True}),
    ("mid level", {"level": 2, "actions_in_level": 30, "actions_total": 70, "elapsed_s": 1500, "tokens": 90000,
                   "clean_streak": 1}),
    ("stuck", {"level": 2, "actions_in_level": 90, "actions_total": 130, "elapsed_s": 3000, "tokens": 160000,
               "gameovers_in_level": 1}),
    ("after game over", {"level": 2, "actions_in_level": 20, "actions_total": 60, "elapsed_s": 1500, "tokens": 90000,
                         "gameovers_in_level": 1, "pending_gameover": True}),
]


def _mean(xs):
    xs = [float(x) for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def _iso(t: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t if t is not None else time.time()))


def campaign_tries(plays: list[dict], campaign: str) -> list[dict]:
    """The campaign's tries as flat rows (one per master file), every stop reason kept."""
    run = rc.campaign_run(campaign)
    out = []
    for p in plays:
        r = p.get("rollout") or {}
        if r.get("run") != run:
            continue
        res = r.get("result") or {}
        steps = sorted(p.get("steps") or [], key=lambda s: s["seq"])
        first = steps[0] if steps else {}
        out.append({
            "node": r.get("origin_state") or first.get("n1"), "game": r.get("game"), "level": first.get("level"),
            "action": (res.get("assignment") or {}).get("mode") or first.get("action") or "stock",
            "cleared": bool(res.get("cleared")), "moves_to_clear": res.get("moves_to_clear"),
            "turns": res.get("turns"), "tokens": res.get("tokens"), "policy_version": res.get("policy_version"),
            "round": res.get("round"), "job": res.get("job"), "k": res.get("try"), "stop": res.get("stop_reason"),
            "restore": r.get("origin_kind"), "fair": res.get("stop_reason") not in rc.BAD_STOPS})
    return out


def vm_rows(campaign: str, instances: list[dict] | None, phases: dict[str, str], summaries: dict[str, dict],
            job_modes: dict[str, str]) -> list[dict]:
    """One row per VM of the campaign. instances: gcloud's JSON (None when the listing failed); phases: run id ->
    phases.tsv text; summaries: VM name -> the server's summary.json; job_modes: job id -> snapshot | replay_exact."""
    def meta(inst, key):
        return next((i.get("value") for i in ((inst.get("metadata") or {}).get("items") or []) if i.get("key") == key),
                    None)
    pre = f"rl-{campaign}-"
    by_vm: dict[str, dict] = {}
    for inst in instances or []:
        name = inst.get("name") or ""
        run_id = meta(inst, "arc3-run-id") or ""
        if name.startswith("arc3-rl-") and (meta(inst, "arc3-campaign") == campaign or run_id.startswith(pre)):
            by_vm[name] = {"name": name, "run_id": run_id or pre + name[len("arc3-rl-"):], "status": inst.get("status")}
    for run_id in phases:
        if run_id.startswith(pre):
            name = "arc3-rl-" + run_id[len(pre):]
            by_vm.setdefault(name, {"name": name, "run_id": run_id})
    for name in summaries:
        by_vm.setdefault(name, {"name": name, "run_id": pre + name[len("arc3-rl-"):]})
    rows = []
    for name, v in sorted(by_vm.items()):
        v.setdefault("status", "unknown" if instances is None else "gone")
        lines = [x for x in (phases.get(v["run_id"]) or "").splitlines() if x.strip()]
        last = lines[-1].split("\t", 1) if lines else [None, None]
        s = summaries.get(name) or {}
        res = s.get("results") or []
        per_job: dict[str, dict] = {}
        for r in res:
            j = per_job.setdefault(str(r.get("job")), {"restore_s": None})
            if j["restore_s"] is None and r.get("restore_s") is not None:
                j["restore_s"] = r["restore_s"]
        restores = Counter(job_modes.get(j, "unknown") for j in per_job)
        cached = [r.get("first_cached") for r in res if r.get("first_cached") is not None]
        row = {**v, "last_phase": last[1] if len(last) > 1 else last[0], "phase_time": last[0] if len(last) > 1 else None,
               "phases": len(lines), "tries_done": s.get("tries") if s else None,
               "tries_running": (s.get("running") or {}).get("tries") if s else None,
               "nodes_done": s.get("nodes") if s else None, "cleared": s.get("cleared") if s else None,
               "errors": len(s.get("errors") or []) if s else None,
               "restores": {"replay_exact": restores.get("replay_exact", 0), "snapshot": restores.get("snapshot", 0),
                            **({"unknown": restores["unknown"]} if restores.get("unknown") else {})},
               "mean_restore_s": _mean(j["restore_s"] for j in per_job.values()),
               "summary_updated": _iso(s["updated_at"]) if s.get("updated_at") else None}
        if cached:
            row["cached_tokens_first_request"] = _mean(cached)
            row["prompt_tokens_first_request"] = _mean(r.get("first_prompt") for r in res if r.get("first_cached") is not None)
        rows.append(row)
    return rows


def status_doc(campaign: str, *, plays: list[dict], state: dict | None, policy: dict | None,
               policies: dict[str, dict] | None = None, jobs: dict[str, dict] | None = None,
               job_counts: dict[int, int] | None = None, vms: list[dict] | None = None,
               human: dict | None = None, now: float | None = None, nodes_cap: int = NODES_CAP,
               token_alpha: float = 0.0, params: dict | None = None) -> dict:
    """The Training view's document (pure: every input given). plays: seed + campaign plays (rc.load_plays with
    drop_bad_stops=False); state: learner/state.json; policy: policy/current.json; policies: version -> archived
    policy (ESS of old rounds); jobs: job id -> {round, class, mode, tries, priority}; job_counts: round -> job files;
    token_alpha: the reward's token charge (as the learner computes it); params: the learner's knobs, shown as is."""
    state, policy, policies, jobs, job_counts = state or {}, policy or {}, policies or {}, jobs or {}, job_counts or {}
    tries = campaign_tries(plays, campaign)
    fair = [t for t in tries if t["fair"]]
    played = Counter(t["round"] for t in tries)
    # rounds: round 1 from init (policy v0), then one per learner round (the version it trained, the round it wrote)
    rounds: dict[int, dict] = {}
    if state:
        rounds[1] = {"round": 1, "version": f"{campaign}-v0", "t": state.get("created"), "train_steps": 0,
                     "nodes_with_siblings": 0, "ess": None, "trained": False}
    for h in state.get("history") or []:
        v = h.get("version")
        ess = h.get("ess")
        if ess is None and h.get("trained"):
            ess = ((policies.get(v) or {}).get("stats") or {}).get("ess")
        rounds[int(h.get("round") or 0)] = {"round": int(h.get("round") or 0), "version": v, "t": h.get("t"),
                                            "train_steps": h.get("train"), "trained": bool(h.get("trained")),
                                            "nodes_with_siblings": h.get("nodes_with_siblings"), "ess": ess,
                                            "job_tries": h.get("job_tries")}
    for r in set(job_counts) | {int(x) for x in played if x is not None}:
        rounds.setdefault(r, {"round": r, "version": None, "t": None, "train_steps": None,
                              "nodes_with_siblings": None, "ess": None})
    for r, row in rounds.items():
        row["jobs"] = job_counts.get(r)
        row["tries"] = played.get(r, 0)
    # the sibling groups: tries per t1 node, newest first
    by_node: dict[str, list[dict]] = defaultdict(list)
    for t in tries:
        if t["node"]:
            by_node[t["node"]].append(t)
    nodes = []
    for node, ts in by_node.items():
        ts.sort(key=lambda t: (t["round"] or 0, str(t["job"]), t["k"] if t["k"] is not None else 99))
        clear = [t for t in ts if t["cleared"] and t["moves_to_clear"] is not None]
        stock = [t for t in clear if t["action"] == "stock"]
        last_job = jobs.get(str(ts[-1]["job"])) or {}
        nodes.append({
            "node": node, "game": ts[0]["game"], "level": ts[0]["level"], "class": last_job.get("class"),
            "round": max((t["round"] or 0) for t in ts), "priority": last_job.get("priority"),
            "tries": [{x: t[x] for x in ("action", "cleared", "moves_to_clear", "turns", "tokens", "policy_version",
                                         "round", "stop")} | ({"censored": True} if not t["fair"] else {})
                      for t in ts],
            "best_moves": min((int(t["moves_to_clear"]) for t in clear), default=None),
            "stock_moves": min((int(t["moves_to_clear"]) for t in stock), default=None)})
    nodes.sort(key=lambda n: (-n["round"], n["priority"] if n["priority"] is not None else 10**6, n["node"]))
    # totals over the fair tries (deadline / divergence / abort are censoring, not a result)
    by_act: dict[str, list[dict]] = defaultdict(list)
    for t in fair:
        by_act[t["action"]].append(t)

    def agg(ts):
        mv = [int(t["moves_to_clear"]) for t in ts if t["cleared"] and t["moves_to_clear"] is not None]
        return {"n": len(ts), "clear_rate": round(sum(t["cleared"] for t in ts) / len(ts), 3) if ts else None,
                "mean_moves": _mean(mv)}
    tot = agg(fair)
    totals = {"tries": len(fair), "cleared": sum(t["cleared"] for t in fair), "clear_rate": tot["clear_rate"],
              "mean_moves_to_clear": tot["mean_moves"], "censored": len(tries) - len(fair),
              "nodes": len(by_node), "nodes_with_siblings": sum(len(v) >= 2 for v in by_node.values()),
              "by_first_action": {a: agg(ts) for a, ts in sorted(by_act.items(), key=lambda kv: -len(kv[1]))}}
    # advantage per first action: G - the sibling baseline, as the learner computes it
    adv: dict[str, dict] = {}
    good = [p for p in plays if not (rc.is_rollout(p) and ((p["rollout"].get("result") or {}).get("stop_reason")
                                                           in rc.BAD_STOPS))]
    train = branch_steps(good, campaign)
    if train:
        every = [s for p in good for s in p["steps"]]
        best = learn_awr.best_known(every)
        G = learn_awr.score_returns(train, human if human is not None else {}, best,
                                    learn_awr.token_totals(every), token_alpha)
        keep = [(s, g) for s, g in zip(train, G) if g is not None]
        base = learn_awr.baselines([s for s, _ in keep], [g for _, g in keep]) if keep else []
        acc: dict[str, list[float]] = defaultdict(list)
        for (s, g), b in zip(keep, base):
            if b is not None:
                acc[s.get("action") or "stock"].append(g - b)
        adv = {a: {"n": len(v), "mean_adv": round(sum(v) / len(v), 4)} for a, v in sorted(acc.items())}
    pol = {"version": policy.get("version"), "seq": policy.get("seq"), "kind": policy.get("kind"),
           "trained_at": policy.get("trained_at"), "stats": policy.get("stats"),
           "mode_dist_at": [{"label": lab, "features": f,
                             "dist": {m: round(p, 4) for m, p in sorted(rc.mode_dist(policy, f).items(),
                                                                         key=lambda kv: -kv[1])}}
                            for lab, f in POLICY_POINTS]}
    blocked = [{"restart_point": k, "game": b.get("game"), "node": b.get("t1"), "why": b.get("why"),
                "tries": b.get("tries"), "jobs": (b.get("jobs") or [])[-5:], "detail": b.get("detail"),
                "since": _iso(b["since"]) if b.get("since") else None}
               for k, b in sorted((state.get("blocked") or {}).items())]
    return {"campaign": campaign, "generated_at": _iso(now), "harness": HARNESS, "vms": vms or [],
            "rounds": [rounds[r] for r in sorted(rounds)], "policy": pol, "nodes": nodes[:nodes_cap],
            "nodes_total": len(nodes), "totals": totals, "advantage_by_action": adv,
            "modes": list(rc.MODES), "state": {"round": state.get("round"), "version": state.get("version")},
            "params": {"token_alpha": token_alpha, **(params or {})}, "queue": state.get("queue"),
            "blocked": blocked, "blocked_nodes": state.get("blocked_nodes") or {}}


def _gcloud_instances() -> list[dict] | None:
    cmd = [WIN_PY, GCLOUD_PY] if Path(GCLOUD_PY).exists() else ["gcloud"]
    try:
        out = subprocess.run(cmd + ["compute", "instances", "list", "--filter=name~^arc3-rl-",
                                    "--format=json(name,status,zone,metadata.items)"],
                             capture_output=True, text=True, timeout=180,
                             env={**os.environ, "CLOUDSDK_PYTHON": WIN_PY})
        return json.loads(out.stdout) if out.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _job_index(rls: rc.Store, names: list[str], cache: Path) -> dict[str, dict]:
    """job id -> {round, class, mode, tries, priority, game, t1, source (rollout id), seq} from the job files
    (write-once: cached locally by name; v2 entries carry the restart point, older cache entries are re-read)."""
    cache.mkdir(parents=True, exist_ok=True)

    def one(name: str) -> dict | None:
        p = cache / name.replace("/", "__")
        if p.exists():
            x = json.loads(p.read_text(encoding="utf-8"))
            if x.get("v") == 2:
                return x
        raw = rls.get(name)
        if not raw:
            return None
        j = json.loads(raw)
        o, src = j.get("origin") or {}, j.get("source") or {}
        x = {"v": 2, "job_id": j.get("job_id"), "round": j.get("round"), "class": (j.get("pick") or {}).get("class"),
             "mode": j.get("mode"), "tries": j.get("tries"), "priority": j.get("priority"),
             "game": str(j.get("game") or j.get("game_id") or "").split("-")[0] or None, "t1": o.get("t1"),
             "source": src.get("rollout_id"), "seq": o.get("seq")}
        p.write_text(json.dumps(x), encoding="utf-8")
        return x
    with ThreadPoolExecutor(16) as ex:
        return {x["job_id"]: x for x in ex.map(one, names) if x}


def learner_params(cfg: argparse.Namespace) -> dict:
    """The knobs the status doc shows (what the learner and its picker run with)."""
    return {k: getattr(cfg, k, None) for k in ("token_alpha", "token_cap", "K", "N", "limit", "per_game", "turn_cap",
                                               "min_ess", "tau", "beta", "floor", "lanes", "refill_below",
                                               "keep_rounds", "block_after", "modes")}


def collect_status(cfg: argparse.Namespace) -> dict:
    """Read everything the Training view shows (read-only on the store) and build the document."""
    rls = rl_store(cfg.store, cfg.campaign)
    state = read_json(rls, "learner/state.json", {}) or {}
    policy = read_json(rls, "policy/current.json", {}) or {}
    paths = rc.sync_masters(cfg.store, list(cfg.seed_runs) + [rc.campaign_run(cfg.campaign)], Path(cfg.cache))
    plays = rc.load_plays(paths, drop_bad_stops=False)
    names = [n for n in rls.list("jobs/") if n.endswith(".json")]
    job_counts = Counter(int(n.split("/")[1].split("-")[1]) for n in names if n.count("/") >= 2)
    jobs = _job_index(rls, names, Path(cfg.cache) / "rl-jobs" / cfg.campaign)
    policies = {}
    for h in state.get("history") or []:
        if h.get("trained") and h.get("ess") is None and h.get("version") and h["version"] not in policies:
            policies[h["version"]] = read_json(rls, f"policy/{h['version']}.json", {}) or {}
    files = list(rls.list("runs/")) + list(rls.list("results/"))
    phases = {n.split("/")[1]: (rls.get(n) or b"").decode("utf-8", "replace")
              for n in files if n.startswith("runs/") and n.endswith("/phases.tsv")}
    summaries = read_summaries(rls, files)
    instances = None if getattr(cfg, "no_vms", False) else _gcloud_instances()
    job_modes = {k: v.get("mode") for k, v in jobs.items()}
    vms = vm_rows(cfg.campaign, instances, phases, summaries, job_modes)
    human = learn_awr._human_baselines() if not getattr(cfg, "no_human", False) else {}
    doc = status_doc(cfg.campaign, plays=plays, state=state, policy=policy, policies=policies, jobs=jobs,
                     job_counts=dict(job_counts), vms=vms, human=human,
                     token_alpha=float(getattr(cfg, "token_alpha", 0.0) or 0.0), params=learner_params(cfg))
    for cap in (150, 60, 20):                   # keep it small enough for the page
        if len(json.dumps(doc, separators=(",", ":"))) <= MAX_DOC:
            break
        doc["nodes"] = doc["nodes"][:cap]
    return doc


def railway_token() -> str:
    """The site's publish token (env ARC3_PUBLISH_TOKEN, else Railway's variable). Never printed."""
    if os.environ.get("ARC3_PUBLISH_TOKEN"):
        return os.environ["ARC3_PUBLISH_TOKEN"]
    exe = shutil.which("railway.cmd") or shutil.which("railway") or "railway"
    out = subprocess.run([exe, "variable", "list", "--service", "arc3-viewer", "--environment", "production", "--json"],
                         cwd=RAILWAY_CWD, check=True, capture_output=True, text=True).stdout
    return json.loads(out)["ARC3_PUBLISH_TOKEN"]


def site_put(token: str, name: str, doc: dict) -> int:
    body = gzip.compress(json.dumps(doc, separators=(",", ":")).encode("utf-8"), compresslevel=6)
    req = urllib.request.Request(f"{SITE}/api/v1/rl2/publication/{name}", data=body, method="PUT",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/gzip",
                                          "User-Agent": "arc3-rl-publisher/1", "Content-Length": str(len(body))})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            r.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{name}: publication refused: {exc.code} {exc.read()[:300]!r}") from exc
    return len(body)


def campaigns_index(store: str, campaign: str, now: float | None = None) -> dict:
    """The index doc: every campaign published so far (rl/published-campaigns.json in the store) plus this one."""
    st = rc.Store(f"{store.rstrip('/')}/rl")
    raw = st.get("published-campaigns.json")
    names = {c["name"]: c for c in (json.loads(raw).get("campaigns") or [])} if raw else {}
    names[campaign] = {"name": campaign, "updated": _iso(now)}
    return {"campaigns": sorted(names.values(), key=lambda c: c.get("updated") or "", reverse=True),
            "generated_at": _iso(now)}


def publish_status(cfg: argparse.Namespace) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", cfg.campaign) or len(cfg.campaign) > 60:
        raise SystemExit(f"campaign {cfg.campaign!r}: the site takes lowercase letters, digits, '.', '_', '-' only")
    doc = collect_status(cfg)
    index = campaigns_index(cfg.store, cfg.campaign)
    size = len(json.dumps(doc, separators=(",", ":")))
    if getattr(cfg, "dry_run", False):
        out = Path(cfg.out or Path(cfg.cache) / "published")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"rl-campaign-{cfg.campaign}.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
        (out / "rl-campaigns.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
        return (f"dry run: rl-campaign-{cfg.campaign} ({size // 1024} KB, {len(doc['nodes'])} nodes, "
                f"{len(doc['vms'])} VMs, {len(doc['rounds'])} rounds) + rl-campaigns -> {out}")
    token = railway_token()
    sent = site_put(token, f"rl-campaign-{cfg.campaign}", doc)
    site_put(token, "rl-campaigns", index)
    rc.write_json(rc.Store(f"{cfg.store.rstrip('/')}/rl"), "published-campaigns.json", index)
    return (f"published rl-campaign-{cfg.campaign} ({size // 1024} KB, {sent // 1024} KB gzip, {len(doc['nodes'])} "
            f"nodes, {len(doc['vms'])} VMs) + rl-campaigns ({len(index['campaigns'])})")


def init(cfg: argparse.Namespace) -> None:
    rls = rl_store(cfg.store, cfg.campaign)
    if read_json(rls, "learner/state.json") and not cfg.force:
        raise SystemExit(f"campaign {cfg.campaign} exists ({rls.root}); --force to start over")
    v0 = {"version": f"{cfg.campaign}-v0", "seq": 0, "kind": "table", "table": {}, "default": {"stock": 1.0},
          "note": "v0: the stock harness after the assigned branch (no learned policy yet)"}
    rc.write_json(rls, "policy/v0.json", v0)
    rc.write_json(rls, "policy/current.json", v0)
    plays = gather(cfg.store, cfg.campaign, cfg.seed_runs, Path(cfg.cache))
    jobs, rep = pick_nodes.pick(plays, campaign=cfg.campaign, round_=1, seed_runs=set(cfg.seed_runs),
                                build=cfg.build or None, pol=v0, N=cfg.N, K=cfg.K, limit=cfg.limit,
                                per_game=cfg.per_game, backward_depth=cfg.backward_depth, turn_cap=cfg.turn_cap,
                                caps=cfg.caps.split(","), state_index=rc.load_state_index(cfg.store, Path(cfg.cache)),
                                store=cfg.store, modes=cfg.modes, token_cap=cfg.token_cap or None,
                                mix=parse_mix(cfg.mix), games=game_set(cfg),
                                stage_k=getattr(cfg, "stage_k", 0) or None, frontier=getattr(cfg, "frontier", 0) or None,
                                    level_counts=frontier_counts(cfg))
    pick_nodes.write_jobs(jobs, queue=rls.root)
    rc.write_json(rls, "learner/state.json", {"version": 0, "round": 1, "history": [], "created": time.time(),
                                              "games": sorted(game_set(cfg) or [])})
    print(json.dumps(rep))
    print(f"campaign {cfg.campaign}: policy v0 + round 1 ({len(jobs)} jobs, {rep['tries']} tries) -> {rls.root}")


def args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("init", "run", "report", "publish-status"))
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--store", default=rc.STORE)
    ap.add_argument("--seed-runs", default=",".join(rc.SEED_RUNS))
    ap.add_argument("--cache", default=r"D:\codex-work\gtree-rl\cache")
    ap.add_argument("--build", default=pick_nodes.DEFAULT_BUILD)
    ap.add_argument("--every", type=float, default=15.0, help="minutes between rounds")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--all-steps", action="store_true", help="also train on the policy's later steps")
    ap.add_argument("--min-steps", type=int, default=50)
    ap.add_argument("--min-ess", type=float, default=30.0, help="deploy a new policy only above this ESS")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--beta", type=float, default=0.1)
    ap.add_argument("--floor", type=float, default=0.05)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--N", type=int, default=4)
    ap.add_argument("--K", type=int, default=5)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--per-game", type=int, default=4)
    ap.add_argument("--backward-depth", type=int, default=6)
    ap.add_argument("--turn-cap", type=int, default=60)
    ap.add_argument("--token-cap", type=int, default=200000,
                    help="new jobs: generated tokens per try after the origin (the server stops the try); 0 = none")
    ap.add_argument("--token-alpha", type=float, default=0.5,
                    help="reward token charge: cleared score x (sibling median tokens / tokens to clear)^alpha; 0 = off")
    ap.add_argument("--caps", default="mode")
    ap.add_argument("--no-freq-correct", action="store_true",
                    help="train without dividing by how often each action was sampled per situation")
    ap.add_argument("--cautious-min-n", type=int, default=15, help="cautious policy: paired tries a mode needs")
    ap.add_argument("--cautious-z", type=float, default=1.0, help="cautious policy: lower bound = mean - z * SE")
    ap.add_argument("--cautious-share", type=float, default=0.5,
                    help="cautious policy: probability of the winning mode where one wins (Stock otherwise)")
    ap.add_argument("--mix", default="level_start=0.4,backward=0.3,uncertain=0.3",
                    help="share of each round per start-state class (first pass); '' = class order only")
    ap.add_argument("--modes", default="all", help="modes the picker assigns: all | original | grader | comma list")
    ap.add_argument("--stage-k", type=int, default=0, help="two-stage groups: a node's first job gets this many tries, "
                    "a top-up to --N only where they split (0 = off: every job gets --K)")
    ap.add_argument("--frontier", type=float, default=0.0, help="restart only levels at or above each game's first level "
                    "not mastered: under 6 plays reached it, or the Wilson lower bound of its clear rate is below this "
                    "(e.g. 0.8; 0 = every level)")
    ap.add_argument("--frontier-runs", default="", help="full-play runs whose per-level results feed --frontier (comma "
                    "list, read from their viewer files; default: the seed paths only)")
    ap.add_argument("--games", default="", help="only these games (comma list); init saves it, run reuses it "
                    "(4-Oct: RL v1 round 1 plays its 14 training games only)")
    ap.add_argument("--lanes", type=int, default=10, help="server lanes per VM (sizes the refill threshold)")
    ap.add_argument("--refill-below", type=int, default=None,
                    help="refill when fewer unstarted jobs are queued (default 2 x (lanes / K + 1) x active VMs)")
    ap.add_argument("--keep-rounds", type=int, default=KEEP_ROUNDS,
                    help="rounds the servers keep (rollout_driver.serve keep_rounds; ARC3_ROLLOUT_KEEP_ROUNDS)")
    ap.add_argument("--block-after", type=int, default=1,
                    help="tries whose restore diverged before a restart point is skipped for the campaign")
    ap.add_argument("--no-refill", action="store_true")
    ap.add_argument("--no-publish", action="store_true", help="run: do not publish the status doc after a round")
    ap.add_argument("--dry-run", action="store_true", help="publish-status: write the docs to --out, no PUT")
    ap.add_argument("--out", help="publish-status --dry-run: directory (default <cache>/published)")
    ap.add_argument("--no-vms", action="store_true", help="publish-status: skip the gcloud VM listing")
    a = ap.parse_args(argv)
    a.seed_runs = [x for x in a.seed_runs.split(",") if x]
    return a


def frontier_counts(cfg: argparse.Namespace) -> dict | None:
    """--frontier-runs: per-level [cleared, reached] of those runs' passes (pick_nodes.level_counts_from_viewers)."""
    runs = [r for r in (getattr(cfg, "frontier_runs", "") or "").split(",") if r]
    if not runs or not getattr(cfg, "frontier", 0):
        return None
    return pick_nodes.level_counts_from_viewers(runs, Path(cfg.cache))


def game_set(cfg: argparse.Namespace) -> set[str] | None:
    """--games as a set (None = every unfenced game)."""
    return {g for g in (getattr(cfg, "games", "") or "").split(",") if g} or None


def parse_mix(spec: str | None) -> dict[str, float] | None:
    """"level_start=0.4,backward=0.3,uncertain=0.3" -> {class: share}; empty = None (class order only)."""
    out = {}
    for part in (spec or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = float(v)
    return out or None


def main(argv=None) -> int:
    cfg = args(argv)
    if cfg.cmd == "init":
        init(cfg)
        return 0
    if cfg.cmd == "report":
        cfg.no_refill = True
        print("\n".join(iterate(cfg, write=False)["report"]))
        return 0
    if cfg.cmd == "publish-status":
        print(publish_status(cfg))
        return 0
    while True:
        try:
            print("\n".join(iterate(cfg)["report"]), flush=True)
        except Exception as exc:                 # noqa: BLE001 - the loop survives a bad round (e.g. gcloud login)
            print(f"learner round failed: {type(exc).__name__}: {exc}", flush=True)
        if not cfg.no_publish:
            try:
                print("  " + publish_status(cfg), flush=True)
            except Exception as exc:             # noqa: BLE001 - the site being down never stops the learner
                print(f"  status publish failed: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        if cfg.once:
            return 0
        time.sleep(max(60.0, cfg.every * 60))


if __name__ == "__main__":
    raise SystemExit(main())
