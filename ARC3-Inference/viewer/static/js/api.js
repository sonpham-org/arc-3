const json = async (url) => {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || response.statusText);
  return payload;
};

const runParam = (run) => (run ? `run=${encodeURIComponent(run)}` : "");

export const fetchRunOverview = (run) => json(`/api/run-overview?${runParam(run)}`);
export const fetchGame = (run, index) => json(`/api/game?${runParam(run)}&index=${index}`);
export const fetchGameFrames = (run, index) => json(`/api/game-frames?${runParam(run)}&index=${index}`);
export const fetchGameStep = (run, index, step) =>
  json(`/api/game-step?${runParam(run)}&index=${index}&step=${step}`);
export const fetchViewerVersion = () => json("/api/viewer-version");
