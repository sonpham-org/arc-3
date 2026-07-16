# opine-port — running OPINE-World locally on our own models

Track B of the OPINE integration: "run theirs first, then port." OPINE-World
(https://david-courtis.github.io/opine-world/) is a coding-agent world-model
loop — an actor plays, a separate agent synthesizes an executable Python
`transition_function`/`reward_function` that must **exactly replay** every
observed transition (CEGIS), and a planner searches the verified program. It
scored 20/25 on the public games with a frontier model.

Their code is cloned in scratchpad (`opine-world/`, not vendored here — it's a
large external repo). This folder records only the **patch** that lets it run on
a local model, plus the run recipe.

## The problem their code posed
OPINE's `codex` backend is hard-wired to hosted OpenAI: `model_provider=
openai_https`, `wire_api=responses`, `requires_openai_auth=true`, run inside a
`codex-agent` docker container through an egress gateway to api.openai.com. The
`claude` backend likewise targets Anthropic. **Neither backend can hit a local
model.** So "run on our Qwen" required a code patch, not config.

## The patch (`codex_backend-local.diff`)
Adds an env-gated local mode to `codex_backend.build_codex_cmd`:
- `OPINE_CODEX_LOCAL=1` → run `codex` on the **host**, no docker, no gateway.
- Isolation is codex's own `--sandbox workspace-write --ask-for-approval never`
  (writes confined to the run workspace) — NOT `--dangerously-bypass-...`, so
  it's safe to run bare on the host.
- Default provider is Ollama via codex's native `--oss --local-provider ollama`.
- `OPINE_CODEX_BASE_URL=<url>` → instead point at any OpenAI `/v1/responses`
  endpoint (e.g. our Qwen on vLLM `:1234` over an SSH tunnel).

Both codex call sites — the actor (`agentic_consumer._choose_actions_codex`) and
the synth world-modeler (`engine`) — route through `build_codex_cmd`, so both go
local. Unit-verified argv for both modes; no auto docker/gateway preflight.

## Key facts learned
- **codex-cli 0.142 dropped `wire_api="chat"`** — it now requires `responses`.
- **Ollama 0.20.2 serves `/v1/responses`** natively, and codex has first-class
  `--oss --local-provider ollama` support. So codex↔Ollama needs no proxy.
- vLLM (our Qwen stack) also serves `/v1/responses`, so the same patch reaches
  the real Qwen via `OPINE_CODEX_BASE_URL`.

## Run recipe (free debug on the 4090's Ollama)
```
cd <scratchpad>/opine-world
ARC_API_KEY=<key> uv run python scripts/download_cloud_games.py --games ls20 ft09
OPINE_CODEX_LOCAL=1 uv run python play.py --game ls20 --backend codex \
  --codex-model gpt-oss:20b --codex-effort high --max-actions 60
```
Then, for the real model: bring up the PRO 6000 Qwen vLLM (serve on :1234),
`gcloud compute start-iap-tunnel <inst> 1234:localhost:1234`, and add
`OPINE_CODEX_BASE_URL=http://localhost:1234/v1 --codex-model vrfai/Qwen3.6-27B-FP8`.

## Status
Backend patched + unit-verified; codex↔Ollama transport proven. Blocked on the
ARC key to download games for the first smoke run. Not yet reimplemented natively
(that's the eventual `../` world-model harness).
