#!/usr/bin/env python3
"""
Author: Claude Opus 5 (Bubba subagent, label arc3-oracle-driver-and-launch)
Date: 18-September-2026
PURPOSE: Apply harnesses/oracle-rules/patch/tool_agent.py.patch to a108's DIVERGENT copy of
inference/agent/tool_agent.py. a108's tree is not a git checkout and is ~15 KB / 5 methods
behind repo main, so `git apply` fails on hunk 1 (its context is a frame_mode import block
a108 does not have). This applies the same six edits by exact-anchor match, refusing rather
than guessing if any anchor is missing, already present, or non-unique. Idempotent: a second
run is a no-op that says so.
SRP/DRY check: Pass - the patch file is the source of truth for WHAT changes; this is the
only thing that knows how to land it on a non-git deployment tree. Nothing else does that.
"""
import sys
from pathlib import Path

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "inference/agent/tool_agent.py")
src = TARGET.read_text(encoding="utf-8")

if "_oracle_rules_block" in src:
    print("already patched: _oracle_rules_block present; no changes made")
    sys.exit(0)

EDITS = [
    # (name, anchor, replacement)
    (
        "import",
        "from inference.agent.reasoning_style import compact_reasoning_enabled\n",
        "from inference.agent.reasoning_style import compact_reasoning_enabled\n"
        "from inference.agent.oracle_rules import load_rulebook, render_block, strip_block\n",
    ),
    (
        "init-attrs",
        "        self._session_runtime_dir: Path | None = None\n",
        "        self._session_runtime_dir: Path | None = None\n"
        "        # Arm O (oracle) only; empty string on every other arm. Resolved once per game\n"
        "        # in _ensure_oracle_rules and re-sent in every user turn thereafter.\n"
        "        self._oracle_rules_block = \"\"\n"
        "        self._oracle_rules_state_path: Path | None = None\n",
    ),
    (
        "ensure-method",
        "    @property\n    def total_tokens(self) -> int:\n",
        '''    def _ensure_oracle_rules(self, state_path: Path) -> None:
        """Resolve this game's rulebook once, on the arm's first turn (arm O only).

        Keyed on the runtime-state path rather than its parent directory: all games in a
        run share one artifacts/ directory, so a directory-keyed cache would hand game 2 the
        rulebook of game 1 if an analyzer were ever reused across games.
        """
        if self._oracle_rules_state_path == state_path:
            return
        self._oracle_rules_state_path = state_path
        self._oracle_rules_block = render_block(load_rulebook(state_path))
        if self._oracle_rules_block:
            log.info(
                "oracle rules loaded state_path=%s block_chars=%d",
                state_path.name,
                len(self._oracle_rules_block),
            )

    @property
    def total_tokens(self) -> int:
''',
    ),
    (
        "user-prompt-prepend",
        "        lines: list[str] = []\n        if previous_step_summary:\n",
        "        lines: list[str] = []\n"
        "        # Arm O treatment. It leads the turn so the rules are read before the frame, and it\n"
        "        # is re-sent every turn for the same reason action_semantics and win_pattern are\n"
        "        # (_summarized_knowledge_lines below): the first user turn is evictable --\n"
        "        # _trim_messages_for_context drops the oldest history block and then\n"
        "        # _drop_until_first_user_message discards what is left of it -- so anything injected\n"
        "        # once and left in history is gone the moment the context fills. Empty on every\n"
        "        # other arm, which keeps arm B byte-identical.\n"
        "        if self._oracle_rules_block:\n"
        "            lines.append(self._oracle_rules_block)\n"
        "        if previous_step_summary:\n",
    ),
    (
        "strip-method-and-call",
        "    def _persistent_history_messages(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:\n",
        '''    def _strip_oracle_block_from_history(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop the re-sent rulebook from turns being filed into history (arm O only).

        The live turn always carries it (_build_user_prompt), so removing it here leaves
        exactly one copy in context rather than one per retained turn. See
        oracle_rules.strip_block for why that matters. Messages are rebuilt, never mutated
        in place: the same dicts are still referenced by the request that was just sent and
        by the prompt-log snapshot written from it.
        """
        block = self._oracle_rules_block
        if not block:
            return history
        out: list[dict[str, Any]] = []
        for message in history:
            content = message.get("content")
            if str(message.get("role", "")).strip() != "user":
                out.append(message)
            elif isinstance(content, str):
                out.append({**message, "content": strip_block(content, block)})
            elif isinstance(content, list):
                parts = [
                    {**part, "text": strip_block(part["text"], block)}
                    if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
                    else part
                    for part in content
                ]
                out.append({**message, "content": parts})
            else:
                out.append(message)
        return out

    def _persistent_history_messages(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        messages = [messages[0], *self._strip_oracle_block_from_history(messages[1:])] if messages else messages
''',
    ),
    (
        "analyze-call",
        "        self._ensure_session(state_path)\n        self._step_env_callback = step_env\n",
        "        self._ensure_session(state_path)\n"
        "        self._ensure_oracle_rules(state_path)\n"
        "        self._step_env_callback = step_env\n",
    ),
]

for name, anchor, replacement in EDITS:
    n = src.count(anchor)
    if n != 1:
        sys.exit(f"REFUSING: anchor {name!r} occurs {n} times, expected exactly 1")
    src = src.replace(anchor, replacement, 1)
    print(f"applied {name}")

TARGET.write_text(src, encoding="utf-8")
print(f"wrote {TARGET} ({len(src)} bytes)")
