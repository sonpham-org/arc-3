<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Scope and checklist for shared, versioned Mode explorer modes and recording mode versions at Play
  (Son's ask, #arc-3 6-Oct 08:42 ET). The ask is the approval.
SRP/DRY check: Pass - how Play works is in docs/2026-10-06-spark-runner.md; this covers only the mode store.
-->

# Shared modes for the Mode explorer (6-Oct-2026)

Son: "Mark needs a way to edit and add new modes, is it there? And when will the mode be recorded?"

## Scope
- Modes in the site's Postgres, append-only versions (who, when, note); current = highest version.
- Built-in modes = version 1 from docs/static/data/modes.json, seeded only for ids with no rows.
- Any signed-in user adds a mode or edits any mode; save = new version; restore = copy forward; delete = hidden version.
- Editor on each chip: prompt per wording, diff against the harness Stock prompt, settings, note, history.
- Play records each slot's exact text, settings and version with the job id; results show it.
- Upload browser-only custom modes once (asked), keep the browser copy; queues stay in the browser.

## Decisions
- The diff baseline and the runner's Stock template stay the harness's own Stock text from modes.json, so the page
  never shows a diff against text the runner does not use. Editing the Stock mode changes what Stock turns say.
- Recording happens on the site (relay hook after the runner accepts a Play), so the runner on Jethro is unchanged.

## TODO
- [x] Tables, module, wiring, Dockerfile copy and build guard
- [x] Editor, history, delete/bring back, upload, recording, results display
- [x] Local test: catalog server + throwaway Postgres + stub runner, desktop and phone widths
- [x] Push, confirm deploy
