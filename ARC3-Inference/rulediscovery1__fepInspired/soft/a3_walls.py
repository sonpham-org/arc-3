# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage A3 of docs/plans/2026-09-24-soft-agent-roadmap.md: a SOFT wall map, learned online from boards,
#   compared with the explicit colour rule (rules.MoveRule's blocker / passable colour sets).
#   For every arrow press after the player's move for that arrow is known: the "ahead" region = the player's
#   cells shifted by that arrow's usual displacement, minus the player's own cells. Prediction is made BEFORE
#   the outcome is seen (prequential), then the outcome is stored.
#     - soft map (phasor VSA, hdc/vsa.py): two memory vectors, BLOCKED and FREE. Each outcome adds a query
#       vector q = P(y, x) + bind(P(y, x), C[colour]) + w * C[colour], with P a fractional-power place code (so
#       nearby places are similar) and C a random code per colour. Prediction: blocked if
#       sim(BLOCKED, q) > sim(FREE, q) + margin; with no evidence, "free" (optimistic).
#     - colour rule (the explicit baseline): a colour is a wall once it has blocked and never been passed,
#       passable once passed and never blocked, silent (predict "free") when it has done both.
#   The player and its parts come from perception: the most-moved type on arrow presses plus the parts that
#   common fate fuses with it (soft/a1_common_fate). Truth for scoring: A0's player_moved flag (engine).
#   Reports accuracy on all predicted presses and recall on the blocked ones, per game. Output results/soft/a3.*
#   24-Sep-2026 (HDC integration A/B, OpenMind 10:17 ET): run_game(guards=GUARDS) also scores the two guarded
#   combinations tried for the live agent (soft map first with abstention, or colour rule first with the soft map
#   filling its silence), at several abstention margins; main() output is unchanged.
# SRP/DRY check: Pass -- VSA from hdc/vsa.py, tracking/fusion from a1_common_fate; new: the ahead region,
#   the two memories and the scoring.
"""A3: soft place x colour wall map vs the colour rule."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .. import _distill as D
from ..hdc.vsa import VSA
from .a1_common_fate import CommonFate

OUT = Path(__file__).resolve().parent.parent / "results" / "soft"
ARROWS = ("ACTION1", "ACTION2", "ACTION3", "ACTION4")
W_COLOUR, MARGIN, SCALE = 0.5, 0.02, 0.35      # colour-only weight; decision margin; place-code frequency scale


class SoftWalls:
    def __init__(self, vsa: VSA):
        self.v = vsa
        self.B = np.zeros(vsa.D, complex)
        self.F = np.zeros(vsa.D, complex)
        self.C = {}

    def colour(self, c):
        if c not in self.C:
            self.C[c] = self.v.rand()
        return self.C[c]

    def query(self, cells):
        """cells: [(y, x, colour)] of the ahead region -> one query vector (their bundle)."""
        q = np.zeros(self.v.D, complex)
        for y, x, c in cells:
            p = self.v.power(self.v.Y, y * SCALE) * self.v.power(self.v.X, x * SCALE)
            q += p + p * self.colour(c) + W_COLOUR * self.colour(c)
        return q / max(len(cells), 1)

    def score(self, q) -> float:
        """sim(BLOCKED, q) - sim(FREE, q): > 0 leans blocked, < 0 leans free, 0 = no evidence."""
        return float(self.v.sim(self.B, q) - self.v.sim(self.F, q))

    def predict(self, q) -> bool:
        return bool(self.v.sim(self.B, q) > self.v.sim(self.F, q) + MARGIN)

    def store(self, q, blocked: bool):
        if blocked:
            self.B += q
        else:
            self.F += q


class ColourRule:
    def __init__(self):
        self.blk, self.pas = set(), set()

    def predict(self, colours) -> bool:
        return any(c in self.blk and c not in self.pas for c in colours)

    def verdict(self, colours):
        """True / False when the colours alone decide (a pure wall colour ahead / only passed colours), None when
        the colour rule has no clean evidence (an unseen or both-ways colour): where a soft map may speak."""
        if any(c in self.blk and c not in self.pas for c in colours):
            return True
        if all(c in self.pas and c not in self.blk for c in colours):
            return False
        return None

    def store(self, colours, blocked):
        (self.blk if blocked else self.pas).update(colours)


def guarded(kind: str, tau: float, score: float, col: "ColourRule", colours) -> bool:
    """The two guards tried for the live agent (HDC integration A/B, 24-Sep-2026).
    soft_first: the soft map answers when |score| >= tau, else the colour rule.
    colour_first: the colour rule answers when it has clean evidence, else the soft map when |score| >= tau,
    else "free" (the colour rule's own default)."""
    if kind == "soft_first":
        return score > 0 if abs(score) >= tau else col.predict(colours)
    v = col.verdict(colours)
    if v is not None:
        return v
    return score > 0 if abs(score) >= tau else False


GUARDS = [(k, t) for k in ("soft_first", "colour_first") for t in (0.02, 0.05, 0.1, 0.2)]


def run_game(path: Path, vsa: VSA, guards=()):
    tally = {"soft": Counter(), "colour": Counter()}
    tally.update({f"{k}@{t}": Counter() for k, t in guards})
    for line in path.read_text().splitlines():
        play = json.loads(line)
        cf = CommonFate()
        soft, col = SoftWalls(vsa), ColourRule()
        disp = defaultdict(Counter)                # arrow -> Counter of the player's displacement
        arrow_moves = Counter()
        prev_board = None
        steps = play["steps"]
        for i, s in enumerate(steps):
            board = s["board"]
            act = s["action"]
            if prev_board is not None and act in ARROWS and arrow_moves:
                ptype = arrow_moves.most_common(1)[0][0]
                find = cf.groups()
                ptracks = [t for t, (k, _) in cf.tr.tracks.items() if k == ptype]
                if ptracks and disp[act]:
                    group = [t for t in cf.tr.tracks if find(t) == find(ptracks[0])]
                    own = set()
                    for t in group:
                        own |= set(cf.cells.get(t, []))
                    (dy, dx), _ = disp[act].most_common(1)[0]
                    arr = np.asarray(prev_board)
                    ahead = []
                    for idx in own:
                        y, x = divmod(idx, 64)
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < 64 and 0 <= nx < 64 and (ny * 64 + nx) not in own:
                            ahead.append((ny, nx, int(arr[ny, nx])))
                    truth = s.get("player_moved")
                    if ahead and truth is not None:
                        blocked = not truth
                        q = soft.query(ahead)
                        colours = {c for _, _, c in ahead}
                        preds = [("soft", soft.predict(q)), ("colour", col.predict(colours))]
                        sc = soft.score(q)
                        preds += [(f"{k}@{t}", guarded(k, t, sc, col, colours)) for k, t in guards]
                        for name, pred in preds:
                            tally[name]["n"] += 1
                            tally[name]["ok"] += pred == blocked
                            tally[name]["blocked"] += blocked
                            tally[name]["blocked_hit"] += blocked and pred
                            tally[name]["false_wall"] += pred and not blocked
                        soft.store(q, blocked)
                        col.store(colours, blocked)
            moving = cf.update(board)
            if act in ARROWS:
                for t, d in moving.items():
                    arrow_moves[cf.tr.tracks[t][0]] += 1
                if arrow_moves:
                    ptype = arrow_moves.most_common(1)[0][0]
                    for t, d in moving.items():
                        if cf.tr.tracks[t][0] == ptype:
                            disp[act][d] += 1
            prev_board = board
    return tally


def main():
    vsa = VSA(4096, seed=0)
    res = {}
    for g in ("ls20", "g50t", "wa30", "sp80", "cn04"):
        p = OUT / f"a0_{g}.jsonl"
        if p.exists():
            t = run_game(p, vsa)
            res[g] = {k: {"accuracy": v["ok"] / max(v["n"], 1), "blocked_recall": v["blocked_hit"] / max(v["blocked"], 1),
                          "false_walls": v["false_wall"], "presses": v["n"], "blocked": v["blocked"]} for k, v in t.items()}
            print(g, json.dumps(res[g]), flush=True)
    lines = ["| game | presses (blocked) | soft map: accuracy / blocked recall / false walls | colour rule: accuracy / blocked recall / false walls |",
             "|---|---|---|---|"]
    for g, r in res.items():
        s, c = r["soft"], r["colour"]
        lines.append(f"| {g} | {s['presses']} ({s['blocked']}) | {s['accuracy']:.3f} / {s['blocked_recall']:.3f} / {s['false_walls']} | "
                     f"{c['accuracy']:.3f} / {c['blocked_recall']:.3f} / {c['false_walls']} |")
    text = "A3: predicting blocked moves before seeing them (prequential)\n" + "\n".join(lines)
    print(text)
    (OUT / "a3.json").write_text(json.dumps(res, indent=1))
    (OUT / "a3.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
