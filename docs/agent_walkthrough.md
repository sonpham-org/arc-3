# Duck Harness Agent Walkthrough

This is the practical mental model for Tufa's Duck Harness agent.

## Control Flow

1. TAAF creates game runs and calls `HarnessSolver`.
2. `HarnessSolver` creates one `_HarnessGameSession` per game/pass.
3. Each session writes `tool_runtime_state.json` before every analyzer turn.
4. `ToolAgent.analyze(...)` sends an OpenAI-compatible chat request to the
   local model server.
5. The only model-facing tool is `python`.
6. The model writes Python that inspects structured state and eventually calls
   `action(...)`.
7. `action(...)` calls back into `_HarnessGameSession.step_env(...)`.
8. `step_env(...)` executes real ARC engine actions, updates history/runtime
   state, and returns compact action feedback to the Python tool.
9. The loop repeats until the game is won, game-over, cancelled, timed out, or
   the max action budget is reached.

Core files:

- `ARC3-Inference/inference/framework/solver.py`
- `ARC3-Inference/inference/agent/tool_agent.py`
- `ARC3-Inference/inference/agent/python_tool_sandbox.py`
- `ARC3-Inference/inference/agent/prompts.py`
- `ARC3-Inference/inference/agent/runtime_state.py`

## What The Model Sees

The model is not handed the raw numeric grid as normal prompt text. Inside the
Python tool it gets:

- `current_frame.ascii`
- `current_frame.segmentation`
- `previous_frame`
- `history`
- `transitions`
- `last_transition`
- `last_action_result`
- `valid_actions`
- `action(actions)`

The strongest signal is usually `current_frame.segmentation`: connected objects,
translation-invariant shape hashes, boundaries, containment children, and
adjacency pairs. The prompt explicitly tells the model to use segmentation first
and only inspect small ASCII crops when needed.

## What The Agent Is Really Doing

This is not a simple "LLM predicts next button" policy.

The intended loop is:

1. Summarize the current board structurally.
2. Infer candidate mechanics and goals.
3. Use Python to compare frames and test hypotheses.
4. Write a small search/scorer/controller when the mechanic is understood.
5. Execute one action or a short action batch with `action(...)`.
6. Re-ground on the returned frame.

For navigation-like games, the prompt encourages BFS or shortest-path search.
For object puzzles, it encourages component tracking, frame diffs, and
discriminating probes.

## Memory

There are two memory channels:

- Message history: recent assistant/tool turns are kept until the context budget
  forces trimming.
- Compact world model: assistant text with labels like `World model:`,
  `Goal model:`, `Action model:`, `Recent findings:`, `Open questions:`,
  `Plan:`, and `Cross-level notes:` is parsed and carried forward.

The world model is cleared on level transition, run completion, or game over,
except cross-level notes can remain useful for mechanics that transfer.

## Safety And Robustness

Python runs in a short-lived isolated process with:

- restricted builtins,
- a small allowlist of standard-library modules,
- no persistent filesystem state,
- CPU/file-descriptor/file-size limits where available,
- a hard timeout,
- compact/truncated tool output.

The server side also recovers some malformed Qwen tool-call markup and retries
when the model responds with prose instead of a parsed tool call.

## Trace Files To Study After A Run

After a run on a108, start with:

- `runs/<run>/transcripts/<game>_p0.txt`: full model/tool transcript.
- `runs/<run>/solver_analysis/<game>_p0.html`: readable transcript view.
- `runs/<run>/artifacts/<game>_p0_viewer_data.json`: viewer summary.
- `runs/<run>/artifacts/<game>_p0_viewer_data.events.jsonl`: event stream.
- `runs/<run>/artifacts/<game>_p0_tool_runtime_state.json`: transient while a
  game is running; removed at normal session end.
- `runs/<run>/evaluation.json`: scoring output after `make score_run`.

For learning, the transcript is the main artifact: it shows the prompt, Qwen's
world model, Python code, tool outputs, action results, and where the loop
failed or succeeded.

## Improvement Hooks

Likely high-leverage changes:

- Add richer object features to segmentation output: bounding boxes, centroids,
  holes, aspect ratio, symmetry, line/rectangle tags, and edge/HUD flags.
- Add a deterministic frame-diff helper so the model does not need to rewrite
  diff code every turn.
- Add controller mining from successful traces: once a game mechanic is
  discovered, cache a small deterministic policy for that game family.
- Improve prompt/feedback around failed probes and HUD-only board changes.
- Add per-game notebooks or replay summaries that classify failure modes from
  transcripts.
