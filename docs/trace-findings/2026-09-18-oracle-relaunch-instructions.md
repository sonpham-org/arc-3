<!--
Author: Claude Opus 5 (Bubba sub-agent, label arc3-oracle-bp2-relaunch)
Date: 18-September-2026
PURPOSE: The exact commands to resume the oracle B/O multipass driver on gx10-a108 from
whatever state it is in, so a fresh session restarts it without re-deriving anything. Written
on the Boss's 18:40 ET instruction, after the 17:48 abort left the box idle for an hour. Records
what is banked, what is invalid, the two live hazards in the driver's resume path, and the
schedule deviation the evening relaunch introduced.
SRP/DRY check: Pass - 2026-09-18-oracle-test-plan.md owns the design, 2026-09-18-oracle-test-build.md
the build, 2026-09-18-oracle-marker-guard-artifact.md the 17:48 abort and its guard fix. This owns
only the resume procedure and duplicates none of them.
-->

# Oracle multipass: how to restart the driver

**Box:** `son@100.118.4.20` (gx10-a108). **Work dir:** `~/arc3-oracle-20260918`.
**Ledger (read this first, it is append-only):** `~/arc3-oracle-20260918/guards/ledger.txt`.
**Driver:** `~/GitHub/arc-3/ARC3-Inference/scripts/run_oracle_multipass.sh`.

## 1. State as of 18:50 ET, 18-Sep-2026

| pass | arm | status |
|---|---|---|
| P1 | B | **BANKED, valid.** `runs/20260918_161821_qwen38-27b-oracle-b-p1`, rc=0, marker PASS, parity `unexpected_diffs=[]` |
| P2 | O | **ABORTED at 20 s on the old marker guard. Not a result.** Run dir renamed `runs/20260918_174825_qwen38-27b-oracle-o-p1.INVALID_MARKER_GUARD_ABORT`; `banked/P2` removed. The abort was a guard artifact, not a bad injection — see `2026-09-18-oracle-marker-guard-artifact.md`. The fixed `check_oracle_marker.sh` is deployed on a108. |
| P3 | B | **RUNNING** since 18:45:55 ET, `runs/20260918_184557_qwen38-27b-oracle-b-p2`. 90 min/game cap ⇒ ends ~20:15–20:20 ET. In-flight marker guard PASSed (0 occurrences, arm B clean). |
| P4 | O | not started |

## 2. Two hazards in the resume path — read before typing anything

1. **`banked/` is the driver's only resume memory, and it now holds `P1` alone.** A re-run with
   the default `PASS_PLAN` skips P1 and then launches **P2:O**. If P3 is still running, that
   starts a second 7-lane run against the same vLLM. Lane contention would then correlate with
   the treatment, which is precisely what this driver serialises passes to prevent. **Check for a
   live driver before every launch** (§3 step 1).
2. **`run_oracle_multipass.sh` does `rm -f "$WORK/ABORTED"` before its loop.** The sentinel from
   the 17:48 abort is preserved as `ABORTED.P2-marker-fail-1748`; the ledger text is the durable
   record. Do not read the absence of `ABORTED` as "nothing ever aborted."

There is no lock file. Serialisation is manual.

## 3. Restart procedure

**Step 1 — is anything already running?**
```bash
ssh son@100.118.4.20 'pgrep -af "run_oracle_multipass|make interactive"; tail -5 ~/arc3-oracle-20260918/guards/ledger.txt'
```
If a `run_oracle_multipass.sh` or `make interactive` is listed, **stop.** Wait for it. Do not
launch a second pass.

**Step 2 — pick the plan. Always pin `PASS_PLAN`; never take the default.**

| situation | `PASS_PLAN` |
|---|---|
| P3 finished, resume the O arm (needs the go in §4) | `P2:O:qwen38-27b-oracle-o-p1` |
| P3 died or was killed before banking, re-run arm B p2 | `P3:B:qwen38-27b-oracle-b-p2` |
| Boss authorises the full remaining B/O/B/O tail | `P2:O:qwen38-27b-oracle-o-p1 P4:O:qwen38-27b-oracle-o-p2` (P3:B is already banked) |

**Use the `P2` label, not `P4`, for the o-p1 relaunch.** The label is the driver's `banked/`
key, and the name is the run dir. Banking the o-p1 run under `P4` would leave the P2 slot
permanently empty, so every later default-plan run would try `P2:O:...-o-p1` again and create a
*second* dir matching `*_qwen38-27b-oracle-o-p1` — at which point `run_dir_for()`'s
`ls -1d ... | tail -1` silently picks one of two for the marker and parity checks. Banking it as
`P2` leaves `banked = {P1,P2,P3}` and the driver's own default plan then resolves cleanly to
`P4:O:...-o-p2` with no pinning needed.

The run name must stay `*-oracle-*` on **both** arms — `distill/extract_sft.py` refuses that glob,
and arm-B transcripts in this tree sit beside the answer key.

**Step 3 — launch, detached.**
```bash
ssh son@100.118.4.20 'cd ~/GitHub/arc-3/ARC3-Inference && \
  nohup setsid env PASS_PLAN="P4:O:qwen38-27b-oracle-o-p1" \
  bash scripts/run_oracle_multipass.sh < /dev/null \
  >> ~/arc3-oracle-20260918/driver.P4.out 2>&1 & echo launched'
```
Use a fresh `driver.<label>.out` each time; the driver appends to the ledger, not to stdout.

**Step 4 — confirm within 60 s.** The in-flight marker guard fires once all 7 prompt logs exist
(~20 s) and kills the pass if the treatment is wrong.
```bash
ssh son@100.118.4.20 'tail -8 ~/arc3-oracle-20260918/guards/ledger.txt'
```
Want: `Pn START`, `Pn env ARC3_ORACLE_RULES_DIR=...`, `oracle_marker: PASS`, `Pn marker_inflight PASS`.
On `marker_inflight FAIL` the driver kills the pass and touches `ABORTED` by design. **Do not
relaunch past a failing marker guard and do not edit the guard to get past it.** Diagnose, and if
the guard itself is wrong, say so in writing before changing it.

## 4. The O arm is NOT pre-authorised

The Boss's 18:40 ET gate stands: no O pass relaunches past a failing marker guard.

**The fact that decides it: the old assertion was unsatisfiable, not merely too strict.** An
arm-O prompt log holds `1 + analysis_steps` copies of the rulebook by construction — one in
`[MODEL INPUT]` (the message list actually sent) and one per analysis step in the
`[TURN TRANSCRIPT SO FAR]` echo, which re-prints the same turn's `[USER PROMPT]` verbatim. All
seven logs of the aborted pass read exactly 2, and scoped to `[MODEL INPUT]` alone all seven read
exactly **1**. No correct arm-O pass could ever have satisfied `MAXOCC <= 1` against the whole
file. So the rewrite is not a loosened guard; it is a guard that was never runnable.

That said, **the fix was still a guard change, and a guard change made to unblock a run is the
exact move the gate exists to stop.**
Get the Boss's explicit go before launching P4:O. Arm B needs no such go — it is the control and
its guard has passed on both passes.

## 5. Schedule deviation, recorded because it costs the comparison something

Arm B p1 ran 16:18–17:48 and arm B p2 runs 18:45–20:15. **Both evening.** The driver alternates
arms specifically so neither monopolises a time of day; for arm B that alternation is now gone.
The second-order cost is the one that bites: an arm-O pass run overnight is confounded with
time-of-day against **both** B passes rather than one, so a time-of-day effect can no longer be
partially cancelled by the pairing. The 17-Sep style experiment already logged "arms ran at
different times of day" as an unverified confound (`docs/2026-09-17-arc3-style-experiment.md` §7.3);
this repeats it deliberately, to avoid leaving the box idle overnight.

## 6. Not verified here

- That P3 completes. It was running when this was written; read the ledger for `P3 BANKED`.
- Anything about the experiment's result. No arm has been compared.
- That the fixed guard passes on a full-length arm-O pass. It has only run against the 20-second
  aborted pass and against banked arm-B passes.
