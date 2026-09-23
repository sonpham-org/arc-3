"""Author: Codex (GPT-6)
Date: 2026-09-14
PURPOSE: Build per-concept glow-up statistics with stable public names while
preserving canonical concept IDs and completed-history accounting.
SRP/DRY check: Pass — names come from the shared immutable identity registry.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from research_game_ids import public_id, public_version_id


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PATH = ROOT / "research" / "canonical-pool-v2.json"
STATE_PATH = ROOT / "research" / "glowup-loop-state-v1.json"
GROWTH_PATH = ROOT / "research" / "pool-growth-seeds-v1.json"
OUTPUT_PATH = ROOT / "research" / "glowup-game-stats-v1.json"


def concept_id(game_id: str) -> str:
    return game_id.rsplit("-v", 1)[0]


def metadata_by_id() -> dict[str, dict]:
    result = {}
    for path in (ROOT / "research" / "games").glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        result[f"{item['game_id']}-{item['version']}"] = item
    return result


def build() -> dict:
    canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    growth = json.loads(GROWTH_PATH.read_text(encoding="utf-8"))
    metadata = metadata_by_id()
    active_ids = list(canonical["game_ids"])
    if len(active_ids) != canonical["canonical_count"] or len(active_ids) != len(set(active_ids)):
        raise ValueError("canonical count and unique active IDs disagree")

    completed = defaultdict(int)
    attempts = defaultdict(int)
    foil_uses = defaultdict(int)
    last_sampled: dict[str, str] = {}
    last_glowed: dict[str, str] = {}
    qc_revisions = defaultdict(int)
    for maintenance in state.get('maintenance_history', []):
        if maintenance.get('status') == 'completed' and maintenance.get('type') == 'quality-control':
            for game_id in maintenance.get('result_game_ids', []):
                qc_revisions[concept_id(game_id)] += 1
    for row in state.get("history", []):
        sampled_at = row.get("sampled_at")
        roles = row.get("target_roles", {})
        for game_id in row.get("game_ids", []):
            concept = concept_id(game_id)
            attempts[concept] += 1
            if sampled_at:
                last_sampled[concept] = sampled_at
            if roles.get(game_id) == "foil":
                foil_uses[concept] += 1
        if row.get("status") != "completed":
            continue
        completed_at = row.get("completed_at")
        for game_id in row.get("result_game_ids", []):
            concept = concept_id(game_id)
            completed[concept] += 1
            if completed_at:
                last_glowed[concept] = completed_at

    seed_by_concept = {
        item["concept_id"]: item for item in growth.get("seed_concepts", [])
    }
    games = []
    for active_id in active_ids:
        if active_id not in metadata:
            raise ValueError(f"missing metadata for active game {active_id}")
        item = metadata[active_id]
        concept = concept_id(active_id)
        seed = seed_by_concept.get(concept, {})
        mechanics = item.get("mechanics", {})
        initial = metadata.get(f"{concept}-v1", {}).get("mechanics", {})
        initial_mechanics = {
            initial.get("primary"), *initial.get("secondary", [])
        } - {None}
        current_mechanics = {
            mechanics.get("primary"), *mechanics.get("secondary", [])
        } - {None}
        games.append(
            {
                "concept_id": concept,
                "public_id": public_id(concept),
                "public_version_id": public_version_id(concept, item["version"]),
                "current_game_id": active_id,
                "current_version": item["version"],
                "origin": seed.get("origin", item.get("author_partition", "unknown")),
                "glow_up_count": completed[concept],
                "qc_revision_count": qc_revisions[concept],
                "attempt_count": attempts[concept],
                "times_used_as_foil": foil_uses[concept],
                "last_sampled_at": last_sampled.get(concept),
                "last_glowed_at": last_glowed.get(concept),
                "primary_mechanic": mechanics.get("primary"),
                "secondary_mechanics": mechanics.get("secondary", []),
                "mechanics_added_by_glowup": sorted(current_mechanics - initial_mechanics),
            }
        )

    counts = [game["glow_up_count"] for game in games]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_manifest": CANONICAL_PATH.relative_to(ROOT).as_posix(),
        "loop_state": STATE_PATH.relative_to(ROOT).as_posix(),
        "summary": {
            "active_games": len(games),
            "completed_glowups": sum(counts),
            "completed_qc_revisions": sum(qc_revisions[concept_id(game_id)] for game_id in active_ids),
            "minimum_glow_up_count": min(counts, default=0),
            "maximum_glow_up_count": max(counts, default=0),
            "zero_glow_up_games": sum(count == 0 for count in counts),
            "active_v1_games": sum(game_id.endswith("-v1") for game_id in active_ids),
        },
        "games": games,
    }


def main() -> None:
    result = build()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
