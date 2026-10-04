"""Offline node picker for the RL rollout server: master files -> sibling jobs (no site, no auth).

Author: Claude Opus 5.5 (3-Oct-2026, Son: "take advantage of the high throughput in the 10 lanes to do sampled
rollouts off policy").

  C:/Python312/python.exe pick_nodes.py --campaign c1 --round 1 [--store gs://.../arc3-gtree/v1 | DIR]
        [--seed-runs a,b] [--cache DIR] [--policy current.json] [--N 4] [--K 5] [--limit 40] [--per-game 4]
        [--backward-depth 6] [--turn-cap 60] [--token-cap 200000] [--caps mode] [--games sb26,ls20]
        (--out DIR | --queue gs://.../rl/c1)

Node stats come from every play of the seed runs and of the campaign's rollouts (tree t1 = the unbiased, path-keyed
tree; counts per (t1 node, action)). Restart points are steps of the SEED plays only (their request + event logs are
in the duck bucket): resumable (ctx_before set, i.e. the turn's exact context was logged) and from the target build.
Nodes in priority order, round-robin over games inside each class:
  1. level_start  the first step of each level in a play (moves == 0 after a clear, or the game root); when that
                  step is not resumable (the clear happened mid-turn), the first resumable step of the level
  2. backward     along each level's best known seed path (fewest moves to clear), walking back from the clearing
                  step one step per depth (Salimans & Chen 2018: start near the end, move the start back)
  3. uncertain    the rest by 1 - |2p - 1| + 1/sqrt(visits + 1), p = (clears + 1) / (visits + 2)
A node is eligible while some mode has fewer than N samples there. t5 (level, screen, moves // 6) is the restart grid:
one node per t5 cell per round, so near-duplicate states are not restarted twice.
Game order (3-Oct pilot: every round started with ar25, bp35, cd82, cn04 and the VM only reached those four): inside
each class the games take turns least-sampled first (the campaign's tries so far + the jobs still queued), ties
rotated by the round number, so the head of every round is the games the campaign has seen least.
Skipped: a node with a job still queued (pending: it would be played twice), and a restart point (source play, step)
whose restore diverged (blocked: the learner reads the servers' results; another seed play of the same node is used
instead), or a node blocked outright (its restore diverged from 2+ source plays).

A job = the node + K tries. Try 0 is 'stock' (the anchor); the others get the modes with the fewest samples at the
node (counting this job's own assignments), ties broken by the current policy's probability there, then by the
coach's mode order. Each try records design_prob (the share of the job's tries given its mode) and policy_prob (the
current policy at the source step's features; the live coach logs it again at the real decision). Stop rule: the
origin's level cleared, the play ends, a move budget of 2 x the best known moves to clear from the node (min 30,
max 200; 200 when nothing is known), the turn cap (default 60) or the token cap (generated tokens after the origin,
default 200k from the learner). A game over does not stop a try.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rl_common as rc  # noqa: E402

DEFAULT_BUILD = "hist/daniel-hicache-sbt06"


def _short(n1: str) -> str:
    return n1.rsplit(":", 1)[-1][:12]


def seed_paths(plays: list[dict], seed_runs: set[str], build: str | None) -> list[tuple[dict, list[tuple[dict, int]]]]:
    """Seed plays as (rollout, [(step, actions_before)]) in step order."""
    out = []
    for play in plays:
        r = play["rollout"]
        if rc.is_rollout(play) or r.get("run") not in seed_runs or r.get("game") in rc.FENCED:
            continue
        if build and r.get("build") != build:
            continue
        rows, before = [], 0
        for s in sorted(play["steps"], key=lambda s: s["seq"]):
            rows.append((s, before))
            before += int(s.get("moves_step") or 0)
        out.append((r, rows))
    return out


_SNAPS: dict[tuple[str, int], dict] = {}        # the state index pick() was given (restartable() reads it)


def snapshot_of(r: dict, s: dict) -> str | None:
    """The state snapshot that restores this step: its own state_ref, or the index (a replayed seed node)."""
    if s.get("state_ref"):
        return s["state_ref"]
    x = _SNAPS.get((r.get("id"), int(s["seq"]))) if r else None
    return x["sha"] if x else None


def restartable(s: dict, r: dict | None = None) -> bool:
    """A restart point: a snapshot restores it, or (a seed play) its turn's exact context was logged (replay)."""
    if int((s.get("detail") or {}).get("part") or 1) != 1:
        return False
    return bool(s.get("resumable") and s.get("ctx_before")) or bool(snapshot_of(r or {}, s))


def classify(paths, stats: rc.NodeStats, backward_depth: int, extra_paths=()) -> dict[str, dict[str, list]]:
    """{game: {class: [(score, step, actions_before, rollout, extra)]}} in priority order inside each class.
    extra_paths: the campaign's own tries; their snapshotted steps join the uncertain class."""
    out: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    taken: set[str] = set()
    for r, rows in paths:                                    # 1. level starts
        g = r["game"]
        for i, (s, before) in enumerate(rows):
            if i and rows[i - 1][0]["level"] == s["level"]:
                continue
            j = i
            while j < len(rows) and rows[j][0]["level"] == s["level"] and not restartable(rows[j][0], r):
                j += 1
            if j < len(rows) and rows[j][0]["level"] == s["level"]:
                st, b = rows[j]
                out[g]["level_start"].append((st["level"], st, b, r, {"shifted": j != i}))
                taken.add(st["n1"])
    for g in out:
        out[g]["level_start"].sort(key=lambda x: (x[0], x[1]["seq"]))
    best: dict[tuple[str, int], tuple[int, dict, list]] = {}    # 2. the best seed path per level
    for r, rows in paths:
        by_level = defaultdict(list)
        for s, before in rows:
            by_level[s["level"]].append((s, before))
        for lv, lrows in by_level.items():
            lm = rc.level_moves(lrows[0][0])
            if lm is None:
                continue
            key = (r["game"], lv)
            if key not in best or lm < best[key][0]:
                best[key] = (lm, r, lrows)
    for (g, lv), (lm, r, lrows) in best.items():
        depth = 0
        for s, before in reversed(lrows):
            if depth >= backward_depth:
                break
            if not restartable(s, r):
                continue
            depth += 1
            if s["n1"] in taken:
                continue
            out[g]["backward"].append((depth, s, before, r, {"level_moves": lm}))
            taken.add(s["n1"])
    for g in out:
        out[g]["backward"].sort(key=lambda x: (x[0], x[1]["level"]))
    for r, rows in list(paths) + list(extra_paths):         # 3. the rest by uncertainty
        for s, before in rows:
            if restartable(s, r) and s["n1"] not in taken:
                out[r["game"]]["uncertain"].append((-stats.uncertainty(s["n1"]), s, before, r, {}))
                taken.add(s["n1"])
    for g in out:
        out[g]["uncertain"].sort(key=lambda x: x[0])
    return out


# Full plays of the base model whose per-level results feed the frontier for round 1 (4-Oct, Son: "how to measure 90%
# if we play less than 10 times?" - the 4 seed runs alone give 4 plays a game, where '< 90%' only meant 'not all 4').
DUCK_RUNS = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
BASE_RUNS = (*rc.SEED_RUNS, "daniel-base-a-1001", "daniel-base-b-1001", "daniel-noborder-c-1001",
             "daniel-noborder-d-1001", "daniel-p5train-base-b-1002", "daniel-p5train-base-s2-1003",
             "daniel-p4hard-base-a-1002")


def level_counts_from_viewers(runs, cache: Path, root: str = DUCK_RUNS) -> dict[str, dict[int, list[int]]]:
    """{game: {level: [cleared, reached]}} over every pass of these full-play runs, from their small per-game viewer
    files (levels_completed, total_levels): a pass reached levels 1..completed+1 and cleared 1..completed."""
    counts: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    bucket = root[5:].split("/", 1)[0]
    for run in runs:
        items, _ = rc.gcs_list(f"{root.rstrip('/')}/{run}/working/artifacts/")
        for it in items:
            name = it["name"].rsplit("/", 1)[-1]
            if not name.endswith("_viewer_data.json") or name[:4] in rc.FENCED:
                continue
            dest = cache / "viewers" / run / name
            if not dest.exists() or dest.stat().st_size != int(it["size"]):
                dest.parent.mkdir(parents=True, exist_ok=True)
                rc.gcs_download(f"gs://{bucket}/{it['name']}", dest)
            d = json.loads(dest.read_text(encoding="utf-8"))
            done, total = int(d.get("levels_completed") or 0), int(d.get("total_levels") or 0)
            for lv in range(1, min(done + 1, total) + 1):
                counts[name[:4]][lv][1] += 1
                counts[name[:4]][lv][0] += int(lv <= done)
    return {g: {lv: list(v) for lv, v in c.items()} for g, c in counts.items()}


def wilson_lower(k: int, n: int, z: float) -> float:
    """Lower end of the Wilson interval for k clears in n plays (0 for n = 0)."""
    if n <= 0:
        return 0.0
    p, z2 = k / n, z * z
    return (p + z2 / (2 * n) - z * ((p * (1 - p) + z2 / (4 * n)) / n) ** 0.5) / (1 + z2 / n)


def frontier_levels(paths, threshold: float, counts: dict | None = None, z: float = 1.28,
                    min_reached: int = 6) -> dict[str, dict]:
    """Per game, the first level the base model has not mastered: a level counts as mastered only when at least
    min_reached plays reached it AND the Wilson lower bound (z 1.28: one-sided 90%) of its clear rate is >= threshold,
    e.g. 8/8 (0.83), 17/18 (0.83) pass 0.8; 4/4 (0.71), 9/10 (0.72) do not. Levels below the frontier are not
    restarted (4-Oct, Son: sample where the model is not yet sure to win). counts: {game: {level: [cleared,
    reached]}} (level_counts_from_viewers); without it, the seed paths are counted. {game: {"level", "rates"}}; a
    game whose every level is mastered gets its highest level."""
    seen: dict = counts
    if seen is None:
        seen = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for r, rows in paths:
            levels: dict[int, bool] = {}
            for s, _ in rows:
                lv = int(s["level"])
                levels[lv] = levels.get(lv, False) or bool((s.get("outcome") or {}).get("cleared_level"))
            for lv, cleared in levels.items():
                seen[r["game"]][lv][1] += 1
                seen[r["game"]][lv][0] += int(cleared)
    out = {}
    for g, rates in seen.items():
        lvls = sorted(int(lv) for lv in rates)
        rate = {lv: rates.get(lv, rates.get(str(lv))) for lv in lvls}
        mastered = lambda lv: rate[lv][1] >= min_reached and wilson_lower(rate[lv][0], rate[lv][1], z) >= threshold  # noqa: E731
        f = next((lv for lv in lvls if not mastered(lv)), lvls[-1])
        out[g] = {"level": f, "rates": rate}
    return out


def stage_tries(cstats: rc.NodeStats, n1: str, stage_k: int, N: int) -> int:
    """Two-stage groups (4-Oct): a node's first job gets stage_k tries; it gets more (up to N in all) only when this
    campaign's tries there split (some cleared, some not): an all-clear or all-fail group carries no signal, and 6
    of 20 speed2 nodes had every try at full marks. 0 = settled, do not pick."""
    v = cstats.visits(n1)
    if v == 0:
        return stage_k
    w = sum(cstats.clears[n1].values())
    return N - v if 0 < w < v and v < N else 0


def mode_set(spec: str | None) -> list[str]:
    """The modes a job may assign: 'all' (every coach mode), 'original', 'grader', or a comma list (stock always)."""
    raw = (spec or "all").strip().lower()
    if raw == "all":
        names = list(rc.MODES)
    elif raw == "original":
        names = list(rc.coach.ORIGINAL_MODES)
    elif raw == "grader":
        names = ["stock"] + list(rc.coach.GRADER_MODES)
    else:
        names = [m.strip() for m in raw.split(",") if m.strip() in rc.MODES]
    return ["stock"] + [m for m in names if m != "stock"]


def assign(K: int, counts: Counter, pdist: dict[str, float], N: int, caps: list[str],
           modes_allowed: list[str] | None = None, gcount: Counter | None = None) -> list[dict]:
    """Try 0 = stock (anchor); then the least-sampled modes still under N at this node; ties: the mode the whole
    campaign has assigned least (gcount: campaign tries + queued jobs + this round so far), then policy probability,
    then mode order. Without gcount every fresh node got the same first modes in list order (rl2 round 1, 3-Oct)."""
    allowed = modes_allowed or list(rc.MODES)
    gcount = gcount if gcount is not None else Counter()
    modes = ["stock"]
    extra = Counter({"stock": 1})
    while len(modes) < K:
        open_ = [m for m in allowed if counts[m] + extra[m] < N]
        if not open_:
            break
        m = min(open_, key=lambda m: (counts[m] + extra[m], gcount[m] + extra[m], -pdist.get(m, 0.0),
                                      rc.MODES.index(m)))
        modes.append(m)
        extra[m] += 1
    tries = len(modes)
    cap_of = ["mode"] + [caps[(k - 1) % len(caps)] for k in range(1, tries)]
    cap_n = Counter(cap_of)
    return [{"k": k, "mode": m, "anchor": k == 0, "cap": None if cap_of[k] == "mode" else cap_of[k],
             "design_prob": round(extra[m] / tries, 6), "cap_design_prob": round(cap_n[cap_of[k]] / tries, 6),
             "policy_prob": (round(pdist[m], 6) if m in pdist else None),
             "samples_before": counts[m]} for k, m in enumerate(modes)]


def restart_key(rollout_id: str | None, seq) -> str:
    """A restart point: the source play and the step (blocked lists key on it; JSON-safe)."""
    return f"{rollout_id}#{int(seq)}"


def game_order(games, plays: list[dict], campaign: str, pending: list[dict] | None, round_: int) -> list[str]:
    """Least-sampled game first: the campaign's tries per game plus the jobs still queued for it; ties rotated by
    round so no game is always first."""
    run = rc.campaign_run(campaign)
    n = Counter(p["rollout"].get("game") for p in plays if p["rollout"].get("run") == run)
    n.update(str(j.get("game") or "") for j in pending or [])
    names = sorted(games)
    rank = {g: (i - round_) % max(1, len(names)) for i, g in enumerate(names)}
    return sorted(names, key=lambda g: (n[g], rank[g]))


def budget(stats: rc.NodeStats, s: dict) -> tuple[int, int | None]:
    m = stats.best_from(s["n1"])
    if m is None:
        lv = stats.best_level.get((s["game"], int(s["level"])))
        m = lv - int(s.get("moves") or 0) if lv and lv > int(s.get("moves") or 0) else None
    return (max(30, min(200, 2 * m)) if m else 200), m


def pick(plays: list[dict], *, campaign: str, round_: int, seed_runs: set[str], build: str | None = DEFAULT_BUILD,
         pol: dict | None = None, N: int = 4, K: int = 5, limit: int = 40, per_game: int = 4,
         backward_depth: int = 6, turn_cap: int = 60, caps: list[str] | None = None, games: set[str] | None = None,
         sources: str = rc.SEED_SOURCES, coach_spec: str = "policy", state_index: dict | None = None,
         store: str = rc.STORE, campaign_restarts: bool = True, modes: str | None = "all",
         pending: list[dict] | None = None, blocked: dict | None = None, blocked_nodes: dict | None = None,
         token_cap: int | None = None, mix: dict[str, float] | None = None, stage_k: int | None = None,
         frontier: float | None = None, level_counts: dict | None = None) -> tuple[list[dict], dict]:
    """pending: jobs still queued ({game, t1, ...}: their nodes are skipped, their games count as sampled);
    blocked: restart_key(source rollout, seq) -> why (a restore that diverged); blocked_nodes: t1 -> why;
    token_cap: generated tokens per try after the origin (the server stops the try there; None = no cap);
    mix: share of the round per class ({"level_start": .4, "backward": .3, "uncertain": .3}): a first pass fills each
    class up to its share, a second pass fills what is left in class order (None = class order only; rl2 3-Oct:
    level starts alone filled every round, so no backward or uncertain node, nor any campaign branch, was played).
    stage_k: two-stage groups (stage_tries): a node's first job gets stage_k tries, a top-up only where they split;
    frontier: only levels at or above each game's first level not mastered (frontier_levels: the Wilson lower bound of
    its clear rate below `frontier`, or too few plays), counted from level_counts (level_counts_from_viewers) or, without
    it, the seed paths."""
    allowed = mode_set(modes)
    blocked, blocked_nodes = blocked or {}, blocked_nodes or {}
    pending_n1 = {str(j.get("t1")) for j in pending or [] if j.get("t1")}
    _SNAPS.clear()
    _SNAPS.update(state_index or {})
    stats = rc.NodeStats(plays)
    paths = [p for p in seed_paths(plays, seed_runs, build) if not games or p[0]["game"] in games]
    extra = []
    if campaign_restarts:                    # the campaign's own tries: restartable where a turn snapshot exists
        run = rc.campaign_run(campaign)
        for play in plays:
            r = play["rollout"]
            if r.get("run") == run and r.get("game") not in rc.FENCED and (not games or r.get("game") in games):
                rows, before = [], int((r.get("result") or {}).get("origin_actions_before") or 0)
                for s in sorted(play["steps"], key=lambda s: s["seq"]):
                    rows.append((s, before))
                    before += int(s.get("moves_step") or 0)
                extra.append((r, rows))
    classes = classify(paths, stats, backward_depth, extra)
    fronts = frontier_levels(paths, frontier, counts=level_counts) if frontier else {}
    below = Counter()
    for g, f in fronts.items():              # levels every seed play clears: never restarted
        for cls in list(classes.get(g, {})):
            keep = [x for x in classes[g][cls] if int(x[1]["level"]) >= f["level"]]
            below[g] += len(classes[g][cls]) - len(keep)
            classes[g][cls] = keep
    run_c = rc.campaign_run(campaign)
    cstats = rc.NodeStats([p for p in plays if p["rollout"].get("run") == run_c]) if stage_k else None
    gcount = Counter()                       # first-mode assignments campaign-wide: spreads modes across nodes
    for r, rows in extra:
        if rows:
            gcount[rows[0][0].get("action")] += 1
    for j in pending or []:
        for a in j.get("assignments") or []:
            gcount[a.get("mode")] += 1
    pol = pol or {}
    jobs, seen_n1, seen_n5 = [], set(), set()
    per = Counter()
    order = game_order(classes, plays, campaign, pending, round_)
    report = {"plays": len(plays), "seed_plays": len(paths), "campaign_plays": len(extra), "skipped_full": 0,
              "skipped_grid": 0, "skipped_pending": 0, "skipped_blocked": 0, "skipped_settled": 0,
              "skipped_below_frontier": sum(below.values()), "by_class": Counter(),
              "by_restore": Counter(), "games": sorted(classes), "game_order": order,
              "frontier": {g: f["level"] for g, f in sorted(fronts.items())}}
    seen_n1.update(pending_n1)
    share = {c: -(-limit * float((mix or {}).get(c, 0.0)) // 1) for c in ("level_start", "backward", "uncertain")}
    for capped, cls in ([(True, c) for c in share] if mix else []) + \
            [(False, c) for c in ("level_start", "backward", "uncertain")]:
        queues = {g: list(classes[g][cls]) for g in order}
        full = (lambda c=cls, k=capped: k and report["by_class"][c] >= share[c])
        while any(queues.values()) and len(jobs) < limit and not full():
            for g in order:
                if len(jobs) >= limit or full():
                    break
                while queues[g] and per[g] < per_game:
                    score, s, before, r, extra = queues[g].pop(0)
                    if s["n1"] in pending_n1:
                        report["skipped_pending"] += 1
                        continue
                    if s["n1"] in seen_n1:
                        continue
                    if s["n1"] in blocked_nodes or restart_key(r.get("id"), s["seq"]) in blocked:
                        report["skipped_blocked"] += 1        # the next source play of this node may still serve
                        continue
                    if s.get("n5") in seen_n5:
                        report["skipped_grid"] += 1
                        continue
                    k_node = K
                    if stage_k:                       # this campaign's own tries decide: first stage, top-up, or done
                        counts = cstats.n[s["n1"]]
                        k_node = min(K, stage_tries(cstats, s["n1"], stage_k, N))
                        if k_node <= 0:
                            report["skipped_settled"] += 1
                            continue
                    else:
                        counts = stats.n[s["n1"]]
                    # stock-only rounds (--modes stock) count stock itself: 'every non-stock mode at N' was vacuously
                    # true there and skipped every node (4-Oct: 2792 of 2792 skipped, 0 jobs)
                    capped_modes = [m for m in allowed if m != "stock"] or ["stock"]
                    if all(counts[m] >= N for m in capped_modes):
                        report["skipped_full"] += 1
                        continue
                    pdist = rc.mode_dist(pol, s.get("features") or {})
                    tries = assign(k_node, counts, pdist, N, caps or ["mode"], allowed, gcount)
                    if len(tries) < 2:
                        report["skipped_full"] += 1
                        continue
                    for t in tries:
                        gcount[t["mode"]] += 1
                    b, best_from = budget(stats, s)
                    res = r.get("result") or {}
                    gid, ps, run = res.get("game_id"), int(res.get("pass") or 0), r["run"]
                    snap = snapshot_of(r, s)
                    src = {"run": run, "rollout_id": r["id"], "coach_log": None}
                    if not rc.is_rollout({"rollout": r}):        # a seed play: its logs replay it (or back a snapshot)
                        src.update(requests=f"{sources}/{run}/working/{gid}_p{ps}_requests.jsonl",
                                   events=f"{sources}/{run}/working/artifacts/{gid}_p{ps}_events.jsonl")
                    if snap:
                        src.update(state_ref=snap, state=f"{store.rstrip('/')}/state/{snap}.pkl.gz",
                                   ctx_before=s.get("ctx_before"))
                    report["by_restore"][("snapshot" if snap else "replay_exact")] += 1
                    jobs.append({
                        "job_id": f"{campaign}-r{round_:03d}-{g}-{_short(s['n1'])}", "campaign": campaign,
                        "round": round_, "priority": len(jobs), "game_id": gid, "pass": ps,
                        "mode": "snapshot" if snap else "replay_exact", "source": src,
                        "origin": {"seq": s["seq"], "turn": (s.get("detail") or {}).get("turn"), "t1": s["n1"],
                                   "t5": s.get("n5"), "screen_hash": s["screen_hash"], "level": s["level"],
                                   "actions_before": before, "moves": s.get("moves")},
                        "tries": len(tries), "assignments": tries,
                        "policy": {"version": pol.get("version"), "seq": pol.get("seq"), "dist": pdist},
                        "stop": {"move_budget": b, "turn_cap": turn_cap, "stop_on_game_over": False,
                                 "token_cap": int(token_cap) if token_cap else None},
                        "coach": {"spec": coach_spec, "cap": None},
                        "pick": {"class": cls, "score": round(-score, 4) if cls == "uncertain" else score,
                                 "visits": stats.visits(s["n1"]), "clear_rate": round(stats.clear_rate(s["n1"]), 3),
                                 "counts": dict(counts), "best_from_node": best_from, **extra}})
                    seen_n1.add(s["n1"])
                    seen_n5.add(s.get("n5"))
                    per[g] += 1
                    report["by_class"][cls] += 1
                    break
                else:
                    queues[g] = []
    report["jobs"] = len(jobs)
    report["tries"] = sum(j["tries"] for j in jobs)
    report["by_class"] = dict(report["by_class"])
    report["by_restore"] = dict(report["by_restore"])
    report["per_game"] = dict(per)
    return jobs, report


def job_name(j: dict) -> str:
    """Sortable file name: round, priority, job id (the server plays its kept rounds oldest first, in priority order)."""
    return f"{int(j['round']):04d}-{int(j['priority']):05d}-{j['job_id']}.json"


def write_jobs(jobs: list[dict], *, out: str | None = None, queue: str | None = None) -> str:
    if out:
        d = Path(out)
        d.mkdir(parents=True, exist_ok=True)
        for j in jobs:
            (d / job_name(j)).write_text(json.dumps(j, indent=1), encoding="utf-8")
        return str(d)
    store = rc.Store(queue)
    for j in jobs:
        rc.write_json(store, f"jobs/round-{int(j['round']):04d}/{job_name(j)}", j)
    return queue


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--store", default=rc.STORE)
    ap.add_argument("--seed-runs", default=",".join(rc.SEED_RUNS))
    ap.add_argument("--cache", default=r"D:\codex-work\gtree-rl\cache")
    ap.add_argument("--build", default=DEFAULT_BUILD, help="'' = any build of the seed runs")
    ap.add_argument("--policy", help="policy JSON (current.json); none = ties by mode order")
    ap.add_argument("--N", type=int, default=4)
    ap.add_argument("--K", type=int, default=5)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--per-game", type=int, default=4)
    ap.add_argument("--backward-depth", type=int, default=6)
    ap.add_argument("--turn-cap", type=int, default=60)
    ap.add_argument("--token-cap", type=int, default=200000, help="generated tokens per try after the origin; 0 = none")
    ap.add_argument("--caps", default="mode", help="cap assignment cycled over the non-anchor tries, e.g. mode,4,none")
    ap.add_argument("--games", help="only these games")
    ap.add_argument("--modes", default="all", help="modes to assign: all | original | grader | comma list")
    ap.add_argument("--out", help="write jobs to this directory")
    ap.add_argument("--queue", help="write jobs to <queue>/jobs/round-NNNN/ (gs://.../arc3-gtree/v1/rl/<campaign>)")
    a = ap.parse_args()
    if not (a.out or a.queue):
        ap.error("--out or --queue")
    seed = {x for x in a.seed_runs.split(",") if x}
    runs = sorted(seed) + [rc.campaign_run(a.campaign)]
    plays = rc.load_plays(rc.sync_masters(a.store, runs, Path(a.cache)))
    games = {g for g in (a.games or "").split(",") if g} or None
    if games and games & rc.FENCED:
        raise SystemExit(f"held-out games are never sampled: {sorted(games & rc.FENCED)}")
    jobs, rep = pick(plays, campaign=a.campaign, round_=a.round, seed_runs=seed, build=a.build or None,
                     pol=rc.policy_doc(a.policy), N=a.N, K=a.K, limit=a.limit, per_game=a.per_game,
                     backward_depth=a.backward_depth, turn_cap=a.turn_cap, caps=a.caps.split(","), games=games,
                     state_index=rc.load_state_index(a.store, Path(a.cache)), store=a.store, modes=a.modes,
                     token_cap=a.token_cap or None)
    where = write_jobs(jobs, out=a.out, queue=a.queue)
    print(json.dumps(rep))
    print(f"{len(jobs)} jobs ({rep['tries']} tries) -> {where}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
