// Large immutable viewer artifacts stay on the Railway volume. The mutable
// run catalog and score curves are served from Railway Postgres.
const DATA = new URL("../../data/", import.meta.url);
const SITE = new URL("../../", import.meta.url);
async function json(rel) {
  const response = await fetch(new URL(rel, DATA), { cache: "no-store" });
  if (!response.ok) throw new Error(`${rel}: ${response.status}`);
  return response.json();
}
async function api(rel) {
  const response = await fetch(new URL(rel, SITE), { cache: "no-store" });
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
export const fetchRunScoreCurve = (run) =>
  api(`api/v1/runs/${r(run)}/score-curve?v=${Date.now()}`).catch(() =>
    api(`api/runs/${r(run)}/score-curve.json?v=${Date.now()}`)
  );
export const fetchViewerVersion = async () => ({ version: "static" });
export const fetchRunsIndex = () =>
  api(`api/v1/catalog?v=${Date.now()}`)
    .catch(() => json(`runs-index.json?v=${Date.now()}`))
    .catch(() => null);
