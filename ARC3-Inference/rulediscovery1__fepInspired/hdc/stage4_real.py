# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 4 of docs/plans/2026-09-24-hdc-ghost-roadmap.md: the stage-3 lag filter on REAL Ghost Twin
#   plays (the same 20 recorded plays as stage 0), offline, from the recorded boards only.
#   Perception (boards only, no game internals):
#     - objects = non-background components (distill/object_events.board_comps), keyed by type (colour +
#       shape); instances of one type are tracked frame to frame by nearest position (<= MAX_JUMP px), so two
#       ghosts of the same type stay apart.
#     - player = the single-instance type that moved most often on arrow presses before the first rewind.
#     - rewind event = the player is back at its level-start position after an action that was not RESET
#       (a run ends); a level change or RESET clears everything.
#   Model: hdc/stage3_synth.GhostFinder with one tape per earlier run of the level (sources prev1, prev2, cur),
#   both clocks, lags 0-3, plus the stand-still null; every tracked non-player object is a candidate.
#   Scoring against the stage-0 labels (simulator, used ONLY here): after each rewind that created a ghost,
#   (a) was some object explained as a copy of an earlier run, and is that object the real ghost (its
#   perceived moves match the true ghost's moves on >= 90 % of the actions); (b) after the decision, how often
#   is the ghost's next move predicted exactly (cleanup of the tape read-out, or "stands still"); (c) which
#   clock won. Output results/hdc/stage4_real.json + .md.
#   24-Sep-2026 (HDC integration A/B, OpenMind 10:17 ET): Tracker.update_objects takes an already-parsed object
#   list and records each track's component, so the live agent (hdc_bridge.GhostTape) reuses its own Scene.
# SRP/DRY check: Pass -- components from distill/object_events, trace reading from verify_env, the filter from
#   stage3_synth, tapes/codebook from stage2_tape; new: the instance tracker, player/rewind detection and the
#   scoring against labels.
"""Stage 4: lag filter on 20 real Ghost Twin plays, offline."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .. import _distill as D
from ..verify_env import load_rows
from .stage2_tape import MOVES, Tape, book
from .stage3_synth import LAGS, GhostFinder, Hypothesis
from .vsa import VSA

OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"
MAX_JUMP = 8
ARROWS = {"ACTION1", "ACTION2", "ACTION3", "ACTION4"}


def board_of(r):
    b = r["board"]
    return json.loads(b) if isinstance(b, str) else b


class Tracker:
    """Instances per type, matched frame to frame by nearest top-left corner."""

    def __init__(self):
        self.tracks = {}          # track id -> (type, (y, x))
        self.next_id = 0
        self.comp_of = {}         # track id -> component on the latest board

    def update(self, board) -> dict:
        """Returns track id -> (dy, dx) for tracks seen in both boards; new tracks get (0, 0)."""
        bc = D.oe.board_comps(board, None)
        return self.update_objects([c for c in bc.comps if not c.bg and c.colour != bc.mode])

    def update_objects(self, objs) -> dict:
        """update() on an already-parsed object list (the live agent passes its Scene.objects(), so the board
        is not parsed twice). self.comp_of[track id] = that track's component on this board (24-Sep-2026)."""
        now = [(c.type_key, (c.y0, c.x0)) for c in objs]
        self.comp_of = {}
        moves, used = {}, set()
        for tid, (tk, (y, x)) in list(self.tracks.items()):
            cands = [(abs(yy - y) + abs(xx - x), i) for i, (k2, (yy, xx)) in enumerate(now)
                     if k2 == tk and i not in used and abs(yy - y) <= MAX_JUMP and abs(xx - x) <= MAX_JUMP]
            if not cands:
                del self.tracks[tid]
                continue
            _, i = min(cands)
            used.add(i)
            yy, xx = now[i][1]
            moves[tid] = (yy - y, xx - x)
            self.tracks[tid] = (tk, (yy, xx))
            self.comp_of[tid] = objs[i]
        for i, (tk, pos) in enumerate(now):
            if i not in used:
                self.tracks[self.next_id] = (tk, pos)
                self.comp_of[self.next_id] = objs[i]
                moves[self.next_id] = (0, 0)
                self.next_id += 1
        return moves

    def positions_of(self, tk):
        return [pos for (k, pos) in self.tracks.values() if k == tk]

    @staticmethod
    def area(board, tk) -> int:
        bc = D.oe.board_comps(board, None)
        return max((c.size for c in bc.comps if c.type_key == tk), default=0)


class MultiRunFinder(GhostFinder):
    """GhostFinder with one source per earlier run of the level (prev1 = last run, prev2 = the one before)."""

    def __post_init__(self):
        super().__post_init__()
        self.runs = []                               # earlier runs' tapes, newest last

    def rewind(self):
        self.runs.append(self.cur)
        self.cur = {"moves": Tape(self.vsa), "actions": Tape(self.vsa)}
        srcs = [f"prev{i}" for i in range(1, min(len(self.runs), 2) + 1)] + ["cur"]
        self.hyps = [Hypothesis(o, s, c, L) for o in self.objects for s in srcs for c in ("moves", "actions")
                     for L in LAGS] + [Hypothesis(o, "still", "-", 0) for o in self.objects]
        self.decided, self.t = {}, 0

    def add_objects(self, objs):
        new = [o for o in objs if o not in self.objects]
        if not new:
            return
        self.objects = self.objects + new
        if self.hyps:
            srcs = sorted({h.source for h in self.hyps})
            self.hyps += [Hypothesis(o, s, c, L) for o in new for s in srcs if s != "still"
                          for c in ("moves", "actions") for L in LAGS] + [Hypothesis(o, "still", "-", 0) for o in new]

    def predict(self, h, player_moved):
        if h.source.startswith("prev"):
            i = int(h.source[4:])
            if i > len(self.runs):
                return None
            saved = self.prev
            self.prev = self.runs[-i]
            try:
                return super().predict(Hypothesis(h.obj, "prev", h.clock, h.lag), player_moved)
            finally:
                self.prev = saved
        return super().predict(h, player_moved)


def run_play(play, trace_rows, vsa, initial, on_ghost_step=None):
    """initial: the board before the first action (the level's start). boards and steps are both prefixed
    (initial board / None) so that steps[i] labels the action that produced boards[i].
    on_ghost_step(action, true_move, tape_prediction_or_None) is called on every action with a ghost on the
    board (stage 5 uses it; labels only feed the scoring)."""
    steps = [None] + play["steps"]
    tracker = Tracker()
    boards = [initial] + [board_of(r) for r in trace_rows]
    trace_rows = [None] + trace_rows
    # player type: the single-instance type moving most on arrows before the first labelled-free rewind guess
    arrow_moves = {}
    tr0 = Tracker()
    tr0.update(boards[0]) if boards else None
    for r, b in zip(trace_rows[1:], boards[1:]):
        mv = tr0.update(b)
        if r["action_name"] == "ACTION5":
            break                                      # before the first rewind only
        if r["action_name"] in ARROWS:
            for tid, d in mv.items():
                if d != (0, 0):
                    tk = tr0.tracks[tid][0]
                    arrow_moves[tk] = arrow_moves.get(tk, 0) + 1
    if not arrow_moves:
        return []
    # the most-moved type; a part that always moves with it (a 1-pixel centre mark) ties, so prefer the larger
    top = max(arrow_moves.values())
    ptype = max((tk for tk, n in arrow_moves.items() if n >= 0.8 * top), key=lambda tk: Tracker.area(boards[0], tk))
    finder = MultiRunFinder(vsa, [])
    tracker.update(boards[0])
    level_start = (tracker.positions_of(ptype) or [None])[0]
    level = 0
    events = []                    # one entry per detected rewind
    cur_event = None
    b = book(vsa)
    for i in range(1, len(boards)):
        r, s = trace_rows[i], steps[i]
        before = (tracker.positions_of(ptype) or [None])[0]
        mv = tracker.update(boards[i])
        after = (tracker.positions_of(ptype) or [None])[0]
        if s["level"] != level or r["action_name"] == "RESET":          # new level or level restart: forget runs
            level = s["level"]
            finder = MultiRunFinder(vsa, [])
            level_start, cur_event = after, None
            continue
        pmove = (after[0] - before[0], after[1] - before[1]) if (before and after) else (0, 0)
        rewound = (after is not None and level_start is not None and after == level_start and before != level_start
                   and abs(pmove[0]) + abs(pmove[1]) > MAX_JUMP)
        if rewound:
            finder.rewind()
            cur_event = {"step": i, "truth_ghost": bool(s["ghosts"]), "decided": None, "pred_ok": 0, "pred_n": 0}
            events.append(cur_event)
            continue
        others = {tid: d for tid, d in mv.items() if tracker.tracks.get(tid, (None,))[0] != ptype}
        finder.add_objects(list(others))
        pm = pmove if abs(pmove[0]) + abs(pmove[1]) <= MAX_JUMP else (0, 0)
        prev_g, cur_g = (steps[i - 1]["ghosts"] if steps[i - 1] else None), s["ghosts"]
        true = None
        if prev_g and cur_g and len(prev_g) == len(cur_g):
            # the newest ghost (created by the latest rewind) is the last in the list
            true = (cur_g[-1][1] - prev_g[-1][1], cur_g[-1][0] - prev_g[-1][0])
        pred = None
        if cur_event is not None and cur_event["decided"] is not None and true is not None:
            # predict the true ghost's move with the decided hypothesis before this action is observed
            key = cur_event["decided_key"]
            h = next(h for h in finder.hyps if h.key() == key)
            p = finder.predict(h, pm != (0, 0))
            pred = MOVES[vsa.cleanup(p, b)] if p is not None else (0, 0)
            cur_event["pred_n"] += 1
            cur_event["pred_ok"] += int(tuple(pred) == true)
        if on_ghost_step is not None and true is not None:
            on_ghost_step(r["action_name"], true, pred)      # stage 5 hook: labels + the tape rule's prediction
        finder.observe(pm, others)
        if cur_event is not None and cur_event["decided"] is None:
            for o, (key, t) in finder.decided.items():
                if key[1].startswith("prev"):
                    cur_event.update(decided=str(key), decided_key=key, decided_after=t, obj=o,
                                     source=key[1], clock=key[2], lag=key[3])
                    # is o the real ghost? compare its perceived moves so far with the latest true ghost's
                    cur_event["obj_moves"] = []
                    break
    # identity check: decided object's perceived moves vs the true ghost's moves (replay the tracker)
    return events


def identity_check(play, trace_rows, events, vsa, initial):
    """For each event with a decision, replay the tracker and compare the decided track's moves with the true
    moves of the newest ghost (the one the rewind created) over the actions until the next rewind."""
    steps = [None] + play["steps"]
    boards = [initial] + [board_of(r) for r in trace_rows]
    out = []
    for ev in events:
        if ev.get("decided") is None or not ev["truth_ghost"]:
            continue
        tr = Tracker()
        tr.update(boards[0])
        match = tot = 0
        end = next((e["step"] for e in events if e["step"] > ev["step"]), len(boards))
        for i in range(1, end):
            mv = tr.update(boards[i])
            if i <= ev["step"]:
                continue
            pg, cg = (steps[i - 1]["ghosts"] if steps[i - 1] else None), steps[i]["ghosts"]
            if not pg or not cg or len(pg) != len(cg) or ev["obj"] not in mv:
                continue
            true = (cg[-1][1] - pg[-1][1], cg[-1][0] - pg[-1][0])
            tot += 1
            match += int(tuple(mv[ev["obj"]]) == true)
        out.append(match / tot if tot else None)
    return out


def main(n: int = 20):
    OUT.mkdir(parents=True, exist_ok=True)
    vsa = VSA(4096, seed=0)
    plays = json.loads((OUT / "stage0_groundtruth.json").read_text())[:n]
    all_events, identities = [], []
    for play in plays:
        all_rows = load_rows(Path(play["trace"]))
        rows = [r for r in all_rows if r.get("type") == "action"]
        init = next((r for r in all_rows if r.get("type") == "initial"), None)
        if not rows or init is None:
            continue
        ev = run_play(play, rows, vsa, board_of(init))
        identities += identity_check(play, rows, ev, vsa, board_of(init))
        for e in ev:
            e.pop("decided_key", None)
            e["play"] = Path(play["trace"]).parent.parent.parent.name + "/" + Path(play["trace"]).name
        all_events += ev
    truth_rewinds = sum(s["rewind"] for p in plays for s in p["steps"])
    with_ghost = [e for e in all_events if e["truth_ghost"]]
    decided = [e for e in with_ghost if e.get("decided")]
    ident_ok = sum(1 for x in identities if x is not None and x >= 0.9)
    pred_ok = sum(e["pred_ok"] for e in decided)
    pred_n = sum(e["pred_n"] for e in decided)
    clocks = {}
    for e in decided:
        clocks[e["clock"]] = clocks.get(e["clock"], 0) + 1
    res = {"plays": len(plays), "true_rewinds": truth_rewinds, "detected_rewinds": len(all_events),
           "detected_rewinds_with_true_ghost": len(with_ghost), "copy_decided": len(decided),
           "decided_object_is_true_ghost_(>=90%_moves_match)": ident_ok, "identity_scores": identities,
           "ghost_next_move_exact": [pred_ok, pred_n], "clock_chosen": clocks,
           "median_actions_to_decide": float(np.median([e["decided_after"] for e in decided])) if decided else None,
           "events": all_events}
    text = (f"stage 4 (20 real Ghost Twin plays, offline): true rewinds {truth_rewinds}, detected {len(all_events)} "
            f"({len(with_ghost)} with a real ghost); a copy of an earlier run found after {len(decided)} of them "
            f"(median {res['median_actions_to_decide']} actions); that object is the real ghost in {ident_ok} of "
            f"{len(identities)}; ghost's next move predicted exactly {pred_ok}/{pred_n}; clock chosen {clocks}")
    print(text)
    (OUT / "stage4_real.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "stage4_real.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
