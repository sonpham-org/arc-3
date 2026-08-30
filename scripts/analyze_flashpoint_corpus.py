#!/usr/bin/env python3
"""Create a reproducible mechanic-oriented audit of a Flashpoint SQLite snapshot.

The database itself is an external research input and is intentionally not copied into
the repository.  This script reads it in SQLite read-only mode and emits only aggregate
counts.  It does not download or execute archived games.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


SOURCE_URL = "https://download.flashpointarchive.org/flashpoint.sqlite"
YEAR_RE = re.compile(r"^(19\d{2}|20\d{2})")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def primary_domain(raw_source: str) -> str | None:
    value = raw_source.strip().split(";")[0].strip()
    if not value:
        return None
    value = re.sub(r"\s+\(via Wayback Machine\)$", "", value)
    if "://" not in value:
        value = "https://" + value.lstrip("/")
    parsed = urlparse(value)
    host = parsed.hostname
    if not host:
        return None
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def query_scalar(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = connection.execute(sql, params).fetchone()
    if row is None:
        raise RuntimeError("aggregate query returned no row")
    return int(row[0])


def flash_game_ids_sql() -> str:
    return """
        SELECT DISTINCT g.id
        FROM game AS g
        JOIN game_platforms_platform AS gp ON gp.gameId = g.id
        JOIN platform AS p ON p.id = gp.platformId
        JOIN platform_alias AS pa ON pa.id = p.primaryAliasId
        WHERE g.library = 'arcade' AND pa.name = 'Flash'
    """


def build_report(database: Path, published_at: str | None) -> tuple[dict, list[dict]]:
    uri = database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row

    integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"SQLite quick_check failed: {integrity}")

    flash_ids = flash_game_ids_sql()
    total_arcade = query_scalar(
        connection, "SELECT COUNT(*) FROM game WHERE library = 'arcade'"
    )
    total_flash = query_scalar(connection, f"SELECT COUNT(*) FROM ({flash_ids})")

    field_counts = {}
    for field in ("developer", "source", "originalDescription", "releaseDate", "tagsStr"):
        if field not in {
            "developer",
            "source",
            "originalDescription",
            "releaseDate",
            "tagsStr",
        }:
            raise AssertionError(field)
        field_counts[field] = query_scalar(
            connection,
            f"""
            SELECT COUNT(*)
            FROM game AS g
            JOIN ({flash_ids}) AS f ON f.id = g.id
            WHERE TRIM(g.{field}) <> ''
            """,
        )

    genre_rows = connection.execute(
        f"""
        WITH flash AS ({flash_ids}),
        flash_counts AS (
            SELECT t.id AS tag_id, COUNT(DISTINCT gt.gameId) AS game_count
            FROM flash AS f
            JOIN game_tags_tag AS gt ON gt.gameId = f.id
            JOIN tag AS t ON t.id = gt.tagId
            WHERE t.categoryId = 2
            GROUP BY t.id
        ),
        arcade_counts AS (
            SELECT t.id AS tag_id, COUNT(DISTINCT gt.gameId) AS game_count
            FROM game AS g
            JOIN game_tags_tag AS gt ON gt.gameId = g.id
            JOIN tag AS t ON t.id = gt.tagId
            WHERE g.library = 'arcade' AND t.categoryId = 2
            GROUP BY t.id
        )
        SELECT ta.name AS tag,
               COALESCE(fc.game_count, 0) AS flash_games,
               COALESCE(ac.game_count, 0) AS arcade_games,
               t.description AS description
        FROM tag AS t
        JOIN tag_alias AS ta ON ta.id = t.primaryAliasId
        LEFT JOIN flash_counts AS fc ON fc.tag_id = t.id
        LEFT JOIN arcade_counts AS ac ON ac.tag_id = t.id
        WHERE t.categoryId = 2
        ORDER BY flash_games DESC, tag COLLATE NOCASE
        """
    ).fetchall()
    genre_tags = [
        {
            "rank": index,
            "tag": row["tag"],
            "flash_games": int(row["flash_games"]),
            "flash_share": round(int(row["flash_games"]) / total_flash, 8),
            "arcade_games": int(row["arcade_games"]),
            "description": row["description"] or "",
        }
        for index, row in enumerate(genre_rows, start=1)
    ]

    pair_rows = connection.execute(
        f"""
        WITH flash AS ({flash_ids}),
        tagged AS (
            SELECT DISTINCT f.id AS game_id, t.id AS tag_id, ta.name AS tag
            FROM flash AS f
            JOIN game_tags_tag AS gt ON gt.gameId = f.id
            JOIN tag AS t ON t.id = gt.tagId AND t.categoryId = 2
            JOIN tag_alias AS ta ON ta.id = t.primaryAliasId
        )
        SELECT a.tag AS left_tag, b.tag AS right_tag, COUNT(*) AS game_count
        FROM tagged AS a
        JOIN tagged AS b ON b.game_id = a.game_id AND b.tag_id > a.tag_id
        GROUP BY a.tag_id, b.tag_id
        HAVING COUNT(*) >= 25
        ORDER BY game_count DESC, left_tag COLLATE NOCASE, right_tag COLLATE NOCASE
        LIMIT 500
        """
    ).fetchall()

    year_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    developer_counts: Counter[str] = Counter()
    for row in connection.execute(
        f"""
        SELECT g.releaseDate, g.source, g.developer
        FROM game AS g
        JOIN ({flash_ids}) AS f ON f.id = g.id
        """
    ):
        match = YEAR_RE.match((row["releaseDate"] or "").strip())
        if match:
            year_counts[match.group(1)] += 1
        domain = primary_domain(row["source"] or "")
        if domain:
            domain_counts[domain] += 1
        for developer in (row["developer"] or "").split(";"):
            developer = developer.strip()
            if developer:
                developer_counts[developer] += 1

    category_counts = [
        {
            "category": row["category"],
            "games": int(row["games"]),
            "tags": int(row["tags"]),
        }
        for row in connection.execute(
            f"""
            WITH flash AS ({flash_ids})
            SELECT tc.name AS category,
                   COUNT(DISTINCT gt.gameId) AS games,
                   COUNT(DISTINCT t.id) AS tags
            FROM flash AS f
            JOIN game_tags_tag AS gt ON gt.gameId = f.id
            JOIN tag AS t ON t.id = gt.tagId
            JOIN tag_category AS tc ON tc.id = t.categoryId
            GROUP BY tc.id
            ORDER BY games DESC, category
            """
        )
    ]

    report = {
        "schema_version": 1,
        "method": "complete metadata enumeration; no game binaries executed",
        "database": {
            "source_url": SOURCE_URL,
            "published_at": published_at,
            "bytes": database.stat().st_size,
            "sha256": sha256_file(database),
            "integrity": integrity,
        },
        "selection": {
            "library": "arcade",
            "platform_primary_alias": "Flash",
            "distinct_games": True,
        },
        "counts": {
            "all_arcade_games": total_arcade,
            "flash_games": total_flash,
            "flash_share_of_arcade": round(total_flash / total_arcade, 8),
            "flash_games_with_nonempty_fields": field_counts,
            "genre_tags_with_at_least_one_flash_game": sum(
                row["flash_games"] > 0 for row in genre_tags
            ),
        },
        "tag_categories": category_counts,
        "release_year_counts": dict(sorted(year_counts.items())),
        "top_source_domains": [
            {"domain": name, "games": count}
            for name, count in domain_counts.most_common(100)
        ],
        "top_developers": [
            {"developer": name, "games": count}
            for name, count in developer_counts.most_common(100)
        ],
        "genre_tags": genre_tags,
        "frequent_genre_tag_pairs": [
            {
                "left": row["left_tag"],
                "right": row["right_tag"],
                "flash_games": int(row["game_count"]),
            }
            for row in pair_rows
        ],
        "limitations": [
            "The public SQLite snapshot is dated and does not contain every Flash work ever made.",
            "Tags and descriptions are curator metadata, not direct observations of play.",
            "Genre frequency does not measure mechanic originality or research value.",
            "A separate manual play-and-source review is required before using any title as prior art.",
        ],
    }
    connection.close()
    return report, genre_tags


def write_tags_tsv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "rank\ttag\tflash_games\tflash_share\tarcade_games\tdescription\n"
        )
        for row in rows:
            description = row["description"].replace("\t", " ").replace("\n", " ")
            handle.write(
                f"{row['rank']}\t{row['tag']}\t{row['flash_games']}\t"
                f"{row['flash_share']:.8f}\t{row['arcade_games']}\t{description}\n"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-tags-tsv", required=True, type=Path)
    parser.add_argument(
        "--published-at",
        help="Upstream snapshot timestamp, kept separate from local download time.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.database.is_file():
        raise SystemExit(f"database not found: {args.database}")
    report, tags = build_report(args.database, args.published_at)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_tags_tsv(args.output_tags_tsv, tags)
    print(
        f"audited {report['counts']['flash_games']:,} Flash games; "
        f"wrote {args.output_json} and {args.output_tags_tsv}"
    )


if __name__ == "__main__":
    main()
