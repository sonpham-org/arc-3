// Games page data access.
//
// Trees, versions and feedback come from the Railway API (railway/games_store.py). Reads use
// the public prefix, which oauth2-proxy lets anyone through; change notes and team reviews use
// the team prefix, which only answers a signed-in session. If the API is unreachable, or its
// database has not been filled yet, the page falls back to the static manifest baked into the
// image, so the catalog still lists and plays -- as one-version trees with no history.

const PUBLIC = "/api/v1/public/games";
const TEAM = "/api/v1/games";

// Visible categories. Everything we made and reviewed is one category, "Additional games"
// (19-Sep-2026): the reviewed arena set, the in-house games, glow-ups and the research
// collection. The API still keys on the family; ADDITIONAL is what the "synthetic" filter
// and pool select server-side (every family but official and redbluepill).
export const ADDITIONAL = "synthetic";
export const CATEGORY_ORDER = [ADDITIONAL, "official", "redbluepill"];
export const CATEGORY_LABELS = {
  [ADDITIONAL]: "Additional games",
  official: "Official",
  redbluepill: "theredbluepill's arc-interactive",
};
export const categoryOf = (family) => (family === "official" || family === "redbluepill" ? family : ADDITIONAL);
export const familyLabel = (family) => CATEGORY_LABELS[categoryOf(family)];
// Who primarily drove a version (19-Sep-2026): GPT or Claude as the main driver, or a person
// actively tuning it. "other" is an import made elsewhere.
export const AUTHOR_LABELS = {
  gpt: "GPT-driven",
  claude: "Claude-driven",
  human: "Human-tuned",
  other: "Imported",
  unknown: "Unknown",
};
export const AUTHOR_GLYPHS = { gpt: "G", claude: "C", human: "H", other: "·", unknown: "?" };
// Families played blind: never show anything but the id (AGENTS.md: "Games must not speak").
export const BLIND_FAMILIES = new Set(["arena", "contributed-glowup", "research"]);
// Kept in manifest.json for arc-explainer's mirror, but off this page: the unreviewed generator
// set and theredbluepill's catalog. Same list as RETIRED_FAMILIES in
// scripts/publish_game_versions.py, which never publishes them to the trees; this drops them
// from the static fallback too.
const RETIRED_FAMILIES = new Set(["ai-generated", "redbluepill"]);

class ApiError extends Error {
  constructor(status, body) {
    super((body && (body.message || body.error)) || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function getJson(url) {
  const response = await fetch(url, {
    cache: "no-store",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body);
  return body;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    cache: "no-store",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body);
  return body;
}

// The signed-in team member, or null. oauth2-proxy answers an unauthenticated JSON request on
// a gated route with 401 (and a browser navigation with its sign-in page), so anything but a
// 200 carrying an email means "public".
export async function whoAmI() {
  try {
    const response = await fetch(`${TEAM}/me`, {
      cache: "no-store",
      credentials: "same-origin",
      redirect: "manual",
      headers: { Accept: "application/json" },
    });
    if (response.type === "opaqueredirect" || !response.ok) return null;
    const body = await response.json();
    return body && body.email ? body : null;
  } catch (e) {
    return null;
  }
}

export const signInUrl = () => `/oauth2/start?rd=${encodeURIComponent("/")}`;

// A random id per browser, so public reviews from one person can be told apart (and rate
// limited) without an account. Never sent anywhere but our own API.
export function visitorId() {
  const valid = (id) => typeof id === "string" && /^[A-Za-z0-9-]{8,64}$/.test(id);
  try {
    let id = localStorage.getItem("arc3-visitor");
    if (!valid(id)) {
      id = crypto.randomUUID ? crypto.randomUUID() : `v-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem("arc3-visitor", id);
    }
    return id;
  } catch (e) {
    return `v-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

export const listTrees = (params) => getJson(`${PUBLIC}/trees?${new URLSearchParams(params)}`);
export const treeDetail = (treeId) => getJson(`${PUBLIC}/trees/${encodeURIComponent(treeId)}`);
export const treeNotes = (treeId) => getJson(`${TEAM}/trees/${encodeURIComponent(treeId)}/notes`);
export const nextVersion = (team, params) => getJson(`${team ? TEAM : PUBLIC}/next?${new URLSearchParams(params)}`);
export const submitFeedback = (team, payload) => postJson(`${team ? TEAM : PUBLIC}/feedback`, payload);
export const setFeedbackHidden = (feedbackId, hidden) =>
  postJson(`${TEAM}/feedback/${encodeURIComponent(feedbackId)}/hidden`, { hidden });
// The ideas board (team-only: an idea names its mechanic).
// Comments and the training tick are team-only, like change notes: a comment names mechanics,
// and most families are played blind.
export const listComments = (treeId, limit = 50) =>
  getJson(`${TEAM}/trees/${encodeURIComponent(treeId)}/comments?limit=${limit}`);
export const addComment = (payload) => postJson(`${TEAM}/comments`, payload);
export const setCommentHidden = (commentId, hidden) => postJson(`${TEAM}/comments/${commentId}/hidden`, { hidden });
export const setTrainOk = (versionId, good) =>
  postJson(`${TEAM}/versions/${encodeURIComponent(versionId)}/train`, { good });

export const listIdeas = (params) => getJson(`${TEAM}/ideas?${new URLSearchParams(params)}`);
export const updateIdea = (ideaId, change) => postJson(`${TEAM}/ideas/${encodeURIComponent(ideaId)}`, change);

// ── Static fallback ─────────────────────────────────────────────────────────

let staticGames = null;

export async function staticCatalog() {
  if (!staticGames) {
    // no-store: the catalog changes whenever a game is added (see the old games-play.js note).
    const rows = await fetch("./static/games/manifest.json", { cache: "no-store" }).then((r) => r.json());
    staticGames = rows.map(staticVersion).filter((v) => !RETIRED_FAMILIES.has(v.family));
  }
  return staticGames;
}

export function staticVersion(g) {
  const family = g.category || (g.official ? "official" : "custom");
  const blind = BLIND_FAMILIES.has(family);
  return {
    versionId: null,
    gameId: g.id,
    treeId: g.id,
    family,
    title: blind ? g.id : g.title,
    description: blind ? null : g.description || null,
    tags: blind ? [] : g.tags || [],
    defaultFps: g.default_fps,
    className: g.class_name,
    srcFile: g.src_file,
    tileScale: g.tile_scale || null,
    sourceUrl: `./static/games/src/${g.id}/${g.src_file}`,
    thumbUrl: `./static/img/games/${g.id}.png`,
    kind: "seed",
    number: 1,
    author: { kind: "unknown", model: null },
    createdAt: null,
    isTreeHead: true,
    isLineHead: true,
    static: true,
  };
}

// The static catalog shaped like listTrees(): one single-version tree per game.
export async function staticTrees({ family, q, evolved, offset, limit }) {
  const all = await staticCatalog();
  const needle = (q || "").trim().toLowerCase();
  const families = {};
  for (const v of all) families[v.family] = (families[v.family] || 0) + 1;
  const matches = all.filter((v) => {
    if (evolved) return false;
    if (family === "synthetic" && (v.family === "official" || v.family === "redbluepill")) return false;
    if (family && family !== "synthetic" && v.family !== family) return false;
    if (!needle) return true;
    return `${v.gameId} ${v.title} ${(v.tags || []).join(" ")}`.toLowerCase().includes(needle);
  });
  const page = matches.slice(offset, offset + limit).map((v) => ({
    treeId: v.treeId,
    family: v.family,
    rootGameId: v.gameId,
    defaultFps: v.defaultFps,
    title: v.title,
    description: v.description,
    tags: v.tags,
    head: v,
    versionCount: 1,
    gameCount: 1,
    branchCount: 0,
    lastChangedAt: null,
    authors: { gpt: 0, claude: 0, human: 0, other: 0, unknown: 0 },
    feedback: { team: 0, public: 0 },
  }));
  return { apiVersion: 1, total: matches.length, offset, limit, families, trees: page, static: true };
}

// ── Sources ─────────────────────────────────────────────────────────────────

export async function sha256Hex(buffer) {
  if (!globalThis.crypto || !crypto.subtle) return null; // insecure context: no WebCrypto
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// The exact bytes the game runs from, and their hash: that hash (first 12 hex) is the version
// id a review is filed under, so feedback always names the build that was actually played.
export async function fetchSource(url) {
  // Uploaded versions are content-addressed and immutable, so they may be cached; the static
  // copies are rewritten in place and must not be.
  const immutable = url.startsWith("/data/_games/");
  const response = await fetch(url, { cache: immutable ? "default" : "no-store" });
  if (!response.ok) throw new Error(`game source HTTP ${response.status}`);
  const buffer = await response.arrayBuffer();
  return { text: new TextDecoder().decode(buffer), sha256: await sha256Hex(buffer) };
}
