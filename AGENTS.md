# AGENTS.md

**Author:** Mark Barney / Claude Opus 5
**Date:** 05-September-2026
**Purpose:** What an AI agent must know before touching this project, and the specific
false assumptions that agents keep making. Every item below is something that has actually
gone wrong, not a hypothetical.

---

## 0. Read this first, in ten seconds

- The **25 official games are NOT the target.** They are a solved tutorial, built on
  purpose to be unlike the real test. Do not treat them as a quality bar to match.
- The synthetic games are **training data**, not a product.
- **Game IDs are deliberately opaque.** Never surface a real title.
- The **source of truth for game code is `autoresearch-arena/arc3games/`**, not this repo.
- **A cron rewrites those games every few hours.** `git pull` before you form any opinion.
- Use **`python3.13`**. The system `python3` is 3.9 and will hand you a false green.

Full context: [`docs/how-this-feeds-kaggle.md`](docs/how-this-feeds-kaggle.md).

---

## 1. The false assumptions, in the order agents make them

### ❌ "The 25 official games are the benchmark — make ours look like those."

**Wrong, and it is the single most expensive mistake available here.**

ARC-AGI-3 has 135 games: 25 public (tutorial), 55 semi-private (public leaderboard), 55
private (the competition). ARC states the public 25 are intentionally easier and
**deliberately do not represent the mechanics of the private set**, specifically to punish
teams that overfit to them.

> Imitating the public 25 is not a conservative choice. It is the specific failure the
> report designed the public set to expose.

**Match ARC on conventions** (action space, run-ending failure, scoring, frame format,
16-colour palette, 64×64 frame). **Diverge on mechanics.**

If you measure our games against the official set, say which half you measured. "Ours look
different from the official 25" is often the goal, not a defect.

### ❌ "This game hasn't been polished yet."

Check `autoresearch-arena/arc3games/revisions.jsonl` before assuming. Most of the 50 have
had a full glow-up pass. A game can look rough *and* be fully processed — that is a finding
about the recipe, not a game nobody got to.

### ❌ "The published build must be stale."

`check_dist_current.py` reports staleness. Run it before alleging drift. The packaged file
legitimately differs from source: the packager strips the authoring docstring, inlines
`sprite_book.py` helpers, and renames the class. Those diffs are expected, not rot.

### ❌ "I read the file, so I know how many levels it has."

Read the **whole** file, or parse it. Level specs live in a long `LEVELS_SPEC` list and
partial reads have produced confidently wrong level counts.

### ❌ "The manifest is missing the game titles — I'll wire them up."

**Never.** IDs are opaque on purpose. Research artifacts carry real titles; those are
internal metadata. A readable title names the mechanic and hands the agent the answer,
which defeats the benchmark. Keep `title` == the ID in every manifest and UI.

### ❌ "I'll write a tool to render/measure the games."

**Look in `autoresearch-arena/arc3games/tools/` first.** It already has
`contact_sheet.py`, `pair_screenshot.py`, `build_dist_manifest.py`,
`build_triage_entries.py`. A duplicate tool has already been built here by accident.

### ❌ "I pulled at the start of the session, so I'm current."

The differentiation cron commits **every few hours**, rebuilding games onto new board
shapes and palettes. A session lasting an afternoon will go stale mid-analysis. `git fetch`
and re-check before reporting any measurement, and state the commit you measured at.

Rules also move: "topology is assigned by rarity" was true one day and retired the next.
Do not quote a rule you read yesterday without re-checking it.

### ❌ "I'll guess the function signature."

`differentiate.py`'s `topology()` and `cell_scale()` take a **Path**, not source text.
Guessing produced a whole table of `?` values that looked like real data. Check with
`inspect` or a one-line probe before running an analysis on top of an API you assumed.

---

## 2. Hard rules

### Where to edit

| what | where |
|---|---|
| game source (canonical) | `autoresearch-arena/arc3games/gNNN_*.py` |
| packaged single-file build | `autoresearch-arena/arc3games/dist/` |
| published copy | `arc-3/docs/static/games/src/<id>/` |

**Edit the canonical source.** Editing the published copy gets overwritten by the next
package run.

### Python version

Use **`python3.13`**. The engine uses `match`/`case`, which 3.9 cannot parse.

The dangerous case: `probe_one.py` under 3.9 **does not crash**. It prints well-formed JSON
with `"loads": false` and `"random_win": false` — and an agent ticking the "not mashable"
box reads that as a pass on a game that never loaded. **Check `"loads": true` before
believing any probe output.**

`legibility_gate.py` is pure AST and runs anywhere. Everything else needs 3.13.

### Harness scoring

- `harnesses/baseline-v12/` is **frozen**. Variants are copy + patch under a new name.
- Score **ex-`ft09`** — that one game swings the all-25 average by ±1.0.
- Replicate anything promising **2–3×**. Small evaluation sets are noisy; see the ARC Prize
  2025 5th-place writeup, where a random-seed change moved a team from 344th to 5th.

### Verifiers

A verifier that passes both before and after a mutation proves nothing. **Mutate one wall
and confirm the verifier fails.** A tautological check has shipped here before and was only
caught by mutation testing. A verifier must import the game's own movement table rather
than restating it, or it will happily search a square graph over hex level data.

### Games must not speak

No titles, tutorial hints, labels, or text of any kind on the play surface. Draw the rule;
never write it. A picture is fine. A word is a spoiler.

---

## 3. How to talk to the boss

He is a **video game producer**, not a CS professor, and he says so. He is also placing
top-five on the Kaggle leaderboard, so he knows the domain — it is the jargon and the
volume that get in the way, not the concepts.

- **Plain language. No decimals unless he asks.** "Two-thirds of the screen is empty" beats
  a table of edge densities.
- **Lead with the answer**, then the evidence. Not the other way round.
- **Do not run off and build.** He has stopped work mid-flight more than once to say the
  documentation already exists. Read `autoresearch-arena/arc3games/*.md` first — the
  formula, the studies, and the contract are all written down.
- **Say what you don't know.** He would rather hear "I haven't opened that yet" than a
  confident guess. He has caught guesses.
- **Don't swarm agents at a problem that is already documented.**

---

## 4. Repo map

| repo | what it is |
|---|---|
| `arc-3` | harness variants (`harnesses/`), the duck (`ARC3-Inference/`), Kaggle notebooks (`kaggle/`), the published game catalog (`docs/static/games/`) |
| `autoresearch-arena` | **game authoring source of truth** (`arc3games/`), the polish/differentiation loop, and its documentation |
| `arc-explainer` | the public site, written analyses of official games, ARCEngine submodule |
| `arc-interactive` | ARC Prize's own game repo and toolkit |

### The pipeline in one line

Author games in `autoresearch-arena` → package → publish to `arc-3` → the duck plays them
→ `ARC3-Inference/distill/extract_sft.py` keeps **only solved levels** → fine-tune the
model on its own wins → Kaggle notebook plays games nobody has seen.

**The consequence that governs game design:** a game contributes training data only for
levels the model actually beats. Too hard yields nothing; too easy teaches nothing.

---

## 5. The open question

**Nothing in this pipeline measures whether polishing a game moves the Kaggle score.**

We measure whether games differ from each other, and whether they load and can be won.
Neither asks the question that pays. Until a game-set change can be traced to a harness
score, describe this work as craft on a plausible theory — not as a scoring result.
