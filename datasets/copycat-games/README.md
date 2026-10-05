<!--
Author: Claude Opus 5.5 (Bubba sub-agent)
Date: 04-October-2026
PURPOSE: What the copycat games are, how they are built and proven, and how to use the
packaged folder. Travels with the package into sonpham-org/arc-3 (datasets/copycat-games/).
-->

# Copycat games

Close copies of the public ARC-AGI-3 games for reinforcement learning. Each copycat keeps one
public game's **rules and level-by-level progression exactly** -- the original game class
runs every step -- and changes what a player could memorise: **the maps, the colours, sprite
drawings, HUD position, and tile size where the game's code allows**. Asked for by Son Pham on
4-Oct-2026 so a model learns mechanics rather than maps and click positions.

## What is in the package

```
dist/
  environment_files/<id>/v1/<id>.py, metadata.json   # drop-in for arc_agi / taaf environments_dir
  solutions/<id>.json                                # a winning line per level
  previews/<id>/L<n>_original_vs_copycat.png         # level start, original left, copycat right
  manifest.json                                      # every build: original, levels, what changed, verified
```

- Ids are four characters so arc_agi's default class-name rule works: the second letter of
  the original id becomes `x` (first copycat) or `y` (second copycat): ls20 -> lx20, ly20.
  Titles equal the id. `baseline_actions` is empty on purpose (a list whose length differs
  from the level count kills a whole taaf run).
- `solutions/<id>.json`: `levels[k]` is the list of actions for level k+1, each
  `{"id": "ACTION1".."ACTION7"}` or `{"id": "ACTION6", "x": .., "y": ..}` in 64x64 display
  coordinates. Play from RESET and chain the levels in one run.
- `verified: true` in the manifest means both checks passed: (1) the stored line, played from
  RESET through a fresh copycat, clears every level exactly at the end of its segment and ends
  in WIN; (2) the packaged folder, scanned by arc_agi's offline Arcade, makes the game by id
  and the same line stepped through that wrapper reaches WIN with the right level count.

## Games in this package

30 copycats of 18 public games, every one `verified: true`.

| original | copycats | levels |
|---|---|---|
| bp35 | bx35, by35 | 9 |
| cd82 | cx82, cy82 | 6 |
| cn04 | cx04, cy04 | 6 |
| dc22 | dx22, dy22 | 6 |
| ft09 | fx09, fy09 | 6 |
| g50t | gx0t, gy0t | 7 |
| ka59 | kx59 | 7 |
| lf52 | lx52, ly52 | 10 |
| lp85 | lx85, ly85 | 8 |
| ls20 | lx20, ly20 | 7 |
| m0r0 | mxr0 | 6 |
| r11l | rx1l | 6 |
| s5i5 | sxi5 | 8 |
| sc25 | sx25, sy25 | 6 |
| sk48 | sx48 | 8 |
| sp80 | sx80, sy80 | 6 |
| tn36 | tx36 | 7 |
| wa30 | wx30, wy30 | 9 |

6 games have one copycat so far (ka59, m0r0, r11l, s5i5, sk48, tn36); the rest have two.
The `kept`, `changed` and `not_changed` notes in `manifest.json` name games by our internal
nicknames: they are build notes for people, never text to show an agent. Game files and
`metadata.json` carry opaque ids only.

## Held out

This package holds no copies of the seven held-out public games (vc33, ar25, sb26, re86,
su15, tr87, tu93) or of as66, and must never be mixed with them: it is training material.
Their test-only copies were built separately (Son asked for them on 4-Oct-2026); they live in
`arc3games/copycats_heldout/` here and `datasets/test-only-games/` on sonpham-org/arc-3, and
are never trained on.

On sonpham-org/arc-3 this folder also holds ws03 and ws04, two earlier Locksmith reskins
(August 2026, ws04 the repaired build). They were not made by this packager and are not in
`manifest.json`.

## How a copycat is made

`copycat_core.py` holds the shared machinery; `cc_<game>.py` holds one game's knowledge;
`build_all.py` builds, proves and packages. The method:

1. Start from the original's recorded winning line (arc-explainer human-reasoning release,
   executed in the local engine; all 18 buildable games replay to WIN).
2. Apply a square symmetry (mirror / quarter turn / half turn) to every map, conjugate the
   game's internal direction tables so moving parts behave as the mirror image, and push the
   winning line through the same symmetry.
3. Rework the map for real: regrow mazes around the winning route, carve and fill cells the
   line never touches, add decoys, or write new puzzle contents built backwards from a random
   answer. Every edit is kept only if the level still clears; generated puzzles are rejected
   if they are easier than the original level.
4. Recolour through a bijection applied to the camera's final frame (rules that read sprite
   colours are untouched), redraw decorative sprites, move code-drawn HUD, change tile scale
   where the code allows.
5. Package and prove (above).

Build: `~/GitHub/arc-explainer/external/ARCEngine/.venv/bin/python build_all.py ls20:1 ...`
