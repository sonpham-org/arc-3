// Static-mode API: reads pre-exported JSON from ./data instead of a live server.
const DATA = new URL("../../data/", import.meta.url);
async function json(rel) {
  const response = await fetch(new URL(rel, DATA), { cache: "no-store" });
  if (!response.ok) throw new Error(`${rel}: ${response.status}`);
  return response.json();
}
const r = (run) => encodeURIComponent(run);
export const fetchRunOverview = (run) =>
  run ? json(`${r(run)}/run-overview.json`) : json("default-run-overview.json");
export const fetchGame = (run, index) => json(`${r(run)}/game-${index}.json`);
export const fetchGameFrames = (run, index) => json(`${r(run)}/game-${index}-frames.json`);
export const fetchGameStep = (run, index, step) => json(`${r(run)}/game-${index}-step-${step}.json`);
export const fetchRunTimeline = (run, version = "") =>
  json(`${r(run)}/run-timeline.json${version ? `?v=${encodeURIComponent(version)}` : ""}`);
export const fetchViewerVersion = async () => ({ version: "static" });
// The index is mutable on Railway's persistent volume. Give every dashboard
// load a unique URL as well as bypassing the browser cache so a just-published
// run cannot appear in the scoreboard while remaining absent from comparisons.
export const fetchRunsIndex = () =>
  json(`runs-index.json?v=${Date.now()}`).catch(() => null);
