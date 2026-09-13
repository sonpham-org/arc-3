import assert from "node:assert/strict";
import fs from "node:fs/promises";

const source = await fs.readFile(new URL("../docs/static/js/viewer-route.js", import.meta.url), "utf8");
const route = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

assert.deepEqual(
  route.parseViewerHash("#run=run%201&game=ft09&turn=T12&frame=42"),
  { run: "run 1", game: "ft09", instance: null, turn: 12, frame: 42 },
);
assert.equal(
  route.viewerHash({ run: "run 1", game: "ft09", turn: 12, frame: 42 }),
  "#run=run+1&game=ft09&turn=12&frame=42",
);

const games = [{ game_id: "ft09" }, { game_id: "vc33" }, { game_id: "ft09" }];
assert.deepEqual(route.canonicalGameRef(games, 2), { game: "ft09", instance: 2 });
assert.equal(route.resolveGameIndex(games, "ft09", 2), 2);
assert.equal(route.resolveGameIndex(games, "vc33"), 1);

const frames = [
  { frameIndex: 0, analysis_step: null },
  { frameIndex: 4, analysis_step: 2 },
  { frameIndex: 7, analysis_step: 2 },
  { frameIndex: 9, analysis_step: 3 },
];
assert.equal(route.framePositionForRoute(frames, { turn: 2 }), 1);
assert.equal(route.framePositionForRoute(frames, { turn: 2, frame: 7 }), 2);
assert.equal(route.framePositionForRoute(frames, { turn: 99, frame: 99 }), null);

console.log("viewer route contract: ok");
