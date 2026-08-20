# Generated viewer data

This directory is a local export cache only. Its generated run directories and
indexes are not stored in Git.

- Raw, durable run artifacts live in `gs://cellens-ai-artifacts/arc3-duck/`.
- `scripts/export_viewer_data.py` and the related exporters normalize those
  artifacts locally under `docs/data/`.
- `scripts/publish_railway_data.py` streams one immutable run plus the refreshed
  index directly into Railway's persistent `/srv/data` volume.

The website image contains HTML, CSS, JavaScript, and game assets, but never
trace payloads. A Railway redeploy therefore preserves traces through the
mounted volume without requiring generated data in the repository.
