/*
Author: Claude Opus 5.5 (Bubba) (7-Oct changes only; the file predates headers)
Date: 07-October-2026
PURPOSE: Where the trace viewer pages get their data: static run exports on the Railway volume, the catalog and
  score curves from the site API, and (7-Oct) Spark runner samples through spark-watch.js for "spark:" runs.
SRP/DRY check: Pass - one branch per payload; the Spark shaping stays in spark-watch.js.
*/
import { isSparkRun, sparkFrames, sparkGame, sparkOverview, sparkStep } from "./spark-watch.js?v=20261007-watch";

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
// A "spark:<job>:<sample>" run is a Spark runner sample, live or finished, read through the site relay (spark-watch.js).
export const fetchRunOverview = (run) =>
  isSparkRun(run) ? sparkOverview(run)
    : run ? json(`${r(run)}/run-overview.json`) : json("default-run-overview.json");
export const fetchGame = (run, index) => isSparkRun(run) ? sparkGame(run) : json(`${r(run)}/game-${index}.json`);
export const fetchGameFrames = (run, index) =>
  isSparkRun(run) ? sparkFrames(run) : json(`${r(run)}/game-${index}-frames.json`);
export const fetchGameStep = (run, index, step) =>
  isSparkRun(run) ? sparkStep(run, step) : json(`${r(run)}/game-${index}-step-${step}.json`);
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
