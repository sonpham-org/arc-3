# Where the loop's rules came from

Recovered 19-September-2026 by Claude Opus 5. The v4 loop ([../README.md](../README.md)) is
a reform of three earlier bodies of work. Here is where each one lives, and what v4 took from it.

## 1. Codex's canonical-pair glow-up loop (steps 1-3)

- **Where:** the Codex workspace `C:\Users\celle\Documents\Codex\2026-08-27\f\work\arc3-publisher-source`,
  a clone of this repo on branch `codex/game-public-ids-20260914`. The rules were committed
  there in local commits `170084e` and `6fb2b98` (14-Sep-2026) and never pushed. Its
  recurring job is `~\.codex\automations\arc3-canonical-pair-glow-up\automation.toml`
  (status PAUSED; a pass every 90 minutes).
- **State when paused:** 27 cycles completed (54 glow-ups across a 50-game pool); six games
  still at zero glow-ups; a 44-game QC maintenance batch in progress (5 qualified, 1 failed
  the new recovery audit, 38 prepared); pool growth never triggered.
- **Copied here verbatim** (in [codex/](codex/)): the program (`glowup-program-v3.md`), rubric
  (`glowup-rubric-v3.md`), quality control (`glowup-quality-control-v1.md`), the recovery
  policy that became step 4a (`glowup-recovery-policy-v1.md`), agent isolation
  (`glowup-agent-isolation-v1.md`), the mechanic registry, the pool and growth definitions,
  and the pair sampler and stats builder. The sampler and stats builder are for reference:
  they read per-game files that are not in this repo.
- **Left out on purpose:** the loop state's per-cycle notes, the registry's draw history, the
  per-game metadata and stats, and the QC batch's descriptions and reviews. They describe
  the designs of games that are shown blind (the contributed glow-ups), and this repo is
  public. They remain in the Codex workspace.

## 2. The September fix rounds (step 4)

Codex revised the 32 feedback-reviewed arena games twice. The write-ups live in the private
`sonpham-org/autoresearch-arena` repo; they are summarised here rather than copied.

- **Not dying right away, clearer** (`arc3games/FEEDBACK_2026-09-12.md`, plus Codex's
  `glowup-recovery-policy-v1.md` above, 14-Sep): Son asked that games not end on unclear
  actions, ideally not end at all, or end only with a visible lives mechanism. The rounds
  made rejected moves harmless and visible, removed hidden budgets, kept completed levels on
  retry, replaced hex movement with square movement where it confused, added direct
  controls, and made hazards persistent and visible.
- **Honest translation animation** (`arc3games/MOVEMENT_AUDIT_2026-09-16.md`, website
  commit `63295f3`, PRs #33/#34 in this repo). The shared browser animation had matched
  same-coloured pixels independently and staggered their replacement, so moving characters
  split, trailed, or picked up unrelated pixels. Some renderers also flipped silhouettes by
  tile parity or painted hints over characters. The fix: real game positions produce the
  intermediate frames; whole sprites translate intact; presentation frames never tick
  rules; the camera follows; RESET clears pending animation; routes follow their actual
  rule-generated path; native effects that show a real rule stay; short moves play at about
  40 ms per frame. `docs/static/js/games-play.js` still lists those 32 games.

## 3. Claude's clarity loop (level 1 and noise)

`arc3games/CLARITY_LOOP.md` and `CRON_PROMPT_CLARITY.md` (private repo, 7-8 Sep) record
Son's direction that level 1 be extremely easy so the mechanic is readable, and that the
"salt and pepper" noise be reduced without stripping decoration entirely. It measured three
things: level 1 winnable in at most 10 actions, random play never dying on level 1, and
random play not reaching level 2. Its key ruling carries into v4: discovery cost moves to
level 2 and later, and a random-clearable game is fixed by hardening level 2, never by
lengthening level 1. `vet_game.py`'s `level1_short`, `level1_safe` and `random_resistance`
checks are these gates.

## 4. The Flashpoint corpus (where step 1's topics come from)

Codex surveyed the Flashpoint Archive's 20-Mar-2024 SQLite snapshot (30-Aug-2026): 169,962
archived game records, 129,019 of them Flash. That is metadata (titles, tags, descriptions,
source links), not the playable files. The 414 MB database is not in git. The local copy is
`C:\Users\celle\Documents\Codex\2026-08-22\res\outputs\flashpoint-2024-03-20.sqlite`, and it
can be re-downloaded from `download.flashpointarchive.org/flashpoint.sqlite`. What it produced
is already in this repo's `research/`:
- the survey (`flash-game-mechanics-survey.md`);
- the corpus audit and all genre tags;
- a ranked long-tail queue of rare-mechanic games, each with its nearest existing game
  (`flash-long-tail-queue-v1.tsv`);
- two reviewed lineage ledgers (48 classic lineages and 80 long-tail ones). These became
  the ideas board's `flash-lineages-v1` and `flash-long-tail-v1` ideas.

The scripts are `scripts/analyze_flashpoint_corpus.py` and `scripts/mine_flashpoint_long_tail.py`.
Step 1 draws topics from these ideas and from the queue.

## Related, not carried over

Claude's arena glow-up and differentiation lanes (`arc3games/GLOWUP_RECIPE.md`,
`PAIRWISE_DIFFERENTIATION.md`, `differentiate.py`, same private repo) are a sibling loop over
the 50 arena games. v4 does not edit arena games in new-seed mode. Before running normal
mode on an arena game, check that loop's latest `revisions.jsonl` so the two don't fight
over the same game.
