"""Bounded per-game function source, owned by the host, never executed there."""
from __future__ import annotations

import ast
import keyword
import re
from typing import Any


MAX_HELPERS = 16
MAX_SOURCE_BYTES = 8_192
MAX_TOTAL_SOURCE_BYTES = 65_536
MAX_DESCRIPTION_CHARS = 160
MAX_SIGNATURE_CHARS = 240
MAX_INDEX_BYTES = 3_000
_RESERVED_NAMES = {
    "save", "list", "get", "delete", "call", "helpers", "action", "vision",
    "current_frame", "latest_frame", "history", "transitions", "last_transition",
    "previous_frame", "last_action_frame", "last_action", "valid_actions",
    "last_action_result", "last_animation",
}
HELPER_INDEX_START = "\n\nPersistent Python helper index (source saved for this game):\n"


def _immutable_default(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (str, bytes, int, float, complex, bool, type(None)))
    if isinstance(node, ast.Tuple):
        return all(_immutable_default(item) for item in node.elts)
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) in (int, float, complex)
    )


def _validate_source(name: str, source: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,47}", name):
        raise ValueError("Helper name must be a 1-48 character ASCII Python identifier.")
    if keyword.iskeyword(name) or name in _RESERVED_NAMES:
        raise ValueError("Helper name is reserved.")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Helper source must be a non-empty string.")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError(f"Helper source exceeds {MAX_SOURCE_BYTES} bytes.")
    try:
        tree = ast.parse(source, filename="<persistent_helper>")
        compile(tree, "<persistent_helper>", "exec")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("Helper source is not valid Python.") from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Source must contain exactly one function definition; put imports inside it.")
    function = tree.body[0]
    if function.name != name:
        raise ValueError("Function name must match the saved helper name.")
    if function.decorator_list or getattr(function, "type_params", []):
        raise ValueError("Helper decorators and type parameters are not supported.")
    arguments = function.args
    params = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    params += [item for item in (arguments.vararg, arguments.kwarg) if item is not None]
    if function.returns is not None or any(item.annotation is not None for item in params):
        raise ValueError("Helper annotations are not supported; describe types in the docstring.")
    defaults = [*arguments.defaults, *(item for item in arguments.kw_defaults if item is not None)]
    if not all(_immutable_default(item) for item in defaults):
        raise ValueError("Helper defaults must be immutable literals; initialize other values in the body.")
    signature = f"{name}({ast.unparse(arguments)})"
    if len(signature) > MAX_SIGNATURE_CHARS:
        raise ValueError(f"Helper signature exceeds {MAX_SIGNATURE_CHARS} characters.")
    return signature


class HelperRegistry:
    """Only validated text survives snippets; replacement commits atomically."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(entry) for _, entry in sorted(self._entries.items())]

    def list(self) -> list[dict[str, Any]]:
        return [{key: value for key, value in entry.items() if key != "source"}
                for entry in self.snapshot()]

    def save(self, name: str, source: str, description: str = "") -> dict[str, Any]:
        signature = _validate_source(name, source)
        if not isinstance(description, str):
            raise ValueError("Helper description must be a string.")
        description = " ".join(description.split())
        if len(description) > MAX_DESCRIPTION_CHARS:
            raise ValueError(f"Helper description exceeds {MAX_DESCRIPTION_CHARS} characters.")
        if name not in self._entries and len(self._entries) >= MAX_HELPERS:
            raise ValueError(f"At most {MAX_HELPERS} helpers; delete one before adding another.")
        total = len(source.encode("utf-8")) + sum(
            len(entry["source"].encode("utf-8"))
            for key, entry in self._entries.items() if key != name
        )
        if total > MAX_TOTAL_SOURCE_BYTES:
            raise ValueError(f"Total helper source exceeds {MAX_TOTAL_SOURCE_BYTES} bytes.")
        version = self._entries.get(name, {}).get("version", 0) + 1
        self._entries[name] = {"name": name, "source": source, "signature": signature,
                               "description": description, "version": version}
        return dict(self._entries[name])

    def handle(self, message: dict[str, Any]) -> Any:
        operation = message.get("operation")
        if operation == "save":
            return self.save(message.get("name"), message.get("source"), message.get("description", ""))
        if operation == "list":
            return self.list()
        name = message.get("name")
        if not isinstance(name, str) or name not in self._entries:
            raise ValueError("No saved helper with that name.")
        if operation == "get":
            return dict(self._entries[name])
        if operation == "delete":
            del self._entries[name]
            return True
        raise ValueError("Unknown helper operation.")

    def context_index(self) -> str:
        def shorten(text: str, limit: int) -> str:
            encoded = text.encode("utf-8")
            return text if len(encoded) <= limit else encoded[:limit - 3].decode("utf-8", errors="ignore") + "..."

        lines = [HELPER_INDEX_START.rstrip("\n")]
        for entry in self.list():
            signature = shorten(entry["signature"], 96)
            description = shorten(entry["description"] or "No description.", 40)
            # 16 rows of at most 150 bytes preserve every complete name while
            # keeping the always-visible prompt far smaller than the registry.
            lines.append(shorten(f"- {signature} [v{entry['version']}]: {description}", 150))
        if not self._entries:
            lines.append("- No saved helpers yet.")
        lines.append("Call helpers.<name>(...) or helpers.call(name, ...); helpers.list() shows full metadata; helpers.get(name) retrieves source.")
        rendered = "\n".join(lines)
        assert len(rendered.encode("utf-8")) <= MAX_INDEX_BYTES
        return rendered
