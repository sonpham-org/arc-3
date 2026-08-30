#!/usr/bin/env python3
"""Mine a diverse mechanic-review queue from every Flashpoint Flash record.

This is a retrieval stage, not an automatic novelty judge. It enumerates the complete
metadata snapshot, scores descriptions for mechanic-bearing language and rare curator
tags, applies source/developer/template diversity caps, and reports the nearest existing
ARC3 concept for human review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTERNAL = ROOT.parent / "autoresearch-arena-source" / "arc3" / "game-ideas" / "ledger.jsonl"
TOKEN_RE = re.compile(r"[a-z0-9]+")
YEAR_RE = re.compile(r"^(19\d{2}|20\d{2})")

STOPWORDS = {
    "about", "after", "again", "against", "also", "another", "around", "because",
    "been", "before", "being", "between", "both", "button", "click", "control",
    "each", "from", "game", "games", "have", "help", "into", "level", "levels",
    "more", "mouse", "must", "only", "other", "play", "player", "press", "screen",
    "than", "that", "their", "there", "these", "they", "this", "through", "using",
    "when", "where", "which", "while", "will", "with", "your", "you",
}

BROAD_TAGS = {
    "Action", "Adventure", "Arcade", "Creative", "Educational", "Other", "Puzzle",
    "Simulation", "Sports", "Strategy", "Toy", "Score-Attack", "Time-Attack",
    "Mouse-only", "Auto-zipped", "Fixed Screen", "Side View", "Top-Down", "Pixel",
    "Cartoon", "Experimental", "Demonstration", "Advertisement", "Promotional",
}

# Flashpoint is a web-media archive, not only a game archive.  These genres are
# useful historical material, but they swamp a game-mechanic queue when rarity is
# rewarded.  We retain a small, explicitly labelled cross-media sample instead.
CROSSMEDIA_TAGS = {
    "Calculator", "Clock", "Comic", "Computing Device", "Demonstration", "ePub",
    "Loading Screen", "Microsite", "Music Video", "Panorama", "Photo Gallery",
    "Print Studio", "Public Service Announcement", "Slideshow", "Soundboard",
    "Tutorial", "Utility", "Virtual Tour", "Walk Cycle", "X-Ray Viewer",
}

# These curator genres describe interaction structures rather than subject matter,
# visual style, sport, or a conventional clone family.  They are allowed to act as
# retrieval signals even when a short archive description lacks our phrase lexicon.
MECHANIC_SIGNAL_TAGS = {
    "Assemblage", "Auditory Illusion", "Augmented Reality", "Balancing", "Bomb Maze",
    "Cellular Automata", "Choose Your Own Adventure", "Claw Game", "Codebreaker",
    "Community Content", "Drawing", "Experimental", "Food Chain", "Fractal",
    "Game Creation Tool", "Grid Toggle", "Interactive Fiction", "Klotski",
    "Lane-Based Strategy", "Lemmings", "Level Editor", "Loop", "Luck Roller",
    "Mixing", "Node-Based Strategy", "Object Creator", "Optical Illusion",
    "Physics", "Pipe Connector", "Ragdoll", "Sandbox", "Scavenger Hunt",
    "Sequence Dropper", "Sequential", "Shell Game", "Sliding", "Sokoban", "Sorting",
    "Stealth", "Tile Traveler", "Timing", "Turn-Based", "Twisty Puzzle",
    "Walking Simulator",
}

CORE_MECHANIC_TAGS = {
    "Assemblage", "Auditory Illusion", "Augmented Reality", "Balancing", "Bomb Maze",
    "Cellular Automata", "Claw Game", "Codebreaker", "Food Chain", "Fractal",
    "Game Creation Tool", "Grid Toggle", "Klotski", "Lane-Based Strategy", "Lemmings",
    "Luck Roller", "Mixing", "Node-Based Strategy", "Optical Illusion", "Pipe Connector",
    "Sequence Dropper", "Sequential", "Shell Game", "Sorting", "Tile Traveler",
    "Twisty Puzzle",
}

BOILERPLATE_RE = re.compile(
    r"(?:https?://|www\.)\S+|<[^>]+>|(?:version|update|changelog)\s*[:\d][^.!?]*(?:[.!?]|$)",
    re.IGNORECASE,
)

EXCLUDED_TAGS = {
    "Adult", "Sexual Content", "Nudity", "Porn", "Fetish", "Gore", "Strong Violence",
    "Suicide", "Bestiality", "Vore", "Masturbation", "Vaginal", "Anal", "Fellatio",
    "Expansion", "Inflation Fetish", "Weight Gain Fetish",
}

TEMPLATE_PHRASES = {
    "another point and click escape game": 7.0,
    "find all the hidden objects": 6.0,
    "dress up": 4.5,
    "makeover": 4.0,
    "jigsaw puzzle": 4.0,
    "spot the difference": 4.0,
    "parking game": 3.5,
    "cooking game": 3.0,
    "shoot all": 2.0,
}

MECHANIC_PHRASES = {
    "state-transformation": (
        "change form", "changes color", "copy yourself", "duplicates itself",
        "grow and shrink", "merge together", "mirror image", "rotate the world",
        "split yourself", "swap places", "switch forms",
    ),
    "time-and-order": (
        "after a delay", "copies your moves", "past self", "previous self",
        "record your moves", "record your path", "replay your moves", "reverse time",
        "rewind time", "simultaneous control", "synchronize", "time loop",
        "turn back time",
    ),
    "construction": (
        "assemble", "build a bridge", "build a machine", "circuit", "connect the",
        "draw a line", "draw a path", "hinge", "place objects", "program the",
        "route the", "wire the",
    ),
    "indirect-physics": (
        "balance", "bounce", "chain reaction", "electric field", "flow", "fluid",
        "friction", "gravity", "inflate", "light beam", "magnet", "momentum",
        "reflect", "signal", "weight changes",
    ),
    "information": (
        "blind", "cannot see", "decode the", "discover the rule", "hidden rule",
        "infer the", "invisible", "limited vision", "sound only", "your shadow",
    ),
    "topology-and-view": (
        "camera angle", "different perspective", "inside out", "move the screen",
        "multiple screens", "rotate the room", "wrap around",
    ),
    "distributed-agency": (
        "control both", "cooperate", "different abilities", "follow each other",
        "multiple characters", "repel each other", "several characters", "teamwork",
    ),
    "system-dynamics": (
        "cellular automata", "ecosystem", "infect all", "population grows",
        "resource management", "spreads to", "supply chain", "trade with",
    ),
    "goal-revision": (
        "avoid the goal", "cannot touch", "goal is to die", "lose to win", "must not",
        "protect the enemy", "sacrifice", "things are not what", "wrong way",
    ),
    "constraint-and-interface": (
        "one button", "only move when", "you can only move", "you cannot move",
        "without moving", "without touching", "two buttons",
    ),
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(TOKEN_RE.findall(value.lower()))


def clean_description(value: str) -> tuple[str, int]:
    """Remove markup/URLs/update notes that create false mechanic matches."""
    decoded = html.unescape(value or "")
    noise_matches = len(BOILERPLATE_RE.findall(decoded))
    cleaned = BOILERPLATE_RE.sub(" ", decoded)
    return re.sub(r"\s+", " ", cleaned).strip(), noise_matches


def contains_phrase(normalized: str, phrase: str) -> bool:
    """Match whole normalized phrases, not `role` inside `controller`."""
    return f" {normalize(phrase)} " in f" {normalized} "


def features(value: str) -> set[str]:
    tokens = [
        token for token in normalize(value).split()
        if token not in STOPWORDS and len(token) > 2
    ]
    result = set(tokens)
    result.update(f"{a}::{b}" for a, b in zip(tokens, tokens[1:]))
    return result


def primary_domain(raw_source: str) -> str:
    value = raw_source.strip().split(";")[0].strip()
    if not value:
        return "unknown"
    value = re.sub(r"\s+\(via Wayback Machine\)$", "", value)
    if "://" not in value:
        value = "https://" + value.lstrip("/")
    host = urlparse(value).hostname or "unknown"
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_existing(external: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with (ROOT / "research" / "gpt-ideas-v1.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append({"id": row["id"], "title": row["internal_title"], "text": " ".join(row.values())})
    with (ROOT / "research" / "anthropic-build-ideas-v1.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append({"id": row["id"], "title": row["internal_title"], "text": " ".join(row.values())})
    with external.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append({
                "id": row["id"],
                "title": row["title"],
                "text": " ".join(str(row.get(key, "")) for key in (
                    "title", "mechanic_axis", "secondary_axes", "pitch", "mechanics",
                    "ai_failure_mode", "novelty_vs", "flash_inspiration",
                )),
            })
    lineage_path = ROOT / "research" / "flash-mechanic-lineages-v1.tsv"
    with lineage_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append({
                "id": row["id"],
                "title": row["source_games"],
                "text": " ".join(row.values()),
            })
    return rows


def nearest_existing(candidates: list[dict], existing: list[dict[str, str]]) -> None:
    existing_features = [features(row["text"]) for row in existing]
    inverted: dict[str, set[int]] = defaultdict(set)
    for index, terms in enumerate(existing_features):
        for term in terms:
            inverted[term].add(index)

    for candidate in candidates:
        terms = features(" ".join((candidate["title"], candidate["description"], candidate["tags"])))
        possible: set[int] = set()
        for term in terms:
            possible.update(inverted.get(term, ()))
        best_index = -1
        best_score = 0.0
        for index in possible:
            other = existing_features[index]
            score = len(terms & other) / math.sqrt(max(1, len(terms) * len(other)))
            if score > best_score:
                best_index = index
                best_score = score
        if best_index >= 0:
            candidate["nearest_existing_id"] = existing[best_index]["id"]
            candidate["nearest_existing_title"] = existing[best_index]["title"]
            candidate["nearest_existing_similarity"] = round(best_score, 4)
        else:
            candidate["nearest_existing_id"] = ""
            candidate["nearest_existing_title"] = ""
            candidate["nearest_existing_similarity"] = 0.0


def diverse_review_order(rows: list[dict]) -> list[dict]:
    """Round-robin interaction strata so rank is useful for human review."""
    ordered: list[dict] = []
    for tier in ("gameplay", "crossmedia"):
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            if row["content_tier"] != tier:
                continue
            bucket = (
                (row["core_mechanic_tags"].split("; ")[0] if row["core_mechanic_tags"] else "")
                or (row["mechanic_families"].split("; ")[0] if row["mechanic_families"] else "")
                or "secondary-mechanic-tag"
            )
            row["review_bucket"] = bucket
            groups[bucket].append(row)
        for group in groups.values():
            group.sort(key=lambda row: (
                -row["retrieval_score"], row["nearest_existing_similarity"],
                row["title"].lower(),
            ))
        bucket_order = sorted(
            groups,
            key=lambda bucket: (-groups[bucket][0]["retrieval_score"], bucket),
        )
        offset = 0
        while True:
            appended = False
            for bucket in bucket_order:
                if offset < len(groups[bucket]):
                    ordered.append(groups[bucket][offset])
                    appended = True
            if not appended:
                break
            offset += 1
    return ordered


def mine(database: Path, external: Path, limit: int) -> tuple[list[dict], dict]:
    uri = database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    flash_sql = """
        SELECT DISTINCT g.id
        FROM game AS g
        JOIN game_platforms_platform AS gp ON gp.gameId = g.id
        JOIN platform AS p ON p.id = gp.platformId
        JOIN platform_alias AS pa ON pa.id = p.primaryAliasId
        WHERE g.library = 'arcade' AND pa.name = 'Flash'
    """
    total_flash = int(connection.execute(f"SELECT COUNT(*) FROM ({flash_sql})").fetchone()[0])
    tag_counts = {
        row["tag"]: int(row["games"])
        for row in connection.execute(f"""
            WITH flash AS ({flash_sql})
            SELECT ta.name AS tag, COUNT(DISTINCT gt.gameId) AS games
            FROM flash AS f
            JOIN game_tags_tag AS gt ON gt.gameId = f.id
            JOIN tag AS t ON t.id = gt.tagId AND t.categoryId = 2
            JOIN tag_alias AS ta ON ta.id = t.primaryAliasId
            GROUP BY t.id
        """)
    }
    copyright_tags = {
        row["tag"]
        for row in connection.execute("""
            SELECT ta.name AS tag
            FROM tag AS t
            JOIN tag_alias AS ta ON ta.id = t.primaryAliasId
            WHERE t.categoryId = 4
        """)
    }

    counters = Counter()
    scored: list[dict] = []
    rows = connection.execute(f"""
        WITH flash AS ({flash_sql})
        SELECT g.id, g.title, g.developer, g.releaseDate, g.source, g.tagsStr,
               g.originalDescription, g.extreme
        FROM game AS g
        JOIN flash AS f ON f.id = g.id
        ORDER BY g.id
    """)
    for row in rows:
        counters["examined"] += 1
        description, noise_matches = clean_description(row["originalDescription"] or "")
        if len(description) < 80:
            counters["short_or_missing_description"] += 1
            continue
        tags = [part.strip() for part in (row["tagsStr"] or "").split(";") if part.strip()]
        if bool(row["extreme"]) or EXCLUDED_TAGS.intersection(tags):
            counters["safety_excluded"] += 1
            continue

        normalized_description = normalize(description)
        matched = {
            family: sorted({
                phrase for phrase in phrases
                if contains_phrase(normalized_description, phrase)
            })
            for family, phrases in MECHANIC_PHRASES.items()
        }
        matched = {family: phrases for family, phrases in matched.items() if phrases}
        mechanic_tags = sorted(
            (tag for tag in tags if tag in MECHANIC_SIGNAL_TAGS),
            key=lambda tag: (tag_counts.get(tag, total_flash), tag.lower()),
        )
        core_mechanic_tags = [tag for tag in mechanic_tags if tag in CORE_MECHANIC_TAGS]
        if not matched and not mechanic_tags:
            counters["no_mechanic_signal"] += 1
            continue

        crossmedia_hits = sorted(CROSSMEDIA_TAGS.intersection(tags))
        title_normalized = normalize(row["title"] or "")
        if "panorama" in title_normalized or "photo gallery" in title_normalized:
            crossmedia_hits.append("title-format-signal")
        content_tier = "crossmedia" if crossmedia_hits else "gameplay"
        counters[f"retrieval_{content_tier}"] += 1
        row_copyright_tags = sorted(copyright_tags.intersection(tags))
        mechanic_hits = sum(len(phrases) for phrases in matched.values())
        core_tag_signal = sum(
            math.log1p(total_flash / max(1, tag_counts.get(tag, total_flash)))
            for tag in core_mechanic_tags[:3]
        )
        secondary_tag_signal = sum(
            math.log1p(total_flash / max(1, tag_counts.get(tag, total_flash)))
            for tag in mechanic_tags if tag not in CORE_MECHANIC_TAGS
        )
        template_penalty = sum(
            penalty for phrase, penalty in TEMPLATE_PHRASES.items()
            if phrase in normalized_description
        )
        description_score = min(math.log1p(len(description)) / 2.0, 4.0)
        copyright_penalty = min(2.5, 0.65 * len(row_copyright_tags))
        score = (
            2.3 * len(matched)
            + 0.75 * mechanic_hits
            + 0.72 * core_tag_signal
            + 0.12 * secondary_tag_signal
            + description_score
            + min(len(tags), 8) * 0.12
            - template_penalty
            - copyright_penalty
            - min(2.0, noise_matches * 0.35)
        )
        release = (row["releaseDate"] or "").strip()
        year_match = YEAR_RE.match(release)
        scored.append({
            "flashpoint_id": row["id"],
            "title": row["title"],
            "developer": row["developer"],
            "year": year_match.group(1) if year_match else "",
            "source_domain": primary_domain(row["source"] or ""),
            "source": row["source"],
            "content_tier": content_tier,
            "crossmedia_signals": "; ".join(sorted(set(crossmedia_hits))),
            "copyright_tags": "; ".join(row_copyright_tags),
            "tags": "; ".join(tags),
            "core_mechanic_tags": "; ".join(core_mechanic_tags),
            "mechanic_tags": "; ".join(mechanic_tags[:6]),
            "mechanic_families": "; ".join(sorted(matched)),
            "mechanic_phrases": "; ".join(
                phrase for family in sorted(matched) for phrase in matched[family]
            ),
            "description": description[:700],
            "retrieval_score": round(score, 4),
        })

    scored.sort(key=lambda row: (-row["retrieval_score"], row["title"].lower(), row["flashpoint_id"]))
    selected: list[dict] = []
    developer_cap: Counter[str] = Counter()
    domain_cap: Counter[str] = Counter()
    signature_cap: Counter[str] = Counter()
    core_tag_cap: Counter[str] = Counter()
    normalized_titles: set[str] = set()
    normalized_descriptions: set[str] = set()
    crossmedia_limit = min(200, max(1, limit // 10))
    selected_crossmedia = 0
    for row in scored:
        developer = normalize(row["developer"]) or "unknown"
        domain = row["source_domain"]
        signature = row["mechanic_tags"] or row["mechanic_families"]
        title = normalize(row["title"])
        description_signature = normalize(row["description"])
        if title in normalized_titles:
            continue
        if description_signature in normalized_descriptions:
            counters["duplicate_description_skipped"] += 1
            continue
        if row["content_tier"] == "crossmedia" and selected_crossmedia >= crossmedia_limit:
            continue
        row_core_tags = [
            tag for tag in row["core_mechanic_tags"].split("; ") if tag
        ]
        if (
            (developer != "unknown" and developer_cap[developer] >= 12)
            or (domain != "unknown" and domain_cap[domain] >= 180)
            or signature_cap[signature] >= 35
            or any(core_tag_cap[tag] >= 18 for tag in row_core_tags)
        ):
            continue
        selected.append(row)
        normalized_titles.add(title)
        normalized_descriptions.add(description_signature)
        developer_cap[developer] += 1
        domain_cap[domain] += 1
        signature_cap[signature] += 1
        for tag in row_core_tags:
            core_tag_cap[tag] += 1
        if row["content_tier"] == "crossmedia":
            selected_crossmedia += 1
        if len(selected) >= limit:
            break

    nearest_existing(selected, load_existing(external))
    selected = diverse_review_order(selected)
    for rank, row in enumerate(selected, start=1):
        row["rank"] = rank

    audit = {
        "schema_version": 2,
        "method": (
            "complete Flash metadata enumeration followed by interaction-signal retrieval, "
            "format separation, diversity caps, and round-robin review strata"
        ),
        "database": {"bytes": database.stat().st_size, "sha256": sha256(database)},
        "counts": {
            "flash_games": total_flash,
            **dict(counters),
            "retrieval_candidates": len(scored),
            "selected_for_review": len(selected),
            "selected_gameplay": sum(row["content_tier"] == "gameplay" for row in selected),
            "selected_crossmedia": sum(row["content_tier"] == "crossmedia" for row in selected),
        },
        "selection_caps": {
            "per_normalized_developer": 12,
            "per_source_domain": 180,
            "per_mechanic_tag_or_phrase_signature": 35,
            "per_core_mechanic_tag": 18,
            "duplicate_normalized_titles": 1,
            "duplicate_normalized_descriptions": 1,
            "crossmedia_records": crossmedia_limit,
        },
        "mechanic_phrase_families": {
            key: list(value) for key, value in sorted(MECHANIC_PHRASES.items())
        },
        "core_mechanic_tags": sorted(CORE_MECHANIC_TAGS),
        "crossmedia_tags": sorted(CROSSMEDIA_TAGS),
        "interpretation_boundary": (
            "Ranking identifies records worth human source/play review. Metadata language, "
            "rarity, and lexical distance do not establish mechanic novelty."
        ),
    }
    connection.close()
    return selected, audit


def write_queue(path: Path, rows: list[dict]) -> None:
    fields = [
        "rank", "flashpoint_id", "title", "developer", "year", "source_domain",
        "source", "content_tier", "crossmedia_signals", "copyright_tags", "tags",
        "review_bucket", "core_mechanic_tags", "mechanic_tags", "mechanic_families",
        "mechanic_phrases", "retrieval_score",
        "nearest_existing_id", "nearest_existing_title", "nearest_existing_similarity",
        "description",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--external-ledger", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--output-queue", required=True, type=Path)
    parser.add_argument("--output-audit", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=2000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    rows, audit = mine(args.database, args.external_ledger, args.limit)
    write_queue(args.output_queue, rows)
    args.output_audit.parent.mkdir(parents=True, exist_ok=True)
    args.output_audit.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"selected {len(rows):,} review candidates from "
        f"{audit['counts']['flash_games']:,} Flash records"
    )


if __name__ == "__main__":
    main()
