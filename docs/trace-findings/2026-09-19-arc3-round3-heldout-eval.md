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

**Status: IN PROGRESS — this file is being written as the runs complete.**

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

## 4. STEP 3 — matched gameplay passes

*(results pending)*

---

## 5. Verdict

*(pending)*

---

## 6. What I did NOT verify

*(pending)*
