# ffa7g-textgrid-reasoning-effort — reasoning_effort passthrough for harmony-format models

Adds one thing on top of `ffa7g-textgrid`: a `reasoning_effort` top-level
request field, for models (like `openai/gpt-oss-120b`) that ignore
`chat_template_kwargs.enable_thinking` entirely.

- **Derives from:** `bundle-v12ffa7gnsg-textgrid.tgz`'s own
  `src/ARC3-Inference/`. `patch/reasoning_effort.patch` is relative to that
  bundle (mirrors `../ffa7g-textgrid-concise/MANIFEST.md`'s own note about why).
- **Patch:** `patch/reasoning_effort.patch` — 2 files
  (`inference/utils/openai_compat.py`, `inference/agent/tool_agent.py`), 16
  lines added, all additive/no-op-when-unset.
- **Bundle:** `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-v12ffa7gnsg-textgrid-reasoning.tgz`.

## Why this exists

Built while evaluating `openai/gpt-oss-120b` as a Laguna S 2.1 replacement
(the Laguna attempt failed on token efficiency -- see
[[laguna-model-swap]] -- 6-10x more tokens/action than Qwen3.6-27B, root-caused
to thinking-mode verbosity that a hard `max_tokens` cap made *worse*, not
better, by truncating completions mid-reasoning and forcing an infinite
retry loop).

gpt-oss-120b has a **native, graduated `reasoning_effort` (low/medium/high)**
control, which looked like a much better lever than Laguna's binary
`enable_thinking` on/off. But the harness's existing thinking control
(`build_chat_payload` in `inference/utils/openai_compat.py`) only sets
`chat_template_kwargs = {"enable_thinking": ...}` -- and gpt-oss doesn't use
the repo's Jinja chat template at all. vLLM renders gpt-oss's harmony-format
prompt server-side via a dedicated builtin (`harmony_utils.py`, imports
directly from the `openai_harmony` package), completely bypassing
`chat_template_kwargs`. So the existing lever is a silent no-op for this
model family -- sending it does nothing, good or bad.

vLLM instead exposes `reasoning_effort` as a **top-level field** in the
`/v1/chat/completions` request body (verified directly against vLLM 0.25.1
source, `chat_completion/protocol.py`): `{"model": ..., "messages": [...],
"reasoning_effort": "low"}`. vLLM's harmony renderer picks this up and
injects the corresponding "Reasoning: low" system-prompt line itself -- no
manual system-prompt string-building needed on our side.

## What changed (2 files, 16 lines)

1. **`inference/utils/openai_compat.py`**: `build_chat_payload()` gains an
   optional `reasoning_effort: str | None = None` parameter; when truthy and
   the provider is `vllm`, adds `payload["reasoning_effort"] = reasoning_effort`
   as a sibling of `model`/`messages`, not nested under
   `chat_template_kwargs`. Omitted entirely when unset, so non-harmony models
   (Qwen, Laguna) never see a field their server might not expect.
2. **`inference/agent/tool_agent.py`**: new env var
   `LOCAL_ANALYZER_REASONING_EFFORT` (default empty = omit the field), read
   once at import time next to the existing `_LOCAL_ANALYZER_ENABLE_THINKING`,
   threaded into the one `build_chat_payload(...)` call site in this bundle
   copy (confirmed only one call site exists here -- repo-root's
   `tool_agent.py` has diverged and has a second `thinking_override`-based
   call site that doesn't exist in the deployed bundle; see
   `ffa7g-textgrid/MANIFEST.md`'s note on bundle-vs-repo-root divergence).

## Usage

Set `LOCAL_ANALYZER_REASONING_EFFORT=low` (or `medium`/`high`) in the
harness's environment alongside pointing `LOCAL_ANALYZER_MODEL_ID`/
`OPENAI_BASE_URL` at a gpt-oss-family vLLM server. Leave unset for any other
served model (Qwen, Laguna) -- the field is simply never added to the
request payload, zero behavior change for those.
