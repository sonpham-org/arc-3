#!/usr/bin/env python3.13
"""
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Pass E, the falsifiability gate of docs/plans/2026-09-15-step4-segment-and-label-execution.md
section 3. Every finished record is judged keep-or-cut by a reviewer that did not write it: a
separate headless `claude -p` process per record, with every tool switched off and no project
customisations loaded, so the only things it can see are the rules below, the record, and the
evidence frame_evidence.py renders from the recording. It never sees the annotator's session.
Verdicts are appended to a JSONL results file; this script deletes nothing. Cutting is a separate,
visible step (--apply), so the verdicts can be read before any record is removed, and a cut record
is deleted rather than rewritten.
SRP/DRY check: Pass - frame_evidence.py owns the evidence; validate.py owns schema checks (and
action_role_source is test-checked elsewhere, so the reviewer is told to ignore it). This only
runs the independent review and applies its cuts.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame_evidence import DEFAULT_RECORDINGS, Recording, evidence  # noqa: E402

RULES = """You are pass E, the falsifiability gate for a corpus of decision-step records. Each record is a
label an annotator attached, after the fact, to one move in a HUMAN's replay of a 64x64 grid game.
You did not write it. Decide KEEP or CUT. A record is kept only if it passes every check below; a
weak record is cut, never softened. You have no tools: judge from the evidence given.

Checks (use these names in failed_checks):
1. falsifiable - decision.expected_observation names something concrete that the board after the
   decision could show to be false: positions, a cell region, colours, counts, the state or the
   level. Vague claims ("something changes", "progress is made", "the board updates") fail.
2. matches_frames - read BOARD BEFORE, BOARD AFTER, CHANGED REGION and the state/level lines
   yourself and decide whether they confirm or refute expected_observation. Fail if
   outcome.expectation_held disagrees with your reading, or if a specific claim in the expectation
   cannot be checked from the evidence shown (unverifiable counts as fail).
3. observed_consistent - outcome.observed must agree with the frames and the timeline line for the
   decision row (cells changed, state and level transitions).
4. memory_from_run - memory_in may hold only what a player could know from this run up to this row:
   effects visible in earlier frames, actions tried, outcomes seen. Fail if it holds knowledge only
   the game's source code gives: internal variable or sprite-tag names, exact hidden-counter
   arithmetic, line numbers, or mechanics nothing shown so far could reveal. LEVEL HISTORY shows this
   level so far; earlier levels may have taught general facts, which is allowed when plausible.
5. rationale_and_role - decision.rationale and action_role must not assert anything the frames or
   the history contradict. For tier "negative", corrected_decision must exist and
   outcome.expectation_held must be false.
Ignore action_role_source (a separate test checks citations) and rationale_provenance.

Respond with ONLY one JSON object, no prose around it:
{"verdict": "keep" or "cut", "failed_checks": [names], "reason": "one or two specific sentences"}
"""

DEFAULT_MODEL = "claude-opus-5"


def review(record: dict, recordings_dir: Path, model: str, timeout: int) -> dict:
    rec = Recording(recordings_dir, record["game_id"], record["source"]["recording_guid"])
    prompt = (
        RULES
        + "\n\nRECORD:\n"
        + json.dumps(record, indent=1)
        + "\n\nEVIDENCE rendered from the recording:\n"
        + evidence(rec, record)
    )
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as cwd:  # no project files, no CLAUDE.md, no memory
        proc = subprocess.run(
            ["claude", "-p", "--model", model, "--tools", "", "--safe-mode",
             "--no-session-persistence", "--output-format", "json"],
            input=prompt, capture_output=True, text=True, cwd=cwd, timeout=timeout,
        )
    envelope = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
    text = (envelope.get("result") or proc.stdout or proc.stderr).strip()
    verdict = {"verdict": "error", "failed_checks": [], "reason": text[:300]}
    decoder = json.JSONDecoder()
    at = text.find("{")
    while at != -1:  # the first well-formed object that carries a verdict, fences or not
        try:
            try:
                obj, _ = decoder.raw_decode(text, at)
            except json.JSONDecodeError:
                # replies sometimes stop one brace short; the verdict itself is intact
                obj, _ = decoder.raw_decode(text[at:].rstrip().rstrip("`").rstrip() + "}")
            if isinstance(obj, dict) and obj.get("verdict") in ("keep", "cut"):
                verdict = obj
                break
        except json.JSONDecodeError:
            pass
        at = text.find("{", at + 1)
    verdict["raw"] = text if verdict.get("verdict") == "error" else None
    return {
        **verdict,
        "reviewer_model": model,
        "cost_usd": envelope.get("total_cost_usd"),
        "seconds": round(time.monotonic() - started, 1),
        "prompt_chars": len(prompt),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("episodes", nargs="+", type=Path, help="episode .jsonl files")
    p.add_argument("--results", type=Path, required=True, help="JSONL file verdicts are appended to")
    p.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--apply", action="store_true",
                   help="instead of reviewing, delete every record the results file marks cut")
    args = p.parse_args(argv)

    if args.apply:
        cut = {}
        for line in args.results.read_text().splitlines():
            r = json.loads(line)
            if r["verdict"] == "cut":
                cut.setdefault(r["file"], set()).add(r["line"])
        for path in args.episodes:
            lines = path.read_text().splitlines()
            keep = [l for i, l in enumerate(lines) if i not in cut.get(path.name, set())]
            if len(keep) != len(lines):
                if keep:
                    path.write_text("\n".join(keep) + "\n")
                else:
                    path.unlink()
                print(f"{path.name}: cut {len(lines) - len(keep)} of {len(lines)}")
        return 0

    jobs = []
    for path in args.episodes:
        for i, line in enumerate(path.read_text().splitlines()):
            jobs.append((path, i, json.loads(line)))
    args.results.parent.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(review, rec, args.recordings_dir, args.model, args.timeout): (path, i, rec)
                   for path, i, rec in jobs}
        for fut in concurrent.futures.as_completed(futures):
            path, i, rec = futures[fut]
            try:
                verdict = fut.result()
            except Exception as exc:  # a failed review is recorded, never silently kept
                verdict = {"verdict": "error", "failed_checks": [], "reason": f"{type(exc).__name__}: {exc}"}
            row = {"file": path.name, "line": i, "game_id": rec["game_id"],
                   "row_index": rec["source"]["row_index"], "segment": rec["segment"]["id"],
                   "tier": rec["tier"], **verdict}
            with args.results.open("a") as out:
                out.write(json.dumps(row) + "\n")
            print(f"{row['verdict']:<5} {path.name}:{i} row {row['row_index']} {row.get('failed_checks')} {row.get('reason', '')[:160]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
