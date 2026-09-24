# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 3 of docs/plans/2026-09-24-hdc-ghost-roadmap.md: find the ghost (an object that repeats an
#   earlier run's moves) on SYNTHETIC data, with decoys, by brute-force scoring of explicit hypotheses.
#   World (mimics Ghost Twin's rule, read from its source): the player walks; some moves are blocked (no move).
#   A rewind ends a run. The ghost then repeats the previous run's SUCCESSFUL moves, one per successful player
#   move of the new run (so its clock counts player moves, not actions), and stops when that path is used up.
#   Decoys: two random walkers, one stationary object, one "follower" that repeats the player's move of the
#   previous action in the CURRENT run (a lag-1 copy -- the hardest decoy).
#   Hypotheses, per object o: source in {previous run, current run} x clock in {player moves, actions} x lag in
#   {0..3}. Evidence per action = sim(observed move code, tape read-out) (vsa.sim, ~1 when right, ~0 when not).
#   Decision, per object (first version demanded one winner across objects, which wrongly counted the lag-1
#   follower -- a genuine copier -- as a rival): an object is explained by its best hypothesis once that has
#   >= MIN_OBS observations and mean evidence >= ACCEPT, and beats the object's best hypothesis with a
#   different SOURCE by MARGIN. Reports over many synthetic episodes: ghost explained right / wrong / not,
#   follower explained right / wrong / not, decoys (walkers, stationary) falsely explained, and actions after
#   the rewind until the ghost's decision. Each object also has a null hypothesis "stands still"; a copy
#   explanation must beat it too (without it, a still object matched every blocked move by chance).
#   Also defines Hypothesis/GhostFinder, reused by stage 4. Output results/hdc/stage3_synth.json + .md.
# SRP/DRY check: Pass -- vectors from hdc/vsa.py, tapes from hdc/stage2_tape.py; new: the synthetic world,
#   the hypothesis grid and the decision rule.
"""Stage 3: brute-force lag filter on a synthetic ghost with decoys."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .stage2_tape import MOVES, Tape
from .vsa import VSA

OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"
D = 4096
MIN_OBS, ACCEPT, MARGIN = 8, 0.8, 0.2       # "mean" rule (stages 3-4 first run)
DECISION = "mean"                           # "mean" (kept: best on real plays) or "evidence" (tried 24-Sep-2026, worse on real plays at EVID 2.5 / 4 / 5.5)
MIN_OBS_E, EVID = 3, 2.5
LAGS = range(4)


@dataclass
class Hypothesis:
    obj: object
    source: str          # "prev" | "cur"
    clock: str           # "moves" | "actions"
    lag: int
    total: float = 0.0
    n: int = 0

    def key(self):
        return (self.obj, self.source, self.clock, self.lag)

    @property
    def mean(self):
        return self.total / self.n if self.n else 0.0


@dataclass
class GhostFinder:
    """Keeps per-run tapes of the player's moves (both clocks) and scores every hypothesis each action."""
    vsa: VSA
    objects: list
    hyps: list = field(default_factory=list)
    prev: dict = field(default_factory=dict)      # clock -> Tape of the previous run
    cur: dict = field(default_factory=dict)       # clock -> Tape of the current run
    decided: dict = field(default_factory=dict)   # object -> (hypothesis key, action index)
    t: int = 0

    def __post_init__(self):
        self.cur = {"moves": Tape(self.vsa), "actions": Tape(self.vsa)}

    def rewind(self):
        self.prev, self.cur = self.cur, {"moves": Tape(self.vsa), "actions": Tape(self.vsa)}
        self.hyps = [Hypothesis(o, s, c, L) for o in self.objects for s in ("prev", "cur")
                     for c in ("moves", "actions") for L in LAGS]
        # null explanation per object: it simply stands still (a copy must beat this, or a still object
        # "copies" every blocked move and every exhausted tape by chance)
        self.hyps += [Hypothesis(o, "still", "-", 0) for o in self.objects]
        self.decided, self.t = {}, 0

    def predict(self, h: Hypothesis, player_moved: bool):
        if h.source == "still":
            return self.vsa.move(0, 0)
        tapes = self.prev if h.source == "prev" else self.cur
        tape = tapes.get(h.clock)
        if tape is None:
            return None
        # called BEFORE this action's player move is appended: cur[clock].n = entries so far this run
        k = self.cur[h.clock].n - h.lag       # "prev": the copied run's entry with this run's index
        if h.clock == "moves" and not player_moved:
            return self.vsa.move(0, 0)         # a move-clock copier stands still when the player is blocked
        if h.source == "cur":
            k -= 1                             # "cur": lag 0 = the player's previous entry in this run
        if k < 0 or k >= tape.n:
            return self.vsa.move(0, 0)         # before the start / after the end of the copied path
        return tape.readout(k)

    def observe(self, player_move, obj_moves: dict):
        """player_move: (dy, dx) of the player this action; obj_moves: object -> (dy, dx)."""
        moved = tuple(player_move) != (0, 0)
        if self.hyps:
            self.t += 1
            for h in self.hyps:
                p = self.predict(h, moved)
                if p is None or h.obj not in obj_moves:
                    continue
                h.total += self.vsa.sim(self.vsa.move(*obj_moves[h.obj]), p)
                h.n += 1
            for o in self.objects:
                if o not in self.decided:
                    k = self.decide(o)
                    if k is not None:
                        self.decided[o] = (k, self.t)
        if moved:                              # append AFTER scoring (the index is "moves so far")
            self.cur["moves"].append(*player_move)
        self.cur["actions"].append(*player_move)

    def ranking(self):
        return sorted(self.hyps, key=lambda h: -h.mean)

    def decide(self, obj):
        if DECISION == "evidence":
            return self.decide_evidence(obj)
        r = [h for h in self.ranking() if h.obj == obj and h.n >= MIN_OBS]
        if not r or r[0].mean < ACCEPT or r[0].source == "still":
            return None
        best = r[0]
        rival = max((h.mean for h in r if h.source != best.source), default=0.0)
        return best.key() if best.mean - rival >= MARGIN else None


    def decide_evidence(self, obj):
        """Summed evidence instead of a fixed number of observations (24-Sep-2026, after stage 4): a copy
        hypothesis wins once its summed similarity beats the object's "stands still" null by EVID and the best
        hypothesis with another source by EVID / 2. Steps where both predict "no move" add nothing to the
        difference, so a ghost that stops after its path is not out-voted by the null, and strong evidence
        decides early."""
        hs = [h for h in self.hyps if h.obj == obj and h.n > 0]
        still = next((h for h in hs if h.source == "still"), None)
        cands = [h for h in hs if h.source != "still" and h.n >= MIN_OBS_E and h.mean >= ACCEPT]
        if still is None or not cands:
            return None
        best = max(cands, key=lambda h: h.total)
        rival = max((h.total for h in hs if h.source not in (best.source, "still")), default=-1e9)
        if best.total - still.total >= EVID and best.total - rival >= EVID / 2:
            return best.key()
        return None


def episode(rng, vsa, n1, n2, block_p=0.25):
    """Returns (finder, truth key, rewind_index)."""
    def step():
        return MOVES[rng.integers(1, 5)] if rng.random() > block_p else (0, 0)
    objs = ["ghost", "walker1", "walker2", "stationary", "follower"]
    f = GhostFinder(vsa, objs)
    run1 = []
    last_player = (0, 0)
    for _ in range(n1):
        m = step()
        if m != (0, 0):
            run1.append(m)
        f.observe(m, {})
        last_player = m
    f.rewind()
    k = 0
    for _ in range(n2):
        m = step()
        ghost = (0, 0)
        if m != (0, 0):
            ghost = run1[k] if k < len(run1) else (0, 0)
            k += 1
        obs = {"ghost": ghost, "walker1": step(), "walker2": step(), "stationary": (0, 0),
               "follower": last_player}
        f.observe(m, obs)
        last_player = m
    return f, {"ghost": ("ghost", "prev", "moves", 0), "follower": ("follower", "cur", "actions", 0)}


def main(episodes: int = 200):
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    vsa = VSA(D, seed=0)
    tally = {o: {"right": 0, "wrong": 0, "none": 0} for o in ("ghost", "follower")}
    false_decoys, when, wrong_keys = 0, [], []
    for _ in range(episodes):
        f, truth = episode(rng, vsa, n1=int(rng.integers(10, 40)), n2=40)
        for o, key in truth.items():
            d = f.decided.get(o)
            if d is None:
                tally[o]["none"] += 1
            elif d[0] == key:
                tally[o]["right"] += 1
                if o == "ghost":
                    when.append(d[1])
            else:
                tally[o]["wrong"] += 1
                wrong_keys.append(d[0])
        false_decoys += sum(o in f.decided for o in ("walker1", "walker2", "stationary"))
    res = {"episodes": episodes, "tally": tally, "decoys_falsely_explained": false_decoys,
           "ghost_actions_to_decide_median": float(np.median(when)) if when else None,
           "ghost_actions_to_decide_max": int(max(when)) if when else None,
           "wrong_examples": [list(map(str, k)) for k in wrong_keys[:5]],
           "rule": {"min_obs": MIN_OBS, "accept": ACCEPT, "margin": MARGIN, "D": D}}
    g, fo = tally["ghost"], tally["follower"]
    text = (f"stage 3 (synthetic, {episodes} episodes; decoys 2 random walkers + 1 stationary; plus a lag-1 follower): "
            f"ghost right {g['right']} / wrong {g['wrong']} / undecided {g['none']}; follower right {fo['right']} / "
            f"wrong {fo['wrong']} / undecided {fo['none']}; decoys falsely explained {false_decoys} of {3 * episodes}; "
            f"actions after the rewind until the ghost is found: median {res['ghost_actions_to_decide_median']}, "
            f"max {res['ghost_actions_to_decide_max']}")
    print(text)
    (OUT / "stage3_synth.json").write_text(json.dumps(res, indent=1))
    (OUT / "stage3_synth.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
