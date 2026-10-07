# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026 (debate three pick 3 later the same day)
# PURPOSE: Stage one, pick 2 of the second Warehouse debate (docs 2026-09-25-warehouse-expert-debate-2.md, Round 8;
#   OpenMind #arc-3 25-Sep-2026 02:38 ET "yes proceed"): the step budget as part of expected free energy.
#     - Gauges are found from the screen by the A4 finder (soft/a4_gauges.GaugeFinder: a colour's pixel count in a
#       changing region that moves one way in steady small ticks, widened to the colour's connected pieces, mirror
#       images dropped). Here it runs online on a RING of the last `ring` raw boards (not a preallocated play-long
#       array) and is refreshed every `refresh` steps; between refreshes the found (region, colour) is read directly.
#       Transitions that are a RESET, a level change or a scene change are left out of the tick statistics.
#     - Forecast per DRAINING gauge (a filling gauge's end is not known until it is reached, so it is not forecast):
#       rate = mean drain per action over the last `window` usable transitions (refill jumps left out, steps that cost
#       nothing kept), steps left s = value / rate. Value after a RESET: the value last seen right after a RESET on this
#       level (learned), else the value on the level's first board (RESET restarts the level). Only a gauge with at
#       least `min_ticks` drain ticks in the window is forecast; with none the budget term is exactly zero.
#     - What the end means: P(game over | the gauge runs out) is a Beta(a0, b0) belief, updated when the gauge ran out
#       (hit zero, or jumped back up from its last ticks without a RESET or level change) and the play went on
#       (a life lost and a refill, as on Locksmith) -> less weight, or ended in a game over.
#     - Risk of an action: P(over | end) * sigmoid((horizon - steps left after the action) / tau): steps left after a
#       RESET are the refill's, after any other action one fewer. The policy folds it into the pragmatic term with the
#       existing preference for a game over (goals.Preferences.c_game_over): G += w_prag * w_budget * risk * -c_game_over.
#       With the smallest forecast over the gauges; "urgent" when s <= horizon + margin (the agent then stops explorer
#       trips and archive replays and lets the policy choose, so RESET can be picked before the bar runs out).
#   Nothing here reads game internals: only the raw boards the agent receives and its own actions.
#   25-Sep-2026 debate three, pick 3 (docs 2026-09-25-warehouse-expert-debate-3.md, OpenMind #arc-3 05:47 ET; Claude Opus 5.5
#   (Bubba)), BudgetConfig.learn_end (AgentConfig.budget_learn), off by default = the stage-one model exactly:
#     - Lives reader (LivesReader): on the level's first board, a COUNTER beside a draining gauge = at least two identical
#       small items (same colour and shape, at most max_cells cells, one row, gaps at most max_gap) lying inside the
#       gauge's own rows (the rows the gauge colour occupies in its region, +-1), not the gauge's colour. Its value on a
#       board = how many such items are still there. "Spare lives" = the counter shows at least two. No counter = none.
#     - End belief as two hypotheses: FATAL (running out ends the play) vs LIFE (it costs one life; the play ends only on
#       the last). Log-odds of FATAL = logit(a0 / (a0 + b0)) [the stage-one prior mean, 0.8] + evidence: a run-out the
#       play survived (a refill without a RESET: "a refill with a life lost") x ln(eps / (1 - eps)); a game over at a
#       run-out x ln((1 - eps) / eps) when spare lives showed, else x ln((1 - eps) / 0.5). While a counter shows spare
#       lives, it counts as evidence for LIFE with likelihood ratio lr_counter (a stated prior: a counter of identical
#       items beside a bar is taken as lives; the agent never sees what the items are). P(game over | run out) = P(FATAL)
#       + P(LIFE) x (0 with spare lives, 1 on the last life, 1/2 with no counter).
#     - Information value (lives-gated): while spare lives show, an action that lets the gauge run out tests the belief;
#       its outcome is decisive under either hypothesis, so the expected information = H[P(FATAL)] nats, weighted by the
#       same closeness-to-the-end sigmoid as the risk (info()). RESET avoids the test (0). Without spare lives: 0.
#     - Plan-aware urgency: urgent(plan_left) is False while the current plan's remaining steps (an explorer trip or an
#       archive replay) fit in the forecast steps left, and when the net cost of running out (P(over) x -c_game_over -
#       information) is below the price of a RESET; otherwise as before.
# SRP/DRY check: Pass -- gauge finding is soft/a4_gauges.GaugeFinder's (its monotone test, widening and mirror rule reused
#   by subclassing; only the storage is a ring); the preference is goals.Preferences'. New: the ring storage, the drain
#   forecast, the refill value, the end belief and the risk; the lives reader, the two-hypothesis end belief, its
#   information value and plan-aware urgency (debate three).
"""Step budget from a learned gauge: steps left, refill on RESET, risk of running out."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .soft.a4_gauges import SCENE, GaugeFinder


@dataclass
class BudgetConfig:
    ring: int = 96               # raw boards kept for gauge finding
    refresh: int = 10            # steps between gauge searches
    window: int = 30             # usable transitions the drain rate is averaged over
    min_ticks: int = 6           # drain ticks in the window needed for a forecast
    horizon: float = 4.0         # risk is 1/2 when this many steps would be left after the action
    tau: float = 1.0             # softness of the horizon (steps)
    margin: float = 3.0          # urgent when steps left <= horizon + margin
    a0: float = 4.0              # Beta prior on "the gauge running out ends the game"
    b0: float = 1.0
    # debate three pick 3 (learn_end False = the stage-one model exactly)
    learn_end: bool = False      # learnable end belief + lives reader + information value + plan-aware urgency
    eps: float = 0.05            # outcome noise of the two end hypotheses
    lr_counter: float = 30.0     # likelihood ratio for LIFE while a counter beside the gauge shows spare lives
    w_info: float = 1.0          # weight of the test's information (nats) against the risk
    max_cells: int = 9           # a counter item is at most this many cells
    max_gap: int = 3             # ... and at most this far from the next item in its row


@dataclass
class Forecast:
    colour: int
    region: tuple
    value: int
    rate: float
    steps_left: float
    steps_after_reset: float
    p_over: float


class RingGaugeFinder(GaugeFinder):
    """GaugeFinder over the last `n` boards. `skip` flags a transition into a board that must not count as a tick
    (a RESET, a level change or a scene change)."""

    def __init__(self, n: int):                       # no super().__init__: no play-long preallocation
        self.ring: deque = deque(maxlen=n)
        self.flags: deque = deque(maxlen=n)           # per board: the transition INTO it is skipped
        self.first = None
        self.boards: list = []
        self.scene: list = []
        self.E = None
        self._arr = None

    def push(self, board, skip: bool) -> None:
        b = np.asarray(board, dtype=np.int16)
        if self.first is None:
            self.first = b
        if self.ring and b.shape == self.ring[-1].shape and not skip:
            skip = bool((b != self.ring[-1]).mean() > SCENE)
        self.ring.append(b)
        self.flags.append(bool(skip) or len(self.ring) == 1)

    def _prepare(self) -> None:
        """Materialise the ring for the inherited gauges() / _monotone(): boards, per-transition skip flags, and E =
        cells that changed on usable transitions."""
        self.boards = list(self.ring)
        self._arr = np.stack(self.boards)
        self.scene = list(self.flags)[1:]
        d = self._arr[1:] != self._arr[:-1]
        ok = ~np.asarray(self.scene, bool)
        self.E = d[ok].any(0) if ok.any() else np.zeros(self._arr.shape[1:], bool)

    def count(self, region, c):
        y0, y1, x0, x1 = region
        return (self._arr[:, y0:y1 + 1, x0:x1 + 1] == c).sum((1, 2)).astype(np.int64)

    def _widen(self, region, c, comp_mask):
        from scipy import ndimage
        from .soft.a4_gauges import EIGHT
        y0, y1, x0, x1 = region
        for b in (self.first, self.boards[-1]):
            if b.shape != comp_mask.shape:
                continue
            lab, _ = ndimage.label(b == c, structure=EIGHT)
            for i in np.unique(lab[comp_mask & (lab > 0)]):
                ys, xs = np.nonzero(lab == i)
                y0, y1, x0, x1 = min(y0, ys.min()), max(y1, ys.max()), min(x0, xs.min()), max(x1, xs.max())
        return int(y0), int(y1), int(x0), int(x1)

    def find(self) -> list:
        if len(self.ring) < 8:
            return []
        self._prepare()
        return self.gauges()


def read(board, region, colour) -> int:
    y0, y1, x0, x1 = region
    b = np.asarray(board)
    return int((b[y0:y1 + 1, x0:x1 + 1] == colour).sum())


def _h2(p: float) -> float:
    return 0.0 if p <= 0.0 or p >= 1.0 else -(p * math.log(p) + (1 - p) * math.log(1 - p))


class LivesReader:
    """Debate three pick 3: a counter of identical small items inside a draining gauge's rows (see the header)."""

    def __init__(self, max_cells: int = 9, max_gap: int = 3):
        self.max_cells, self.max_gap = max_cells, max_gap
        self.spec: Optional[tuple] = None             # (colour, shape bytes, shape dims, row y0, rows (a, b))

    @staticmethod
    def rows_of(board, region, colour) -> Optional[tuple]:
        y0, y1, x0, x1 = region
        b = np.asarray(board)
        ys = np.nonzero((b[y0:y1 + 1, x0:x1 + 1] == colour).any(1))[0]
        if not ys.size:
            return None
        return max(int(ys.min()) + y0 - 1, 0), min(int(ys.max()) + y0 + 1, b.shape[0] - 1)

    def _items(self, board, rows, colours):
        from scipy import ndimage
        from .soft.a4_gauges import EIGHT
        b = np.asarray(board)
        r0, r1 = rows
        out = []
        for c in colours:
            lab, k = ndimage.label(b == c, structure=EIGHT)
            for sl_i, sl in enumerate(ndimage.find_objects(lab), 1):
                if sl is None:
                    continue
                ys, xs = sl
                if ys.start < r0 or ys.stop - 1 > r1:
                    continue
                m = lab[sl] == sl_i
                n = int(m.sum())
                if n > self.max_cells:
                    continue
                out.append((int(c), m.tobytes(), m.shape, ys.start, xs.start, xs.stop - 1))
        return out

    def find(self, board, region, colour) -> None:
        """Identify the counter on a level's first board (or none)."""
        self.spec = None
        rows = self.rows_of(board, region, colour)
        if rows is None:
            return
        b = np.asarray(board)
        band = b[rows[0]:rows[1] + 1]
        vals, cnt = np.unique(band, return_counts=True)
        floor = int(vals[np.argmax(cnt)])
        cols = [int(v) for v in vals if int(v) not in (int(colour), floor)]
        groups: dict = {}
        for c, sh, dims, y0, xa, xb in self._items(board, rows, cols):
            groups.setdefault((c, sh, dims, y0), []).append((xa, xb))
        best = None
        for key, xs in groups.items():
            xs.sort()
            run, best_run = [xs[0]], [xs[0]]
            for a in xs[1:]:
                run = run + [a] if a[0] - run[-1][1] - 1 <= self.max_gap else [a]
                if len(run) > len(best_run):
                    best_run = run
            if len(best_run) >= 2 and (best is None or len(best_run) > best[1]):
                best = (key, len(best_run), (best_run[0][0], best_run[-1][1]))
        if best is not None:
            (c, sh, dims, y0), _, span = best
            self.spec = (c, sh, dims, y0, rows, span)

    def count(self, board) -> Optional[int]:
        """Items of the counter still on this board (None: no counter)."""
        if self.spec is None:
            return None
        c, sh, dims, y0, rows, (xa, xb) = self.spec
        n = 0
        for c2, sh2, dims2, yy, x0, x1 in self._items(board, rows, [c]):
            if sh2 == sh and dims2 == dims and yy == y0 and x0 >= xa - self.max_gap and x1 <= xb + self.max_gap:
                n += 1
        return n


class BudgetModel:
    def __init__(self, cfg: Optional[BudgetConfig] = None):
        self.cfg = cfg or BudgetConfig()
        self.finder = RingGaugeFinder(self.cfg.ring)
        self.gauges: list = []                        # [{"region", "colour", "sign"}] from the last search
        self.level_start = None                       # raw first board of the current level
        self.after_reset: dict = {}                   # colour -> value seen right after the last RESET (this level)
        self.ends: dict = {}                          # colour -> [runs-out survived, game overs]
        self.last_vals: dict = {}                     # colour -> value on the previous board
        self.last_rate: dict = {}
        self.t = 0
        self._fc = (-1, None)
        # bookkeeping (reported by game_sweep)
        self.found_at: Optional[int] = None
        self.urgent_steps = 0
        self.risky_steps = 0
        self.min_steps_left: Optional[float] = None
        self.survived_ends = 0
        # debate three pick 3 (cfg.learn_end)
        self.lives = LivesReader(self.cfg.max_cells, self.cfg.max_gap)
        self.lives_key = None                         # (gauge colour, region) the counter was looked for beside
        self.lives_now: Optional[int] = None          # items the counter shows on the current board
        self.over_spare: dict = {}                    # colour -> game overs at a run-out while spare lives showed
        self.c_over = 6.0                             # -goals.Preferences.c_game_over (the agent sets it)
        self.reset_cost = 0.5                         # policy.PolicyConfig.cost_reset (the agent sets it)
        self.lives_found = 0                          # levels on which a counter was found
        self.tests = 0                                # run-outs met while spare lives showed (the belief tested)
        self.plan_left = 0                            # remaining steps of the agent's current plan (the agent sets it)
        self.plan_fits = 0                            # near-end steps not urgent because the plan fits
        self.cheap_ends = 0                           # near-end steps not urgent because running out is cheap

    # -- per board
    def begin(self, grid) -> None:
        self.finder.push(grid, True)
        self.level_start = np.asarray(grid)

    def observe(self, tr, grid) -> None:
        self.t += 1
        new_level = bool(tr.level_completed) or (tr.post is not None and tr.pre is not None
                                                 and tr.post.level != tr.pre.level)
        self.finder.push(grid, bool(tr.reset) or new_level)
        if new_level:
            self.level_start = np.asarray(grid)
            self.after_reset = {}
            self.lives_key = None
        spare_before = self.spare()
        for g in self.gauges:
            if g["sign"] >= 0:
                continue
            c = g["colour"]
            v = read(grid, g["region"], c)
            prev = self.last_vals.get(c)
            if tr.reset:
                self.after_reset[c] = v
            elif not new_level and prev is not None:
                # ran out and the play went on: the bar jumped back up from its last ticks without a RESET (a life
                # lost and a refill); ran out and the play ended: a game over with the bar at its last ticks. An
                # empty bar by itself is neither (the game over may come a few steps later).
                low = prev <= 2 * (self.last_rate.get(c) or 1.0)
                if low and tr.game_over:
                    self.ends.setdefault(c, [0, 0])[1] += 1
                    if spare_before:
                        self.over_spare[c] = self.over_spare.get(c, 0) + 1
                elif low and v > prev:
                    self.ends.setdefault(c, [0, 0])[0] += 1
                    self.survived_ends += 1
                if low and (tr.game_over or v > prev) and spare_before:
                    self.tests += 1
            self.last_vals[c] = v
        if self.t % self.cfg.refresh == 0 or (self.found_at is None and self.t >= 8):
            found = self.finder.find()
            if found:
                self.gauges = [{"region": g["region"], "colour": g["colour"], "sign": g["sign"]} for g in found]
                if self.found_at is None:
                    self.found_at = self.t
        if self.cfg.learn_end:
            self._read_lives(grid)
        f = self.forecast()
        if f is not None:
            self.min_steps_left = f.steps_left if self.min_steps_left is None else min(self.min_steps_left,
                                                                                         f.steps_left)
            u = self.urgency(self.plan_left)
            self.urgent_steps += int(u == "urgent")
            self.plan_fits += int(u == "plan_fits")
            self.cheap_ends += int(u == "cheap")
            if self.risk_of(f, False) > 0.01:
                self.risky_steps += 1

    # -- debate three pick 3: lives and the end belief
    def _read_lives(self, grid) -> None:
        drain = [g for g in self.gauges if g["sign"] < 0]
        if not drain:
            self.lives_now = None
            return
        g = drain[0]
        key = (g["colour"], tuple(g["region"]))
        if key != self.lives_key and self.level_start is not None and self.level_start.shape == np.asarray(grid).shape:
            self.lives.find(self.level_start, g["region"], g["colour"])
            self.lives_key = key
            self.lives_found += int(self.lives.spec is not None)
        self.lives_now = self.lives.count(grid)

    def spare(self) -> bool:
        return self.cfg.learn_end and self.lives_now is not None and self.lives_now >= 2

    def p_fatal(self, c: int) -> float:
        cfg = self.cfg
        p0 = cfg.a0 / (cfg.a0 + cfg.b0)
        lo = math.log(p0 / (1 - p0))
        s_ok, s_over = self.ends.get(c, [0, 0])
        o_sp = self.over_spare.get(c, 0)
        lo += s_ok * math.log(cfg.eps / (1 - cfg.eps))
        lo += o_sp * math.log((1 - cfg.eps) / cfg.eps) + (s_over - o_sp) * math.log((1 - cfg.eps) / 0.5)
        if self.spare():
            lo -= math.log(cfg.lr_counter)
        return 1.0 / (1.0 + math.exp(-max(min(lo, 50.0), -50.0)))

    def p_over(self, c: int) -> float:
        pf = self.p_fatal(c)
        life = 0.0 if self.spare() else (1.0 if self.lives_now is not None else 0.5)
        return pf + (1 - pf) * life

    def _near(self, f: Forecast, reset: bool) -> float:
        left = f.steps_after_reset if reset else f.steps_left - 1.0
        z = (self.cfg.horizon - left) / self.cfg.tau
        return 1.0 / (1.0 + math.exp(-max(min(z, 50.0), -50.0)))

    def info(self, action) -> float:
        """Information (nats) about the end belief from letting the gauge run out after `action`: only while spare lives
        show (lives-gated), 0 for RESET (it avoids the test) and without a forecast."""
        if not self.cfg.learn_end or not self.spare() or action.name == "RESET":
            return 0.0
        f = self.forecast()
        if f is None:
            return 0.0
        return self.cfg.w_info * _h2(self.p_fatal(f.colour)) * self._near(f, False)

    # -- forecast
    def _gauge_forecast(self, g) -> Optional[Forecast]:
        fnd = self.finder
        if len(fnd.ring) < 3:
            return None
        arr = np.stack(list(fnd.ring))
        y0, y1, x0, x1 = g["region"]
        c = g["colour"]
        n = (arr[:, y0:y1 + 1, x0:x1 + 1] == c).sum((1, 2)).astype(np.int64)
        d = np.diff(n)
        ok = ~np.asarray(list(fnd.flags)[1:], bool)
        d = d[ok]
        d = d[d <= 0][-self.cfg.window:]                # refill jumps left out; steps that cost nothing kept
        if (d < 0).sum() < self.cfg.min_ticks:
            return None
        rate = float(-d.mean())
        if rate <= 0:
            return None
        self.last_rate[c] = rate
        value = int(n[-1])
        if c in self.after_reset:
            v_reset = self.after_reset[c]
        elif self.level_start is not None and self.level_start.shape == arr.shape[1:]:
            v_reset = read(self.level_start, g["region"], c)
        else:
            v_reset = value
        s_ok, s_over = self.ends.get(c, [0, 0])
        p = (self.cfg.a0 + s_over) / (self.cfg.a0 + self.cfg.b0 + s_ok + s_over)
        if self.cfg.learn_end:
            p = self.p_over(c)
        return Forecast(c, tuple(g["region"]), value, rate, value / rate, v_reset / rate, p)

    def forecast(self) -> Optional[Forecast]:
        """The draining gauge with the fewest steps left, or None (no gauge, or too few ticks to forecast)."""
        if self._fc[0] == self.t:
            return self._fc[1]
        best = None
        for g in self.gauges:
            if g["sign"] >= 0:
                continue
            f = self._gauge_forecast(g)
            if f is not None and (best is None or f.steps_left < best.steps_left):
                best = f
        self._fc = (self.t, best)
        return best

    def risk_of(self, f: Forecast, reset: bool) -> float:
        return f.p_over * self._near(f, reset)

    def risk(self, action) -> float:
        """Probability-weighted risk that the play ends by running out of budget soon after `action` (0 without a
        forecast)."""
        f = self.forecast()
        if f is None:
            return 0.0
        return self.risk_of(f, action.name == "RESET")

    def urgency(self, plan_left: int = 0) -> str:
        """'far' (no forecast / not near the end), 'urgent', or with learn_end (debate three) 'plan_fits' (the current
        plan's remaining steps fit in the steps left) / 'cheap' (running out costs less than a RESET, net of the test's
        information)."""
        f = self.forecast()
        if f is None or f.steps_left > self.cfg.horizon + self.cfg.margin:
            return "far"
        if not self.cfg.learn_end:
            return "urgent"
        if plan_left > 0 and plan_left <= f.steps_left - 1.0:
            return "plan_fits"
        net = f.p_over * self.c_over - self.cfg.w_info * (_h2(self.p_fatal(f.colour)) if self.spare() else 0.0)
        return "cheap" if net < self.reset_cost else "urgent"

    def urgent(self, plan_left: int = 0) -> bool:
        return self.urgency(plan_left) == "urgent"

    def return_len(self) -> Optional[int]:
        """Longest archive replay after a RESET that still leaves the horizon plus margin, or None (no forecast)."""
        f = self.forecast()
        if f is None:
            return None
        return max(int(f.steps_after_reset - self.cfg.horizon - self.cfg.margin), 0)
