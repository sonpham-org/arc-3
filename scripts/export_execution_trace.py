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


def world_model_block(step: dict) -> tuple[int, str] | None:
    """Return the exact curator ledger block captured in a gameplay request.

    Historical curator logs intentionally retained compact call metadata rather
    than the full prompt/response.  Exact gameplay request logs *do* retain the
    injected replacement ledger, so use the first captured request for each
    revision as the curator call's observable output.
    """
    context = step.get("context") if isinstance(step.get("context"), dict) else {}
    for section in context.get("sections") or []:
        if section.get("source") != "request":
            continue
        content = str(section.get("content") or "")
        start = content.find("World-model priors synthesized from other games")
        if start < 0:
            continue
        end_marker = "End of synthesized cross-game world models."
        end = content.find(end_marker, start)
        if end < 0:
            continue
        block = content[start : end + len(end_marker)].strip()
        revision_match = re.search(r"Ledger revision\s+(\d+)", block)
        if revision_match:
            return int(revision_match.group(1)), block
    return None


def section_phase(section: dict) -> str:
    """Map a saved context section onto the four trace colors.

    The exporter deliberately records composition, not synthetic token timing.
    A tool result is new model input; only an emitted tool invocation is orange.
    """
    label = str(section.get("label") or "").upper()
    kind = str(section.get("kind") or "").lower()
    if "COMPACT" in label or kind in {"compact", "compaction"}:
        return "compact"
    if "TOOL CALL" in label or kind == "tool_call":
        return "tool_call"
    if label.startswith(("THINKING", "ASSISTANT")) or kind == "reasoning":
        return "reasoning"
    return "input"


def call_phase_summary(step: dict) -> list[dict]:
    """Return ordered character-weighted phases for a gameplay turn.

    Exact request sections are counted once as input.  Generated transcript
    sections are taken only after the last user prompt so historical reasoning
    is not mislabelled as work performed by the selected call.
    """
    context = step.get("context") if isinstance(step.get("context"), dict) else {}
    local = step.get("localContext") if isinstance(step.get("localContext"), dict) else {}
    request_sections = [
        section
        for section in (context.get("sections") or [])
        if section.get("source") == "request"
    ]
    local_sections = list(local.get("sections") or [])
    last_user = max(
        (index for index, section in enumerate(local_sections) if str(section.get("label") or "").upper().startswith("USER PROMPT")),
        default=-1,
    )
    generated_sections = local_sections[last_user + 1 :] if last_user >= 0 else []
    ordered: list[tuple[str, str, int]] = []
    if request_sections:
        ordered.append(
            (
                "input",
                "Request context",
                sum(len(str(section.get("content") or "")) for section in request_sections),
            )
        )
    elif last_user >= 0:
        ordered.append(
            (
                "input",
                "Request context",
                sum(len(str(section.get("content") or "")) for section in local_sections[: last_user + 1]),
            )
        )
    for section in generated_sections:
        ordered.append(
            (
                section_phase(section),
                str(section.get("label") or "Model section"),
                len(str(section.get("content") or "")),
            )
        )
    collapsed: list[dict] = []
    for phase, label, chars in ordered:
        chars = max(1, chars)
        if collapsed and collapsed[-1]["phase"] == phase:
            collapsed[-1]["charCount"] += chars
            collapsed[-1]["sectionCount"] += 1
            if label not in collapsed[-1]["labels"] and len(collapsed[-1]["labels"]) < 4:
                collapsed[-1]["labels"].append(label)
        else:
            collapsed.append(
                {
                    "phase": phase,
                    "charCount": chars,
                    "sectionCount": 1,
                    "labels": [label],
                }
            )
    return collapsed


def gameplay_concurrency(run_dir: Path, game_count: int) -> int:
    """Read the requested worker count without inventing idle lanes for archives."""
    for path in sorted(run_dir.glob("LAUNCH_STATE*.json")):
        try:
            state = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        candidates = [
            state.get("gameplay_concurrency"),
            (state.get("gameplay") or {}).get("concurrency") if isinstance(state.get("gameplay"), dict) else None,
            (state.get("gameplay_fixed") or {}).get("concurrency") if isinstance(state.get("gameplay_fixed"), dict) else None,
        ]
        for candidate in candidates:
            if candidate is not None and int(candidate) > 0:
                return int(candidate)
    return max(1, game_count)


def assign_gameplay_slots(benchmark: dict, started: datetime, ended: datetime, concurrency: int) -> tuple[dict[str, int], list[list[str]]]:
    """Reconstruct stable worker slots from non-overlapping game intervals."""
    intervals: list[tuple[datetime, datetime, str]] = []
    for run in benchmark.get("game_runs", []):
        game_id = str(run.get("game_id") or "")
        if not game_id:
            continue
        game_started = parse_iso(run.get("started_at")) or started
        game_ended = parse_iso(run.get("ended_at"))
        wallclocks = [
            float(row.get("wallclock_seconds"))
            for row in run.get("history", [])
            if row.get("wallclock_seconds") is not None
        ]
        if game_ended is None and wallclocks:
            game_ended = game_started + timedelta(seconds=max(wallclocks))
        intervals.append((game_started, game_ended or ended, game_id))
    intervals.sort(key=lambda row: (row[0], row[2]))
    slot_ends = [started - timedelta(seconds=1) for _ in range(concurrency)]
    slot_games: list[list[str]] = [[] for _ in range(concurrency)]
    mapping: dict[str, int] = {}
    for game_started, game_ended, game_id in intervals:
        available = [index for index, slot_end in enumerate(slot_ends) if slot_end <= game_started]
        if available:
            slot = available[0]
        else:
            # More overlapping games than the recorded concurrency is data drift;
            # preserve every game visibly instead of silently merging calls.
            slot = len(slot_ends)
            slot_ends.append(started - timedelta(seconds=1))
            slot_games.append([])
        mapping[game_id] = slot
        slot_games[slot].append(game_id)
        slot_ends[slot] = max(slot_ends[slot], game_ended)
    return mapping, slot_games


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


def action_pace_points(
    timed_actions: list[datetime],
    started: datetime,
    ended: datetime,
    total_actions: int,
    sample_seconds: int = 60,
    window_seconds: int = 600,
) -> list[dict]:
    """Sample cumulative actions and a trailing action rate on the run clock."""
    duration = max(0.0, (ended - started).total_seconds())
    bounded = sorted(at for at in timed_actions if started <= at <= ended)
    offsets = [float(value) for value in range(0, int(duration), sample_seconds)]
    if not offsets or offsets[-1] != duration:
        offsets.append(duration)

    points: list[dict] = []
    for elapsed in offsets:
        at = started + timedelta(seconds=elapsed)
        cumulative = bisect_right(bounded, at)
        window_start = max(started, at - timedelta(seconds=window_seconds))
        window_minutes = (at - window_start).total_seconds() / 60.0
        in_window = cumulative - bisect_right(bounded, window_start)
        rate = in_window / window_minutes if window_minutes > 0 else 0.0
        if elapsed == duration:
            cumulative = total_actions
        points.append(
            {
                "at": iso(at),
                "elapsedSeconds": round(elapsed, 3),
                "cumulativeActions": cumulative,
                "actionsPerMinute": round(rate, 6),
                "kind": "start" if elapsed == 0 else "end" if elapsed == duration else "sample",
            }
        )
    return points


def score_curve(
    benchmark: dict,
    artifact_root: Path,
    started: datetime,
    ended: datetime,
    main_events: list[dict],
    influence_dir: Path,
) -> dict:
    """Build the cross-game mean score as a timestamped step function.

    Reviewed-theme runs use the exact prompt-injection clock.  Other archived
    runs use the already-exported model-call timestamp for the matching
    ``analysis_step``.  A completion emitted inside a previously generated
    action batch inherits that batch's call-start timestamp.
    """
    run_by_game = {str(run.get("game_id")): run for run in benchmark.get("game_runs", [])}
    game_count = max(1, len(run_by_game))
    token_events: list[tuple[datetime, int]] = []
    game_call_completions: dict[str, list[datetime | None]] = {}
    for game_id, run in run_by_game.items():
        game_started = parse_iso(run.get("started_at")) or started
        call_completions: list[datetime | None] = []
        for history_row in run.get("history", []):
            wallclock = history_row.get("wallclock_seconds")
            completed_at = game_started + timedelta(seconds=float(wallclock)) if wallclock is not None else None
            call_completions.append(completed_at)
            generated = int(history_row.get("generated_tokens") or 0)
            if completed_at is not None and generated > 0:
                token_events.append((completed_at, generated))
        game_call_completions[game_id] = call_completions
    token_events.sort(key=lambda item: item[0])
    token_times = [item[0] for item in token_events]
    token_prefix = [0]
    for _, generated in token_events:
        token_prefix.append(token_prefix[-1] + generated)
    final_generated_tokens = token_prefix[-1]

    def generated_tokens_at(at: datetime) -> int:
        return token_prefix[bisect_right(token_times, at)]

    main_times: dict[tuple[str, int], datetime] = {}
    for event in main_events:
        game_id = str(event.get("gameId") or "")
        step_index = event.get("stepIndex")
        at = parse_iso(event.get("start"))
        if game_id and step_index is not None and at is not None:
            main_times[(game_id, int(step_index))] = at

    injections: dict[str, list[tuple[int, datetime]]] = {}
    injection_path = influence_dir / "gameplay-theme-injections.jsonl"
    if not injection_path.exists():
        injection_path = influence_dir / "gameplay-injections.jsonl"
    for row in read_jsonl(injection_path):
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
            batch_start = action_number - batch_index + 1
            at, basis = action_time(game_id, action_number, batch_index, analysis_step)
            completions_for_game = game_call_completions.get(game_id, [])
            completed_at = completions_for_game[batch_start - 1] if 0 < batch_start <= len(completions_for_game) else at
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
                    "completedAt": completed_at or at,
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
    token_completions = sorted(completions, key=lambda row: (row["completedAt"], row["gameId"], row["action"]))
    token_game_scores: dict[str, float] = {}
    token_points = [
        {
            "at": iso(started),
            "elapsedSeconds": 0.0,
            "cumulativeGeneratedTokens": 0,
            "meanScore": 0.0,
            "kind": "start",
        }
    ]
    for row in token_completions:
        token_game_scores[row["gameId"]] = float(row["gameScore"])
        token_points.append(
            {
                "at": iso(row["completedAt"]),
                "elapsedSeconds": round((row["completedAt"] - started).total_seconds(), 3),
                "cumulativeGeneratedTokens": generated_tokens_at(row["completedAt"]),
                "meanScore": round(sum(token_game_scores.values()) / game_count, 9),
                "kind": "level_completion",
                "gameId": row["gameId"],
                "action": row["action"],
                "level": row["level"],
                "gameScore": round(float(row["gameScore"]), 9),
                "timestampBasis": "exact benchmark call-completion wallclock",
            }
        )
    token_points.append(
        {
            "at": iso(ended),
            "elapsedSeconds": round((ended - started).total_seconds(), 3),
            "cumulativeGeneratedTokens": final_generated_tokens,
            "meanScore": round(final_mean, 9),
            "kind": "end",
        }
    )
    pace_points = action_pace_points(timed_actions, started, ended, total_actions)
    return {
        "points": points,
        "tokenPoints": token_points,
        "actionPoints": pace_points,
        "actionRateWindowSeconds": 600,
        "completionEvents": len(completions),
        "untimedCompletions": untimed,
        "finalMeanScore": round(final_mean, 9),
        "finalActions": total_actions,
        "timedActions": len(timed_actions),
        "finalGeneratedTokens": final_generated_tokens,
        "tokenEvents": len(token_events),
        "actionTimestampCoverage": round(len(timed_actions) / total_actions, 6) if total_actions else 1.0,
        "timestampNote": (
            "Score changes are placed at the generating model-call start. "
            "Reviewed-theme runs use exact injection timestamps; older runs use transcript/model-call reconstruction. "
            "The action axis counts every environment action at that same generating-call timestamp."
        ),
        "tokenNote": (
            "The generated-token axis uses exact per-call generated-token counts from benchmark history, "
            "placed at each call's recorded completion wallclock. Batched actions inherit the completion "
            "of the model call that generated their batch."
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


def main_agent_events(out_dir: Path, anchor: datetime, benchmark: dict) -> tuple[list[dict], dict[int, str]]:
    overview = read_json(out_dir / "run-overview.json")
    events: list[dict] = []
    curator_outputs: dict[int, str] = {}
    game_ends: dict[str, datetime] = {}
    game_token_completions: dict[str, list[tuple[datetime, int]]] = {}
    for run in benchmark.get("game_runs", []):
        game_id = str(run.get("game_id") or "")
        started_at = parse_iso(run.get("started_at")) or anchor
        ended_at = parse_iso(run.get("ended_at"))
        if game_id:
            completions: list[tuple[datetime, int]] = []
            for history_row in run.get("history") or []:
                generated_tokens = int(history_row.get("generated_tokens") or 0)
                wallclock_seconds = history_row.get("wallclock_seconds")
                if generated_tokens > 0 and wallclock_seconds is not None:
                    completions.append(
                        (started_at + timedelta(seconds=float(wallclock_seconds)), generated_tokens)
                    )
            game_token_completions[game_id] = sorted(completions)
        if game_id and ended_at is not None:
            game_ends[game_id] = ended_at
    for game_index, game in enumerate(overview.get("games", [])):
        step_index = 0
        call_index = 0
        while True:
            path = out_dir / f"game-{game_index}-step-{step_index}.json"
            if not path.exists():
                break
            payload = read_json(path)
            step = payload.get("step") or {}
            captured_block = world_model_block(step)
            if captured_block is not None:
                revision, block = captured_block
                curator_outputs.setdefault(revision, block)
            if step.get("stepKind") == "turn" and step.get("traceTimestamp"):
                at = clock_on_run_date(str(step["traceTimestamp"]), anchor)
                if at is not None:
                    game_id = str(game.get("game_id") or "")
                    completed_at = at + timedelta(seconds=1)
                    exact = bool(step.get("traceInputExact") or (step.get("context") or {}).get("hasExactModelContext"))
                    events.append(
                        {
                            "id": f"main-{game_index}-{step_index}",
                            "lane": f"game-{game_index}",
                            "kind": "main_call",
                            "start": iso(at),
                            "end": iso(completed_at),
                            "instant": False,
                            "label": f"{game.get('display_name') or game.get('game_id')} · {step.get('title') or f'Step {step_index + 1}'}",
                            "status": "recorded",
                            "resource": "Qwen3.8-27B-FP8 · GPU inference queue",
                            "cores": "GPU-bound; host CPU affinity was not recorded",
                            "gameId": game.get("game_id"),
                            "gameIndex": game_index,
                            "stepIndex": step_index,
                            "callIndex": call_index,
                            "score": step.get("score"),
                            "level": step.get("level"),
                            "action": step.get("actionDisplay"),
                            "contextExact": exact,
                            "contextProvenance": "exact saved request" if exact else "cumulative transcript reconstruction",
                            "timestampBasis": step.get("traceTimestampBasis"),
                            "durationSeconds": round((completed_at - at).total_seconds(), 3),
                            "phaseSummary": call_phase_summary(step),
                            "phaseProvenance": "Ordered saved context sections; widths are character-weighted composition, not token timestamps.",
                            "durationProvenance": "Next saved model-call start, or benchmark game end for the final call.",
                            "detail": {"type": "game_step", "gameIndex": game_index, "stepIndex": step_index},
                        }
                    )
                    call_index += 1
            step_index += 1
    by_game: dict[str, list[dict]] = {}
    for event in events:
        by_game.setdefault(str(event.get("gameId") or ""), []).append(event)
    for game_id, game_events in by_game.items():
        game_events.sort(key=lambda event: event["start"])
        token_completions = game_token_completions.get(game_id, [])
        token_index = 0
        for index, event in enumerate(game_events):
            event_start = parse_iso(event["start"]) or anchor
            next_start = parse_iso(game_events[index + 1]["start"]) if index + 1 < len(game_events) else game_ends.get(game_id)
            event_end = next_start if next_start is not None and next_start > event_start else event_start + timedelta(seconds=1)
            event["end"] = iso(event_end)
            event["durationSeconds"] = round((event_end - event_start).total_seconds(), 3)
            event_tokens = 0
            while token_index < len(token_completions) and token_completions[token_index][0] <= event_end + timedelta(seconds=2):
                completed_at, generated_tokens = token_completions[token_index]
                if completed_at >= event_start - timedelta(seconds=2):
                    event_tokens += generated_tokens
                token_index += 1
            if event_tokens:
                event["tokenCount"] = event_tokens
                event["tokenBasis"] = "exact benchmark generated-token count"
    return events, curator_outputs


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
    events, curator_outputs = main_agent_events(out_dir, started, benchmark)
    game_runs = list(benchmark.get("game_runs") or [])
    concurrency = gameplay_concurrency(run_dir, len(game_runs))
    game_to_slot, slot_games = assign_gameplay_slots(benchmark, started, ended, concurrency)
    model_info_path = run_dir / "model-info.json"
    model_info = read_json(model_info_path) if model_info_path.exists() else {}
    main_model = str(model_info.get("model_id") or "Qwen3.8-27B-FP8")
    quantization = str(model_info.get("quantization") or "GPU")
    for event in events:
        event["resource"] = f"{main_model} · {quantization} inference queue"
        game_id = str(event.get("gameId") or "")
        if game_id in game_to_slot:
            event["lane"] = f"gameplay-{game_to_slot[game_id]}"
    main_events = list(events)
    gameplay_lanes: list[dict] = []
    for slot, games in enumerate(slot_games):
        if len(games) == 1:
            label = f"Thread {slot + 1:02d} · {games[0]}"
        elif games:
            label = f"Thread {slot + 1:02d} · {len(games)} games"
        else:
            label = f"Thread {slot + 1:02d} · idle"
        gameplay_lanes.append(
            {
                "id": f"gameplay-{slot}",
                "label": label,
                "resource": f"{main_model} · {quantization}",
                "cores": "shared GPU inference queue",
                "group": "gameplay",
                "slot": slot,
                "games": games,
            }
        )
    lanes: list[dict] = []
    topology: dict[str, dict] = {}
    metrics_path: Path | None = None

    shadow = run_dir / "shadow-frame-themes"
    reviewed = run_dir / "reviewed-themes"
    curator = run_dir / "curator"
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
            lane = f"gameplay-{game_to_slot[game_id]}" if game_id in game_to_slot else "theme-injection"
            if lane == "theme-injection" and not any(item["id"] == lane for item in lanes):
                lanes.append(
                    {
                        "id": lane,
                        "label": "Ledger → prompt",
                        "resource": "gameplay prompt builder",
                        "cores": "main harness process",
                        "group": "influence",
                    }
                )
            events.append(
                {
                    "id": f"inject-{index}",
                    "lane": lane,
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

    if curator.exists():
        health_path = curator / "health.json"
        health = read_json(health_path) if health_path.exists() else {}
        curator_mode = str(health.get("mode") or "themes")
        curator_label = "World-model curator" if curator_mode == "world_models" else "Theme curator"
        injection_kind = "world_model_injection" if curator_mode == "world_models" else "theme_injection"
        lanes.append(
            {
                "id": "nvfp4-curator",
                "label": curator_label,
                "resource": f"{main_model} · shared persistent request stream",
                "cores": "shared GPU inference queue · asynchronous single-flight",
                "group": "curator",
                "games": [],
            }
        )
        for index, row in enumerate(read_jsonl(curator / "curator-requests.jsonl")):
            if row.get("event") == "request":
                continue
            started_at = parse_iso(row.get("started_at"))
            completed_at = parse_iso(row.get("completed_at") or row.get("failed_at")) or started_at
            if started_at is None or completed_at is None:
                continue
            status = "completed" if row.get("event") == "completed" else "error"
            revision = row.get("revision_after", row.get("revision_before"))
            revision_number = int(revision) if revision is not None else None
            request_summary = {
                "mode": row.get("mode"),
                "evidenceGames": row.get("evidence_games") or [],
                "evidenceCount": row.get("evidence_count"),
                "persistentMessageCount": row.get("persistent_message_count"),
                "promptChars": row.get("prompt_chars"),
                "ledgerRevisionBefore": row.get("revision_before"),
            }
            observable_output = curator_outputs.get(revision_number or -1)
            if observable_output is None:
                observable_output = json.dumps(
                    {
                        "ledgerRevisionAfter": row.get("revision_after"),
                        "ledgerEntryCount": row.get("entry_count"),
                        "ledgerHashBefore": row.get("ledger_hash_before"),
                        "ledgerHashAfter": row.get("ledger_hash_after"),
                        "finishReason": row.get("finish_reason"),
                        "error": row.get("error"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            events.append(
                {
                    "id": f"curator-{index}",
                    "lane": "nvfp4-curator",
                    "kind": "curator_synthesis",
                    "start": iso(started_at),
                    "end": iso(completed_at),
                    "instant": False,
                    "label": f"{curator_label} · ledger r{revision}",
                    "status": status,
                    "resource": f"{main_model} · shared persistent request stream",
                    "cores": "shared GPU inference queue · asynchronous single-flight",
                    "durationSeconds": row.get("wall_seconds"),
                    "games": row.get("evidence_games") or [],
                    "evidenceCount": row.get("evidence_count"),
                    "promptChars": row.get("prompt_chars"),
                    "persistentMessageCount": row.get("persistent_message_count"),
                    "ledgerRevisionBefore": row.get("revision_before"),
                    "ledgerRevisionAfter": row.get("revision_after"),
                    "ledgerEntryCount": row.get("entry_count"),
                    "ledgerHashBefore": row.get("ledger_hash_before"),
                    "ledgerHashAfter": row.get("ledger_hash_after"),
                    "finishReason": row.get("finish_reason"),
                    "usage": usage_summary(row),
                    "phaseSummary": [
                        {
                            "phase": "input",
                            "charCount": max(1, int(row.get("prompt_chars") or len(json.dumps(request_summary, ensure_ascii=False)))),
                            "sectionCount": 1,
                            "labels": ["Curator evidence + persistent ledger"],
                        },
                        {
                            "phase": "reasoning",
                            "charCount": max(1, len(observable_output)),
                            "sectionCount": 1,
                            "labels": ["Curator synthesis"],
                        },
                    ],
                    "phaseProvenance": "Character-weighted curator input/output composition; the historical logger retained exact call metadata but not the complete prompt body.",
                    "detail": {
                        "type": "curator_call",
                        "input": json.dumps(request_summary, ensure_ascii=False, indent=2),
                        "output": observable_output,
                        "inputProvenance": "Exact timestamped curator-call metadata; the historical logger did not retain the full synthesized prompt body.",
                        "outputProvenance": (
                            "Exact replacement ledger observed in the first saved gameplay request carrying this revision."
                            if revision_number in curator_outputs
                            else "Exact curator completion metadata; no downstream gameplay request captured this revision body."
                        ),
                        "record": row,
                    },
                }
            )
        for index, row in enumerate(read_jsonl(curator / "gameplay-injections.jsonl")):
            at = parse_iso(row.get("recorded_at"))
            if at is None:
                continue
            game_id = reviewed_game_id(row)
            lane = f"gameplay-{game_to_slot[game_id]}" if game_id in game_to_slot else "nvfp4-curator"
            events.append(
                {
                    "id": f"curator-inject-{index}",
                    "lane": lane,
                    "kind": injection_kind,
                    "start": iso(at),
                    "end": iso(at + timedelta(milliseconds=250)),
                    "instant": True,
                    "label": f"{game_id or 'unknown game'} · action {row.get('action')} · ledger r{row.get('ledger_revision')}",
                    "status": row.get("status") or "injected",
                    "resource": f"{curator_label.lower()} ledger → main-agent user prompt",
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

    lanes = (
        [lane for lane in lanes if lane.get("group") == "curator"]
        + [lane for lane in lanes if lane.get("group") == "sidecar"]
        + gameplay_lanes
        + [lane for lane in lanes if lane.get("group") == "influence"]
    )
    events.sort(key=lambda event: (event["start"], event["lane"], event["id"]))
    samples = parse_process_metrics(metrics_path, topology) if metrics_path else []
    payload = {
        "schemaVersion": 2,
        "run": run_dir.name,
        "title": "Execution trace",
        "startedAt": iso(started),
        "endedAt": iso(ended),
        "durationSeconds": round((ended - started).total_seconds(), 3),
        "topology": {
            "gameplayConcurrency": concurrency,
            "gameplayLaneCount": len(gameplay_lanes),
            "assignment": "Stable worker slots reconstructed from non-overlapping benchmark game intervals.",
            "curatorFirst": any(lane.get("group") == "curator" for lane in lanes),
        },
        "contextPolicy": {
            "exactWhenRequestLogExists": True,
            "fallback": "Cumulative transcript reconstruction; model-side trimming and retention cannot be proven for this historical archive.",
        },
        "lanes": lanes,
        "events": events,
        "processSamples": samples,
        "scoreCurve": score_curve(
            benchmark,
            artifact_root,
            started,
            ended,
            main_events,
            reviewed if reviewed.exists() else curator,
        ),
        "counts": {
            "mainCalls": sum(event["kind"] == "main_call" for event in events),
            "sidecarCalls": sum(
                event["kind"].startswith("sidecar_") or event["kind"] == "curator_synthesis"
                for event in events
            ),
            "curatorCalls": sum(event["kind"] == "curator_synthesis" for event in events),
            "themeInjections": sum(event["kind"] == "theme_injection" for event in events),
            "worldModelInjections": sum(event["kind"] == "world_model_injection" for event in events),
            "processSamples": len(samples),
        },
    }
    target = out_dir / "run-timeline.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{run_dir.name}: {len(events)} events, {len(samples)} samples -> {target}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        export_run(Path(arg))
