"""Sample a count-first, deliberately distant glow-up pair."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import re
import secrets

from build_glowup_game_stats import build as build_stats, concept_id


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PATH = ROOT / "research" / "canonical-pool-v2.json"
STATE_PATH = ROOT / "research" / "glowup-loop-state-v1.json"
STATS_PATH = ROOT / "research" / "glowup-game-stats-v1.json"


def mechanic_vector(metadata: dict) -> Counter:
    mechanics = metadata.get("mechanics", {})
    vector: Counter = Counter()
    for phrase, weight in [
        (mechanics.get("primary", ""), 3),
        *((phrase, 2) for phrase in mechanics.get("secondary", [])),
    ]:
        for token in set(re.findall(r"[a-z0-9]+", phrase.lower())):
            vector[token] += weight
    return vector


def mechanic_distance(left: dict, right: dict) -> float:
    a, b = mechanic_vector(left), mechanic_vector(right)
    keys = set(a) | set(b)
    similarity = sum(min(a[key], b[key]) for key in keys) / max(
        1, sum(max(a[key], b[key]) for key in keys)
    )
    return 1.0 - similarity


def metadata_by_id() -> dict[str, dict]:
    result = {}
    for path in (ROOT / "research" / "games").glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        result[f"{item['game_id']}-{item['version']}"] = item
    return result


def pool_expansion_requirement(canonical: dict, active_ids: list[str], game_stats: list[dict]) -> dict | None:
    counts = {row['current_game_id']: row['glow_up_count'] for row in game_stats}
    if set(counts) != set(active_ids):
        raise ValueError('growth requires complete current per-game counts')
    if any(counts[game_id] < 1 for game_id in active_ids):
        return None
    added = math.ceil(canonical["canonical_count"] * canonical["growth_policy"]["growth_fraction"])
    return {
        "operation": "pool-expansion-required",
        "current_pool_size": canonical["canonical_count"],
        "games_to_add": added,
        "next_pool_size": canonical["canonical_count"] + added,
        "reason": "Every active concept has at least one completed glow-up; add one atomic genuinely-new seed generation before sampling.",
    }


def draw_pair(seed: int | None = None) -> dict:
    canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    active_ids = list(canonical["game_ids"])
    if len(active_ids) != canonical["canonical_count"] or len(active_ids) != len(set(active_ids)):
        raise ValueError("canonical count and unique active IDs disagree")
    unfinished = [row for row in state.get("history", []) if row.get("status") != "completed"]
    if unfinished:
        raise RuntimeError(
            f"cycle {unfinished[-1].get('cycle')} is still {unfinished[-1].get('status')}; "
            "overlapping passes are forbidden"
        )

    pending_batch = state.get('pending_qc_batch')
    if pending_batch:
        batch = json.loads((ROOT / pending_batch).read_text(encoding='utf-8'))
        if batch.get('status') != 'completed':
            return {'operation': 'qc-batch-required', 'batch': pending_batch,
                    'reason': 'Complete, qualify, activate and commit the requested QC maintenance batch before drawing another pair.'}

    stats = build_stats()
    expansion = pool_expansion_requirement(canonical, active_ids, stats['games'])
    if expansion:
        return expansion

    stat_by_id = {row["current_game_id"]: row for row in stats["games"]}
    metadata = metadata_by_id()
    recent_concepts = {
        concept_id(game_id)
        for game_id in state.get("recent_game_ids", [])[-canonical["selection_policy"]["recent_exclusion_size"] :]
    }
    min_count = min(stat_by_id[game_id]["glow_up_count"] for game_id in active_ids)
    minimum_tier = [
        game_id for game_id in active_ids if stat_by_id[game_id]["glow_up_count"] == min_count
    ]
    first_pool = [game_id for game_id in minimum_tier if concept_id(game_id) not in recent_concepts]
    if not first_pool:
        first_pool = minimum_tier
    rng = random.Random(seed) if seed is not None else secrets.SystemRandom()
    first = rng.choice(first_pool)

    same_tier = [game_id for game_id in minimum_tier if game_id != first]
    second_tier_count = min_count
    if not same_tier:
        higher_counts = sorted(
            {
                stat_by_id[game_id]["glow_up_count"]
                for game_id in active_ids
                if game_id != first and stat_by_id[game_id]["glow_up_count"] > min_count
            }
        )
        if not higher_counts:
            raise RuntimeError("the canonical pool must contain at least two games")
        second_tier_count = higher_counts[0]
        same_tier = [
            game_id
            for game_id in active_ids
            if game_id != first and stat_by_id[game_id]["glow_up_count"] == second_tier_count
        ]
    candidate_pool = [
        game_id for game_id in same_tier if concept_id(game_id) not in recent_concepts
    ] or same_tier
    ranked = sorted(
        (
            {
                "game_id": game_id,
                "mechanic_distance": round(mechanic_distance(metadata[first], metadata[game_id]), 6),
            }
            for game_id in candidate_pool
        ),
        key=lambda row: (-row["mechanic_distance"], row["game_id"]),
    )
    farthest_size = max(1, math.ceil(len(ranked) * 0.20))
    farthest = ranked[:farthest_size]
    second = rng.choice([row["game_id"] for row in farthest])
    return {
        "cycle": int(state.get("cycle", 0)) + 1,
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "game_ids": [first, second],
        "selection": "minimum-glow-count-then-random-farthest-20-percent",
        "selection_evidence": {
            "minimum_glow_up_count": min_count,
            "minimum_tier_size": len(minimum_tier),
            "first_candidate_pool_size": len(first_pool),
            "second_glow_up_count": second_tier_count,
            "second_candidate_pool_size": len(candidate_pool),
            "farthest_20_percent_size": farthest_size,
            "farthest_candidates": farthest,
            "recent_concepts_excluded_where_possible": sorted(recent_concepts),
        },
        "target_roles": {first: "glow-up-target", second: "glow-up-target"},
        "status": "selected",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, help="deterministic test/debug seed")
    parser.add_argument("--record", action="store_true", help="append the draw to loop state")
    args = parser.parse_args()
    result = draw_pair(args.seed)
    if args.record:
        if result.get("operation"):
            raise SystemExit(result['reason'] + '; no pair was recorded')
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        state["cycle"] = result["cycle"]
        state["recent_game_ids"] = (
            state.get("recent_game_ids", []) + result["game_ids"]
        )[-10:]
        state.setdefault("history", []).append(result)
        STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        stats = build_stats()
        STATS_PATH.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
