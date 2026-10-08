# ARC leaderboard history and featured competitors

The public leaderboard highlights NVARC3, David Hartmann, Jan Disselhoff, Lord Han Solo,
and the last dance, alongside the existing pinned team. The collector identifies each
by Kaggle team ID and retains score/rank trails and score-change events even below its
normal top-300 history and top-500 event thresholds. Ordinary teams keep those limits.
Existing gaps are not backfilled or interpreted as periods with an unchanged rank.

The same collector also supports ARC-AGI-2 (`arc-prize-2026-arc-agi-2`). Its pinned
teams are `user` (17023174) and `Son` (15605185); Jan Disselhoff (15507730) and
nvbanana (15486939) are also retained at every rank. Team identities are specific
to each competition: nvbanana is not labelled as the ARC-3 team NVARC3.

The half-hourly `leaderboard_publish.sh` job picks changes up from main in its
dedicated clone and refreshes both competitions independently. A failed download
skips that competition's push and allows the other competition to continue. There
is no second LaunchAgent. The existing board API stores documents by competition;
no database change is needed.

`LEADERBOARD_COMPETITION` selects the full Kaggle competition slug, defaulting to
ARC-3. `LEADERBOARD_DATA_DIR` remains the existing data root (by default
`~/.cache/arc3-leaderboard-data`): ARC-3 keeps its existing files there, while ARC-2
uses the `arc-2/` child directory. Both collector and pusher share this configuration.
Snapshots identify their competition; only legacy ARC-3 files may omit it, and
mismatches are rejected before recording history or sending data. `ourTeamId`
remains for compatibility, and `pinnedTeamIds` identifies all pinned teams.

The first day of collection has no previous-day baseline: rank and score comparisons
are null, including on repeated snapshots that day. The next UTC day uses the last
observation of the preceding UTC day. Missing days also produce null comparisons.
These page comparisons are distinct from the evening recap's Eastern-day comparison.

A separate Codex scheduled task covers both competitions and runs at
6 pm America/New_York with GPT-6 SOL through ChatGPT sign-in. It reads the public
board API, compares snapshots near consecutive Eastern evening boundaries, and saves
a Discord-ready draft plus supporting values in
`/Users/macmini/bubba-workspace/reports/`.
It covers the whole board and meaningful changes among featured competitors. It does
not send to Discord until a destination is explicitly selected. The Mac must be on
and the Codex app running. Configure the task in Codex, not the snapshot LaunchAgent.

Verification: `python3.13 scripts/test_leaderboard_pipeline.py` covers unknown first-day
comparisons, repeat snapshots, day rollover, collection gaps, separate saved histories
and POST payloads, rejection of competition mismatches, featured competitors below
both cutoffs, rank-only history changes, and continuation of ARC-2 after ARC-3 fails.
`bash -n scripts/leaderboard_publish.sh` checks shell syntax. A real first ARC-2
snapshot was prepared from the 7 October Kaggle download in
`/tmp/arc-leaderboard-preview/arc-2/` for local preview; it has not been published.
