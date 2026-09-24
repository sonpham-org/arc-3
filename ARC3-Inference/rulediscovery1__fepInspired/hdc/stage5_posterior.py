# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 5 of docs/plans/2026-09-24-hdc-ghost-roadmap.md (OpenMind, #arc-3, 01:15 ET: "continue with
#   the roadmap: 5, 6, 7"). Does the tape rule earn its place in a Bayesian posterior against a counts model,
#   scored the way the rule-discovery agent scores rules (prequential log likelihood minus a description-
#   length price)? Predicted quantity: the true ghost's move on every action with a ghost on the board (labels
#   from stage 0), on the 20 Ghost Twin plays.
#     - counts: a chained back-off count model of the ghost's move, learned online within the play (context
#       (action, ghost's previous move) -> (action) -> all), the same idea as round seven's chain back-off.
#     - tape rule: when the stage-4 filter has decided on a copy hypothesis, it predicts the tape's move with
#       probability 1 - eps (eps = 0.05) and spreads eps by the counts; before a decision it equals counts.
#     - posterior: two hypotheses, prior weight exp(-PRICE) on the tape rule (PRICE = ln of the hypothesis grid
#       it was chosen from), updated by each step's predictive probability (Bayesian model averaging, as in
#       beliefs.BeliefState).
#   Reports nats per ghost step for counts alone vs the posterior mixture, on all ghost steps and on the steps
#   where the tape rule had a decided prediction, plus the tape rule's final posterior weight.
#   NOT done here: wiring the tape rule into rulediscovery1__fepInspired's own RuleSet / offline_eval (its rule
#   contexts carry no run history); this measures the same contest in isolation.
#   Output results/hdc/stage5_posterior.json + .md.
# SRP/DRY check: Pass -- the filter and perception are stage4_real.run_play (via its on_ghost_step hook); new
#   here: the counts model, the two-hypothesis posterior and the nats bookkeeping.
"""Stage 5: tape rule vs counts in a Bayesian posterior (nats on ghost moves)."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from ..verify_env import load_rows
from .stage2_tape import MOVES
from .stage4_real import board_of, run_play
from .vsa import VSA

OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"
EPS = 0.05
BETA = 2.0
PRICE = math.log(20 * 4 * 2 * 4)        # objects x sources x clocks x lags the rule was picked from


class ChainCounts:
    def __init__(self):
        self.c = defaultdict(Counter)
        self.prev = (0, 0)

    def _level(self, ctx, back):
        n = self.c[ctx]
        tot = sum(n.values())
        return {m: (n[m] + BETA * back[m]) / (tot + BETA) for m in MOVES}

    def dist(self, action):
        p0 = {m: 1.0 / len(MOVES) for m in MOVES}
        p1 = self._level(("all",), p0)
        p2 = self._level(("a", action), p1)
        return self._level(("ap", action, self.prev), p2)

    def update(self, action, move):
        for ctx in (("all",), ("a", action), ("ap", action, self.prev)):
            self.c[ctx][move] += 1
        self.prev = move


def main(n: int = 20):
    vsa = VSA(4096, seed=0)
    plays = json.loads((OUT / "stage0_groundtruth.json").read_text())[:n]
    tot = {"counts": 0.0, "mix": 0.0, "n": 0, "counts_dec": 0.0, "mix_dec": 0.0, "n_dec": 0}
    weights = []
    for play in plays:
        rows_all = load_rows(Path(play["trace"]))
        rows = [r for r in rows_all if r.get("type") == "action"]
        init = next((r for r in rows_all if r.get("type") == "initial"), None)
        if not rows or init is None:
            continue
        cm = ChainCounts()
        logw = {"counts": 0.0, "tape": -PRICE}

        def on_step(action, true, pred):
            true = tuple(true)
            if true not in MOVES:
                return                                   # a ghost jump (rewind animation end): not a move
            pc = cm.dist(action)
            pt = pc if pred is None else {m: (1 - EPS) * (m == tuple(pred)) + EPS * pc[m] for m in MOVES}
            z = max(logw.values())
            w = {k: math.exp(v - z) for k, v in logw.items()}
            s = sum(w.values())
            p_mix = (w["counts"] * pc[true] + w["tape"] * pt[true]) / s
            tot["counts"] += -math.log(pc[true])
            tot["mix"] += -math.log(p_mix)
            tot["n"] += 1
            if pred is not None:
                tot["counts_dec"] += -math.log(pc[true])
                tot["mix_dec"] += -math.log(p_mix)
                tot["n_dec"] += 1
            logw["counts"] += math.log(pc[true])
            logw["tape"] += math.log(pt[true])
            cm.update(action, true)

        run_play(play, rows, vsa, board_of(init), on_ghost_step=on_step)
        z = max(logw.values())
        weights.append(math.exp(logw["tape"] - z) / sum(math.exp(v - z) for v in logw.values()))
    res = {"ghost_steps": tot["n"], "counts_nats_per_step": tot["counts"] / tot["n"],
           "mixture_nats_per_step": tot["mix"] / tot["n"],
           "decided_steps": tot["n_dec"],
           "counts_nats_on_decided": tot["counts_dec"] / max(tot["n_dec"], 1),
           "mixture_nats_on_decided": tot["mix_dec"] / max(tot["n_dec"], 1),
           "tape_final_weight_per_play": [round(w, 3) for w in weights], "price_nats": PRICE, "eps": EPS}
    text = (f"stage 5 (20 Ghost Twin plays, {tot['n']} ghost steps): counts alone {res['counts_nats_per_step']:.3f} "
            f"nats/step, posterior with the tape rule {res['mixture_nats_per_step']:.3f}; on the {tot['n_dec']} steps "
            f"where the tape rule had decided: counts {res['counts_nats_on_decided']:.3f} vs posterior "
            f"{res['mixture_nats_on_decided']:.3f}; tape rule's final posterior weight > 0.5 in "
            f"{sum(w > 0.5 for w in weights)} of {len(weights)} plays (price {PRICE:.1f} nats)")
    print(text)
    (OUT / "stage5_posterior.json").write_text(json.dumps(res, indent=1))
    (OUT / "stage5_posterior.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
