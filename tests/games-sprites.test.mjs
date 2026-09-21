// Unit checks for the pure half of docs/static/js/games-sprites.js.
//
// Author: Claude Opus 5
// Date: 20-September-2026
// PURPOSE: Assert the patch/render contract the sprite editor rests on, out of the browser and
// without Pyodide: that an untouched sprite round-trips to byte-identical source, that a painted
// one rewrites exactly its own literal and nothing else, that every encoding survives
// grid -> literal -> grid, and that an anchor which no longer resolves is dropped rather than
// patched blind. The in-browser half (does the board actually change?) is
// scripts/verify_game_sprites.py; this is the half that does not need a browser.
//
// SRP/DRY check: Pass -- assertions only. The functions under test are exported by
// games-sprites.js; nothing is reimplemented here.
//
//   node --test tests/games-sprites.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  renderSprite, patchSprite, resolveSprites, toGrid, fromGrid, sameGrid,
} from "../docs/static/js/games-sprites.js";

// Shaped exactly like a generated spec entry, and quoted exactly like sd78's real source.
const lantern = {
  id: "s0", label: "Lantern", encoding: "charStencil", rows: 4, cols: 3,
  alphabet: [".", "W", "c", "o"],
  anchor: '(".W.", "cWc", "ccc", ".o.")',
  default: [".W.", "cWc", "ccc", ".o."],
};

const coral = {
  id: "s1", label: "Coral", encoding: "charStencil", rows: 6, cols: 5,
  alphabet: [".", "c"],
  anchor: '[\n    "c...c",\n    ".c.c.",\n    "c.c.c",\n    ".ccc.",\n    "..c..",\n    "..c..",\n]',
  default: ["c...c", ".c.c.", "c.c.c", ".ccc.", "..c..", "..c.."],
};

const plane = {
  id: "s2", label: "Plane", encoding: "intGrid", rows: 3, cols: 6,
  alphabet: [-1, 7, 8, 9, 15],
  anchor: "[\n    [-1, -1, -1, 9, 9, -1],\n    [8, 8, 15, 15, -1, -1],\n    [8, 15, 15, 15, 7, -1],\n]",
  default: [[-1, -1, -1, 9, 9, -1], [8, 8, 15, 15, -1, -1], [8, 15, 15, 15, 7, -1]],
};

const pips = {
  id: "s3", label: "Pips", encoding: "offsets", rows: 2, cols: 2,
  alphabet: [0, 1], originX: 1, originY: 1,
  anchor: "((1, 1), (2, 2))",
  default: [[1, 1], [2, 2]],
};

test("an untouched sprite renders back to its own anchor, byte for byte", () => {
  for (const sprite of [lantern, coral, plane, pips]) {
    const grid = toGrid(sprite);
    assert.equal(renderSprite(sprite, fromGrid(sprite, grid)), sprite.anchor, sprite.label);
  }
});

test("patching with the default leaves the source completely unchanged", () => {
  const source = `LANTERN_ART = ${lantern.anchor}\nX = 1\n`;
  assert.equal(patchSprite(source, lantern, fromGrid(lantern, toGrid(lantern))), source);
});

test("a paint rewrites that literal and nothing else around it", () => {
  const source = `before = 1\nLANTERN_ART = ${lantern.anchor}\nafter = 2\n`;
  const grid = toGrid(lantern);
  grid[0][0] = "W";
  const out = patchSprite(source, lantern, fromGrid(lantern, grid));
  assert.match(out, /^before = 1\n/);
  assert.match(out, /\nafter = 2\n$/);
  assert.ok(out.includes('("WW.", "cWc", "ccc", ".o.")'), out);
});

test("the multi-line layout, bracket and quote style are preserved", () => {
  const grid = toGrid(coral);
  grid[0][0] = ".";
  const out = renderSprite(coral, fromGrid(coral, grid));
  assert.ok(out.startsWith("[\n    \""), out.slice(0, 20));
  assert.ok(out.endsWith("\n]"), out.slice(-6));
  assert.equal(out.split("\n").length, coral.rows + 2);
});

test("intGrid keeps its inner brackets and spacing", () => {
  const grid = toGrid(plane);
  grid[0][0] = 15;
  const out = renderSprite(plane, fromGrid(plane, grid));
  assert.ok(out.includes("[15, -1, -1, 9, 9, -1]"), out);
});

test("offsets round-trip through a boolean grid, and painting adds a pixel", () => {
  const grid = toGrid(pips);
  assert.deepEqual(grid, [[1, 0], [0, 1]]);
  grid[0][1] = 1;
  assert.deepEqual(fromGrid(pips, grid), [[1, 1], [2, 1], [2, 2]]);
});

test("an anchor that no longer occurs is dropped, not guessed at", () => {
  const moved = "LANTERN_ART = ('.X.', 'cXc', 'ccc', '.o.')\n";
  assert.deepEqual(resolveSprites({ schema: 1, gameId: "sd78", sprites: [lantern] }, moved), []);
});

test("an anchor that occurs twice is ambiguous and is dropped", () => {
  const twice = `A = ${lantern.anchor}\nB = ${lantern.anchor}\n`;
  assert.deepEqual(resolveSprites({ schema: 1, gameId: "sd78", sprites: [lantern] }, twice), []);
  assert.equal(patchSprite(twice, lantern, [["W", "W", "W"]]), twice, "patch must be a no-op too");
});

test("a resolved sprite carries the art the source actually has, as its base", () => {
  const source = `LANTERN_ART = ${lantern.anchor}\n`;
  const [resolved] = resolveSprites({ schema: 1, gameId: "sd78", sprites: [lantern] }, source);
  assert.ok(sameGrid(resolved.base, toGrid(lantern)));
});

test("a spec of the wrong schema yields nothing", () => {
  assert.deepEqual(resolveSprites({ schema: 2, sprites: [lantern] }, lantern.anchor), []);
});

test("two sprites in one source patch independently and compose", () => {
  let source = `A = ${lantern.anchor}\nB = ${pips.anchor}\n`;
  const g1 = toGrid(lantern); g1[0][0] = "W";
  const g2 = toGrid(pips); g2[0][1] = 1;
  source = patchSprite(source, lantern, fromGrid(lantern, g1));
  source = patchSprite(source, pips, fromGrid(pips, g2));
  assert.ok(source.includes('("WW.", "cWc", "ccc", ".o.")'), source);
  assert.ok(source.includes("((1, 1), (2, 1), (2, 2))"), source);
});
