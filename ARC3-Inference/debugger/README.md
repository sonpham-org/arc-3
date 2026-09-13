# ARC Debugger gateway

`debugger.server` is the authenticated bridge between the static ARC run site
and the private two-DGX-Spark Qwen endpoint. It is deliberately separate from
vLLM: deploying or restarting this gateway does not disturb the model server.

## Security boundary

- The production process listens only on `a108`'s stable Tailscale address at
  port 8033. The listener is unreachable from the public internet and accepts
  only the server-side bearer token.
- The browser calls Railway's same-origin `/api/v1/debugger/*` route after the
  existing Google login. Railway is the only browser-facing trust boundary.
- Railway joins the tailnet in userspace mode and injects `ARC3_DEBUGGER_TOKEN`
  on the private hop. It also supplies the Google email as `X-ARC3-User`, but
  the gateway accepts that owner identity only when the bearer token matches.
- `ARC3_DEBUGGER_ALLOWED_USERS` remains available for a loopback Tailscale
  Serve deployment, but production relay mode uses token authentication only.
- `ARC3_DEBUGGER_ALLOWED_ORIGINS` is an exact CORS allowlist. No wildcard origin
  is accepted.
- Sessions are owner-scoped and stored under
  `~/.local/state/arc-debugger/` without the original embedded board data URL.

Never bind this service to a LAN or Tailscale interface with
`ARC3_DEBUGGER_ALLOWED_USERS` configured: a direct client could spoof that
identity header. The non-loopback production listener must use token-only
authentication.

## API

- `GET /v1/capabilities`: model, cluster nodes, and the authoritative editable
  flag registry.
- `POST /v1/sessions`: build a Qwen request from one exported turn and run it
  asynchronously.
- `POST /v1/preview`: render that final request read-only and count it with
  Qwen's live tokenizer before any inference is queued.
- `GET /v1/sessions/{id}`: poll the context fork.
- `POST /v1/sessions/{id}/messages`: continue inside a completed fork.

Every entry returned by the flag registry is applied by
`debugger.flags.build_resume_request`. Unknown flags fail closed. The contract
test toggles each registry entry and asserts that the outbound Qwen payload
changes.

### Existing harness flag audit

The repository did not have one universal feature-flag layer to reuse. The
audit found three different kinds of controls:

| Location | Controls | Result |
|---|---|---|
| Mainline `tool_agent.py` | `LOCAL_ANALYZER_ENABLE_THINKING`, sampling, limits, timeouts, tool steps, seed | Each is consumed by the client/tool loop; most are numeric settings rather than feature flags. |
| Mainline context modules | `ARC3_FRAME_MODE`, `MULTIMODAL_CONTEXT`, `MULTIMODAL_STYLE`, `ARC3_COMMON_THEMES_PATH` | Each gates frame history, the current-grid image/style, or cross-game prompt material. |
| `harnesses/ffa7g` patch | `ARC3_STATE_GRAPH`, `ARC3_REEXPLORE_STRICT` | Real behavior gates, but they are not present in the mainline runtime source. No-impact detection in that patch is behavior/intent-driven, not one independent environment flag. |

The Debugger therefore uses a request-level registry instead of displaying
every historical environment variable as if it could change a stored turn.
Its seven switches are thinking, carried memory, Python tools, current grid,
transition guidance, strategy guidance, and mouse guidance. Source-only
features such as state graph, animation context, and common themes are shown as
detected/not detected; they are not presented as editable unless the selected
request contains material the gateway can actually transform.

The Debugger's **Context so far** panel is deliberately read-only. It shows the
ordered message stack, tool definitions, and request settings after the current
fork flags are applied, replaces embedded image bytes with a visible marker,
and reports the prompt-token budget from vLLM's `/tokenize` endpoint. Play is
disabled when the prompt plus requested completion would exceed the model's
context window.

Resume sampling defaults match the recent ARC analyzer runs: temperature 1.0,
top-p 0.95, and top-k 20. The Debugger exposes those three values plus the
maximum output-token count as editable numeric controls, and the preview is
re-tokenized whenever any of them changes.

## Two-Spark deployment

The current cluster has one GPU per node: `a108` is the Ray/vLLM head and
`a424` is its worker. vLLM stays on head-loopback port 1234; the debugger runs
on the head next to it.

Install the three Python source files under
`~/.local/share/arc-debugger/ARC3-Inference/debugger/`, copy
`arc-debugger.service` to `~/.config/systemd/user/`, and create a mode-0600
`~/.config/arc-debugger.env` containing the stable Tailscale bind address and
shared server-only secret:

```bash
ARC3_DEBUGGER_HOST=100.118.4.20
ARC3_DEBUGGER_TOKEN=<same secret stored in Railway>
systemctl --user daemon-reload
systemctl --user enable --now arc-debugger.service
```

Verify from a tailnet node without exposing the secret in shell history:

```bash
curl -H "Authorization: Bearer $ARC3_DEBUGGER_TOKEN" \
  http://100.118.4.20:8033/v1/capabilities
```

Railway starts `tailscaled` with userspace networking and stores its state on
the persistent site volume. On the first deployment without `TS_AUTHKEY`, its
logs print a one-time Tailscale enrollment URL. After an administrator approves
that node, later deployments reuse the saved state. For automated enrollment,
set a tagged Tailscale auth key or OAuth client secret as Railway's
`TS_AUTHKEY`; never put it in source or browser JavaScript.

Railway's hosted network currently needs `TS_DEBUG_ALWAYS_USE_DERP=1`. Without
it, a direct UDP path can accept the request but stall the small HTTP response.
This affects only the Browser-to-Spark control API; Qwen inference and the Ray
traffic between `a108` and `a424` remain local and do not traverse DERP.

## Resume semantics

This is a **model-context fork**. The static exporter retains exact roles,
message content, tool definitions, tool choice, and inferred flag defaults,
while omitting the large embedded image. The browser attaches the board that
Qwen saw before the selected analyzer turn.

The live `taaf.game.Game` object is not persisted and cannot safely be pickled
after play starts. Therefore a fork can produce Qwen's next reasoning, answer,
or Python tool call, but does not mutate the archived engine. A true playable
branch is a separate feature: rebuild the exact environment revision, replay
the recorded action prefix with frame/hash divergence checks, and execute new
tool calls only after the replay matches.
