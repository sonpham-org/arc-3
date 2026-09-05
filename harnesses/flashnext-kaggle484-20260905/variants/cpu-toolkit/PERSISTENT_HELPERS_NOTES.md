# Persistent Python helpers experiment

This arm adds source persistence to the locked Kaggle-4.84 harness. Gameplay gains are unmeasured. Curator, reflection, action cap, planning, segmentation, and environment implementation remain at their baseline settings.

## Behavior

- `helpers.save(name, source, description='')` creates or replaces a function immediately through a host RPC. The host stores validated text before acknowledging the save; a subsequent snippet exception or timeout does not undo it.
- `helpers.<name>(...)` and `helpers.call(name, ...)` call saved functions in any fresh Python subprocess. `helpers.list()` returns complete metadata; `helpers.get(name)` returns full source; `helpers.delete(name)` removes it. Large source can be inspected in slices under the unchanged tool-output limit.
- The host-owned registry belongs to one `ToolAgent` and full runtime-state path. It survives history eviction, current-level resets, and ordinary level transitions. A new agent or different state path starts empty, including paths sharing the same parent directory.
- Every context trim rebuilds an index in the protected system message, including within the tool loop and context-overflow retry. Full source is not injected into model context. Stored source is transferred to the fresh subprocess; function definitions are compiled lazily on call.
- Each helper has its own fresh function namespace. Imports belong inside the function. Calls between saved helpers use `helpers.<name>(...)`. Runtime frame/history/action-result views refresh inside loaded helpers after `action(...)`.

## Explicit bounds and grammar

Up to 16 helpers, 8,192 UTF-8 source bytes per helper, 65,536 bytes total; descriptions are at most 160 characters and signatures at most 240 characters. The displayed index is at most 3,000 UTF-8 bytes, preserves all names, and shortens descriptions/signatures when needed. Limit violations reject the attempted update; there is no silent eviction.

Each saved source must contain exactly one synchronous `def` matching its name. Top-level imports/statements, decorators, argument/return annotations, and type parameters are rejected. Defaults permit immutable literal scalars and tuples only. This prevents definition-time execution, including actions hidden in decorators, defaults, and annotations. Nested functions and allowed imports can appear in the function body and run only when explicitly called.

Only explicit source saves persist. Snippet objects, arbitrary global dictionaries, compiled function mutations, hidden environment state, processes, and pickles are not retained. Persistence lasts only for the live host agent; host-process restart/resume persistence is outside this arm.

## Validation

13 local tests pass in `work/memory-variants/tests/test_persistent_helpers.py`:

- Source creation, replacement, retrieval, and deletion across real subprocesses.
- Immediate save survives a subsequent exception or timeout.
- Saving/loading/retrieving source does not replay actions.
- Live state refresh after helper actions; fresh level state.
- Existing action interrupt path, plus `ToolAgent` integration with a fake environment callback enforcing a cumulative cap across three subprocess calls. The production solver's cap implementation is unchanged.
- Fresh subprocesses discard helper mutations and snippet objects.
- Allowed and denied imports, cross-helper calls, definition-time execution traps, and rejected replacement preserving the prior function.
- Registry limits and bounded Unicode index.
- Index survives context eviction/level-history reset, refreshes after updates, and clears between games and agent instances.

Runtime: `C:/Users/celle/Documents/Codex/2026-09-02/do/work/preflight-venv/Scripts/python.exe -B -W ignore::ResourceWarning work/memory-variants/tests/test_persistent_helpers.py`.

Local Windows tests use test-only shims: Windows' command-line limit rejects the enlarged `-c` bootstrap, so the same bootstrap is written inside the temporary sandbox and executed with `-I -S`; timeout cleanup uses `process.kill()` in place of the baseline POSIX process-group kill. Production subprocess launch, timeout logic, resource limits, allowed imports, and gameplay action RPC are unchanged. These tests do not validate the unmodified Linux startup command. Linux deployment preflight and GPU gameplay evaluation remain pending. The baseline's pre-existing unclosed-pipe `ResourceWarning` is suppressed in the test command, not changed in production.

## Changed production files

- `inference/agent/persistent_helpers.py`: host-owned source validation, registry, metadata, bounded context index.
- `inference/agent/python_tool_sandbox.py`: source snapshot, helper RPC, per-subprocess function namespaces, refreshed runtime views.
- `inference/agent/tool_agent.py`: per-game registry lifecycle, sandbox wiring, index refresh during context handling.
- `inference/agent/prompts.py`: helper API, source grammar, bounds, and correct ARC color-string example.
