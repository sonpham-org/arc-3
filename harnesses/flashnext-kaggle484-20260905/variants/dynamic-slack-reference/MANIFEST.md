# Flash-Next maximum-upside arm: cap-14 + Reflection V3 + Replay-C + Dynamic Slack

- Preserves RTDv7 animation behavior and the existing top-six GPU curator injection path.
- Adds CPU-only read-only access to the complete settled-event history through `replay`.
- Emits the Replay-C reminder only on exact settled-state repeats.
- Replay takes no environment actions and makes no model request of its own.

- Keeps 6,180 seconds as every game's guaranteed baseline.
- While games remain queued, shares 75% of verified early-finish lane time equally across all unfinished games and reserves 25% for overhead and lane imbalance.
- Once the queue empties, lets each final active game use its own safe-deadline headroom, capped at 1,200 extra seconds.
- Writes a scheduler JSONL ledger so every grant, refund, and active limit is auditable.

- Preserves the Flash-Next V8 literal resized-animation-frame behavior.
- After an engine-verified level completion, runs one short no-tool, no-thinking reflection in the exact winning context.
- Records the winning world model, decisive evidence, minimal recipe, conservatively verified redundant actions, and one next-level rule.
- Resets completed-level rolling chat and injects the compact reflection exactly once in the next-level input.
- Writes per-game reflection JSONL artifacts for audit.

- Base: exact bundle behavior used by the R6 NVFP4 persistent world-model-curator champion.
- The original soft cap is preserved: at most eight actions per individual `action(...)` call, with additional calls still allowed in the same model turn.
- The existing persistent top-six world-model curator and its per-input injection behavior are unchanged.
- The animation detector, checkpoint policy, storyboard, and local inspector are byte-for-byte inherited from dual-lane v6. This arm changes only the instructions presented to the model.
- `last_animation` is now advertised directly in the Python tool schema, where tool choice is made, rather than being buried only in a long system-prompt API inventory.
- The description states that `last_animation` belongs only to the latest real action and that historical transitions do not retain animation objects. This addresses the observed trace failure where the agent searched transition history for an unsupported animation field.
- The system prompt keeps the runtime semantics and decision-critical guidance, but removes repeated API prose and broad search-method laundry lists. It tells the agent to read automatic storyboards first, inspect region summaries next, and request a crop only when that evidence could change its hypothesis.
- Five completed actions establish the animation baseline once per game; level transitions never restart detector warm-up. Identify a temporal tail when changed animation frames are at least `max(2, 2*median, median + max(1, ceil(3*1.4826*MAD)))`. With the usual one changed frame per action, one extra intermediate change is therefore enough to qualify after warm-up.
- Mature level/action-family and level-wide histories are preferred. On a fresh level, the detector falls back to the game-wide action-family history when mature, otherwise the game-wide rolling history. Histories use at most 32 prior observations for threshold calculation.
- Changed pixels are grouped into 8-connected components and linked across adjacent animation transitions. Components that exist for only one transition do not become local animation regions. This removes ordinary one-frame HUD updates without assuming the HUD is on a particular border.
- The old large-motion spatial gate remains as a fallback. A temporally unusual tail may also qualify through a persistent local region even when it touches fewer than eight unique cells, allowing compact blinking and resizing animations.
- A novel tail may hard-checkpoint after a five-action cooldown, up to three times per level. Similar tails continue the queued action sequence uninterrupted and return an explicit model-visible reminder. Terminal actions are never checkpointed.
- Broad motion retains v4's automatic compact storyboard. It selects the largest motion-preserving source block from 4x4 through 8x8 and temporally samples only when the full storyboard would exceed 2,000 estimated tokens.
- Persistent small/local motion adds v5's compact description: absolute bounding box, transition duration, changed-cell count, size range, and likely behavior (`blink`, `resize`, `translate`, or `transform`). Local animation grids are not automatically printed; when broad and local evidence coexist, the tool returns both the automatic overview and the local description.
- Up to 12 native local frames remain in the sandbox state. The agent may inspect the whole region or choose narrower absolute `rows=` and `cols=` with `last_animation.region(i).inspect(...)`.
- Rescaling happens only after that request. The inspector begins at native resolution and tries uniform square source blocks from 1x1 upward until the requested token budget is met. The same scale is used on both axes, so aspect ratio is never stretched. A source block larger than 8x8 is forbidden.
- The settled board remains the source of truth for exact final coordinates.

Validation covers bytecode compilation, the permissive two-change threshold after per-game warm-up, restored broad-storyboard injection, broad-plus-local output, local-only descriptions, one-transition HUD-blip removal, compact blinking, grow/shrink classification, novel-tail interruption, uninterrupted familiar-tail reminders, deferred in-RAM frames, agent-selected crops, adaptive aspect-preserving scaling with a hard 8x8 ceiling, local sandbox inspection, and preservation of the original eight-action checkpoint.
