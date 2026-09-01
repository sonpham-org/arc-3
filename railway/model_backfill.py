"""One-time structured model metadata backfill for preserved ARC3 runs.

These rules cover the catalog rows published before model identity became a
required field. They are deliberately narrow: unmatched rows remain visibly
unlabelled instead of receiving a guessed model.
"""

from __future__ import annotations

import re
from typing import Any


RADIX_REVISION = "7b719225242aacd3dbd3f9407468c2ee9a9d2594"
UNSLOTH_REVISION = "7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108"
QWEN_FP8_REVISION = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"


def _model(
    model_id: str,
    revision: str | None,
    quantization: str,
    evidence: str,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": model_id,
        "display": f"{model_id}@{revision[:8]}" if revision else model_id,
        "quantization": quantization,
        "evidence": [
            {
                "type": "historical-backfill",
                "source": evidence,
                "verifiedAt": "2026-09-01",
            }
        ],
    }
    if revision:
        value["revision"] = revision
    return value


RADIX = _model(
    "RadixArk/Qwen3.8-Flash-Next-NVFP4",
    RADIX_REVISION,
    "NVFP4 routed experts; FP8 PLE table",
    "preserved GCS LAUNCH_STATE.json and model-info.json",
)
UNSLOTH = _model(
    "unsloth/Qwen3.8-27B-NVFP4",
    UNSLOTH_REVISION,
    "NVFP4",
    "preserved GCS LAUNCH_STATE.json and serving manifests",
)
QWEN_FP8 = _model(
    "Qwen/Qwen3.8-27B-FP8",
    QWEN_FP8_REVISION,
    "FP8",
    "preserved GCS model-info.json and curated historical harness",
)
VRFAI_FP8 = _model(
    "vrfai/Qwen3.6-27B-FP8",
    None,
    "FP8 W8A8",
    "preserved serving manifests and curated historical harness",
)


def historical_model_for_run(run_id: str) -> dict[str, Any] | None:
    """Return verified metadata only for the pre-schema run families."""

    if re.fullmatch(r"20260810_0506_v12-ffa7gn-cap8-(?:plan-reset|noimpact-memo)-p[12]", run_id):
        return dict(VRFAI_FP8)
    if re.fullmatch(
        r"202608(?:18_102648_q38-taaf-cap8-shadow-sidecar-p1|"
        r"19_134223_q38-taaf-cap8-reviewedthemes-cen-p2)",
        run_id,
    ):
        return dict(QWEN_FP8)
    if (
        re.search(r"(?:^|_)q38-(?:flashnext|fnv\d+|f14)(?:-|_)", run_id)
        or run_id.startswith("g4run-q38-f14-")
    ):
        return dict(RADIX)
    if re.fullmatch(r"20260827_220911_q38-flashnext-rtdv7-22", run_id):
        return dict(RADIX)
    if re.match(r"^202608(?:20|21|22|23|24|25|26|27|28)_", run_id) and (
        "q38-" in run_id or re.search(r"_n2(?:compact|nocur|prefix|x)", run_id)
    ):
        return dict(UNSLOTH)
    return None


def backfill_catalog_models(cursor: Any, Json: Any) -> tuple[int, list[str]]:
    """Backfill false-fallback rows and return (updated, unresolved)."""

    cursor.execute(
        """
        SELECT run_id
        FROM arc3_runs
        WHERE status = 'published'
          AND NOT (catalog_entry ? 'model')
          AND COALESCE(catalog_entry #>> '{harness,weights}', '') = ''
        ORDER BY run_id
        """
    )
    run_ids = [str(row[0]) for row in cursor.fetchall()]
    updated = 0
    unresolved: list[str] = []
    for run_id in run_ids:
        model = historical_model_for_run(run_id)
        if model is None:
            unresolved.append(run_id)
            continue
        cursor.execute(
            """
            UPDATE arc3_runs
            SET catalog_entry = jsonb_set(catalog_entry, '{model}', %s, true),
                updated_at = now()
            WHERE run_id = %s
              AND status = 'published'
              AND NOT (catalog_entry ? 'model')
            """,
            (Json(model), run_id),
        )
        updated += 1
    return updated, unresolved
