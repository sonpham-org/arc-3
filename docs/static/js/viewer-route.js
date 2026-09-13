// Canonical, shareable viewer routes. Numeric `game` values remain supported
// for old links; new links use the opaque game id and add `instance` only when
// a multi-pass run contains that id more than once.

function optionalInt(value) {
  if (value === null || value === "" || !/^\d+$/.test(value)) return null;
  return Number(value);
}

export function parseViewerHash(hash = location.hash) {
  const params = new URLSearchParams(String(hash || "").replace(/^#/, ""));
  const rawGame = params.get("game");
  const game = rawGame === null ? null : (/^\d+$/.test(rawGame) ? Number(rawGame) : rawGame);
  const rawTurn = params.get("turn");
  return {
    run: params.get("run"),
    game,
    instance: optionalInt(params.get("instance")),
    turn: optionalInt(rawTurn && rawTurn.replace(/^T/i, "")),
    frame: optionalInt(params.get("frame")),
  };
}

export function viewerHash({ run, game = null, instance = null, turn = null, frame = null }) {
  const params = new URLSearchParams();
  if (run) params.set("run", run);
  if (game !== null && game !== undefined && game !== "") params.set("game", String(game));
  if (instance !== null && instance !== undefined) params.set("instance", String(instance));
  if (turn !== null && turn !== undefined) params.set("turn", String(turn));
  if (frame !== null && frame !== undefined) params.set("frame", String(frame));
  const rendered = params.toString();
  return rendered ? `#${rendered}` : "";
}

export function canonicalGameRef(games, index) {
  const game = games?.[index];
  const gameId = String(game?.game_id || "").trim();
  if (!gameId) return { game: index, instance: null };
  const duplicates = games.filter((candidate) => candidate?.game_id === gameId).length > 1;
  return { game: gameId, instance: duplicates ? index : null };
}

export function resolveGameIndex(games, game, instance = null) {
  if (typeof game === "number") return game;
  if (typeof game !== "string") return -1;
  if (instance !== null && games?.[instance]?.game_id === game) return instance;
  return (games || []).findIndex((candidate) => candidate?.game_id === game);
}

export function framePositionForRoute(frames, { turn = null, frame = null } = {}) {
  if (frame !== null) {
    const exact = (frames || []).findIndex((candidate) => candidate?.frameIndex === frame);
    if (exact >= 0) return exact;
  }
  if (turn !== null) {
    const firstInTurn = (frames || []).findIndex((candidate) => candidate?.analysis_step === turn);
    if (firstInTurn >= 0) return firstInTurn;
  }
  return null;
}
