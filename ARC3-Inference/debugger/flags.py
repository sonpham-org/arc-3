"""The debugger's user-editable feature flag contract.

Every editable flag is applied in :func:`build_resume_request`. Keeping the
registry and request transformation together prevents decorative UI toggles
that do not change model behaviour.
"""
from __future__ import annotations

import copy
import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FlagSpec:
    id: str
    label: str
    default: bool
    group: str
    effect: str


FLAG_SPECS = (
    FlagSpec(
        "thinking",
        "Thinking",
        True,
        "Model",
        "Sets Qwen's enable_thinking chat-template argument.",
    ),
    FlagSpec(
        "memory",
        "Carried memory",
        True,
        "Context",
        "Keeps prior messages and the knowledge ledger; off forks from only the selected turn.",
    ),
    FlagSpec(
        "tools",
        "Python tool schema",
        True,
        "Model",
        "Sends the recorded tool definitions and automatic tool choice.",
    ),
    FlagSpec(
        "current_grid",
        "Current grid image",
        True,
        "Context",
        "Attaches the selected board image to the final user message.",
    ),
    FlagSpec(
        "transition_guidance",
        "Transition reminder",
        True,
        "Prompt",
        "Keeps the repeated instruction to distinguish gameplay changes from HUD-only changes.",
    ),
    FlagSpec(
        "strategy_guidance",
        "Strategy reminder",
        True,
        "Prompt",
        "Keeps the repeated compact inspect/search/act instruction.",
    ),
    FlagSpec(
        "mouse_guidance",
        "MOUSE reminder",
        True,
        "Prompt",
        "Keeps the per-turn integer row/column reminder when MOUSE is available.",
    ),
)

FLAG_BY_ID = {spec.id: spec for spec in FLAG_SPECS}

_LEDGER_RE = re.compile(
    r"\n?Knowledge ledger carried from earlier turns:.*?End of carried knowledge ledger\.\n?",
    flags=re.DOTALL | re.IGNORECASE,
)
_LEGACY_WORLD_MODEL_RE = re.compile(
    r"\n?Working world model carried from earlier turns:.*?end of world model\.\s*",
    flags=re.DOTALL | re.IGNORECASE,
)
_GUIDANCE = {
    "transition_guidance": (
        "Inspect the newest transition in Python and distinguish gameplay change from HUD-only change.",
        re.compile(
        r"^.*Inspect the newest transition in Python and distinguish gameplay change from HUD-only change\..*$",
        flags=re.MULTILINE,
        ),
    ),
    "strategy_guidance": (
        "Call `python` with compact inspection/search code and the revised required `world_model` ledger, "
        "then execute the shortest reliable valid action or batch via `action(actions)`. Stop on any terminal result.",
        re.compile(
        r"^.*Call `python` with compact inspection/search code.*?Stop on any terminal result\..*$",
        flags=re.MULTILINE,
        ),
    ),
    "mouse_guidance": (
        "If you use MOUSE, include integer row and col arguments.",
        re.compile(
        r"^.*If you use MOUSE, include integer row and col arguments\..*$",
        flags=re.MULTILINE,
        ),
    ),
}


def flag_manifest() -> list[dict[str, Any]]:
    return [{**asdict(spec), "editable": True} for spec in FLAG_SPECS]


def normalize_flags(raw: Any) -> dict[str, bool]:
    raw_flags = raw if isinstance(raw, dict) else {}
    unknown = sorted(set(raw_flags) - set(FLAG_BY_ID))
    if unknown:
        raise ValueError(f"Unknown debugger flag(s): {', '.join(unknown)}")
    return {
        spec.id: bool(raw_flags.get(spec.id, spec.default))
        for spec in FLAG_SPECS
    }


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    return "\n".join(
        str(part.get("text") or "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    )


def _map_message_text(message: dict[str, Any], transform: Any) -> dict[str, Any]:
    updated = copy.deepcopy(message)
    content = updated.get("content")
    if isinstance(content, str):
        updated["content"] = transform(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                part["text"] = transform(str(part.get("text") or ""))
    return updated


def _remove_images(message: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(message)
    content = updated.get("content")
    if isinstance(content, list):
        updated["content"] = [
            part
            for part in content
            if not (isinstance(part, dict) and part.get("type") in {"image_url", "input_image"})
        ]
    return updated


def _attach_current_grid(messages: list[dict[str, Any]], board_image: str) -> None:
    if not board_image.startswith("data:image/"):
        raise ValueError("boardImage must be an image data URL")
    user_index = next(
        (index for index in range(len(messages) - 1, -1, -1) if messages[index].get("role") == "user"),
        None,
    )
    if user_index is None:
        messages.append({"role": "user", "content": "Current grid image:"})
        user_index = len(messages) - 1
    text = _text_content(messages[user_index].get("content"))
    messages[user_index]["content"] = [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": board_image}},
    ]


def _fallback_messages(context: dict[str, Any]) -> list[dict[str, Any]]:
    system_prompt = str(context.get("systemPrompt") or "").strip()
    user_prompt = str(context.get("userPrompt") or "").strip()
    memory = str(context.get("memory") or "").strip()
    if memory:
        user_prompt = f"Recovered memory from the selected turn:\n{memory}\n\n{user_prompt}".strip()
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt or "Continue from this ARC game turn."})
    return messages


def _without_carried_memory(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    system = next((message for message in messages if message.get("role") == "system"), None)
    latest_user = next(
        (message for message in reversed(messages) if message.get("role") == "user"),
        {"role": "user", "content": "Continue from this ARC game turn."},
    )
    latest_user = _map_message_text(
        latest_user,
        lambda text: _LEGACY_WORLD_MODEL_RE.sub("\n", _LEDGER_RE.sub("\n", text)).strip(),
    )
    return [message for message in (system, latest_user) if message is not None]


def _ensure_user_guidance(messages: list[dict[str, Any]], text: str, pattern: re.Pattern[str]) -> None:
    user_index = next(
        (index for index in range(len(messages) - 1, -1, -1) if messages[index].get("role") == "user"),
        None,
    )
    if user_index is None:
        messages.append({"role": "user", "content": text})
        return
    current = _text_content(messages[user_index].get("content"))
    if pattern.search(current):
        return
    messages[user_index] = _map_message_text(
        messages[user_index],
        lambda value: f"{value.rstrip()}\n{text}".strip(),
    )


def build_resume_request(
    *,
    model: str,
    context: dict[str, Any],
    raw_flags: Any,
    settings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, bool]]:
    """Build one OpenAI-compatible request and return its normalized flags."""
    flags = normalize_flags(raw_flags)
    raw_messages = context.get("messages")
    messages = (
        copy.deepcopy([message for message in raw_messages if isinstance(message, dict)])
        if isinstance(raw_messages, list) and raw_messages
        else _fallback_messages(context)
    )
    messages = [_remove_images(message) for message in messages]

    if not flags["memory"]:
        messages = _without_carried_memory(messages)

    for flag_id, (guidance, pattern) in _GUIDANCE.items():
        if flags[flag_id]:
            _ensure_user_guidance(messages, guidance, pattern)
        else:
            messages = [
                _map_message_text(message, lambda text, rx=pattern: rx.sub("", text).strip())
                for message in messages
            ]

    board_image = str(context.get("boardImage") or "")
    if flags["current_grid"] and board_image:
        _attach_current_grid(messages, board_image)

    settings = settings if isinstance(settings, dict) else {}
    max_tokens = min(16_384, max(64, int(settings.get("maxTokens") or 4096)))
    temperature = min(2.0, max(0.0, float(settings.get("temperature", 1.0))))
    top_p = min(1.0, max(0.01, float(settings.get("topP", 0.95))))
    top_k = min(100, max(0, int(settings.get("topK", 20))))

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "chat_template_kwargs": {"enable_thinking": flags["thinking"]},
    }
    tools = context.get("tools")
    if flags["tools"] and isinstance(tools, list) and tools:
        payload["tools"] = copy.deepcopy(tools)
        payload["tool_choice"] = str(context.get("toolChoice") or "auto")
    return payload, flags
