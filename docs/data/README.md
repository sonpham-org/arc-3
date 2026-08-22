# Generated viewer data

This directory is a local export cache only. Its generated run directories and
indexes are not stored in Git.

- Raw, durable run artifacts live in `gs://cellens-ai-artifacts/arc3-duck/`.
- `scripts/export_viewer_data.py` and the related exporters normalize those
  artifacts locally under `docs/data/`.
- `scripts/publish_complete_run.py` is the single submission command.
- Large viewer/trace artifacts are staged and verified on `/srv/data`.
- Run metadata, per-game scores, score events, artifact hashes, and publication
  receipts are committed to Railway Postgres in one transaction.
- `/data/runs-index.json` is now a database-served compatibility endpoint, not
  an authoritative file that submissions overwrite.

The website image contains HTML, CSS, JavaScript, and game assets, but never
trace payloads. A Railway redeploy therefore preserves traces through the
mounted volume without requiring generated data in the repository.
