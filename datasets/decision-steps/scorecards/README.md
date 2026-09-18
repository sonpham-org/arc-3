<!--
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: Explain what lands in this directory, why the JSON dumps are gitignored, and the one
timestamp trap that makes a naive date filter silently wrong.
SRP/DRY check: Pass — the tool's own docstring covers auth and CLI; this covers the artifacts.
-->

# Scorecard pulls

`tools/pull_boss_scorecards.py` writes `cards-<stamp>.json` and `runs-<stamp>.json` here. Both
are **gitignored** — they are one account's play history, regenerable in a minute, and there is
no reason to accumulate them in git. The durable artifact is the write-up in
`docs/trace-findings/`.

`runs-<stamp>.json` is the input to the bulk replay pull:

```bash
python3.13 tools/pull_boss_scorecards.py --month 2026-09
python3.13 tools/replay_scrape.py bulk --runs-file datasets/decision-steps/scorecards/runs-<stamp>.json
```

## The trap

**Filter on `open_at` from the card DETAIL, never `published_at` from the list.**
`published_at` is a batch-publish timestamp: 117 zero-action opens were published within one
second on 14-Sep-2026, and January plays carry September publish dates. Filtering on it
promotes legacy runs into the current window. The list endpoint zeroes `open_at` to
`0001-01-01`; only `/api/user/scorecards/<card_id>` returns the real value, which is why the
tool fetches every card's detail rather than trusting the list.

## What counts as a real run

`actions > 0` **and** `levels_completed > 0`. Both bars are load-bearing: the first rejects
scorecard opens created just by loading a game, the second rejects a poke that cleared nothing.
Drop the second and a 24-action 0-level open reads as "played", quietly removing a game from
the needs-a-playthrough list.

## Window limit

`/api/user/scorecards` caps at 50 cards and `at` is a page size, not a cursor — `at=50`
re-serves the same 50. The tool prints the `open_at` range it actually covered. Check it before
concluding a game was never played; older cards fall off the bottom.
