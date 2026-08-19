"""Export a timestamped, resource-oriented execution trace for the static viewer.

The regular viewer owns gameplay state and model-context payloads.  This export
adds one aligned time axis across main-agent calls, CPU sidecar calls, ledger
injections, and sampled process utilisation.  Sidecar prompt/response bodies are
preserved verbatim; gameplay calls link to the corresponding lazy step payload.

Usage: python scripts/export_execution_trace.py logs/<run-dir> [...]
"""

from __future__ import annotations

import json
import re
import sys
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "docs" / "data"
UTC = timezone.utc


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def parse_iso(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def clock_on_run_date(value: str, anchor: datetime) -> datetime | None:
    text = str(value or "").strip()
    exact = parse_iso(text) if "T" in text else None
    if exact is not None:
        return exact
    match = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?", text)
    if not match:
        return None
    microsecond = int((match.group(4) or "0").ljust(6, "0")[:6])
    base = anchor.replace(
        hour=int(match.group(1)),
        minute=int(match.group(2)),
        second=int(match.group(3)),
        microsecond=microsecond,
    )
    candidates = [base - timedelta(days=1), base, base + timedelta(days=1)]
    return min(candidates, key=lambda candidate: abs((candidate - anchor).total_seconds()))


def usage_summary(row: dict) -> dict:
    usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
    return {
        "promptTokens": usage.get("prompt_tokens"),
        "completionTokens": usage.get("completion_tokens"),
        "totalTokens": usage.get("total_tokens"),
    }


def reviewed_game_id(row: dict) -> str:
    game_id = str(row.get("game_id") or "").strip()
    if game_id == "artifacts" or not game_id:
        state_name = Path(str(row.get("state_path") or "")).name
        match = re.fullmatch(r"(.+?)(?:_p\d+)?_tool_runtime_state\.json", state_name)
        if match:
            game_id = match.group(1)
    return game_id


def live_game_score(run: dict, actions_per_level: list[int], levels_completed: int) -> float:
    """Mirror ``GameRun._compute_final_score`` at an intermediate completion."""
    baselines = run.get("base_actions_per_level") or []
    number_of_levels = int(run.get("number_of_levels") or 0)
    if not baselines or not number_of_levels:
        return 0.0
    total_score = 0.0
    total_weights = 0
    max_weights = 0
    for level_index in range(number_of_levels):
        weight = level_index + 1
        total_weights += weight
        actions = actions_per_level[level_index] if level_index < len(actions_per_level) else 0
        if level_index < levels_completed and actions > 0:
            level_score = min(115.0, (float(baselines[level_index]) / actions) ** 2 * 100.0)
            total_score += level_score * weight
            max_weights += weight
    if not total_weights:
        return 0.0
    return min(total_score / total_weights, max_weights / total_weights * 100.0)


def score_curve(
    benchmark: dict,
    artifact_root: Path,
    started: datetime,
    ended: datetime,
    main_events: list[dict],
    reviewed: Path,
) -> dict:
    """Build the cross-game mean score as a timestamped step function.

    Reviewed-theme runs use the exact prompt-injection clock.  Other archived
    runs use the already-exported model-call timestamp for the matching
    ``analysis_step``.  A completion emitted inside a previously generated
    action batch inherits that batch's call-start timestamp.
    """
    run_by_game = {str(run.get("game_id")): run for run in benchmark.get("game_runs", [])}
    game_count = max(1, len(run_by_game))
    main_times: dict[tuple[str, int], datetime] = {}
    for event in main_events:
        game_id = str(event.get("gameId") or "")
        step_index = event.get("stepIndex")
        at = parse_iso(event.get("start"))
        if game_id and step_index is not None and at is not None:
            main_times[(game_id, int(step_index))] = at

    injections: dict[str, list[tuple[int, datetime]]] = {}
    for row in read_jsonl(reviewed / "gameplay-theme-injections.jsonl"):
        game_id = reviewed_game_id(row)
        at = parse_iso(row.get("recorded_at"))
        action = row.get("action")
        if game_id and at is not None and action is not None:
            injections.setdefault(game_id, []).append((int(action), at))
    for rows in injections.values():
        rows.sort(key=lambda item: (item[0], item[1]))

    def action_time(game_id: str, action_number: int, batch_index: int, analysis_step: int) -> tuple[datetime | None, str]:
        """Place an environment action on the generating analyzer-call clock."""
        batch_start = action_number - batch_index + 1
        candidates = [item for item in injections.get(game_id, []) if item[0] <= batch_start]
        if candidates:
            best_action = max(item[0] for item in candidates)
            at = max(item[1] for item in candidates if item[0] == best_action)
            basis = "exact prompt-injection call start" if best_action == batch_start else "prior generated-batch call start"
            return at, basis
        at = main_times.get((game_id, analysis_step))
        return at, "model-call timestamp reconstruction" if at is not None else ""

    completions: list[dict] = []
    timed_actions: list[datetime] = []
    total_actions = 0
    untimed = 0
    events_dir = artifact_root / "artifacts"
    for path in sorted(events_dir.glob("*_events.jsonl")):
        match = re.fullmatch(r"(.+?)_p\d+_events\.jsonl", path.name)
        if not match:
            continue
        game_id = match.group(1)
        run = run_by_game.get(game_id)
        if not run:
            continue
        number_of_levels = int(run.get("number_of_levels") or 0)
        actions_per_level = [0] * number_of_levels
        for row in read_jsonl(path):
            if row.get("type") != "action":
                continue
            total_actions += 1
            after = int(row.get("score") or 0)
            completed = bool(row.get("level_completed"))
            level_index = after - 1 if completed else after
            if 0 <= level_index < number_of_levels:
                actions_per_level[level_index] += 1
            action_number = int(row.get("action_num") or 0)
            batch_index = int(row.get("batch_index") or 1)
            analysis_step = int(row.get("analysis_step") or 0)
            at, basis = action_time(game_id, action_number, batch_index, analysis_step)
            if at is not None:
                timed_actions.append(at)
            if at is None:
                if completed:
                    untimed += 1
                continue
            if not completed:
                continue
            game_score = live_game_score(run, actions_per_level, after)
            completions.append(
                {
                    "at": at,
                    "gameId": game_id,
                    "action": action_number,
                    "level": after,
                    "gameScore": game_score,
                    "timestampBasis": basis,
                }
            )

    completions.sort(key=lambda row: (row["at"], row["gameId"], row["action"]))
    timed_actions.sort()
    game_scores: dict[str, float] = {}
    points = [
        {
            "at": iso(started),
            "elapsedSeconds": 0.0,
            "cumulativeActions": 0,
            "meanScore": 0.0,
            "kind": "start",
        }
    ]
    for row in completions:
        game_scores[row["gameId"]] = float(row["gameScore"])
        mean_score = sum(game_scores.values()) / game_count
        points.append(
            {
                "at": iso(row["at"]),
                "elapsedSeconds": round((row["at"] - started).total_seconds(), 3),
                "cumulativeActions": bisect_right(timed_actions, row["at"]),
                "meanScore": round(mean_score, 9),
                "kind": "level_completion",
                "gameId": row["gameId"],
                "action": row["action"],
                "level": row["level"],
                "gameScore": round(float(row["gameScore"]), 9),
                "timestampBasis": row["timestampBasis"],
            }
        )

    final_mean = sum(float(run.get("final_score") or 0.0) for run in run_by_game.values()) / game_count
    points.append(
        {
            "at": iso(ended),
            "elapsedSeconds": round((ended - started).total_seconds(), 3),
            "cumulativeActions": total_actions,
            "meanScore": round(final_mean, 9),
            "kind": "end",
        }
    )
    return {
        "points": points,
        "completionEvents": len(completions),
        "untimedCompletions": untimed,
        "finalMeanScore": round(final_mean, 9),
        "finalActions": total_actions,
        "timedActions": len(timed_actions),
        "actionTimestampCoverage": round(len(timed_actions) / total_actions, 6) if total_actions else 1.0,
        "timestampNote": (
            "Score changes are placed at the generating model-call start. "
            "Reviewed-theme runs use exact injection timestamps; older runs use transcript/model-call reconstruction. "
            "The action axis counts every environment action at that same generating-call timestamp."
        ),
    }


def parse_process_metrics(path: Path, topology: dict[str, dict]) -> list[dict]:
    if not path.exists():
        return []
    samples: list[dict] = []
    current: dict | None = None
    process_re = re.compile(
        r"^\s*(\d+)\s+(\d+)\s+([0-9.]+)\s+([0-9.]+)\s+(\d+)\s+(\d+)\s+\S+\s+(.+)$"
    )
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("# sampled_at "):
            stamp = parse_iso(raw.removeprefix("# sampled_at ").strip())
            if stamp:
                current = {"at": iso(stamp), "processes": []}
                samples.append(current)
            continue
        if current is None:
            continue
        match = process_re.match(raw)
        if not match:
            continue
        command = match.group(7)
        port_match = re.search(r"--port\s+(\d+)", command)
        port = port_match.group(1) if port_match else None
        resource = topology.get(port or "") or {
            "label": "Collector" if "sidecar.py" in command else "Process",
            "cores": "scheduler",
        }
        current["processes"].append(
            {
                "pid": int(match.group(1)),
                "currentLogicalCpu": int(match.group(2)),
                "cpuPercent": float(match.group(3)),
                "memoryPercent": float(match.group(4)),
                "rssMiB": round(int(match.group(5)) / 1024, 1),
                "label": resource["label"],
                "cores": resource["cores"],
                "port": int(port) if port else None,
            }
        )
    return [sample for sample in samples if sample["processes"]]


def main_agent_events(out_dir: Path, anchor: datetime) -> list[dict]:
    overview = read_json(out_dir / "run-overview.json")
    events: list[dict] = []
    for game_index, game in enumerate(overview.get("games", [])):
        step_index = 0
        while True:
            path = out_dir / f"game-{game_index}-step-{step_index}.json"
            if not path.exists():
                break
            payload = read_json(path)
            step = payload.get("step") or {}
            if step.get("stepKind") == "turn" and step.get("traceTimestamp"):
                at = clock_on_run_date(str(step["traceTimestamp"]), anchor)
                if at is not None:
                    exact = bool(step.get("traceInputExact") or (step.get("context") or {}).get("hasExactModelContext"))
                    events.append(
                        {
                            "id": f"main-{game_index}-{step_index}",
                            "lane": "main-model",
                            "kind": "main_call",
                            "start": iso(at),
                            "end": iso(at + timedelta(seconds=1)),
                            "instant": True,
                            "label": f"{game.get('display_name') or game.get('game_id')} · {step.get('title') or f'Step {step_index + 1}'}",
                            "status": "recorded",
                            "resource": "Qwen3.8-27B-FP8 · GPU inference queue",
                            "cores": "GPU-bound; host CPU affinity was not recorded",
                            "gameId": game.get("game_id"),
                            "gameIndex": game_index,
                            "stepIndex": step_index,
                            "score": step.get("score"),
                            "level": step.get("level"),
                            "action": step.get("actionDisplay"),
                            "contextExact": exact,
                            "contextProvenance": "exact saved request" if exact else "cumulative transcript reconstruction",
                            "timestampBasis": step.get("traceTimestampBasis"),
                            "detail": {"type": "game_step", "gameIndex": game_index, "stepIndex": step_index},
                        }
                    )
            step_index += 1
    return events


def sidecar_event(row: dict, *, kind: str, lane: str, label: str, resource: str, cores: str) -> dict | None:
    started = parse_iso(row.get("started_at"))
    completed = parse_iso(row.get("completed_at")) or started
    if started is None:
        return None
    slot = row.get("slot")
    return {
        "id": f"{kind}-{slot}-{int(started.timestamp() * 1000)}",
        "lane": lane,
        "kind": kind,
        "start": iso(started),
        "end": iso(completed or started),
        "instant": False,
        "label": label,
        "status": "error" if row.get("parse_error") or row.get("overflow_errors") else "completed",
        "resource": resource,
        "cores": cores,
        "durationSeconds": row.get("duration_seconds"),
        "serverUrl": row.get("server_url"),
        "games": row.get("games") or [],
        "frames": row.get("frames") or [],
        "themes": row.get("themes") or [],
        "promptChars": row.get("prompt_chars") or len(str(row.get("prompt") or "")),
        "requestMessages": row.get("request_messages"),
        "historyTurnsBefore": row.get("history_turns_before"),
        "historyTurnsAfter": row.get("history_turns_after"),
        "fifoEvictedTurns": row.get("fifo_evicted_turns"),
        "overflowErrors": row.get("overflow_errors") or [],
        "finishReason": row.get("finish_reason"),
        "usage": usage_summary(row),
        "detail": {
            "type": "inline_call",
            "input": str(row.get("prompt") or ""),
            "output": str(row.get("raw_response") or ""),
        },
    }


def export_run(run_dir: Path) -> None:
    artifact_root = run_dir / "runs" if (run_dir / "runs" / "benchmark.json").exists() else run_dir
    benchmark = read_json(artifact_root / "benchmark.json")
    started = parse_iso(benchmark.get("start_time"))
    ended = parse_iso(benchmark.get("end_time"))
    if started is None or ended is None:
        raise RuntimeError(f"Missing benchmark times in {artifact_root}")

    out_dir = OUT_BASE / run_dir.name
    events = main_agent_events(out_dir, started)
    main_events = list(events)
    lanes = [
        {
            "id": "main-model",
            "label": "Main agent",
            "resource": "Qwen3.8-27B-FP8 · GPU",
            "cores": "GPU inference queue",
            "group": "gameplay",
        }
    ]
    topology: dict[str, dict] = {}
    metrics_path: Path | None = None

    shadow = run_dir / "shadow-frame-themes"
    reviewed = run_dir / "reviewed-themes"
    if shadow.exists():
        metrics_path = shadow / "process-metrics.log"
        topology["1235"] = {"label": "Shared sidecar server", "cores": "CPU 28–47"}
        for slot in range(4):
            lane = f"sidecar-{slot}"
            lanes.append(
                {
                    "id": lane,
                    "label": f"Theme slot {slot}",
                    "resource": "shared Qwen3.6-35B-A3B server",
                    "cores": "CPU 28–47 shared · 5 generation threads/slot",
                    "group": "sidecar",
                }
            )
        for row in read_jsonl(shadow / "slot-responses.jsonl"):
            slot = int(row.get("slot", 0))
            event = sidecar_event(
                row,
                kind="sidecar_observer",
                lane=f"sidecar-{slot}",
                label=f"Theme synthesis · slot {slot}",
                resource="Qwen3.6-35B-A3B · shared llama.cpp server",
                cores="CPU 28–47 shared · 5 generation threads/slot",
            )
            if event:
                events.append(event)

    if reviewed.exists():
        metrics_path = reviewed / "process-metrics.log"
        core_sets = ["28–31", "32–35", "36–39", "40–43", "44–47"]
        for slot, cores in enumerate(core_sets):
            role = "Reviewer" if slot == 4 else f"Observer {slot}"
            topology[str(1240 + slot)] = {"label": role, "cores": f"CPU {cores}"}
            lanes.append(
                {
                    "id": f"sidecar-{slot}",
                    "label": role,
                    "resource": "Qwen3.6-35B-A3B · independent server",
                    "cores": f"CPU {cores} · 4 threads",
                    "group": "sidecar",
                }
            )
        lanes.append(
            {
                "id": "theme-injection",
                "label": "Ledger → prompt",
                "resource": "gameplay prompt builder",
                "cores": "main harness process",
                "group": "influence",
            }
        )
        for filename, kind in (("observer-responses.jsonl", "sidecar_observer"), ("reviewer-responses.jsonl", "sidecar_reviewer")):
            for row in read_jsonl(reviewed / filename):
                slot = int(row.get("slot", 4 if kind == "sidecar_reviewer" else 0))
                role = "Reviewer dedup/publish" if kind == "sidecar_reviewer" else f"Observer {slot} theme extraction"
                event = sidecar_event(
                    row,
                    kind=kind,
                    lane=f"sidecar-{slot}",
                    label=role,
                    resource="Qwen3.6-35B-A3B · independent llama.cpp server",
                    cores=f"CPU {core_sets[slot]} · 4 threads",
                )
                if event:
                    events.append(event)
        for index, row in enumerate(read_jsonl(reviewed / "gameplay-theme-injections.jsonl")):
            at = parse_iso(row.get("recorded_at"))
            if at is None:
                continue
            game_id = reviewed_game_id(row)
            events.append(
                {
                    "id": f"inject-{index}",
                    "lane": "theme-injection",
                    "kind": "theme_injection",
                    "start": iso(at),
                    "end": iso(at + timedelta(milliseconds=250)),
                    "instant": True,
                    "label": f"{game_id or 'unknown game'} · action {row.get('action')} · ledger r{row.get('ledger_revision')}",
                    "status": row.get("status") or "injected",
                    "resource": "reviewed theme ledger → main-agent user prompt",
                    "cores": "main harness process",
                    "gameId": game_id or None,
                    "action": row.get("action"),
                    "ledgerRevision": row.get("ledger_revision"),
                    "ledgerUpdatedAt": row.get("ledger_updated_at"),
                    "injectedThemeIds": row.get("injected_theme_ids") or [],
                    "promptBlockChars": row.get("prompt_block_chars"),
                    "promptBlockSha256": row.get("prompt_block_sha256"),
                    "detail": {"type": "metadata", "record": row},
                }
            )

    events.sort(key=lambda event: (event["start"], event["lane"], event["id"]))
    samples = parse_process_metrics(metrics_path, topology) if metrics_path else []
    payload = {
        "schemaVersion": 1,
        "run": run_dir.name,
        "title": "Execution trace",
        "startedAt": iso(started),
        "endedAt": iso(ended),
        "durationSeconds": round((ended - started).total_seconds(), 3),
        "contextPolicy": {
            "exactWhenRequestLogExists": True,
            "fallback": "Cumulative transcript reconstruction; model-side trimming and retention cannot be proven for this historical archive.",
        },
        "lanes": lanes,
        "events": events,
        "processSamples": samples,
        "scoreCurve": score_curve(benchmark, artifact_root, started, ended, main_events, reviewed),
        "counts": {
            "mainCalls": sum(event["kind"] == "main_call" for event in events),
            "sidecarCalls": sum(event["kind"].startswith("sidecar_") for event in events),
            "themeInjections": sum(event["kind"] == "theme_injection" for event in events),
            "processSamples": len(samples),
        },
    }
    target = out_dir / "run-timeline.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{run_dir.name}: {len(events)} events, {len(samples)} samples -> {target}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        export_run(Path(arg))
