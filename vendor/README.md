<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Why third-party source is vendored here, what the one current entry is, and the
provenance chain that makes a citation into it checkable. Read before adding a second entry.
SRP/DRY check: Pass -- datasets/decision-steps/dispatch/README.md owns how a citation is
written and ../SCHEMA.md owns the record contract. This owns only the vendoring rule and the
provenance of what is vendored. vendor-taaf-grafts/ at the repo root is FIRST-PARTY code
despite the name and is not governed by this file.
-->

# vendor/ — third-party source carried so it can be cited

Nothing here is ours and nothing here is imported at runtime. These trees exist so that a
`file:line` citation in the decision-step corpus can point at the code that actually ran.

**The rule for adding one.** Vendor only when a record has to cite code that executes on a
player's action and is not otherwise in this repo. Record the version, the upstream artefact,
and a hash chain back to something that was pinned independently of this commit. If you cannot
write that chain, do not vendor — say the citation is unavailable instead.

---

## `arcengine-0.9.3/`

The ARC-3 game engine. Every game under `docs/static/games/src/` subclasses
`ARCBaseGame` from it (`from arcengine import ARCBaseGame, ...` at the head of each game file),
and the engine — not the game — is what handles `RESET`.

**Why it is here.** `RESET` has no dispatch branch in most game sources, so before this the
corpus could only cite a `RESET` on the two builds that happen to vendor their own branch
(`bp35`, `lf52`). Since `RESET` is the only recovery primitive on 19 of the 25 live builds, and
recovery after falsification is the metric the corpus exists to move, that regex-shaped limit
meant recovery could only be recorded on the games least representative of how recovery works.
The full argument, and the three options rejected in favour of this one, are in
[`docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md`](../docs/trace-findings/2026-09-15-lp85-step-budget-and-the-uncitable-reset.md).

**Provenance, each link checkable.**

| link | value |
|---|---|
| upstream | `https://pypi.org/project/arcengine/` — `arcengine-0.9.3.tar.gz` |
| sdist sha256 | `76441c15fde092a071ca95edce5e643385ab270304f59c1172b460048fffcdfe` |
| pinned independently at | `tufa-arc-agi-framework/uv.lock`, which carries that same sha256 and predates this commit |
| declared as a dependency at | `tufa-arc-agi-framework/pyproject.toml:9`, `arcengine>=0.9.3` |
| licence | MIT, `arcengine-0.9.3/LICENSE`, © 2026 ARC Prize Foundation — redistribution granted |
| contents | the unpacked sdist, byte-identical, `__pycache__` removed and nothing else altered |

`scripts/test_dispatch_tables.py` re-derives the sha256 of every vendored `.py` and fails if one
changes, so an edit to this tree is a test failure rather than a silently drifting citation.

**The scope limit, stated rather than implied.** `0.9.3` is the only release arcengine has ever
published — the PyPI index lists exactly one — and it is what this repo's lock file pins and
what the vendored game sources are written against. It is **not** verifiable from here that
`three.arcprize.org` runs this build; the hosted service exposes no engine version. A citation
into this tree is therefore a citation into *the only arcengine anyone can read*, which is a
weaker claim than "the code that served this recording" and is written that way in the
citations themselves, which carry the version and say so.

**One prediction of this build was checked against play and held.** The session API's `actions`
counter is *not* `ARCBaseGame._action_count`: `base_game.py:278` skips the increment for
`RESET`, yet every first-party recording reconciles only when `RESET` rows are counted as
actions (`ls20` reports 561 actions over 562 rows containing 3 non-boot `RESET`s; under
`_action_count` it would report 558). The two counters are different things, the reconcile rule
in `datasets/decision-steps/README.md` describes the API's, and the apparent contradiction
between them is resolved rather than left hanging.
