# Featured leaderboard competitors

The public leaderboard highlights NVARC3, David Hartmann, Jan Disselhoff, Lord Han Solo,
and the last dance, alongside the existing pinned team. The collector identifies each
by Kaggle team ID and retains score/rank trails and score-change events even below its
normal top-300 history and top-500 event thresholds. Ordinary teams keep those limits.
Existing gaps are not backfilled or interpreted as periods with an unchanged rank.

The half-hourly `leaderboard_publish.sh` job picks this change up from main in its
dedicated clone. The site consumes the same JSON schema; no database change is needed.

A separate Codex scheduled task, **ARC-AGI-3 evening leaderboard recap**, runs at
6 pm America/New_York with GPT-6 SOL through ChatGPT sign-in. It reads the public
board API, compares snapshots near consecutive Eastern evening boundaries, and saves
a Discord-ready draft plus supporting values in
`/Users/macmini/bubba-workspace/reports/arc3-leaderboard/`.
It covers the whole board and meaningful changes among featured competitors. It does
not send to Discord until a destination is explicitly selected. The Mac must be on
and the Codex app running. Configure the task in Codex, not the snapshot LaunchAgent.

Verification: exercise the actual collector with controlled boundary rows, including
a featured team below both cutoffs, an ordinary team below both, a rank-only change,
and a first-seen featured team. Confirm emitted history and events reflect those cases.
