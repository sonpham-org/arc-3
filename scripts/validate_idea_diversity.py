"""Validate an idea ledger against the existing ARC3 research corpus.

This is a small, deterministic retrieval pass: it normalizes the GPT concept ledger,
the pinned external ledger, and current browser manifest into one corpus; computes a
TF-IDF representation over word unigrams and bigrams; and records nearest neighbors for
every candidate. It is a collision detector and review aid, not proof of semantic novelty.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTERNAL = ROOT.parent / "autoresearch-arena-source" / "arc3" / "game-ideas" / "ledger.jsonl"
DEFAULT_CANDIDATES = ROOT / "research" / "anthropic-build-ideas-v1.tsv"
DEFAULT_OUTPUT = ROOT / "research" / "anthropic-build-ideas-v1.audit.json"
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "all", "an", "and", "any", "are", "as", "at", "be", "before",
    "but", "by", "can", "each", "every", "for", "from", "has", "have",
    "in", "into", "is", "it", "its", "later", "may", "must", "not", "of",
    "one", "only", "or", "other", "player", "several", "so", "than", "that",
    "the", "their", "then", "through", "to", "two", "under", "while", "with",
}
PRIOR_THRESHOLD = 0.34
INTERNAL_THRESHOLD = 0.42
TITLE_THRESHOLD = 0.84


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--external-ledger", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(TOKEN_RE.findall(value.lower()))


def features(value: str) -> Counter[str]:
    tokens = [token for token in normalize(value).split() if token not in STOPWORDS and len(token) > 2]
    result: Counter[str] = Counter(tokens)
    result.update(f"{left}::{right}" for left, right in zip(tokens, tokens[1:]))
    return result


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def candidate_text(row: dict[str, str]) -> str:
    return " ".join(
        row[key]
        for key in (
            "internal_title",
            "primary_axis",
            "secondary_axis",
            "interaction_model",
            "concept",
            "differentiator",
            "anticipated_ai_failure",
        )
    )


def load_prior(external_path: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    gpt_path = ROOT / "research" / "gpt-ideas-v1.tsv"
    manifest_path = ROOT / "docs" / "static" / "games" / "manifest.json"
    if not external_path.exists():
        raise SystemExit(f"External ledger not found: {external_path}")

    prior: list[dict[str, str]] = []
    for row in load_tsv(gpt_path):
        prior.append(
            {
                "id": row["id"],
                "title": row["internal_title"],
                "source": "gpt-ideas-v1",
                "text": " ".join(row.values()),
            }
        )

    with external_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            prior.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "source": "autoresearch-arena-63",
                    "text": " ".join(
                        str(row.get(key, ""))
                        for key in (
                            "title",
                            "mechanic_axis",
                            "secondary_axes",
                            "pitch",
                            "mechanics",
                            "ai_failure_mode",
                            "novelty_vs",
                        )
                    ),
                }
            )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest:
        prior.append(
            {
                "id": f"manifest:{row['id']}",
                "title": row["title"],
                "source": "browser-manifest",
                "text": " ".join(
                    (
                        row["title"],
                        str(row.get("category", "")),
                        " ".join(row.get("tags", [])),
                    )
                ),
            }
        )
    hashes = {
        "gpt_ideas_sha256": sha256(gpt_path),
        "external_ledger_sha256": sha256(external_path),
        "manifest_sha256": sha256(manifest_path),
    }
    return prior, hashes


def vectors(texts: list[str]) -> list[dict[str, float]]:
    counts = [features(text) for text in texts]
    document_frequency: Counter[str] = Counter()
    for count in counts:
        document_frequency.update(count.keys())
    total = len(counts)
    result = []
    for count in counts:
        weighted = {
            term: (1.0 + math.log(value))
            * (math.log((1.0 + total) / (1.0 + document_frequency[term])) + 1.0)
            for term, value in count.items()
        }
        norm = math.sqrt(sum(value * value for value in weighted.values())) or 1.0
        result.append({term: value / norm for term, value in weighted.items()})
    return result


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0.0) for term, value in left.items())


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[position]


def main() -> None:
    args = parse_args()
    candidate_path = args.candidates.resolve()
    output_path = args.output.resolve()
    candidates = load_tsv(candidate_path)
    prior, source_hashes = load_prior(args.external_ledger.resolve())

    required = {
        "id", "internal_title", "primary_axis", "secondary_axis", "interaction_model",
        "concept", "differentiator", "anticipated_ai_failure", "lineage",
    }
    if len(candidates) != 200:
        raise SystemExit(f"Expected 200 candidates, found {len(candidates)}")
    if set(candidates[0]) != required:
        raise SystemExit(f"Unexpected columns: {set(candidates[0]) ^ required}")
    for key in required:
        if any(not row[key].strip() for row in candidates):
            raise SystemExit(f"Blank candidate field: {key}")
    if len({row["id"] for row in candidates}) != len(candidates):
        raise SystemExit("Duplicate candidate IDs")
    expected_ids = [f"a{number:03d}" for number in range(1, 201)]
    if [row["id"] for row in candidates] != expected_ids:
        raise SystemExit("Candidate IDs must be ordered a001 through a200")
    if len({normalize(row["internal_title"]) for row in candidates}) != len(candidates):
        raise SystemExit("Duplicate normalized candidate titles")
    if len({normalize(row["concept"]) for row in candidates}) != len(candidates):
        raise SystemExit("Duplicate normalized candidate concepts")
    if any(row["lineage"] != "gpt-seeded-anthropic-build" for row in candidates):
        raise SystemExit("Incorrect or mixed lineage labels")

    all_documents = [entry["text"] for entry in prior] + [candidate_text(row) for row in candidates]
    all_vectors = vectors(all_documents)
    prior_vectors = all_vectors[: len(prior)]
    candidate_vectors = all_vectors[len(prior) :]
    prior_titles = {normalize(entry["title"]): entry for entry in prior}

    exact_title_collisions = []
    fuzzy_title_collisions = []
    records = []
    prior_scores = []
    internal_scores = []
    for index, (row, vector) in enumerate(zip(candidates, candidate_vectors)):
        normalized_title = normalize(row["internal_title"])
        if normalized_title in prior_titles:
            match = prior_titles[normalized_title]
            exact_title_collisions.append({"candidate": row["id"], "prior": match["id"]})

        title_match = max(
            prior,
            key=lambda entry: SequenceMatcher(None, normalized_title, normalize(entry["title"])).ratio(),
        )
        title_score = SequenceMatcher(None, normalized_title, normalize(title_match["title"])).ratio()
        if title_score >= TITLE_THRESHOLD:
            fuzzy_title_collisions.append(
                {
                    "candidate": row["id"],
                    "candidate_title": row["internal_title"],
                    "prior": title_match["id"],
                    "prior_title": title_match["title"],
                    "ratio": round(title_score, 4),
                }
            )

        ranked_prior = sorted(
            (
                (cosine(vector, prior_vector), entry)
                for entry, prior_vector in zip(prior, prior_vectors)
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        ranked_internal = sorted(
            (
                (cosine(vector, other_vector), candidates[other_index])
                for other_index, other_vector in enumerate(candidate_vectors)
                if other_index != index
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        prior_scores.append(ranked_prior[0][0])
        internal_scores.append(ranked_internal[0][0])
        records.append(
            {
                "id": row["id"],
                "title": row["internal_title"],
                "nearest_prior": [
                    {
                        "id": entry["id"],
                        "title": entry["title"],
                        "source": entry["source"],
                        "similarity": round(score, 4),
                    }
                    for score, entry in ranked_prior[:3]
                ],
                "nearest_candidate": {
                    "id": ranked_internal[0][1]["id"],
                    "title": ranked_internal[0][1]["internal_title"],
                    "similarity": round(ranked_internal[0][0], 4),
                },
            }
        )

    gpt_axes = {row["primary_axis"] for row in load_tsv(ROOT / "research" / "gpt-ideas-v1.tsv")}
    with args.external_ledger.resolve().open(encoding="utf-8") as handle:
        external_axes = {
            json.loads(line)["mechanic_axis"] for line in handle if line.strip()
        }
    candidate_axes = Counter(row["primary_axis"] for row in candidates)
    if len(candidate_axes) != 25 or set(candidate_axes.values()) != {8}:
        raise SystemExit("Expected 25 primary axes with exactly 8 concepts each")
    payload = {
        "schema_version": 1,
        "candidate_file": candidate_path.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha256(candidate_path),
        "retrieval_method": "TF-IDF cosine over normalized word unigrams and bigrams",
        "interpretation_boundary": (
            "Lexical retrieval finds collisions and near neighbors but cannot prove semantic novelty. "
            "The differentiator field and human mechanic review remain mandatory."
        ),
        "sources": {
            **source_hashes,
            "prior_documents": len(prior),
            "gpt_concepts": 200,
            "external_concepts": 63,
            "manifest_entries": 299,
        },
        "thresholds": {
            "prior_similarity_review": PRIOR_THRESHOLD,
            "internal_similarity_review": INTERNAL_THRESHOLD,
            "fuzzy_title_review": TITLE_THRESHOLD,
        },
        "summary": {
            "candidates": len(candidates),
            "primary_axes": len(candidate_axes),
            "axis_histogram": dict(sorted(candidate_axes.items())),
            "primary_axis_exact_overlap_with_gpt": sorted(candidate_axes.keys() & gpt_axes),
            "primary_axis_exact_overlap_with_external": sorted(candidate_axes.keys() & external_axes),
            "exact_title_collisions": exact_title_collisions,
            "fuzzy_title_collisions": fuzzy_title_collisions,
            "prior_similarity": {
                "maximum": round(max(prior_scores), 4),
                "median": round(statistics.median(prior_scores), 4),
                "p95": round(percentile(prior_scores, 0.95), 4),
                "review_ids": [
                    record["id"]
                    for record, score in zip(records, prior_scores)
                    if score >= PRIOR_THRESHOLD
                ],
            },
            "internal_similarity": {
                "maximum": round(max(internal_scores), 4),
                "median": round(statistics.median(internal_scores), 4),
                "p95": round(percentile(internal_scores, 0.95), 4),
                "review_ids": [
                    record["id"]
                    for record, score in zip(records, internal_scores)
                    if score >= INTERNAL_THRESHOLD
                ],
            },
        },
        "records": records,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    review_failures = (
        exact_title_collisions
        or fuzzy_title_collisions
        or payload["summary"]["primary_axis_exact_overlap_with_gpt"]
        or payload["summary"]["primary_axis_exact_overlap_with_external"]
        or payload["summary"]["prior_similarity"]["review_ids"]
        or payload["summary"]["internal_similarity"]["review_ids"]
    )
    if review_failures:
        raise SystemExit("Idea diversity audit requires manual collision review")


if __name__ == "__main__":
    main()
