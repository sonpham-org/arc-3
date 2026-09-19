<!--
Author: Claude Opus 5 (Bubba sub-agent, label arc3-round3-heldout-eval)
Date: 19-September-2026
PURPOSE: Held-out evaluation of the round-3 LoRA adapter (human-demo corpus) against base
  and the round-2 adapter. Records the authoritative held-out game set, the teacher-forced
  held-out CE measurement on a424, the vLLM/LoRA serving feasibility finding on a108, and
  the honest verdict. Written to answer Son Pham's ask in #arc-3 and to satisfy Hermes'
  standard: training loss falling is not the signal; a held-out number is.
SRP/DRY check: Pass - measurement is run by distill/eval_lora.py and the ARC3 harness; this
  doc only records method, numbers, and verdict. The held-out split is owned by
  extract_sft.py and is cited, not redefined.
-->

# ARC-3 LoRA round 3 — the held-out evaluation — 19-Sep-2026

**Status: COMPLETE.** Both gameplay arms finished `rc=0`; all numbers below are measured.

---

## 0. The held-out game set, established from the code

Authoritative source: `ARC3-Inference/distill/extract_sft.py`. The fence is a single matcher
applied at game granularity before any record is built (`build_records`, the `dropped =`
expression), read one way by `--exclude-games` (training) and the other way by `--only-games`
(eval). Sharing one matcher is deliberate: an independently written eval filter could disagree
with the training fence and leak a trained-on game into the held-out numbers.

The fence list itself is pinned in the `--exclude-games` help text:

> `vc33,ar25,sb26,re86,su15,tr87,tu93,as66`

`as66` is the withdrawn 26th game and is not present in any run dir on either box
(see `2026-09-15-as66-the-withdrawn-26th-game.md`). So the operative held-out set is the
**seven** codes `ar25 re86 sb26 su15 tr87 tu93 vc33`.

**Round 3 respects this fence.** Its training corpus
(`/home/son/arc3-round3/data/sft_human_windowed.jsonl`, 89 records) contains exactly twelve
game codes, counted directly from the JSONL:

`bp35(9) cd82(6) cn04(6) dc22(6) ft09(6) g50t(14) ka59(7) lp85(8) ls20(7) m0r0(6) r11l(6) s5i5(8)`

Intersection with the held-out seven: **empty**. Verified by set comparison, not by eye.

### `tr87` — why it is in the fence but not in the CE corpus

The held-out CE corpus has 40 records over **six** games, not seven. `tr87` is missing.
Checked directly rather than assumed: `tr87-cd924810` has viewer_data in two run dirs
(`20260711_200118_a424-duck-25game`, `20260711_231159_a424-duck-think-3x`), and
`_solved_level_count()` returns **0** for both. Rejection sampling (`--only-solved`) therefore
drops it. It has artifacts; it has no solved levels.

Consequence: `tr87` is unusable for teacher-forced CE but **is** playable in a gameplay pass,
so the CE arm and the gameplay arm legitimately cover different game counts (6 vs 7).

---

## 1. Pre-registration — written before the numbers were read

This matters more for round 3 than it did for round 2, and the reason is a distribution
mismatch that did not exist last round.

- Round 2 trained on **model traces** extracted by `extract_sft.py` and was evaluated on
  **model traces** from held-out games. Matched distribution.
- Round 3 trained on **human demonstrations** (`sft_human_windowed.jsonl`) and is evaluated
  on the same **model-trace** held-out corpus. **Mismatched.**

Teacher-forced CE on model traces measures *"does this adapter predict the base model's own
token distribution on unseen games."* An adapter trained to imitate humans should move **away**
from that distribution. So, fixed in advance:

| Outcome | Reading |
|---|---|
| CE **down** | weak positive; could equally be generic fluency |
| CE **up** | **not** evidence of harm — it is the expected sign under distribution shift |
| CE **flat** | no information |

**Held-out CE is not an ARC-3 score and must not be reported as one.** For round 3 it is close
to non-diagnostic in either direction. The gameplay pass (§3) is the measurement that can
actually answer Son's question.

### Harness-validity check

The round-2 adapter is scored as a second arm on the *same* corpus in the *same* model load.
Round 2's banked result on this exact corpus was a uniform improvement across all six games.
If the round-2 arm reproduces that here, the measurement apparatus is sound and the round-3
number is real signal about round 3. **If the round-2 arm does not reproduce, nothing from
this run is usable** — that dependency is stated before the numbers, not after.

---

## 2. STEP 1 — teacher-forced held-out CE (a424)

Run on gx10-a424 with the GPU otherwise idle. All three arms — `base`, `round2`, `round3` —
scored in a **single model load** via PEFT's multi-adapter API, so every arm saw a
bit-identical batch; two processes would re-encode the images and preprocessing
nondeterminism would land in the delta and read as learning.

```bash
/home/son/arc3-train-venv/bin/python -u distill/eval_lora.py \
  --corpus /home/son/arc3-round1/data/sft_heldout.jsonl \
  --model /home/son/models/Qwen3.8-27B-BF16 \
  --adapter round2=/home/son/arc3-round2/ckpt/adapter \
  --adapter round3=/home/son/arc3-round3/ckpt/adapter \
  --out distill/results/2026-09-19-round3-heldout-eval.json
```

The venv python is invoked directly rather than through `uv run`; a bare `uv run` resynced the
shared venv mid-run on 18-Sep and is a known hazard on this box. `--max-seq` left at 0 (no cap):
the eval is forward-only, so the 43,687-token *training* cap does not apply, and capping here
would rebuild round 1's long-record bias inside the measurement meant to detect it.

Corpus: 40 records, 298 turns, 557,157 supervised tokens (1,031,188 total), 8,353 / 24,738 /
53,956 tokens min / median / max. `rc=0`, 40/40 scored, 0 skipped, wall 3,859s.

**Sanity gate passed** — every adapter arm differs from base, so neither adapter is a no-op:
`base 0.897728 | round2 0.861535 | round3 0.907147` on the gate record.

### Corpus aggregate

| arm | token-weighted CE | ppl | record-mean CE |
|---|---|---|---|
| base | 0.558503 | 1.7481 | 0.570347 |
| round2 | **0.544508** | 1.7238 | 0.553078 |
| round3 | 0.566870 | 1.7627 | 0.579631 |

### Paired per-record deltas vs base (n = 40)

| arm | improved | worsened | mean Δ | sd | se | t | min Δ | max Δ |
|---|---|---|---|---|---|---|---|---|
| round2 | **40** | 0 | **−0.01727** | 0.008916 | 0.001410 | −12.25 | −0.050206 | −0.005421 |
| round3 | 1 | **39** | **+0.009284** | 0.005635 | 0.000891 | +10.42 | −0.006597 | +0.022241 |

### Per game

| game | records | round2 mean Δ | round3 mean Δ | round2 improved | round3 worsened |
|---|---|---|---|---|---|
| ar25 | 7 | −0.01553 | +0.01017 | 7/7 | 7/7 |
| re86 | 8 | −0.01753 | +0.00568 | 8/8 | 8/8 |
| sb26 | 8 | −0.02757 | +0.00982 | 8/8 | 7/8 |
| su15 | 5 | −0.01420 | +0.01541 | 5/5 | 5/5 |
| tu93 | 3 | −0.01117 | +0.00625 | 3/3 | 3/3 |
| vc33 | 9 | −0.01298 | +0.00894 | 9/9 | 9/9 |

### Reading this, per the §1 pre-registration

**The harness-validity check passed.** The round-2 arm reproduced its banked result — a uniform
improvement, all six games, 40/40 records — on this corpus, in this model load, alongside
round 3. The apparatus is sound, so the round-3 number is a real measurement of round 3 and not
an artifact.

**The round-3 number lands in the pre-registered "CE up" cell, and that cell says: not evidence
of harm.** Round 3 trained on human demonstrations; this corpus is model traces. An adapter
that has been pulled toward human behaviour *should* predict the base model's own token
distribution less well. A +0.0093 mean CE delta is what that looks like. It is highly
consistent (39/40, t = +10.4) — but consistency here measures how reliably the adapter moved
off the base distribution, **not** whether it plays ARC-3 better or worse.

**This step cannot answer Son's question, and it was never going to.** Held-out CE is not an
ARC-3 score. For round 3 specifically it is close to non-diagnostic in either direction, which
is why STEP 3 exists and why the interpretation was fixed in writing before the numbers were
read.

---

## 3. STEP 2 — can a108 serve this model with a LoRA adapter?

**Verdict: YES. Confirmed empirically, not from documentation.**

### The serving stack, as actually installed

a108 serves `/home/son/models/Qwen3.8-27B-NVFP4` — architecture
`Qwen3_5ForConditionalGeneration`, `model_type qwen3_5`, quantization `compressed-tensors`.
Note this is **NVFP4**, while the adapter was trained against
`/home/son/models/Qwen3.8-27B-BF16` (per its own `adapter_config.json`). Different weights.

There are two vLLM installs on the box and they are **not** the same version:

| Path | Version | Serves the harness? |
|---|---|---|
| `/home/son/venv` | 0.19.0 | no |
| `ARC3-Inference/.venv` | **0.26.0** | **yes** (`SERVER_VENV_PYTHON ?= $(REPO_ROOT)/.venv/bin/python`) |

This mattered. In 0.19.0, `Qwen3_5ForConditionalGeneration` has an
`update_packed_mapping(enable_lora=...)` method that splits the fused GDN projection into
`in_proj_qkv` / `in_proj_z` specifically when LoRA is on. **In 0.26.0 that method does not
exist at all**, and `packed_modules_mapping` maps `in_proj_qkvz -> [in_proj_qkv, in_proj_z]`
unconditionally. Our adapter's `target_modules` are
`o_proj, in_proj_z, in_proj_qkv, k_proj, out_proj, v_proj, q_proj` — i.e. it targets exactly
the modules whose handling differs between the two versions.

That is a real theoretical risk of a **silent no-op**: adapter loads, server returns 200, LoRA
applies to nothing, and the gameplay arms come out identical for a reason that has nothing to
do with learning. It was resolved by measurement rather than by reading more source.

### The harness already supports LoRA serving — no tree modification required

`ARC3-Inference/Makefile` carries first-class LoRA variables (`SERVER_ENABLE_LORA`,
`SERVER_LORA_PATH`, `SERVER_LORA_ALIAS`, `SERVER_MAX_LORA_RANK ?= 16`, `SERVER_MAX_LORAS`),
passes `--enable-lora --max-loras --max-lora-rank --lora-dtype` to `vllm serve`, and then
POSTs the adapter to `/v1/load_lora_adapter` once the server is healthy. All of these are
overridable as make variables, so **nothing under `ARC3-Inference/inference/` was touched and
no file was created in a108's tree** (which is confirmed *not* a git checkout — `git status`
there returns `fatal: not a git repository`).

Launch used, verbatim:

```bash
cd /home/son/GitHub/arc-3/ARC3-Inference && make server \
  CONFIG_PATH=configs/a108.qwen38.baseline.json \
  SERVER_ENABLE_LORA=true \
  SERVER_LORA_PATH=/home/son/arc3-adapters/round3 \
  SERVER_LORA_ALIAS=round3 \
  SERVER_MAX_LORA_RANK=16 SERVER_MAX_LORAS=1
```

Result: `rc=0`, weights loaded in 144.15s, `enable_lora: True` in the engine args, adapter
loaded, and `/v1/models` lists both `qwen38-27b-nvfp4` and `round3`.

### Proof the adapter actually applies

A greedy chat A/B (`temperature 0`, `seed 0`) returned **byte-identical** text for both arms.
That is the exact signature of a silent no-op, so it was not accepted as an answer — a short,
confidently-answered prompt can produce the same argmax under a small weight perturbation.

The decisive test was token logprobs on `/v1/completions`, same prompt, greedy, seed 0:

| arm | continuation | first five token logprobs |
|---|---|---|
| `qwen38-27b-nvfp4` | `": if a cell is"` | −0.052090, −2.205686, −1.325727, −0.930945, −1.083302 |
| `round3` | `": fill the grid with"` | −0.030329, −1.881417, −0.822924, −0.334075, −0.469267 |

Different tokens **and** different logprobs, and each arm reproduced its own numbers exactly
when the pair was run twice. The adapter is being applied to the NVFP4 base.

### Oracle confound — the honest version

The brief asked me to flag that relaunching vLLM with `--enable-lora` confounds the banked
oracle passes. The situation on disk is different from what the brief assumed, so here it is
as found:

- `banked/` holds **P1, P2 and P3**.
- All three ran against vLLM **pid 765547** (`etime=3-00:09:54` at 21:47 on 18-Sep).
- **P4 was launched** 2026-09-18T21:47:18, was mid-`g50t-5849a774` at 21:58, and **died in the
  08:09:59 reboot on 19-Sep**. It is incomplete, not banked. There is no `P4 END` in the ledger.
- **That server no longer exists.** It was killed by the reboot, hours before I touched anything.

So I did not disturb a live server; there was none. The parity guarantee the oracle actually
relies on is **config-level**, not process-level: `run_oracle_multipass.sh`'s `parity()`
diffs each pass's `run_config.json` against P1's, ignoring only `.generated_at` and two Kaggle
slug fields.

The real residual risk is therefore narrow and I am stating it loudly:

> **A future oracle P4 must relaunch vLLM WITHOUT `--enable-lora`.** `--enable-lora` is a
> server-level difference (it also flips `cudagraph_specialize_lora: True` and enables dynamic
> LoRA load/unload in the API router). It does not appear in `run_config.json`, so the oracle's
> own parity check **would not catch it**. Do not inherit my server for P4.

I used no separate port and created no config file; the server is the stock
`a108.qwen38.baseline.json` plus the LoRA flags, and it is torn down at the end (§4).

---

## 4. STEP 3 — matched gameplay passes on the held-out games

Two passes, **sequential, never concurrent**, against the **same** vLLM server, differing in
one thing: which model id the analyzer asks for.

```bash
cd /home/son/GitHub/arc-3/ARC3-Inference && make interactive \
  CONFIG_PATH=configs/a108.qwen38.baseline.json \
  GAME="ar25-0c556536,re86-8af5384d,sb26-7fbdac44,su15-1944f8ab,tr87-cd924810,tu93-0768757b,vc33-5430563c" \
  MODEL=<qwen38-27b-nvfp4 | round3> \
  RUN_NAME=round3-heldout-<base|lora> CONCURRENT_JOBS=7 N_PASSES=1
```

All seven held-out games including `tr87` (it has no *solved-level records*, which only barred
it from the CE corpus; it is perfectly playable). Both run dirs confirm `game_count: 7` and the
exact seven ids — checked on disk ~70s into each pass, before committing to the 90 minutes,
rather than discovered afterwards.

| arm | run dir | started | ended | rc |
|---|---|---|---|---|
| base | `runs/20260919_120114_round3-heldout-base` | 12:01:12 | 13:31:16 | 0 |
| adapter | `runs/20260919_133433_round3-heldout-lora` | 13:34:31 | 15:04:35 | 0 |

### Parity

Running the oracle's own `parity()` logic over the two `run_config.json` files
(same flatten, same ignore set):

```
unexpected_diffs = ['.model']
  .model: base='qwen38-27b-nvfp4'  lora='round3'
```

**The only configuration difference between the arms is the model id** — the variable under
test. Same games, same order, same 7 lanes, same 102,985 context, same temperature 1.0 /
top_p 0.95 / top_k 20, same 90-minute per-game cap, same server process, same pinned settings
from `a108.qwen38.baseline.json` whose `_pin.note` demands exactly that.

### Results, per game

`lv` = levels cleared. `err` = turns lost to vLLM read timeouts (`request_error`, no response
at all — see the timeout note below). `tool%` = share of turns that **did** get a response and
emitted at least one tool call.

**BASE arm** (`qwen38-27b-nvfp4`)

| game | lv | /total | score | actions | turns | tool-ok | tool% | terminated |
|---|---|---|---|---|---|---|---|---|
| ar25 | 1 | 8 | 2.778 | 23 | 19 | 2 | 100% | gave_up |
| re86 | 1 | 8 | 1.954 | 31 | 13 | 3 | 100% | gave_up |
| sb26 | 1 | 8 | 2.778 | 55 | 21 | 1 | 100% | gave_up |
| su15 | 1 | 9 | 2.222 | 24 | 20 | 1 | 100% | gave_up |
| tr87 | 0 | 6 | 0.000 | 36 | 14 | 2 | 100% | gave_up |
| tu93 | 1 | 9 | 0.334 | 81 | 15 | 1 | 100% | gave_up |
| vc33 | 2 | 7 | 10.714 | 20 | 21 | 1 | 100% | gave_up |
| **TOTAL** | **7** | 55 | **20.780** | 270 | 123 | 11 | **100%** | 7/7 gave_up |

**ADAPTER arm** (`round3`)

| game | lv | /total | score | actions | turns | tool-ok | tool% | terminated |
|---|---|---|---|---|---|---|---|---|
| ar25 | 0 | 8 | 0.000 | 32 | 24 | 1 | 100% | gave_up |
| re86 | 0 | 8 | 0.000 | 52 | 38 | 1 | 100% | gave_up |
| sb26 | 1 | 8 | 0.510 | 44 | 42 | 1 | 100% | gave_up |
| su15 | 0 | 9 | 0.000 | 50 | 56 | 1 | 100% | gave_up |
| tr87 | 0 | 6 | 0.000 | 1 | 9 | **5** | 100% | gave_up |
| tu93 | 0 | 9 | 0.000 | 39 | 13 | **3** | 100% | gave_up |
| vc33 | 1 | 7 | 0.194 | 51 | 52 | 1 | 100% | gave_up |
| **TOTAL** | **2** | 55 | **0.705** | 269 | 234 | 13 | **100%** | 7/7 gave_up |

### Head to head

| metric | base | adapter | change |
|---|---|---|---|
| levels cleared | **7** | **2** | **−5** |
| total score | **20.780** | **0.705** | **−96.6%** |
| games improved | — | **0 / 7** | — |
| games regressed | — | **5 / 7** | ar25, re86, su15, tu93, vc33 |
| games tied | — | 2 / 7 | sb26 (1=1), tr87 (0=0) |
| actions | 270 | 269 | ≈ equal |
| solver turns | 123 | 234 | +90% |
| mean turn wall time | 307.2s | 161.5s | −47% |
| tool-validity (of answered turns) | **100%** | **100%** | none |
| turns lost to server timeouts | 11 / 123 | 13 / 234 | — |
| wall time lost to timeouts | 5,914s | 6,705s | comparable |
| termination | 7/7 `gave_up` | 7/7 `gave_up` | both hit the 90-min cap |

**Not a tool-format regression — and this is now exact.** Every solver turn that received a
response emitted a well-formed tool call, in **both** arms, on **every** game: 112/112 for base
and 221/221 for the adapter, **100% either side**. The two arms also issued near-identical
action counts (270 vs 269). The adapter is emitting valid tool calls and acting on the board; it
is simply acting much less effectively.

> **Correction.** An earlier cut of this table reported 91.1% / 94.4% tool validity. That was
> wrong: it counted turns that died on a vLLM **read timeout** — where no response arrived at
> all, so there was nothing to be malformed — as tool failures. Excluding `request_error` turns,
> which is the only defensible denominator, both arms are at 100%.

**Server timeouts hit both arms and are not adapter-specific**, but they are not evenly spread.
Base lost 11 turns / 5,914s; the adapter lost 13 turns / 6,705s. Per-turn the base arm actually
timed out *more often* (8.9% vs 5.6%). Two adapter games were badly damaged, though:
**`tr87` lost 3,877s of its 5,400s budget to five consecutive 900s timeouts (72% of the run) and
managed a single action**, and `tu93` lost 2,180s (40%). Those two adapter runs should be treated
as compromised by infrastructure, not as clean measurements of the adapter.

The verdict survives dropping them. Over the five uncompromised games
(`ar25 re86 sb26 su15 vc33`): base **6 levels / 20.446**, adapter **2 levels / 0.704**, with
**4 regressed, 1 tied, 0 improved**.

**The mechanism is visible in the turn timings.** Both arms ran the same 90-minute wall clock
per game, but the adapter fitted 234 turns into it against base's 123, and its mean turn took
161.5s against 307.2s. The adapter deliberates roughly half as long per turn. That is exactly
what training on *human demonstrations* would be expected to do — humans do not write 300
seconds of model-style analysis before pressing a key — and on this harness the long
deliberation is evidently doing real work. Round 3 traded it away.

---

## 5. Verdict

**Round 3 is a regression on gameplay. Not "cannot distinguish" — measurably worse.**

On the seven held-out games, base cleared **7 levels / 20.780 score**; the round-3 adapter
cleared **2 levels / 0.705 score**. **Zero of seven games improved. Five regressed, two tied.**
Restricted to the five games not damaged by server timeouts, it is base **6 levels / 20.446**
against adapter **2 levels / 0.704**, 4 regressed / 1 tied / 0 improved. That is the number
Hermes' standard asks for, and it points the wrong way.

This is not the overfitting-to-trained-games story, because the adapter was never shown these
seven games. It is a straightforward capability regression on unseen games — and it is not a
formatting or tool-use break either: tool validity is 100% on both sides. The most likely
reading, supported by the turn timings, is that the human-demo corpus taught the model to stop
deliberating — turns roughly half as long, twice as many of them, near-identical action count,
far fewer levels cleared. The behaviour it imitated is human, and it is worse at this harness
than what the base model already did.

The held-out **CE** result (§2) is consistent with this but did not and could not establish it:
round 3 moved off the base model's token distribution (39/40 records, +0.0093), exactly as
predicted for a human-demo adapter, and that sign alone was uninformative. The round-2 arm
reproducing its banked uniform improvement (40/40, −0.0173) in the same load is what licenses
trusting either number.

**Honest limits on this verdict.**

- **n = 1 pass per game per arm, at `temperature 1.0`.** These are stochastic samples, not
  means. Over the five non-tied games, a clean 5-worse / 0-better split is
  **one-sided p ≈ 0.031** on a sign test (two-sided 0.0625). The *direction* is solid; the
  *magnitude* (−96.6% score) is a single draw and must not be quoted as an effect size.
- **Two adapter games were degraded by server timeouts,** not by the adapter (`tr87` lost 72%
  of its budget, `tu93` 40%). Dropping both still leaves base 6 levels / 20.446 vs adapter
  2 levels / 0.704 over the remaining five games, 4 regressed / 1 tied / 0 improved — so the
  conclusion does not rest on the compromised runs. But the clean comparison is five games, not
  seven.
- **Both arms were runtime-capped on all 14 runs** (`gave_up` at 90 minutes). This measures
  "levels cleared within 90 minutes," not asymptotic ability. An adapter that is merely *slower
  per level* would look like this too — though the adapter's turns were *faster*, not slower,
  which argues against that reading.
- **The CE arm and the gameplay arm ran on different weights** (BF16 on a424, NVFP4 on a108).

Before round 3 is abandoned outright, the cheap confirmation is n ≥ 3 passes per arm — roughly
nine more hours on a108, same recipe, nothing new to build — and raising the analyzer timeout
or lane count to stop the 900s read timeouts eating whole games.

**Recommendation:** do not promote the round-3 adapter. The windowed human-demo corpus, used
this way, makes the agent worse on held-out games. If the human demos are to be kept, the next
experiment should probably preserve deliberation length rather than let imitation shorten it.

### Server teardown and the oracle

The LoRA-enabled server was stopped after the adapter arm finished (§3 records why this
matters). **A future oracle P4 must relaunch vLLM without `--enable-lora`** — that flag is
server-level, does not appear in `run_config.json`, and the oracle's own parity check would not
catch it.

---

## 6. What I did NOT verify

1. **That the LoRA applies to all seven target modules.** The logprob A/B proves the adapter
   changes the model's output distribution; it does not prove every one of
   `o_proj, in_proj_z, in_proj_qkv, k_proj, out_proj, v_proj, q_proj` is being applied. Given
   the `update_packed_mapping` difference between vLLM 0.19.0 and the 0.26.0 that actually
   serves (§3), a *partial* application is possible and would mean the gameplay arm tested
   something weaker than the trained adapter. Both arms ran on the same served weights, so the
   comparison is valid either way — but "round 3 as served" may not equal "round 3 as trained."
2. **Numerical equivalence of the BF16-trained adapter on an NVFP4 base.** The adapter's
   `base_model_name_or_path` is the BF16 model; a108 serves NVFP4. I did not quantify the error
   this introduces. The CE arm (§2, on a424) *did* run against the BF16 base, so the two steps
   are not measuring the same stack.
3. **That 90 minutes is enough to separate the arms.** Every game in both arms terminated
   `gave_up` at the cap. I did not run an uncapped or longer pass.
4. **Statistical robustness of the gameplay result.** n=1 pass per game per arm, temperature
   1.0. No repeat passes were run.
5. **Whether the round-2 adapter would also regress on gameplay.** Only base and round 3 were
   played. Round 2 appears in the CE arm only.
6. **The `as66` claim.** I repeated the round-2 write-up's finding that `as66` is absent from
   all run dirs rather than re-deriving it; I verified only that it is named in
   `extract_sft.py`'s help text.
7. **Base-arm comparability to the banked oracle arm-B numbers.** My base arm ran on a
   LoRA-enabled server (`--enable-lora` also flips `cudagraph_specialize_lora`). It is matched
   to *my* adapter arm, not to the oracle's passes. Do not cross-compare.
8. **The root cause of the 900s vLLM read timeouts.** They occurred in both arms (11 base /
   13 adapter turns) and I did not diagnose them — 7 concurrent lanes against a 102,985-token
   context on one GB10 is the obvious suspect, but I did not confirm it, and I did not check
   whether the banked oracle passes show the same rate. Anyone repeating this should look before
   trusting per-game budgets.
9. **`train_report.json` internals for round 3.** I read its scalar summary
   (178 steps, 18,462s wall, 224.7 tok/s) and took the corpus composition from the JSONL
   directly; I did not audit the loss curve the brief quotes (0.2740 → 0.0325).
