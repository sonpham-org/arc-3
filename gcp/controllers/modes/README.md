# modes — per-turn mode switching on a shared minimal system prompt

Son, 25-Sep: "we simplify system prompt and try to switch mode in user prompt". Kept **separate** from
`gcp/controllers/cv5-cr-clock/` (the non-mode-switching harness family) so both can be developed
side by side: this directory only *reads* the 19-Sep `compaction_v5_clean_return_a` arm as its base.

- `patch_modes.py` — the harness change, applied to a copy of the base candidate tree. Shared system
  prompt = the solver prompt (five surfaces deleted by env). Per turn the host appends one mode
  paragraph (`[Turn mode: …]`) to the last user message of the *request* and strips it from the
  persistent history (same mechanics as the `[Runtime budget]` reminder), so the KV prefix is never
  touched and paragraphs do not accumulate. Host gates enforce the mode through the sandbox payload:
  action cap per call and whether `expect(check)` is required before `action()`.
  Modes: `act` (= solver), `verify` (expect before every action, cap 14), `probe` (cap 1, name the
  untested control, write the goal spec, RESET allowed), `batch` (cap 8 once predictions hold),
  `router` (rules on host state: probe for the first 6 turns of a level and every 4th turn of a
  stall, batch after 3 passed verdicts, verify otherwise). `ARC3_TURN_MODE` selects; the router
  lives in `budget_reminder.py` because the bundle's file set is fixed by its release manifest.
  Every turn's decision is written to the transcript as a `TURN MODE` block.
- `derive_modes.py act|verify|probe|batch|router [--suite N] [--all25]` — builds an arm from the
  base (hard seven, one wave by default); `verify_396.py`, `launch_396.py`, `watchdog.py` as in the
  clock controller; `smoke_modes.py` runs the patched sandbox and router against a fake host.
- `arms/modes_hard7_<mode>_132/` — the five arms launched 25-Sep (ids below once they report).

## Results (25-Sep, hard seven, one wave, 132 min; 7-game mean / levels / actions)

| mode | run | mean | levels | actions | notes |
|---|---|---|---|---|---|
| act (shared solver prompt, no mode text) | `…-567d7e9bad` | **10.06** | 17 | 3,639 | best hard-seven run of the program; g50t 35.7/4 |
| router (probe 6 turns per level → verify → batch after 3 passed checks) | `…-e249080d39` | 5.90 | 15 | 4,110 | rule fired as designed (per-game P/V/B counts in the transcripts' TURN MODE blocks) |
| verify (expect() required before every action) | `…-17c592245b` | 4.97 | 11 | 3,611 | |
| probe / batch | preempted at ~min 60; relaunched `…-f69238c5d1` / `…-ff958134a3` | — | — | — | |

The silent mode wins: the per-turn channel works mechanically (paragraph in, paragraph stripped, gates
enforced), but the obligations we sent (mandatory expect(), single-step probing, the router schedule)
cost levels on this model. The solver prompt itself is the ingredient (solver n=3: 9.13 / 4.73 / 10.06).
Also launched: act on all 25 games x2 (`g4run-modes-all25-act-132-w7-20260924-4204d91f17`, `…-0fd7afe3dd`).
