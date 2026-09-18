<!--
Author: Claude Opus 5 (Bubba subagent)
Date: 18-September-2026
PURPOSE: What steps 1-3 of the oracle test (docs/plans/2026-09-18-oracle-test-plan.md section 6)
actually are, as built: the rulebook renderer and the three-rulebook check against the live
pages, the injection point and the code path that proves the block survives compaction, the
treatment-marker guard and its dry-build output, the premises in the brief that did not hold
when checked, and an explicit list of what was not verified. No run, no driver, no analysis.
SRP/DRY check: Pass - the plan owns the experiment's design and harnesses/oracle-rules/MANIFEST.md
owns the variant's registry entry. This is the build record and the verification evidence, and
duplicates neither.
-->

# The oracle arm, built. Nothing run.

**18-September-2026.** Steps 1, 2 and 3 of the oracle test plan, in the plan's own order. The
box (a108) is still running the compact-reasoning multipass that started 11:34 ET, and nothing
here has touched it. No inference, no training, on a108 or a424.

---

## 0. Premises in the brief that did not survive checking

Four, listed first because three of them changed what got built.

1. **"Add the `*-oracle-*` pattern to the distill README's exclusion list."** There was no
   distill README. `ARC3-Inference/distill/` held nine Python files and no markdown, and
   `find . -ipath '*distill*' -name '*.md'` was empty. The nearest existing fence is
   `datasets/test-only-games/README.md` §"The rule: never train on it", which is a **game**
   fence (`--exclude-games as66`), not a run-dir one. So `ARC3-Inference/distill/README.md`
   was created as the register of all three fences, and the test-only-games README now points
   at it.

2. **"If `extract_sft.py` already has an exclusion mechanism, use it."** It has
   `--exclude-games` and `--only-games`. Both take bare game codes; neither can express "this
   whole run directory is poisoned". A new guard was needed.

3. **"Check three rendered rulebooks against the live pages."** The pages return HTTP 200 but
   are a client-rendered SPA: the rules are not in the HTML. What they *are* in is the site's
   own JavaScript bundle, which is what the check used — see §2.

4. **`~/bubba-workspace/docs/2026-09-18-arc3-never-cleared-scope-and-failure-audit.md` does not
   exist.** The audit is in this repo, at
   `docs/trace-findings/2026-09-18-never-cleared-scope-and-failure-audit.md` (PR #50).

A fifth thing moved under the build rather than being wrong in it: the plan was amended the same
afternoon (PR #51) to run **the slippery seven only**, not all 25, with a predicted outcome per
game in a new §3a. An intermediate directive saying "all 25 with the seven as the analysis
subset" was withdrawn. Seven games is what the MANIFEST, the distill README and the guard's
default all say.

---

## 1. Step 1 — the rulebook renderer

`tools/render_rulebooks.py` reads `datasets/explainer-games/games.json` (fetched by
`tools/fetch_explainer_games.py`, PR #46 — it was not on disk, so it was fetched; the admin
token is in the Mac Mini login keychain under `arc3-community-admin-token`, which that script
already knows how to read) and writes one `<code>.txt` per game.

Per plan §2: the `newRules` of every level, concatenated in level order, as plain sentences,
grouped under the level each rule starts on. **25 games, 527 rules, 93,822 characters**, from
2,146 (`cd82`) to 5,714 (`su15`); `tn36`, at 5,619, is the largest of the seven games this run plays. Output lands in `datasets/explainer-games/`, which is
gitignored — these files are the answer key and are re-renderable from the fetch.

Left out, deliberately, each of these being available in `games.json` and each being a thing
the plan does not authorise: level images; the Boss's play notes (`observations`,
`observationsAnyLevel` — the separate arm, kept out so the effect stays attributable); run data
(`runs`, `arcBaselineActions`); the `rule.source` code citations (`g50t.py:1636-1653` and the
like — file:line refs into source the agent cannot read); the `rule.category` labels; and the
game's editorial prose (`description`, `plainEnglish`, `controls`, `officialTitle`).
`as66` is refused outright rather than filtered, so a future payload that started including it
would stop the script instead of quietly shipping a rulebook for the test-only game.

Levels with no new rules are skipped, so level numbering is legitimately non-contiguous —
`g50t` runs 1, 2, 3, 4, 6, 7 because level 5 introduces nothing.

## 2. The three-rulebook check, and what it actually compared

The three: **`g50t`** (slippery seven, audit bucket C), **`sc25`** (slippery seven, bucket B —
the game the arm is best aimed at), **`cd82`** (a game the agent already clears, as a contrast).

`https://arc3.markbarney.net/arc3/games/<id>` returns 200 but ships a ~3.6 KB shell; the rules
arrive from `/assets/index-2ybA3P9l.js`. So the comparison was made against **that bundle,
fetched from the live site** — not against the admin API `games.json` came from, which would
have been circular. The bundle is the exact data the page renders, in its `mechanicsBreakdown`
arrays.

Four things were compared, for all 57 rules across the three games:

| check | result |
|---|---|
| every rendered rule present **verbatim** in the live bundle | 57 / 57 |
| level assignment matches the bundle's `introducedOnLevel` (absent = level 1) | 0 mismatches |
| `category` matches the bundle's | 0 mismatches |
| within-level rule order matches the page's own `MECHANIC_CATEGORY_ORDER` | 0 levels out of order |

The level grouping is not independently re-derived by the page and the API: `shared/arc3Games/
gameLevels.ts` in arc-explainer is a single cut consumed by the game page, by
`arc3GameDataset.ts` (the endpoint we fetch) and by the markdown export, and says so in its own
header. The check above confirms that holds in the shipped bundle rather than taking the
comment's word for it.

A separate leak check across all 25: zero `rule.source` citations in any rulebook, and of 171
play-note strings, one apparent hit — `lf52`'s "From level 3 most boards are bigger than the
screen, and the view slides along." That is not a leak. It is the `inCode` field of a note,
which holds *the rule sentence the note was checked against*, and that same sentence is
genuinely `lf52`'s level-3 `newRule`. The Boss's own words on that note ("Everything is
side-scrolling: you have to go way off the original screen...") appear nowhere.

**What this does not establish:** nobody looked at a rendered page in a browser. Layout,
ordering as a human reads it down the page, and anything the page adds around the rules were
not compared. The claim is data fidelity against the live bundle, not visual fidelity.

## 3. Step 2 — the harness variant

`harnesses/oracle-rules/` (MANIFEST + `patch/`, per `harnesses/README.md`), env toggle
`ARC3_ORACLE_RULES_DIR`, derived from arm B. Two files change and **`prompts.py` is not one of
them** — `git diff origin/main -- ARC3-Inference/inference/agent/prompts.py` is empty and the
system prompt is byte-identical across the arms.

The block, exactly as it enters the turn:

```
Rules of this game, from a verified source.
Level 1:
- Left and Right move the bracket along the answer row. It wraps around from one end to the other.
...
End of the rules of this game.
```

The heading is the plan's wording verbatim. The footer is a delimiter only, mirroring the base
prompt's existing "End of carried knowledge ledger."; it asserts nothing about how to play. This
matters because §3a makes `tr87` the control inside the experiment: any generic steering,
formatting hint or strategy structure in the wrapper would be a reason `tr87` could improve that
has nothing to do with rules content, and would invalidate the control. There is none.

### 3.1 Why not the system prompt

`_build_system_prompt(*, tool_output_tokens: int)` takes no game id and is called once, in
`ToolAgent.__init__`. Confirmed, not assumed. The plan said so and it is true.

### 3.2 The compaction-survival proof, with the code quoted

**The first user turn is not durable.** `_trim_messages_for_context` drops the oldest block in
a loop and then discards whatever is left of it:

```python
target_tokens = max(1, int(budget_tokens * _CONTEXT_TRIM_LOW_WATER))
while history and self._estimate_request_input_tokens([system_message, *history], tools=tools) > target_tokens:
    if not self._drop_oldest_history_block(history, preserve_recent=preserve_recent):
        break
history = self._drop_until_first_user_message(history)
```

So "inject at `action_num == 0` and let it ride" loses the rulebook the moment the context
fills. That was checked before anything was written.

**What survives is what is re-rendered every turn.** That is exactly how `action_semantics` and
`win_pattern` survive, and the plan's requirement is that the block be carried "the same way".
The relevant three lines of `_build_user_prompt`, with the injection above them:

```python
lines: list[str] = []
if self._oracle_rules_block:
    lines.append(self._oracle_rules_block)
...
lines.extend(self._summarized_knowledge_lines())     # <- action_semantics, win_pattern
lines.append("End of carried knowledge ledger.")
```

`_summarized_knowledge_lines()` renders `action_semantics` and `win_pattern` (via
`_LEDGER_GAME_KEYS`) into the user prompt on **every** turn; the compaction request
(`_compact_history_into_ledger`) only refreshes the *values*, it does not carry them into
context. Re-rendering is the carrying mechanism. The rulebook now uses it, three lines above.

`_ensure_oracle_rules(state_path)` resolves the game's rulebook once, called from `analyze()`
before the prompt is built. It is keyed on the runtime-state path, not on `state_path.parent`:
all games in a run share one `artifacts/` directory, so a directory-keyed cache would hand game
2 the rulebook of game 1. The dry build checks each game carries its own and no neighbour's.

### 3.3 The correction that mattered most: one copy, not thirty

Re-sending alone would have been wrong, and this is the thing that would have quietly ruined
the experiment. `_estimate_tokens` charges `(len + 2) // 3`, so a 5,700-character rulebook is
~1,900 tokens. `_PERSISTENT_HISTORY_ASSISTANT_TURNS = 30`, and every retained user turn would
carry its own copy: ~57,000 tokens of repeated rulebook against a default
`_LOCAL_ANALYZER_CONTEXT_WINDOW` of 32,768. Arm O would have held drastically less real history
than arm B, and the arms would have differed by **two** things — the rulebook, and how much of
the game the agent could still see. A null result would have been uninterpretable.

So `_persistent_history_messages` strips the block as a turn is filed into history. The live
turn is the only copy. Measured over 40 turns with the largest block of the seven (`tn36`,
5,693 characters): **95.7% of the previous
request is still reused, 0 turns reused whole** — the divergence is always at the previous
request's final message, and everything before it is byte-stable. That cost is arm O's alone and
is worth ~1,900 tokens per retained turn.

Note that `scripts/test_prefix_stability.py`'s 97% figure does **not** cover this path: it
drives `_trim_messages_for_context` directly and never calls `_persistent_history_messages`. It
still passes unchanged, which is the arm-B check, not the arm-O one.

### 3.3.1 Does the strip survive the duck/graft path a108 actually runs?

The dry build drives `ToolAgent` directly, and a108 does not: `taaf_grafts/composite.py:284`
sets `solver_obj.analyzer_factory = make_analyzer_chain(...)` and `solver._make_analyzer`
returns early on that branch. Checked, because a graft that overrode the history filer would
reintroduce the exact confound §3.3 removes:

- **Nothing in `vendor-taaf-grafts/` overrides `_persistent_history_messages` or
  `_trim_messages_for_context`.** The only `ToolAgent` override anywhere in the grafts is
  `EfficiencyToolAgent._build_user_prompt` (`agent_ext.py:505`), which calls `super()` and
  **appends** its note after the base prompt — so the block still leads the turn, and
  `strip_block`'s `startswith` still matches.
- **The chain layers are wrappers, not subclasses.** `_CHAIN_LAYERS` is `recovery` and
  `retry_guard`, constructed as `layer(inner)`; their `analyze()` delegates inward to the real
  `ToolAgent`, so `_ensure_oracle_rules` and `_persistent_history_messages` both run. Neither
  overrides `analyze` on a `ToolAgent` subclass.
- **A fresh analyzer is built per game.** `make_stock_toolagent_factory`'s `factory(game,
  index)` constructs a new `ToolAgent(...)` per call, so `_history_messages` and
  `_oracle_rules_block` start empty for every game. That also disposes of a related hazard:
  `_ensure_session` keys on `state_path.parent`, which is one shared `artifacts/` directory for
  all games in a run, so it would never clear history mid-run if an analyzer *were* reused.
  On this path it is not.

The guard now **fails**, rather than reporting, if any prompt log carries the block more than
once — it is the only signal that would catch a regression here on pass 1.

### 3.4 The regression this found

`distill/recordings_to_sft.py` calls `ToolAgent._build_user_prompt` **unbound**, with a
duck-typed `_LedgerShim` whose docstring said it "reads exactly one attribute of `self`". Adding
a second attribute broke the human-demo SFT builder with `AttributeError`. `_LedgerShim` now
declares `_oracle_rules_block = ""` explicitly rather than the prompt reading it defensively —
which also makes it structurally impossible for a human demonstration to carry the answer key
into a training corpus, and makes a future prompt field fail loudly instead of silently dropping
out of the corpus.

## 4. The treatment-marker guard, and its output

`ARC3-Inference/scripts/check_oracle_marker.sh <run-dir> <expected-games>` — the shape
`run_style_multipass.sh:53` uses for the compact-reasoning arms:

```bash
MARK=$( { grep -l "$MARKER" "$DIR"/prompts/* 2>/dev/null || true; } | wc -l | tr -d ' ')
```

(The `|| true` is not cosmetic: `grep` exits 1 on no match, which is arm B's *expected* result,
and under `set -euo pipefail` that aborted the guard on its passing case. Caught by the dry
build.)

`ARC3-Inference/scripts/test_oracle_injection.py` proves it fires, with no model, no server and
no game engine. It drives the real `_build_user_prompt`, the real `_persistent_history_messages`
and the real `_write_prompt_log_snapshot` into a temporary run tree shaped like a real one:

```
games: 7  (dc22, g50t, m0r0, sc25, sk48, tn36, tr87)
mean first-turn user prompt: arm B 413 chars -> arm O 4,501 chars
block re-sent on turn 5 as well as turn 0: True
rulebook copies in a 3-turn request: 1 live, 0 retained in history
prefix cache, 40 turns with the largest rulebook (tn36, 5,693 chars): mean 95.7% of the previous request reused, 0 turns reused whole
--- guard, arm O (expect 7) ---
oracle_marker: games_with_treatment=7 expected=7 prompt_logs=7 max_occurrences_in_one_log=1
oracle_marker: PASS
--- guard, arm B (expect 0) ---
oracle_marker: games_with_treatment=0 expected=0 prompt_logs=7 max_occurrences_in_one_log=0
oracle_marker: PASS

all oracle injection checks passed
```

The all-25 set passes too (25 / 0), so the follow-up run needs no rebuild.

**On "exactly once".** The brief asked the guard to prove the block appears exactly once per
game. It does, and `max_occurrences_in_one_log=1` is that number — but only because of §3.3.
Had the block been left in history, the honest guard would have been a *file* count (the shape
`run_style_multipass.sh` uses; `grep -l`, not `grep -c`) and the per-log occurrence count would
have been one per retained turn. Worth stating because the two are easy to conflate.

The existing offline harness tests still pass: `test_v2_ledger.py`, `test_prefix_stability.py`,
`test_tier_a_fixes.py`, all `ALL PASSED`.

## 5. Step 3 — the contamination fence, done first

Plan §5 puts this before the first run, so it is where the work started.

`extract_sft.py` refuses any `--run-dir` whose own name or immediate parent's name matches
`*-oracle-*`, case-insensitively, with exit code 2 and nothing written, **before** the output
file is opened. There is no override flag: a legitimate reason to read an oracle run — scoring,
paired comparison, trace reading — belongs in an analysis script, not the SFT builder. The path
is deliberately not resolved to absolute first, so an unrelated ancestor (a user account named
`db-oracle-1`) cannot fence off every run on a box.

Exercised on four cases: an oracle run dir (refused), the same with a trailing slash (refused),
a clean run dir under an oracle-named parent (refused, naming the parent), and an ordinary arm-B
run dir (passes the guard and runs normally).

`ARC3-Inference/distill/README.md` is the new register of all three fences — this one, `as66`,
and the held-out seven — recording for each whether it is enforced by the tool or by the caller.
Of the slippery seven, exactly one (`tr87`) is also in the held-out split; it is measured here,
not trained on, and this fence is what keeps that distinction true.

## 6. Does this injection plausibly move a bucket-B or bucket-C game?

The brief asked for this judgement rather than a quiet ship. Using the audit's own language:

**Bucket B — `sc25`, `tn36` — yes, this is the arm for them.** The audit's cause lines are
"read the wizard as a HUD knob and the maze as a bar; never looked for a character" and "pressed
the run button seven times without ever recognising it, or the switches, as a program". The
missing thing is a fact, and the fact is the *first* rule in both rulebooks. §3a agrees: "should
clear, most of all: the controls are the first rule."

**Bucket C — `dc22`, `g50t`, `sk48` — weaker than the plan's table implies, and this is the
caveat I want on the record.** §3a predicts these "should clear: the guess is replaced by the
fact". But the audit's verdict is not that the guess was wrong; it is that *"the model does not
convert a stated uncertainty into the cheapest action that resolves it."* `g50t` is the purest
case: it "proved the goal unreachable by arrows, never pressed the fifth verb it flagged on turn
1" — it had already named the thing it needed and did not spend one keypress on it. `dc22`
"named the yellow square as a possible goal, never moved toward it in 18 actions." Handing over
a correct statement removes the uncertainty; it does not install the habit of acting on one. A
model that ignored its own correct hypothesis can ignore a supplied one the same way.

So a **null on the bucket-C three would not mean "execution is the bottleneck"** in the sense
§4's decision table reads it. It would be consistent with a third thing the table has no row
for: the agent knows and still does not probe. If the seven split B-clears-and-C-doesn't, that
split is the finding, and it points at probing protocol rather than at either of the two
investments the table offers.

`tr87` (bucket D, "stated the dictionary mechanic correctly, then spent 33 actions re-measuring
instead of translating") is predicted flat and is the internal control. `m0r0` was not in the
audit's six and is genuinely borderline.

## 7. What I did NOT verify

- **Nothing was run.** No inference, no training, no driver, no analysis, on a108 or a424 or
  anywhere. Steps 4, 5 and 6 of the plan are untouched. Every number above comes from string
  assembly and file reads.
- **No live-model turn.** The dry build exercises the prompt builder, the history filer, the
  prompt-log writer and the guard. It never constructs a `ToolAgent` through `__init__`, never
  opens a socket, and never sends a request. `_ensure_oracle_rules`'s call site in `analyze()`
  is verified by reading, not by execution.
- **The a108 driver was not read.** `~/arc3-multipass-20260918/driver.sh` could not be reached:
  `gx10-a108.tail57a229.ts.net` does not resolve from the Mac Mini in this session. The guard
  was written from the in-repo original, `ARC3-Inference/scripts/run_style_multipass.sh:53`,
  which is the same line the brief quoted.
- **The graft path was verified by reading, not by running.** §3.3.1's conclusions come from
  grep and source reading over `vendor-taaf-grafts/`; no analyzer chain was constructed and no
  game was played. The `max_occurrences_in_one_log <= 1` assertion in the guard is what would
  catch it being wrong, on the first pass.
- **No rendered page was looked at.** §2's comparison is against the live JS bundle's data, not
  against the page as a human sees it. Layout and reading order are unchecked.
- **The other 22 rulebooks were eyeballed only programmatically** — verbatim-presence, citation
  and play-note leak checks ran on all 25, but the level/category/order comparison against the
  live bundle was done for the three games named in §2.
- **Effect on the games the agent already clears is unmeasured and unmeasurable by this run**,
  because the run is seven games. That is the plan's follow-up, not an omission here.
- **The prefix-reuse figure is a simulation**, on synthetic turns with a synthetic system
  prompt, not a measurement against vLLM. It is a ratio of message-list prefixes, not observed
  cache hits.
- **The rulebooks' factual correctness is arc-explainer's**, not this repo's. If a rule is wrong
  there it is wrong here, and the oracle arm would then be measuring the agent's response to a
  false statement. Nothing in this build checks a rule against game source.
