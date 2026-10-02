"""Rewards, group statistics and training picks for RL on ARC-3 (plan: docs/plans/2026-10-01-rl-on-burst-games.md).

Pure functions, no harness or cloud imports, shared by the try runner (VM), the controller and the trainer.

- The reward of one try is the scorer's own per-level score (arc3_minute_score_observer.game_score): a cleared
  level scores min(1.15, (human / actions)^2), where actions counts the level's actions before the fork moment
  plus the try's own. Not cleared, or over its token cap = 0. So RL optimizes the Kaggle metric, efficiency
  included, and slow thinking loses the way the clock makes it lose.
- A group is the tries from one moment under one policy and one kind (plain or hint). A group whose rewards are
  all equal teaches nothing and is skipped; the share of skipped groups is a round's health number.
- Expert iteration (rounds 0-3) trains on the best try of each group that beat the group mean. GRPO (later) gives
  every try its standardized advantage.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

LEVEL_CAP = 1.15          # the scorer caps a level at 115 points
EPS = 1e-6


def level_score(human_actions: int, used_actions: int) -> float:
    """One cleared level, on the scorer's scale divided by 100: min(1.15, (human / used)^2)."""
    if used_actions <= 0 or human_actions <= 0:
        return 0.0
    return min(LEVEL_CAP, (human_actions / used_actions) ** 2)


def try_reward(*, cleared: bool, human_actions: int, prefix_level_actions: int, try_actions: int,
               over_token_cap: bool = False) -> float:
    """Reward of one try from a moment inside a level.

    prefix_level_actions: actions already spent on this level before the moment (they count, as in the scorer).
    try_actions: actions the try spent until the level cleared.
    """
    if not cleared or over_token_cap:
        return 0.0
    return level_score(human_actions, prefix_level_actions + try_actions)


def game_score(levels_completed: int, actions: Sequence[int], baseline: Sequence[int]) -> float:
    """Same number as arc3_minute_score_observer.game_score (0-100), rebuilt from level_score (tested equal)."""
    total = 0.0
    weights = 0
    done = 0
    for i, base in enumerate(baseline):
        w = i + 1
        weights += w
        used = actions[i] if i < len(actions) else 0
        if i < levels_completed and used > 0:
            total += 100.0 * level_score(base, used) * w
            done += w
    if not weights:
        return 0.0
    return min(total / weights, done / weights * 100.0)


def level_weight(level: int, n_levels: int) -> float:
    """Share of a game's score that level `level` (1-based) carries: k / (1 + 2 + ... + N)."""
    return level / (n_levels * (n_levels + 1) / 2)


# ------------------------------------------------------------------------------------------------ groups
def group_stats(rewards: Sequence[float]) -> dict[str, Any]:
    n = len(rewards)
    if not n:
        return {"n": 0, "mean": 0.0, "sd": 0.0, "cleared": 0, "mixed": False}
    mean = sum(rewards) / n
    sd = math.sqrt(sum((r - mean) ** 2 for r in rewards) / n)
    return {"n": n, "mean": mean, "sd": sd, "cleared": sum(r > 0 for r in rewards), "mixed": sd > EPS}


def extra_tries(rewards: Sequence[float], *, won_before: bool, base: int = 8, extra: int = 8) -> int:
    """Tries to add to a group (plan §0c item 1). Play `base` up front; if they all agree on a moment that has been
    won before (by the reference run or an earlier try), play `extra` more to break the tie. A mixed group or a
    moment never won gets none. (The old "4, then 4 more if mixed" rule dropped 41% of 20%-clear moments.)"""
    if len(rewards) < base or group_stats(rewards)["mixed"] or not won_before:
        return 0
    return extra if len(rewards) < base + extra else 0


def grpo_advantages(rewards: Sequence[float], *, scale: str = "std") -> list[float]:
    """Group-relative advantages. scale='std' is GRPO; 'none' keeps the raw centred reward (Dr. GRPO).
    An unmixed group gets all zeros (it is skipped by the trainer, never trained as zero)."""
    st = group_stats(rewards)
    if not st["mixed"]:
        return [0.0] * len(rewards)
    if scale == "std":
        return [(r - st["mean"]) / (st["sd"] + EPS) for r in rewards]
    if scale == "none":
        return [r - st["mean"] for r in rewards]
    raise ValueError(f"unknown scale {scale!r}")


def expert_pick(tries: Sequence[dict], *, k: int = 1) -> list[dict]:
    """Expert iteration: the best k tries of a group that cleared AND beat the group mean.

    Each try is a dict with 'reward' and optionally 'tokens' (tie-break: fewer tokens) and 'excluded'
    (a human or judge flagged the win as luck). Returns copies with 'weight' = advantage over the mean.
    """
    live = [t for t in tries if not t.get("excluded")]
    st = group_stats([t["reward"] for t in tries])
    if not st["mixed"]:
        return []
    good = [t for t in live if t["reward"] > 0 and t["reward"] > st["mean"] + EPS]
    good.sort(key=lambda t: (-t["reward"], t.get("tokens") or 0))
    return [dict(t, weight=t["reward"] - st["mean"]) for t in good[:k]]


def round_health(groups: Iterable[Sequence[float]]) -> dict[str, Any]:
    """Share of mixed groups and the clear rate over a round's groups (the between-round check)."""
    groups = [list(g) for g in groups]
    tries = [r for g in groups for r in g]
    return {
        "groups": len(groups),
        "mixed_share": (sum(group_stats(g)["mixed"] for g in groups) / len(groups)) if groups else 0.0,
        "clear_rate": (sum(r > 0 for r in tries) / len(tries)) if tries else 0.0,
        "mean_reward": (sum(tries) / len(tries)) if tries else 0.0,
    }
