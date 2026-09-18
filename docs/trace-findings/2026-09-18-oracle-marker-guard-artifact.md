<!--
Author: Claude Opus 5 (Bubba subagent, label arc3-oracle-marker-fix-and-relaunch)
Date: 18-September-2026
PURPOSE: Why the oracle test driver aborted 20 seconds into arm-O pass 1 on a108, what the
"second copy" of the rulebook actually was, and why the fix is to the guard rather than to the
injection. Records the evidence that settled it (the wire message lists), the guard rewrite,
the proof that the banked arm-B pass 1 still stands, and what is still unverified.
SRP/DRY check: Pass - docs/plans/2026-09-18-oracle-test-plan.md owns the experiment's design and
2026-09-18-oracle-test-build.md owns the build record for steps 1-3. This owns one abort and its
fix, and duplicates neither.
-->

# The second copy was the log, not the prompt

**18-September-2026.** The oracle driver (`run_oracle_multipass.sh`, pid 957062) aborted itself
at 17:48:43 ET, 20 seconds into arm-O pass 1, on its own in-flight marker guard. Arm-B pass 1 had
finished clean 20 seconds earlier. vLLM (pid 765547) was never touched and is still serving.

The ledger line:

```
oracle_marker: games_with_treatment=7 expected=7 prompt_logs=7 max_occurrences_in_one_log=2
oracle_marker: FAIL -- a prompt log carries the rulebook 2 times; expected at most 1
```

## 1. The tension that had to be resolved first

Plan §2 requires the rulebook be "in context from action 1 and survive compaction ... re-sent or
pinned, not left to eviction". A block that is deliberately re-sent can legitimately appear more
than once in a log. But commit 67c03956d hardened the guard to fail on a second copy, because a
block left in the retained history would cost arm O ~1,900 tokens per retained turn and leave it
holding less real history than arm B — a second difference between the arms, which would make a
null result uninterpretable (build doc §3.3).

Both cannot be right. Two candidate readings:

- **(a)** a legitimate re-pin, and the guard is too strict — count per rendered prompt, not per log
- **(b)** a genuine double-injection, and the injection is wrong — fix that, never the guard

It was neither.

## 2. What the second copy is

**(c) The guard counted the wrong artifact.** A prompt log is not a rendered prompt.
`tool_agent._write_prompt_log_snapshot` writes two sections to one file:

```python
f.write("\n\n[MODEL INPUT]\n");            f.write(rendered_messages.strip())
f.write("\n\n[TURN TRANSCRIPT SO FAR]\n"); f.write(transcript_text)
```

`[MODEL INPUT]` is the message list. `[TURN TRANSCRIPT SO FAR]` re-prints the **same turn's**
`[USER PROMPT]` once per analysis step. In `g50t-5849a774_p0.log`, at `analysis_step: 1`:

| line | section | copy |
|---|---|---|
| 102 | `[MODEL INPUT]` → `[USER]` | 1 |
| 247 | `[TURN TRANSCRIPT SO FAR]` → `[USER PROMPT]` | 2 |

Same turn, same text, printed twice by the writer. All seven logs read exactly 2, identically.

**An arm-O log therefore holds `1 + analysis_steps` copies — a floor of 2, always, with a
perfectly correct single-copy injection.** The old assertion could not have been satisfied by any
arm-O pass. It was not too strict; it was unsatisfiable.

## 3. The evidence that the injection is correct

The prompt log is a rendering for humans. The wire message list is
`<run>/<game>_p0_requests.jsonl`, one JSON record per request actually sent to vLLM. Across all
seven games of the failed pass:

```
req 0  msgs 2  total_copies 1  per [('system', 0), ('user', 1)]
```

`message_count: 2` in the snapshot header agrees. One copy, in the live user message, zero in the
system prompt — exactly what build doc §3.3 designed. **The injection was never wrong.** No
re-pin had happened either: the pass was 20 seconds old and history was still empty.

## 4. Why the dry build passed and the live run did not

`test_oracle_injection.py` drove the real writer with `transcript="(dry build)"` — a placeholder
containing no rulebook. That is the only reason `max_occurrences_in_one_log=1` was ever printed.
The test now feeds the writer a real turn transcript (`_turn_transcript`), so the dry build sees
the same floor of 2 a live run does.

## 5. The fix

`check_oracle_marker.sh` now asks its two questions of two different artifacts:

| check | artifact | assertion |
|---|---|---|
| **treatment** (the export check) | prompt-log FILES carrying the marker | `== expected` (7 in O, 0 in B) |
| **retention** (the confound check) | every request in `*_requests.jsonl` | no single message list carries the block more than once |

The per-file occurrence figure is still printed, labelled `log_occurrences_max`, with its
`1+analysis_steps` construction stated inline, and is **not** asserted on.

This is strictly stronger than what it replaces, not weaker, and that is the claim to check
rather than take on trust:

- The retention assertion now runs against **the bytes sent to the server**, not a human-readable
  echo of them.
- It **accumulates**. One JSON line per request, so by turn 5 it has genuinely exercised
  `_persistent_history_messages` on the live duck/graft path — which the old check never could,
  because it fired at 20 seconds against an empty history and would have aborted before reaching
  the turn where the confound becomes visible.
- `test_oracle_injection.py` now includes a **deliberate double-injection** case — the block put
  back into a retained history turn, which is what a graft overriding the history filer or a
  `strip_block` whose `startswith` stopped matching would produce. The guard refuses it, rc=1.

Nothing under `ARC3-Inference/inference/` changed. `git diff origin/main --
ARC3-Inference/inference/` is empty, which is the point of §6.

## 6. Arm-B pass 1 stands

`runs/20260918_161821_qwen38-27b-oracle-b-p1`, rc=0, config parity `unexpected_diffs=[]`.

The argument is structural, not empirical: the fix touches only
`ARC3-Inference/scripts/check_oracle_marker.sh` and
`ARC3-Inference/scripts/test_oracle_injection.py`. Neither is imported by the harness, and the
empty `inference/` diff means arm B's rendered prompt is **byte-identical** before and after. A
re-run could not produce a different prompt; it could only spend 90 minutes of box time and add
seed variance.

The fixed guard re-run against it, unchanged on disk:

```
games_with_treatment=0 expected=0 prompt_logs=7 log_occurrences_max=0
requests_files=7 requests=247 max_copies_in_one_request=0 requests_with_zero_copies=247
oracle_marker: PASS
```

247 wire requests, zero rulebook text on any of them. B p1 is a valid control pass and is not
re-run. The relaunch resumes at P2.

## 7. The aborted O pass is fenced, not reused

`runs/20260918_174825_qwen38-27b-oracle-o-p1` re-classifies as PASS under the fixed guard — it
was a valid arm-O pass, correctly treated, that got killed at 20 seconds. It is still **not a
result**: seven games, one request each, no level attempted. An `INVALID_MARKER_GUARD_ABORT`
marker file was written into the run dir and the driver's `banked/P2` pointer removed, so nothing
globbing `*oracle-o*` can count it as an O pass. The relaunch writes `-o-p1` afresh under a new
timestamp.

## 8. What I did NOT verify

- **That every arm-O request carries exactly one copy for a whole pass.** The guard asserts
  `<= 1` and *reports* `requests_with_zero_copies`; it does not assert `== 1`. A request shape
  built by the `recovery` or `retry_guard` chain layer, or a `request_index_within_turn > 1`
  retry, could in principle render without the block, and there is no long arm-O run to check
  that against — the aborted pass has one request per game. Asserting `== 1` on an unproven
  invariant would abort a valid pass at turn 40. `requests_with_zero_copies` on the final check
  of P2 is the number that settles it, and the write-up must read it.
- **That the block survives a real compaction.** Plan §2's requirement is met by construction
  (re-rendered every turn in `_build_user_prompt`), verified by reading and by the offline dry
  build, and never yet by a live turn past a compaction event.
- **The transcript-echo count as a function of turn depth.** Arm-B pass 1's final snapshots all
  happen to sit at `analysis_step=1`, so the observed floor is 2. A multi-step turn would print
  more; the dry build shows 3 with two analysis steps. The guard no longer cares, which is why
  this was not pinned down further.
- **Nothing about the experiment's result.** No arm was compared, no level counted. This is one
  abort and its fix.

---

## 9. The relaunch, and a schedule deviation I chose not to correct

**The box state I found at 18:40 ET was not the state the brief described.** A sibling session
(`arc3-oracle-bp2-relaunch`) launched arm-B **pass 2** at 18:45:55 on Boss's 18:40 instruction,
pinned to `PASS_PLAN="P3:B:qwen38-27b-oracle-b-p2"`, five minutes after this session started
diagnosing. By the time the fix was ready it was four minutes in, in-flight marker guard PASSed,
and producing turns.

So the realised schedule is **B, B, then O, O** — not the plan's B/O/B/O.

**That is a real cost, not a footnote.** The driver alternates arms "so neither monopolises a time
of day"; with both B passes in the evening, any overnight O pass is confounded with time of day
against *both* of them rather than one.

**I did not preempt it, and the reasoning should be checkable.** Killing P3 would have bought
B(16:18), O(~18:55), B(~20:30), O(~22:05) — still both O passes later than both B passes, because
the aborted O already burned the 17:48 slot. An irreversible action against a sibling's live work,
for a reordering that does not actually equalise time of day. Plan §4 already contains the test
that surfaces a time-of-day effect if one exists — "any game whose four O passes disagree with each
other more than they disagree with B" — so **the write-up must apply that test explicitly**, and
must not treat B,B,O,O as equivalent to the design. Logged in the a108 ledger as `DEVIATION
ACKNOWLEDGED`, agreeing with the sibling's own 18:50 note.

`ARC3-Inference/scripts/sequence_oracle_remaining_passes.sh` sequences the two remaining arm-O
passes **behind** P3 rather than beside it, because plan §3 forbids concurrent passes — two 7-lane
runs on one vLLM correlates lane contention with the treatment. It polls driver pid 963617 to exit,
then invokes the driver with `PASS_PLAN="P2:O:qwen38-27b-oracle-o-p1 P4:O:qwen38-27b-oracle-o-p2"`.

Its guard gate, all of which must be clear or nothing launches: no `ABORTED` file; no live driver
(`pgrep -x -f`, exact whole-cmdline — a loose `-f` matches the sibling's launcher shell, which was
still alive, and any ssh command line mentioning the driver, and would have blocked forever); P2
and P4 still unbanked; vLLM `/health` 200. It takes `.seq.lock` via `mkdir` so a second sequencer
cannot start, and announced its ownership of P2 and P4 in the ledger, which is the only
coordination channel the sessions share.

It then asserts **liveness rather than a pid**: four minutes after firing it requires the `-o-p1`
run dir to exist with seven prompt logs, and the total `*_requests.jsonl` line count to be *higher*
two minutes later than it was. `SEQ LIVENESS PASS`/`FAIL` goes in the ledger. A launched-and-dead
driver reported as running is the failure mode this exists to close.

**What this session did not and could not verify:** that the arm-O pass is producing turns. It
fires at roughly 20:16 ET, after this session ends. The liveness check above is the substitute, and
`SEQ LIVENESS` in `~/arc3-oracle-20260918/guards/ledger.txt` is the line to read — not a pid, and
not this document.

Also on the record: `check_oracle_marker.sh` was replaced on a108 at 18:48 ET while P3 was
mid-pass, so P3's final check runs the new guard. That is safe and was checked rather than assumed
— the new guard returns PASS on the live P3 dir, and on B p1's completed 90-minute dir (30 MB of
`*_requests.jsonl`, 247 requests) in 0.13 s.
