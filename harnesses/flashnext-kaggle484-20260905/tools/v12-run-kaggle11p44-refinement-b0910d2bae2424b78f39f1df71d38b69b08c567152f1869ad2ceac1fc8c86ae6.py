"""Locked ARC3 Kaggle 11.44 RTDv12 runner with routed Refinement.

This preserves the exact champion benchmark, games, tools, sampling, curator,
scorer, post-unpickle 22-worker/6,480-second lock, and 25-game suite. The sole
reasoning delta is the previously tested Refinement policy: on observably hard
turns, one medium draft and one separate medium critic feed one xhigh revision.
Auxiliary requests are text-only and cannot act. Every routing and refinement
decision is written to the game's artifact directory.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import json
import os
import pickle
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


BUNDLE = Path("/opt/arc3/bundle")
WORKING = Path("/opt/arc3/work")
ENV_FILES = "/opt/arc3/environment_files"
WORKING.mkdir(parents=True, exist_ok=True)

os.environ["MPLBACKEND"] = "Agg"
os.environ["TAAF_RUN_AS_SUBMISSION"] = "0"
os.environ["TAAF_MINIMAL_DIAGNOSTICS"] = "0"
os.environ["ONLY_RESET_LEVELS"] = "true"
os.environ.setdefault("RECORDINGS_DIR", str(WORKING / "server_recording"))

for repo in sorted((BUNDLE / "src").iterdir(), reverse=True):
    for candidate in (repo / "src", repo):
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))


POLICY = os.environ.get("ARC3_REASONING_POLICY", "").strip().lower()
if POLICY != "refinement":
    raise RuntimeError(
        f"This locked runner requires ARC3_REASONING_POLICY='refinement'; got {POLICY!r}"
    )

POLICY_PROMPTS = {"refinement": ""}

# Bound multi-request work across all games in this runner process. Advisors
# are text-only and never receive tools or ownership of a game session.
_MULTIPASS_POLICIES = {"refinement"}
_MULTIPASS_SLOTS = threading.BoundedSemaphore(4)
_ADVISOR_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="arc3-medium-advisor",
)
_ADVISOR_MAX_TOKENS = 900
_REFINEMENT_DRAFT_MAX_TOKENS = 1100
_REFINEMENT_CRITIC_MAX_TOKENS = 800
_FINAL_JUDGE_MAX_TOKENS = 3300
_AUX_TEXT_CHAR_LIMIT = 7000


from inference.agent import tool_agent as tool_agent_module  # noqa: E402


_EFFORT_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "arc3_reasoning_effort", default="medium"
)
_original_payload_builder = tool_agent_module.build_chat_payload
_original_chat_completion = tool_agent_module.ToolAgent._chat_completion
_original_analyze = tool_agent_module.ToolAgent.analyze


def _plain_message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part).strip()
    return ""


def _compact_observation_packet(messages: list[dict[str, Any]]) -> str:
    """Return the newest text observation; images and old hidden traces stay out."""
    for message in reversed(messages):
        if str(message.get("role", "")).strip() == "user":
            text = _plain_message_text(message)
            if text:
                return text[-16000:]
    return "No textual observation packet was available."


def _bounded_response_text(message: dict[str, Any]) -> str:
    reasoning = tool_agent_module._extract_reasoning_text(message)
    content = tool_agent_module._normalize_message_content(message.get("content", ""))
    parts = [part.strip() for part in (reasoning, content) if part and part.strip()]
    text = "\n\n".join(parts).strip() or "(no usable proposal returned)"
    if len(text) > _AUX_TEXT_CHAR_LIMIT:
        omitted = len(text) - _AUX_TEXT_CHAR_LIMIT
        text = f"{text[:_AUX_TEXT_CHAR_LIMIT]}\n...[truncated {omitted} chars]"
    return text


def _append_policy_event(state_path: Path, filename: str, event: dict[str, Any]) -> None:
    path = state_path.parent / filename
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")


def _direct_completion(
    self: Any,
    messages: list[dict[str, Any]],
    *,
    effort: str,
    max_tokens: int,
    tools: list[dict[str, Any]] | None = None,
    request_timeout_seconds: float | None = None,
) -> Any:
    """Issue one bounded request without mutating ToolAgent-wide token limits."""
    payload = _original_payload_builder(
        provider=self._model.provider,
        model=self._model.model_id,
        messages=messages,
        max_tokens=max_tokens,
        temperature=tool_agent_module._LOCAL_ANALYZER_TEMPERATURE,
        top_p=tool_agent_module._LOCAL_ANALYZER_TOP_P,
        top_k=tool_agent_module._LOCAL_ANALYZER_TOP_K,
        thinking=True,
        tools=tools,
        tool_choice=tool_agent_module._request_tool_choice(tools),
        seed=tool_agent_module._LOCAL_ANALYZER_SEED,
    )
    template_kwargs = dict(payload.get("chat_template_kwargs") or {})
    template_kwargs.update(
        {
            "enable_thinking": True,
            "preserve_thinking": True,
            "reasoning_effort": effort,
        }
    )
    payload["chat_template_kwargs"] = template_kwargs
    response = tool_agent_module.requests.post(
        f"{self._model.base_url.rstrip('/')}/chat/completions",
        headers=self._headers(),
        json=payload,
        timeout=request_timeout_seconds if request_timeout_seconds is not None else self._timeout,
    )
    try:
        response.raise_for_status()
    except tool_agent_module.requests.HTTPError as exc:
        detail = response.text.strip()
        message = f"{exc}"
        if detail:
            message += f" | response: {detail}"
        raise tool_agent_module.requests.RequestException(message) from exc
    if getattr(response, "status_code", 200) >= 400:
        detail = response.text.strip()
        message = f"{response.status_code} Error"
        if detail:
            message += f" | response: {detail}"
        raise tool_agent_module.requests.RequestException(message)
    response_payload = response.json()
    choices = response_payload.get("choices", [])
    if not choices:
        raise tool_agent_module.requests.RequestException("server returned no choices")
    choice = choices[0]
    return tool_agent_module._ChatCompletionResult(
        message=choice.get("message", {}),
        finish_reason=str(choice.get("finish_reason", "") or ""),
        usage=response_payload.get("usage"),
    )


def _auxiliary_request(
    self: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    request_timeout_seconds: float | None,
) -> Any:
    return _direct_completion(
        self,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        effort="medium",
        max_tokens=max_tokens,
        tools=None,
        request_timeout_seconds=request_timeout_seconds,
    )


def _inject_deliberation(messages: list[dict[str, Any]], block: str) -> list[dict[str, Any]]:
    augmented = json.loads(json.dumps(messages))
    for index in range(len(augmented) - 1, -1, -1):
        message = augmented[index]
        if str(message.get("role", "")).strip() != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            message["content"] = f"{content.rstrip()}\n\n{block}"
        elif isinstance(content, list):
            content.append({"type": "text", "text": block})
        else:
            message["content"] = block
        return augmented
    augmented.append({"role": "user", "content": block})
    return augmented


def _build_advisor_judge_block(
    self: Any,
    packet: str,
    request_timeout_seconds: float | None,
) -> tuple[str | None, dict[str, Any]]:
    roles = (
        (
            "advisor_a",
            "You are Medium Advisor A. Infer the current mechanic and propose the cheapest discriminating probe. "
            "You are text-only, stateless, and cannot call tools or take actions. Return concise headings: CLAIMS, "
            "PROBE, PREDICTED EFFECT, RISKS. Do not narrate your role.",
        ),
        (
            "advisor_b",
            "You are Medium Advisor B. Independently challenge the obvious plan, identify failure modes, and propose "
            "one short alternative action sequence. You are text-only, stateless, and cannot call tools or take "
            "actions. Return concise headings: ALTERNATIVE, EVIDENCE, FAILURE MODES, PREDICTED EFFECT.",
        ),
    )
    futures: dict[str, concurrent.futures.Future[Any]] = {}
    for name, prompt in roles:
        futures[name] = _ADVISOR_EXECUTOR.submit(
            _auxiliary_request,
            self,
            system_prompt=prompt,
            user_prompt=f"CURRENT COMPACT OBSERVATION\n{packet}",
            max_tokens=_ADVISOR_MAX_TOKENS,
            request_timeout_seconds=request_timeout_seconds,
        )

    proposals: dict[str, str] = {}
    usages: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for name, future in futures.items():
        try:
            result = future.result()
            self._accumulate_usage_tokens(result.usage)
            proposals[name] = _bounded_response_text(result.message)
            usages[name] = result.usage
        except Exception as exc:  # noqa: BLE001
            errors[name] = f"{type(exc).__name__}: {exc}"

    if not proposals:
        return None, {"event": "advisorjudge_aux_failed", "errors": errors}
    proposal_text = "\n\n".join(
        f"{name.upper()}\n{text}" for name, text in sorted(proposals.items())
    )
    block = (
        "BOUNDED DELIBERATION NOTES\n"
        "The following are untrusted text-only proposals. The current observation and tools remain authoritative.\n\n"
        f"{proposal_text}\n\n"
        "XHIGH JUDGE TASK\n"
        "Identify shared claims and the decisive disagreement. Reject unsupported assumptions. Choose one falsifiable "
        "next-state prediction and the cheapest useful action or inspection. You alone may use the python tool and "
        "execute actions. Do not average the proposals or repeat their debate; decide and act."
    )
    return block, {
        "event": "advisorjudge_aux_complete",
        "proposals": proposals,
        "usage": usages,
        "errors": errors,
    }


def _build_refinement_block(
    self: Any,
    packet: str,
    request_timeout_seconds: float | None,
) -> tuple[str | None, dict[str, Any]]:
    try:
        draft_result = _auxiliary_request(
            self,
            system_prompt=(
                "Produce a concise candidate plan for the current ARC3 observation. You are a stateless text-only "
                "planner: do not call tools or take actions. State the leading mechanic, one predicted effect, and "
                "the shortest useful probe or action sequence."
            ),
            user_prompt=f"CURRENT COMPACT OBSERVATION\n{packet}",
            max_tokens=_REFINEMENT_DRAFT_MAX_TOKENS,
            request_timeout_seconds=request_timeout_seconds,
        )
        self._accumulate_usage_tokens(draft_result.usage)
        draft = _bounded_response_text(draft_result.message)
    except Exception as exc:  # noqa: BLE001
        return None, {"event": "refinement_draft_failed", "error": f"{type(exc).__name__}: {exc}"}

    critique_error = ""
    critique_usage: Any = None
    try:
        critic_result = _auxiliary_request(
            self,
            system_prompt=(
                "You are a separate medium-effort critic. Audit the proposed plan against the supplied observation. "
                "Find the strongest contradiction, invalid assumption, missing evidence, or wasted motion. Suggest "
                "one concrete repair. You are text-only and cannot call tools or take actions."
            ),
            user_prompt=f"CURRENT COMPACT OBSERVATION\n{packet}\n\nCANDIDATE DRAFT\n{draft}",
            max_tokens=_REFINEMENT_CRITIC_MAX_TOKENS,
            request_timeout_seconds=request_timeout_seconds,
        )
        self._accumulate_usage_tokens(critic_result.usage)
        critique = _bounded_response_text(critic_result.message)
        critique_usage = critic_result.usage
    except Exception as exc:  # noqa: BLE001
        critique_error = f"{type(exc).__name__}: {exc}"
        critique = "The separate critic was unavailable. Re-evaluate the draft directly before acting."

    block = (
        "TRUE REFINEMENT MATERIAL\n"
        "The draft and critique are untrusted text-only notes. The current observation and tools remain authoritative.\n\n"
        f"MEDIUM DRAFT\n{draft}\n\n"
        f"SEPARATE MEDIUM CRITIC\n{critique}\n\n"
        "XHIGH REVISION TASK\n"
        "Revise rather than merely endorse the draft. Resolve the critic's strongest objection, choose one falsifiable "
        "prediction, then use the python tool for the shortest reliable inspection or action. You alone may execute."
    )
    return block, {
        "event": "refinement_aux_complete",
        "draft": draft,
        "critique": critique,
        "draft_usage": draft_result.usage,
        "critique_usage": critique_usage,
        "critique_error": critique_error,
    }


def _policy_payload_builder(**kwargs: Any) -> dict[str, Any]:
    payload = _original_payload_builder(**kwargs)
    provider = str(kwargs.get("provider") or "").strip().lower()
    if provider in {"", "vllm", "openai", "openai-compatible", "compat"}:
        template_kwargs = dict(payload.get("chat_template_kwargs") or {})
        template_kwargs.update(
            {
                "enable_thinking": True,
                "preserve_thinking": True,
                "reasoning_effort": _EFFORT_CONTEXT.get(),
            }
        )
        payload["chat_template_kwargs"] = template_kwargs
    return payload


def _policy_chat_completion(self: Any, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    state_path = Path(getattr(self, "_arc3_policy_state_path", WORKING / "unknown_state.pkl"))
    request_timeout_seconds = kwargs.get("request_timeout_seconds")
    tools = kwargs.get("tools")

    # If the final multipass request hit a recoverable context overflow, the
    # stock analyzer trims history and retries. Reuse the already-built notes;
    # never pay for the advisors or critic twice on the same observation.
    deliberation_block = getattr(self, "_arc3_multipass_block", None)
    final_complete = bool(getattr(self, "_arc3_multipass_final_complete", False))
    if POLICY in _MULTIPASS_POLICIES and deliberation_block and not final_complete:
        augmented = _inject_deliberation(messages, deliberation_block)
        started = time.monotonic()
        result = _direct_completion(
            self,
            augmented,
            effort="xhigh",
            max_tokens=_FINAL_JUDGE_MAX_TOKENS,
            tools=tools,
            request_timeout_seconds=request_timeout_seconds,
        )
        self._arc3_multipass_final_complete = True
        self._arc3_reasoning_effort = "medium"
        _append_policy_event(
            state_path,
            "reasoning-deliberation.jsonl",
            {
                "event": "multipass_final_complete",
                "policy": POLICY,
                "action_num": getattr(self, "_arc3_policy_action_num", None),
                "analysis_step": getattr(self, "_arc3_policy_analysis_step", None),
                "effort": "xhigh",
                "max_tokens": _FINAL_JUDGE_MAX_TOKENS,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "finish_reason": result.finish_reason,
                "usage": result.usage,
            },
        )
        return result

    if POLICY in _MULTIPASS_POLICIES and bool(getattr(self, "_arc3_multipass_pending", False)):
        self._arc3_multipass_pending = False
        acquired = _MULTIPASS_SLOTS.acquire(blocking=False)
        if acquired:
            started = time.monotonic()
            try:
                packet = _compact_observation_packet(messages)
                if POLICY == "advisorjudge":
                    block, event = _build_advisor_judge_block(self, packet, request_timeout_seconds)
                else:
                    block, event = _build_refinement_block(self, packet, request_timeout_seconds)
                event.update(
                    {
                        "policy": POLICY,
                        "action_num": getattr(self, "_arc3_policy_action_num", None),
                        "analysis_step": getattr(self, "_arc3_policy_analysis_step", None),
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                )
                _append_policy_event(state_path, "reasoning-deliberation.jsonl", event)
                if block:
                    self._arc3_multipass_block = block
                    augmented = _inject_deliberation(messages, block)
                    result = _direct_completion(
                        self,
                        augmented,
                        effort="xhigh",
                        max_tokens=_FINAL_JUDGE_MAX_TOKENS,
                        tools=tools,
                        request_timeout_seconds=request_timeout_seconds,
                    )
                    self._arc3_multipass_final_complete = True
                    self._arc3_reasoning_effort = "medium"
                    _append_policy_event(
                        state_path,
                        "reasoning-deliberation.jsonl",
                        {
                            "event": "multipass_final_complete",
                            "policy": POLICY,
                            "action_num": getattr(self, "_arc3_policy_action_num", None),
                            "analysis_step": getattr(self, "_arc3_policy_analysis_step", None),
                            "effort": "xhigh",
                            "max_tokens": _FINAL_JUDGE_MAX_TOKENS,
                            "elapsed_seconds": round(time.monotonic() - started, 3),
                            "finish_reason": result.finish_reason,
                            "usage": result.usage,
                        },
                    )
                    return result
            finally:
                _MULTIPASS_SLOTS.release()
        else:
            _append_policy_event(
                state_path,
                "reasoning-deliberation.jsonl",
                {
                    "event": "multipass_skipped_capacity",
                    "policy": POLICY,
                    "action_num": getattr(self, "_arc3_policy_action_num", None),
                    "analysis_step": getattr(self, "_arc3_policy_analysis_step", None),
                    "fallback_effort": str(getattr(self, "_arc3_reasoning_effort", "xhigh")),
                },
            )

    effort = str(getattr(self, "_arc3_reasoning_effort", "medium"))
    token = _EFFORT_CONTEXT.set(effort)
    try:
        return _original_chat_completion(self, messages, **kwargs)
    finally:
        _EFFORT_CONTEXT.reset(token)


def _adaptive_effort(self: Any, action_num: int) -> tuple[str, list[str]]:
    """Route one analyzer turn using only state already visible to the harness."""
    reasons: list[str] = []
    summary = getattr(self, "_last_step_summary", None) or {}
    knowledge = getattr(self, "_summarized_knowledge", None) or {}

    if not summary:
        reasons.append("initial_or_unmodeled_turn")
    if summary.get("level_transition") or summary.get("game_over"):
        reasons.append("scene_reset_or_transition")

    if summary:
        streak = int(getattr(self, "_arc3_no_change_streak", 0))
        streak = 0 if summary.get("board_changed") else streak + 1
        self._arc3_no_change_streak = streak
        if streak >= 2:
            reasons.append("two_unproductive_turns")

    if not str(knowledge.get("goal_model", "")).strip():
        reasons.append("goal_unresolved")
    if not str(knowledge.get("current_plan", "")).strip():
        reasons.append("plan_unresolved")
    if len(str(knowledge.get("open_questions", "")).strip()) >= 160:
        reasons.append("material_open_questions")

    # A sparse checkpoint catches silently stale plans without making xhigh the default.
    try:
        if int(action_num) > 0 and int(action_num) % 12 == 0:
            reasons.append("periodic_plan_audit")
    except (TypeError, ValueError):
        pass

    return ("xhigh", reasons) if reasons else ("medium", ["stable_plan_execution"])


def _append_route_event(state_path: Path, event: dict[str, Any]) -> None:
    _append_policy_event(state_path, "reasoning-policy.jsonl", event)


def _policy_analyze(self: Any, state_path: Path, action_num: int, *args: Any, **kwargs: Any) -> Any:
    suffix = POLICY_PROMPTS[POLICY]
    if suffix and not getattr(self, "_arc3_policy_prompt_installed", False):
        self._system_prompt = f"{self._system_prompt.rstrip()}\n\nReasoning policy:\n{suffix}"
        self._arc3_policy_prompt_installed = True

    if POLICY == "adaptive" or POLICY in _MULTIPASS_POLICIES:
        effort, reasons = _adaptive_effort(self, action_num)
    else:
        effort, reasons = "medium", [f"fixed_{POLICY}_prompt"]
    self._arc3_reasoning_effort = effort
    self._arc3_policy_state_path = Path(state_path)
    self._arc3_policy_action_num = int(action_num)
    self._arc3_policy_analysis_step = kwargs.get("analysis_step")
    self._arc3_multipass_pending = POLICY in _MULTIPASS_POLICIES and effort == "xhigh"
    self._arc3_multipass_block = None
    self._arc3_multipass_final_complete = False

    _append_route_event(
        Path(state_path),
        {
            "policy": POLICY,
            "action_num": int(action_num),
            "analysis_step": kwargs.get("analysis_step"),
            "effort": effort,
            "reasons": reasons,
            "multipass_requested": bool(self._arc3_multipass_pending),
            "generated_tokens_before": int(getattr(self, "_session_generated_tokens", 0)),
            "history_messages": len(getattr(self, "_history_messages", [])),
        },
    )
    try:
        return _original_analyze(self, state_path, action_num, *args, **kwargs)
    finally:
        self._arc3_multipass_pending = False
        self._arc3_multipass_block = None
        self._arc3_multipass_final_complete = False


tool_agent_module.build_chat_payload = _policy_payload_builder
tool_agent_module.ToolAgent._chat_completion = _policy_chat_completion
tool_agent_module.ToolAgent.analyze = _policy_analyze


with open(BUNDLE / "deploy_target.pkl", "rb") as fh:
    target = pickle.load(fh)
target.actual_run_as_submission = False
target.is_competition_rerun = False

with open(BUNDLE / "benchmark_initial.pkl", "rb") as fh:
    bm = pickle.load(fh)
bm.job_dir = WORKING
bm.solver.max_runtime_s_per_game = float(os.environ["ARC3_MAX_RUNTIME_S_PER_GAME"])
bm.solver.concurrency = int(os.environ["ARC3_BENCHMARK_CONCURRENCY"])
bm.solver.save_request_logs = False
assert bm.solver.max_runtime_s_per_game == 6480.0
assert bm.solver.concurrency == 22
assert bm.solver.save_request_logs is False
assert os.environ["ARC3_ACTION_CAP"] == "14"
assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"
assert "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ
assert POLICY == "refinement"
print(
    "Kaggle 11.44 runtime lock: 22 workers, 6480 seconds/game, "
    "cap14, fixed30, reflection dormant, routed Refinement enabled, request logs off"
)

import arc_agi  # noqa: E402
import taaf.game_api  # noqa: E402

spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=ENV_FILES)
game_ids = [environment.game_id for environment in arcade.available_environments]
subset = os.environ.get("ARC3_GAME_SUBSET", "").strip()
if subset:
    wanted = {token.strip().lower() for token in subset.replace(",", " ").split() if token.strip()}
    game_ids = [game for game in game_ids if game[:4].lower() in wanted or game.lower() in wanted]
    print(f"[subset] ARC3_GAME_SUBSET={subset!r} -> {len(game_ids)} games: {game_ids}")
assert game_ids, f"no offline environments under {ENV_FILES}"
assert len(game_ids) == 25, f"exact champion Refinement arm requires 25 games, got {len(game_ids)}"
bm.games = [taaf.game_api.GameAPI(env_name=game, arcade_spec=spec) for game in game_ids]
bm.n_passes = 1
bm.game_weights = None
print(f"games: {len(bm.games)} | solver: {type(bm.solver).__name__} | reasoning_policy: {POLICY}")

# Preserve the exact champion's outer submission boundary. The per-game and
# 132-minute suite boundaries terminate these direct GCP evaluations earlier.
soft_end = datetime.now() + timedelta(hours=11, minutes=20)
asyncio.run(bm.run(soft_end_time=soft_end, runtime_environment=target, minimal_diagnostics=False))
print("V12 RUN COMPLETE")
