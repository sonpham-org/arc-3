<!--
Author: Claude Opus 5 (Bubba subagent)
Date: 18-September-2026
PURPOSE: Registry entry for arm O, the oracle arm of docs/plans/2026-09-18-oracle-test-plan.md.
Records what it derives from, the exact diff against arm B, where the rulebook enters the
conversation and the code path that keeps it there, the treatment-marker guard and its dry-build
output, the metric deviation, the contamination fence, and the decision rule copied from the plan
before any number exists.
SRP/DRY check: Pass -- harnesses/README.md requires one MANIFEST per variant; this is that file
for this variant. The rulebook's contents are tools/render_rulebooks.py's business and the
decision rule is the plan's; both are cited, not restated.
-->

# oracle-rules — arm O

## In one paragraph

Arm B plus one thing: the rules of the game being played, as text, in the user turn, from the
first action. It measures whether the agent can execute a mechanic it is simply told, which
splits the failure on the games we never clear into "never had the idea" and "could not play
it". Seven games, four passes per arm, alternating B/O/B/O on a108. Nothing runs until the
compact-reasoning multipass finishes and Boss says go.

## Derives from

Arm B, `harnesses/sparse-deletion/` (`markbarney/taaf-duck-sparse-deletion`), as the a108
compact-reasoning multipass runs it. **Not `baseline-v12`**, and not the Kaggle bundle: this
arm runs locally on a108 out of the `ARC3-Inference` tree, so it is an env toggle in that tree
the way `ARC3_REASONING_STYLE` is, not a published bundle. `harnesses/README.md` rule 3 asks a
variant to be a copy plus a patch; here the copy is "the same checkout with the toggle unset",
which is byte-identical to arm B because the injected block is the empty string when
`ARC3_ORACLE_RULES_DIR` is not set.

## The diff — two files, and `prompts.py` is not one of them

`patch/oracle_rules.py.patch` (new module) and `patch/tool_agent.py.patch` (+65 lines).
Arm B's own patch touches `prompts.py`; this one must not, because the plan allows exactly
one difference between the arms and that difference is the rulebook text. `git diff
origin/main -- inference/agent/prompts.py` is empty, and the system prompt is byte-identical
across the arms.

1. **`inference/agent/oracle_rules.py`** — the toggle. Reads `ARC3_ORACLE_RULES_DIR`, resolves
   the bare game code from the runtime-state path, loads `<code>.txt`, and renders the block.
   Unset is arm B and returns `""`. Set-but-unresolvable **raises**: an arm-O game that
   quietly runs untreated is a wrong number, not a degraded one.
2. **`inference/agent/tool_agent.py`** — three hooks:
   - `analyze()` calls `_ensure_oracle_rules(state_path)` once per game, before the prompt is
     built. Keyed on the runtime-state path, not its parent, because all games in a run share
     one `artifacts/` directory.
   - `_build_user_prompt` puts the block first, ahead of the state lines and therefore ahead
     of the frame image, on **every** turn.
   - `_persistent_history_messages` strips the block from turns on their way into history.

`distill/recordings_to_sft.py`'s `_LedgerShim` gains `_oracle_rules_block = ""`. It calls
`_build_user_prompt` unbound with a duck-typed `self`, so without that line the human-demo SFT
builder would raise `AttributeError` — and declaring it explicitly (rather than reading the
attribute defensively) is also what guarantees human demonstrations can never carry the
answer key into a training corpus.

## Where the block goes, and why it stays there

```
Rules of this game, from a verified source.
Level 1:
- Arrow keys move your blue square ...
...
End of the rules of this game.
```

**In from action 1.** `_build_user_prompt` is the per-turn user prompt, and the block is the
first thing in it. The system prompt was not an option: `_build_system_prompt(*,
tool_output_tokens)` takes no game id and is built once in `__init__`.

**Survives compaction, by re-sending — the same mechanism the ledger uses.** The first user
turn is *not* durable: `_trim_messages_for_context` calls `_drop_oldest_history_block` in a
loop and then `_drop_until_first_user_message` discards whatever is left of the oldest turn,
so anything injected once and left in history is gone the moment the context fills. What does
survive is what gets re-rendered each turn, which is exactly how `action_semantics` and
`win_pattern` survive — `_build_user_prompt` ends with `lines.extend(
self._summarized_knowledge_lines())`. The rulebook is put in by the same means, three lines
above it.

**Exactly one copy in context, not one per turn.** Re-sending alone would be wrong: the
largest rulebook is 5,714 characters (`su15`; 5,619 for `tn36`, the largest of the seven this
run plays), which `_estimate_tokens` charges at ~1,900 tokens, and
`_PERSISTENT_HISTORY_ASSISTANT_TURNS = 30` retained turns of that exceeds the whole
32,768-token window. Arm O would hold far less real history than arm B — two differences, not
one. So `_persistent_history_messages` strips the block as a turn is filed, leaving the live
turn as the only copy.

**What the strip costs, measured.** Because the previous turn is re-sent one block shorter,
the previous *whole* request is never an intact prefix of the next one — the divergence is
always at its final message. Everything before it is byte-stable. Simulated over 40 turns with
the largest block of the seven (`tn36`, 5,693 characters), **95.7% of the previous request is reused on
average and 0 turns are reused whole** (`scripts/test_oracle_injection.py`). That buys back
~1,900 tokens per retained turn, so it is the right trade, but it is a real cost and it is
arm O's alone. `scripts/test_prefix_stability.py`'s 97% figure does **not** cover this path:
it drives `_trim_messages_for_context` directly and never calls
`_persistent_history_messages`. It still passes, unchanged, which is the arm-B check.

## Treatment-marker guard

`scripts/check_oracle_marker.sh <run-dir> <expected-games>`, the shape
`run_style_multipass.sh:53` uses for the compact-reasoning arms — count the prompt logs
containing the marker, expect one per game in O and zero in B. Run it every pass: a missing
`export ARC3_ORACLE_RULES_DIR` on one of four launches is the likeliest way this experiment
produces a confidently wrong number.

`scripts/test_oracle_injection.py` proves it fires, with no model, server or game engine —
it drives the real `_build_user_prompt`, the real `_persistent_history_messages` and the real
`_write_prompt_log_snapshot` into a temporary run tree:

```
games: 7  (dc22, g50t, m0r0, sc25, sk48, tn36, tr87)
mean first-turn user prompt: arm B 413 chars -> arm O 4,501 chars
block re-sent on turn 5 as well as turn 0: True
rulebook copies in a 3-turn request: 1 live, 0 retained in history
--- guard, arm O (expect 7) ---
oracle_marker: games_with_treatment=7 expected=7 prompt_logs=7 max_occurrences_in_one_log=1
oracle_marker: PASS
--- guard, arm B (expect 0) ---
oracle_marker: games_with_treatment=0 expected=0 prompt_logs=7 max_occurrences_in_one_log=0
oracle_marker: PASS
```

It also checks each game carries **its own** rulebook and not a neighbour's, which is the
failure a per-directory cache would have produced. `--games` takes the all-25 set; that run
passes too (25 / 0).

## Run shape

Per plan section 3 as amended 18-Sep: the slippery seven (`dc22 g50t m0r0 sc25 sk48 tn36
tr87`), `qwen38-27b-nvfp4`, a108, four passes per arm alternating B/O/B/O, per-game cap
5,400 s.

Seven parallel lanes, so a pass is about the cap and eight passes are about half a day of box
time. An intermediate directive on 18-Sep saying "all 25 with the seven as the analysis
subset" was withdrawn the same afternoon; seven games only is the standing instruction, and
the plan on disk has said so since `2ca516dca`. The renderer still emits all 25 rulebooks and
the guard takes the expected game count as an argument, so the follow-up run needs no rebuild.

Launch:

```bash
export ARC3_ORACLE_RULES_DIR=$REPO/datasets/explainer-games/rulebooks   # arm O; unset for arm B
# run dir MUST match *-oracle-* -- see the fence below
```

## Metric deviation — stated on purpose

`harnesses/README.md` rule 5 says score on ex-`ft09` all-25. This arm does not: it is scored
per game, paired B against O, level clears first and score second, per
`docs/trace-findings/2026-09-17-seed-variance-and-the-sb26-jackpot.md`. No arm totals, and no
ex-`ft09` number. `ft09` is not in the seven-game lane set at all.

## Contamination fence

Oracle transcripts contain the answer key. Run dirs must be named `*-oracle-*`;
`distill/extract_sft.py` refuses such a dir with exit code 2 and no override
(`ARC3-Inference/distill/README.md`). A held-out game getting rules does not breach
`datasets/splits/public25-train-test-split.json`: the only held-out game in the seven is
`tr87`, it is measured here rather than trained on, and that fence is what keeps the
distinction true.

## Decision rule — the plan's, copied before any number exists

Plan section 3a gives a prediction per game: `dc22`/`g50t`/`sk48` (guessed and never checked)
and `sc25`/`tn36` (never got the controls) should clear; `tr87` (knew it, fumbled it) should
**not** improve and is the control inside the experiment; `m0r0` is borderline. If everything
improves including `tr87`, the rulebook is doing something other than supplying the idea and
nothing is concluded until the per-level variant runs.

**A limitation to hold on to while reading the result.** The failure audit's verdict is that
the common defect is *not converting a stated uncertainty into the cheapest action that
resolves it*. Handing over the rules removes the uncertainty; it does not install the habit.
So the arm is well aimed at `sc25` and `tn36`, where the missing thing is a fact the rulebook
states outright. It is a weaker instrument on `dc22`, `g50t` and `sk48`: those runs already
had a hypothesis and spent their actions on anything except the probe that would settle it,
and a correct hypothesis handed over for free can be ignored the same way a self-generated one
was. A null on the bucket-C three would not by itself mean "execution is the bottleneck".

## Score

Not run. Blocked on the compact-reasoning multipass finishing on a108 (started 11:34 ET
18-Sep) and on Boss's go.
