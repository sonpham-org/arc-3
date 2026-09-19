<!--
Author: Claude Opus 5 (Bubba sub-agent, label arc3-oracle-driver-and-launch)
Date: 18-September-2026
PURPOSE: Step 4 of docs/plans/2026-09-18-oracle-test-plan.md as executed: the oracle driver, the
guards it runs, what had to be done to land the arm-O code on a108's non-git deployment tree, the
evidence that pass 1 is really playing, the deviation from the plan's eight passes and what that
costs the decision rule, and the LoRA round-3 launch on a424 including the brief premise that did
not survive checking. No results: the first pass was 9 minutes old when this was written.
SRP/DRY check: Pass - the plan owns the experiment's design, harnesses/oracle-rules/MANIFEST.md
owns the variant, 2026-09-18-oracle-test-build.md owns steps 1-3. This is the run record for
step 4 and duplicates none of them.
-->

# The oracle test, launched. No results yet.

**18-September-2026, 16:18 ET.** Step 4 of the plan. The driver is running on a108, pass 1 is
arm B and is playing, and LoRA round 3 is queued on a424 behind the round-2 job. Every number
below is a guard reading or a file on disk; there is not one score in this document.

---

## 0. Status in three lines

- **Driver running:** yes. `scripts/run_oracle_multipass.sh`, a108 pid 957062, detached
  (`setsid nohup`), launched 16:18:19 ET. Pass P1 (arm B) run dir
  `runs/20260918_161821_qwen38-27b-oracle-b-p1`.
- **Guards:** pass. vLLM 765547 alive (etime 2-18:40 at launch, `/health` 200), treatment marker
  in flight `games_with_treatment=0 expected=0 prompt_logs=7` PASS, seven games in seven lanes,
  `run_config.json` `games` exactly the seven resolved ids.
- **Round 3 launched:** **queued, not yet running.** Supervisor a424 pid 1009118 waits for the
  round-2 job (pid 935181) to exit, then starts. See §5 for why it waits instead of killing.

## 1. The deviation from plan §3: four passes, not eight

Plan §3 says four passes **per arm**, eight in total. Boss's 18-Sep instruction was "four
passes," taken literally: **two per arm, four in total, B/O/B/O.**

What that costs, stated rather than argued: plan §4's third disqualifier — *"any game whose four
O passes disagree with each other more than they disagree with B"* — **is not computable on two
O passes.** Tonight's run cannot fire that check. The other two disqualifiers (a single pass is
not a result; an arm total is not a result) still hold and are still honoured.

The driver is resumable so the second cycle can be appended without re-running banked passes:
every finished pass drops a file in `$WORK/banked/`, and

```bash
PASS_PLAN="$DEFAULT_PLAN P5:B:qwen38-27b-oracle-b-p3 P6:O:qwen38-27b-oracle-o-p3 \
           P7:B:qwen38-27b-oracle-b-p4 P8:O:qwen38-27b-oracle-o-p4" \
  bash scripts/run_oracle_multipass.sh
```

skips P1–P4 and runs the rest, restoring the plan's eight.

## 2. Run names, and the fence checked against them rather than reasoned about

Four run names, **all four containing `oracle`, arm B included**: `qwen38-27b-oracle-b-p1`,
`-oracle-o-p1`, `-oracle-b-p2`, `-oracle-o-p2`. Arm B is named this way on purpose: the two arms
share this experiment's run tree, arm-B transcripts here sit beside the answer key, and
`distill/extract_sft.py`'s refusal must cover both or half the experiment is silently trainable.

`extract_sft.py` was then **run** against the literal dated dir names, not inspected:

| `--run-dir` | exit | reason printed |
|---|---|---|
| `20260918_231500_qwen38-27b-oracle-b-p1` | 2 | matches `*-oracle-*` |
| `20260919_010000_qwen38-27b-oracle-o-p1` | 2 | matches `*-oracle-*` |
| `20260919_030000_qwen38-27b-oracle-b-p2` | 2 | matches `*-oracle-*` |
| `20260919_050000_qwen38-27b-oracle-o-p2` | 2 | matches `*-oracle-*` |
| `20260918_113435_qwen38-27b-mp-compact-p1` (negative control) | 0 | not an oracle run; proceeds |

Note the shape of the glob: `*-oracle-*` needs a hyphen **after** `oracle`, so a name *ending*
in `-oracle` would not match. These four do.

## 3. a108 is not a git checkout, and that changed how the arm was deployed

The build write-up (§7) could not reach a108 and said so. Reached now, it is worse than stale:
`/home/son/GitHub/arc-3` **has no `.git`**. It is a hand-maintained deployment tree, and its
`inference/agent/` has no `frame_mode.py` and no `common_themes.py`, both of which exist in the
repo. Its `tool_agent.py` was **98,140 bytes / 38 methods** against repo main's **113,101 / 43**.

So `git apply` cannot be used — hunk 1's context is an import block a108 does not have — and
**syncing the repo's files over is worse than the patch**, because a108's `prompts.py` also
differs from the repo's and overwriting it would change **arm B's prompt**, which is the one
thing plan §2 forbids and the MANIFEST explicitly promises is untouched.

What was deployed, and nothing else: `inference/agent/oracle_rules.py` (new, no dependency on
the two missing modules), `scripts/check_oracle_marker.sh`,
`scripts/test_oracle_injection.py`, the 25 rendered rulebooks (a108 had no `datasets/` at all),
and six anchor-matched edits to a108's own `tool_agent.py` via
`scripts/apply_oracle_patch_to_deployment.py`. That script refuses rather than guesses if any
anchor is missing or non-unique, and is idempotent. Result: `98,140 -> 101,649` bytes, and the
`diff` against the pre-patch backup is **six insertions, zero deletions, zero modifications**, in
one file:

```
29a30   984a986,989   1019a1025,1042   1219a1243,1251   1688a1721,1751 / 1689a1753   1756a1821
```

Backup at `inference/agent/tool_agent.py.bak-pre-oracle-20260918`.

### 3.1 Why this matters more than a deployment chore

Every structural claim in the build write-up — §3.2 (the block survives compaction only because
it is re-rendered), §3.3 (one copy in context, not thirty), §3.3.1 (the duck/graft path does not
override the history filer) — was verified against the **local** `tool_agent.py`. The file that
executes is a108's. None of those claims had been checked against the code that runs.

`scripts/test_oracle_injection.py`, run **on a108 against a108's patched file**, is what carries
them across. It needs no model, no server and no game engine:

```
games: 7  (dc22, g50t, m0r0, sc25, sk48, tn36, tr87)
mean first-turn user prompt: arm B 2,706 chars -> arm O 6,794 chars
block re-sent on turn 5 as well as turn 0: True
rulebook copies in a 3-turn request: 1 live, 0 retained in history
--- guard, arm O (expect 7) ---  oracle_marker: games_with_treatment=7 ... max_occurrences_in_one_log=1  PASS
--- guard, arm B (expect 0) ---  oracle_marker: games_with_treatment=0 ... max_occurrences_in_one_log=0  PASS
all oracle injection checks passed
```

**The arm-B figure is the evidence that a108's real prompt builder was exercised, not the
local one**: the same test reports 413 chars on the Mac Mini and 2,706 on a108. Same test, same
arm, different prompt — because it is a different `_build_user_prompt`.

### 3.2 The link the dry build still could not reach, checked separately

`test_oracle_injection.py` sets `ARC3_ORACLE_RULES_DIR` in-process. The live path is
driver shell -> `bash -lc` -> `make` -> `uv run --no-sync inference-taaf-run`, and a variable
lost anywhere along that chain is arm O running untreated. Checked end to end before P2 needs it:

```
env= /home/son/GitHub/arc-3/datasets/explainer-games/rulebooks
dir= /home/son/GitHub/arc-3/datasets/explainer-games/rulebooks
tn36 chars= 5618
```

## 4. Why this is a separate driver, and what it guards

`run_style_multipass.sh` could not be reused with a flag swapped, as plan §6 step 4 suggested.
Its game selector is `KAGGLE_DUCK_PUBLIC_HARNESS=true`, and `_resolve_game_ids` **raises** if
that is combined with `--game`:

> `--kaggle-duck-public-harness cannot be combined with --game, --dataset, --include-tags, or --exclude-tags.`

A seven-game run therefore cannot use it, and `scripts/run_oracle_multipass.sh` is the adaptation.
The flag's only other effect is one boolean in `run_config.json` (checked by grep: two call
sites, game selection and the config dump), so dropping it changes which games are played and
nothing about how they are played.

Operating point, the multipass's: `configs/a108.qwen38.baseline.json`, `AGENT=duck-harness`,
7 lanes, `MAX_RUNTIME_MINUTES=90` (the plan's 5,400 s), `N_PASSES=1`, `qwen38-27b-nvfp4` against
the already-serving vLLM. `--game dc22,g50t,m0r0,sc25,sk48,tn36,tr87` resolves to the same seven
build ids the multipass played. **Passes run strictly sequentially**: lane contention correlates
with the treatment if they overlap. `ARC3_REASONING_STYLE` is unset on both arms — that is the
other experiment's toggle.

Per pass, into `$WORK/guards/ledger.txt`:

1. **vLLM before and after** — pid, `etime`, `/health`. A dead server before a pass aborts the
   driver instead of producing a pass of timeouts.
2. **The treatment marker, twice.** Once **in flight**, as soon as all seven prompt logs exist
   (20 s on P1), and once at the end. The in-flight check is the one that matters: the failure
   this experiment dies of is a missing `export` on one of four launches, and finding that out
   90 minutes later wastes the pass. On failure it kills the harness process tree and aborts the
   driver rather than banking a pass whose arm is unknown. It deliberately does **not** run
   before seven logs exist, because with zero logs arm B's expectation of zero passes vacuously.
3. **`run_config.json` parity against P1** — flattened and diffed, `games` compared as a sorted
   set (lane order is not promised), ignoring `generated_at` and the two kaggle kernel-name
   fields. Anything else differing means the arms were not matched.

`scripts/collect_oracle_passes.sh` is the read side: the ledger, then per banked pass the
per-game `levels_completed` / `number_of_levels` / `final_score` / `state`. It computes no
statistic and prints no total, because plan §4 forbids arm totals;
`scripts/multipass_compare.py` does the paired work when there is enough to pair.

### 4.1 Pass 1 is playing, checked rather than assumed

Nine minutes in, all seven lanes have taken actions — `solver turn start` counts dc22 5,
g50t 2, m0r0 4, sc25 4, sk48 2, tn36 2, tr87 5 — with real analyzer round trips against vLLM
(`finish=tool_calls`, `prompt_tokens≈4,050`, `completion_tokens≈340`, python tool executing).
Re-checked at 16:26 after the spawning ssh session had closed: driver alive, log still advancing.
`prompt_tokens≈4,050` with no rulebook is itself consistent with an untreated arm-B pass.

## 5. LoRA round 3 on a424, and the brief premise that did not survive checking

**The brief said the round-2 job was training "the OLD 40-record corpus ... That corpus is
superseded." It is not.** `~/arc3-round1/data/sft_fenced.jsonl` is 40 records / 440 assistant
turns of **model-trace** SFT from `extract_sft.py` over the `20260915_230835_...baseline-25g` and
`20260916_102724_...massdata-25g-4p` run dirs. It is not an earlier cut of the human demos; it is
a different corpus answering a different question. Round 3 does not supersede it.

Given that, round 2 was **not killed**. Three reasons, in the brief's own order of authority:

1. The brief's conditional — "check whether that job is near done" — is satisfied: **step 44 of
   58**, 3 h 48 m sunk, ETA 1.18 h, checkpoints banked at steps 8/16/24/32/40 with the last two
   rungs of the evaluable ladder outstanding.
2. The brief says the plan wins on conflict.
   `docs/trace-findings/2026-09-18-arc3-lora-round2-heldout-eval.md` §7: *"Never run training
   concurrently with another GPU job. GB10 memory is unified; a second allocation invokes the
   kernel OOM killer and takes bystander processes with it."* Overlap is not an option, so the
   choice was kill-or-wait, not kill-or-parallel.
3. That same document's Results section is `PLACEHOLDER — filled in when the run completes`.
   Killing at 44/58 destroys the result a committed repo doc is waiting for.

So `scripts/run_lora_round3.sh` polls `kill -0 935181` (it is not the supervisor's child, so
`wait` is unusable), logs round 2's final `== STEP` line so a crash cannot be reported as a
completion, settles 120 s, and launches. It does **not** gate on `nvidia-smi
--query-gpu=memory.used`, which returns `[N/A]` on this box.

### 5.1 The corpus, generated with the merged tooling and verified twice

Generated on the Mac Mini from repo main (where PR #52 is merged), so the prompt builder writing
the records is the current one:

```bash
python3.13 distill/recordings_to_sft.py \
  --recordings-dir ../datasets/decision-steps/v0/recordings \
  --human-play ~/GitHub/arc-explainer/shared/arc3Games/humanPlay.generated.json \
  --out ../scratch/sft_human_windowed.jsonl --inline-images \
  --exclude-games vc33,ar25,sb26,re86,su15,tr87,tu93,as66
```

**89 records / 2,281 assistant turns**, which is exactly what
`2026-09-18-human-demos-to-sft.md` §1 publishes for "windowed, held-out fence applied", and the
per-game table reproduces too (bp35 9/246, g50t 14/394, dc22 6/173, ...). Then re-verified on
a424 with the training venv's **own tokenizer**, CPU-only, via `train_lora.py --measure-only`:

```
records_in 89   records_trained 89   over_max_seq 0   zero_supervised_dropped 0
turns_trained 2281   images_trained 2281   total_tokens 1,037,092
tokens_min 5,144   tokens_median 12,632   tokens_max 13,495
ETA estimate 4.76 h for 4 epochs
```

`tokens_max 13,495` is the same number the write-up's §8 reports, and `over_max_seq 0` confirms
its "0 records over 19,046 and 0 over 31,744". Corpus md5 `fef79e06…` matches on both boxes.

### 5.2 Round 3 differs from round 2 in one thing

Hyperparameters are round 2's, unchanged: `--epochs 4 --grad-accum 2 --lr 1e-4 --schedule cosine
--seed 0 --probe`. a424's `distill/train_lora.py`, `sft_batch.py` and `corpus_adapter.py` are
**byte-identical to repo main** (md5s compared), so the training code is not a second difference
either. Only the checkpoint cadence is rescaled: 89 records x 4 epochs / 2 accum = **178 steps**,
so `--save-every 24 --census-every 12` reproduces round 2's ~7-checkpoint, 14-census ladder.

`--probe` is kept, though `--probe-start` defaults to 45,056 and this corpus tops out at 13,495,
so the ladder probes far above anything round 3 needs. It is kept for the step-0 pre-flight
census (`lora_A 0/208 nonzero`, `lora_B 208/208`), which is the part that catches a dead
adapter.

## 6. A mistake I made on a108, and what it did

Checking §3.2's env propagation, the command used bare `uv run` instead of the Makefile's
`uv run --no-sync`. **That resynced the shared `.venv` to `uv.lock`** — "Uninstalled 10 packages,
Installed 10 packages", numpy now 2.2.6 — while both pass 1 and the vLLM server were running out
of that venv.

Checked immediately afterwards: vLLM 765547 still up (etime 2-18:48), `/health` 200,
`import vllm` -> 0.26.0, pass 1 still issuing analyzer requests and advancing, no `ImportError`
or `Traceback` in the pass log. Nothing broke — a running process holds its loaded modules and
its open inodes. But if that venv had been deliberately hand-pinned away from `uv.lock`, that
drift is now gone and this is where to look. `--no-sync` is in the Makefile for this reason.

## 7. What I did NOT verify

- **No results, of any kind.** Pass 1 was 9 minutes into a 90-minute cap when this was written.
  Nothing here is a score, a level clear or a delta, and §3a's per-game predictions are untested.
- **No arm-O pass has run.** Arm O's marker guard has passed in the dry build on a108 and the env
  var has been proven to reach python through `uv run`, but **P2 is the first time the rulebook
  will be in front of the model**, and the in-flight guard at ~20 s into P2 is what confirms it.
  If that guard fails the driver aborts itself and passes P3/P4 will not run.
- **`_ensure_oracle_rules`'s call site was never executed.** It is verified by reading a108's
  patched `analyze()` and by the diff; the dry build drives `_build_user_prompt` directly.
- **The graft path is still verified by reading only.** §3.3.1's conclusions came from grep over
  `vendor-taaf-grafts/` on the Mac Mini's tree, and a108's graft tree was not re-grepped. The
  guard's `max_occurrences_in_one_log <= 1` assertion on P2 is what would catch it.
- **The parity check has no reference yet.** P1's `run_config.json` becomes it when P1 banks, so
  P1's own parity line will be vacuous and only P2/P3/P4 are really compared.
- **Round 3 is not running.** It is a supervisor waiting on a pid. That it will start when 935181
  exits is untested by construction; the evidence will be a `LAUNCH round3` line in
  `/home/son/arc3-round3/queue.log`.
- **Round 2's completion is unverified.** It was at 44/58 at decision time. Whether it reaches
  58/58 or dies is recorded by the supervisor, not predicted here.
- **The rulebooks' factual correctness is still arc-explainer's**, as in the build write-up.
- **The human-demo corpus was not re-audited.** The 89/2,281 match and the tokenizer figures are
  count agreement with PR #48/#52, not a re-derivation of the windowing proofs.
