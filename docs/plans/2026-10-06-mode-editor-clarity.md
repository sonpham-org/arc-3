<!--
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Scope and checklist for the Mode explorer's mode editor rework and the "lean turn message" setting (the Boss,
  #arc-3 6-Oct 16:39 ET, with a screenshot of the Edit Probe panel). The Boss's note is the approval.
SRP/DRY check: Pass - the shared mode store is docs/plans/2026-10-06-shared-modes.md, Play is
  docs/2026-10-06-spark-runner.md; this covers only the editor and lean.
-->

# Mode editor: clear about what is edited, and a lean turn message (6-Oct-2026)

The Boss: "On desktop it's somewhat hard to read the text." "It's not clear what part I'm able to edit, and there are
parts I absolutely do not want to accidentally edit." "Stuff like the Python tool calling belongs in the system prompt
and shouldn't get duplicated in the user prompt. ... I still don't understand if this is the system prompt, the user
prompt, or what, and where it's getting inserted." "The alignment's a little messed up for desktop and I wish it wasn't
upper-left vertically aligned."

## Scope
- Editor is a centred window, wide on a desktop (text left; where-this-goes and settings right), a full-screen sheet on
  a phone; larger, higher-contrast text. Cause of the top-left placement: theme.css zeroes every margin, which removed
  the browser's own centring of a modal dialog.
- "Where this goes": system prompt (same for every mode, never changed by one, readable behind "Show system prompt",
  from static/data/system-prompts.json built by the runner's own harness) -> turn message, the user message at the
  start of each turn the mode runs.
- Turn message split into harness lines (read-only, greyed, locked, "Added by the harness every turn - not editable
  here") and the mode's own instruction (the only editable box). Stored text stays the whole turn message; the editor
  splits and rejoins it with the same line diff the runner uses, byte for byte when unedited.
- The four stock tool-call reminders are marked "also in the system prompt". Per-mode "Lean turn message" (off by
  default) has the runner leave them out of that mode's turn message; stored in the mode version, sent per Play slot,
  recorded with each job. Built-in "Stock (lean)" = Stock with lean on.
- Tour gets an "Editing a mode" step; history, restore, delete (hide) unchanged.

## Checks
- [x] Every built-in and every mode on the live site splits and rejoins to its exact stored text (both wordings).
- [x] Runner: with lean off, every mode x wording x kind of turn x optional lines builds the same prompt as before
      (old and new modes.py); with lean on exactly the reminder lines go.
- [x] The four reminder lines match the real turn messages saved on the runner (every saved request) exactly.
- [x] Headless desktop and phone against the live data, every write caught in the browser: centred / full screen, one
      editable box, locked harness blocks, reminders marked, system prompt read-only, unedited save byte-identical,
      edit changes only the instruction, lean saved, history loads, new mode, Stock has no instruction box, tour step.
- [ ] Runner deployed to Jethro with a backup while no Play sample runs; repo and Jethro identical.
- [ ] Live page serves the new files; Stock (lean) seeded as a built-in.
