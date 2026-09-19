// Games page: one row per game tree.
//
// Left, frozen: a big thumbnail of the tree's current version, the one to play. Right, in a
// strip that scrolls sideways: the tree itself, root on the left, leaves on the right. Each
// column is one generation; a revision continues its parent's lane, a branch (a new game grown
// from an old one) drops to a lane of its own, joined by a dashed edge.
//
// Everything user-written (change notes, reviews) goes into the page with textContent, never
// innerHTML: public reviews are untrusted input read by the signed-in team.

import { AUTHOR_GLYPHS, AUTHOR_LABELS, BLIND_FAMILIES, familyLabel } from "./games-api.js?v=20260919-trees";

export const COL_W = 156;
export const NODE_W = 128;
const PAD = 14;
const THUMB = 116;
const LANE_H_NOTES = 244;
const LANE_H_PLAIN = 198;

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
};

export function shortDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function longDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// ── Layout ──────────────────────────────────────────────────────────────────

// Places every version on a grid: col = generation (distance from the root), lane = row.
// Depth-first, continuation first: a node's lane passes to the revision that leads to the
// line's current version; every other child (a branch, or a second revision forking the same
// game) opens a new lane once that continuation has been fully laid out. That order hangs the
// deepest branches nearest the main line, so their edges never cross an earlier branch's line.
export function layoutTree(versions) {
  const byId = new Map(versions.map((v) => [v.versionId, v]));
  const children = new Map();
  const roots = [];
  for (const v of versions) {
    if (v.parentVersionId && byId.has(v.parentVersionId)) {
      if (!children.has(v.parentVersionId)) children.set(v.parentVersionId, []);
      children.get(v.parentVersionId).push(v);
    } else {
      roots.push(v);
    }
  }
  // Mark the path from each line's current version back to where its line started, so the
  // continuation is the revision that leads to it, not merely the oldest one.
  const towardHead = new Set();
  for (const v of versions) {
    if (!v.isLineHead) continue;
    let cursor = v;
    while (cursor) {
      towardHead.add(cursor.versionId);
      if (cursor.kind !== "revision") break;
      cursor = byId.get(cursor.parentVersionId);
    }
  }
  const pos = new Map();
  let lanes = 0;
  let maxCol = 0;
  const stack = roots.slice().reverse().map((root) => [root, 0, null]);
  while (stack.length) {
    const [v, col, inherited] = stack.pop();
    const lane = inherited === null ? lanes++ : inherited;
    pos.set(v.versionId, { col, lane });
    if (col > maxCol) maxCol = col;
    const kids = children.get(v.versionId) || [];
    const revisions = kids.filter((k) => k.kind === "revision");
    const next = revisions.find((k) => towardHead.has(k.versionId)) || revisions[0] || null;
    const others = kids.filter((k) => k !== next);
    for (let i = others.length - 1; i >= 0; i--) stack.push([others[i], col + 1, null]);
    if (next) stack.push([next, col + 1, lane]);
  }
  return { pos, cols: maxCol + 1, lanes: Math.max(1, lanes) };
}

// ── Nodes ───────────────────────────────────────────────────────────────────

export function authorBadge(author) {
  const kind = (author && author.kind) || "unknown";
  const badge = el("span", `auth ${kind}`, AUTHOR_GLYPHS[kind] || "?");
  badge.title = [AUTHOR_LABELS[kind] || kind, author && author.model].filter(Boolean).join(" · ");
  return badge;
}

export function feedbackLine(feedback) {
  if (!feedback) return "";
  const team = feedback.team;
  const pub = feedback.public;
  const parts = [];
  if (team && team.count) parts.push(`${team.fun != null ? `★${team.fun.toFixed(1)} ` : ""}team ${team.count}`);
  if (pub && pub.count) parts.push(`public ${pub.count}`);
  return parts.join(" · ");
}

function nodeButton(version, { notes, parentGameId, onSelect }) {
  const node = el("button", "node");
  node.type = "button";
  node.dataset.version = version.versionId || version.gameId;
  if (version.isTreeHead) node.classList.add("head");
  else if (version.isLineHead) node.classList.add("line-head");
  if (version.kind === "branch") node.classList.add("branch");

  const img = el("img");
  img.loading = "lazy";
  img.alt = "";
  if (version.thumbUrl) img.src = version.thumbUrl;
  else img.classList.add("missing");
  img.onerror = () => img.classList.add("missing");
  node.appendChild(img);

  const top = el("span", "n-top");
  top.append(authorBadge(version.author), el("span", "v", `v${version.number || 1}`));
  top.append(el("span", "kind", version.isTreeHead ? "current" : version.kind === "seed" ? "seed" : version.kind));
  top.append(el("span", "date", shortDate(version.createdAt)));
  node.appendChild(top);

  if (parentGameId !== undefined && parentGameId !== version.gameId) {
    node.appendChild(el("span", "n-game", version.gameId));
  }
  const note = notes && notes[version.versionId];
  if (note && note.reason) node.appendChild(el("span", "reason", note.reason));
  const fb = feedbackLine(version.feedback);
  if (fb) node.appendChild(el("span", "fb", fb));

  node.title = [
    `${version.gameId} v${version.number || 1}`,
    `${AUTHOR_LABELS[(version.author || {}).kind] || "Unknown"}${version.author && version.author.model ? ` (${version.author.model})` : ""}`,
    longDate(version.createdAt),
    note && note.reason,
  ]
    .filter(Boolean)
    .join("\n");
  node.addEventListener("click", () => onSelect(version));
  return node;
}

function edgePath(from, to, laneH) {
  const x1 = PAD + from.col * COL_W + NODE_W;
  const y1 = PAD + from.lane * laneH + 6 + THUMB / 2;
  const x2 = PAD + to.col * COL_W;
  const y2 = PAD + to.lane * laneH + 6 + THUMB / 2;
  if (y1 === y2) return `M${x1},${y1} L${x2},${y2}`;
  const mid = x1 + (x2 - x1) / 2;
  return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`;
}

export function renderTreeCanvas(container, versions, { notes, onSelect }) {
  const { pos, cols, lanes } = layoutTree(versions);
  const laneH = notes ? LANE_H_NOTES : LANE_H_PLAIN;
  const width = PAD * 2 + (cols - 1) * COL_W + NODE_W;
  const height = PAD * 2 + (lanes - 1) * laneH + (laneH - 24);
  const canvas = el("div", "tree-canvas");
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("class", "tree-edges");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  svg.setAttribute("aria-hidden", "true");
  const byId = new Map(versions.map((v) => [v.versionId, v]));
  for (const v of versions) {
    const parent = v.parentVersionId && byId.get(v.parentVersionId);
    if (!parent) continue;
    const path = document.createElementNS(svgNS, "path");
    path.setAttribute("d", edgePath(pos.get(parent.versionId), pos.get(v.versionId), laneH));
    if (v.kind === "branch") path.setAttribute("class", "branch");
    svg.appendChild(path);
  }
  canvas.appendChild(svg);

  for (const v of versions) {
    const p = pos.get(v.versionId);
    const parent = v.parentVersionId && byId.get(v.parentVersionId);
    const node = nodeButton(v, { notes, parentGameId: parent ? parent.gameId : v.gameId, onSelect });
    node.style.left = `${PAD + p.col * COL_W}px`;
    node.style.top = `${PAD + p.lane * laneH}px`;
    canvas.appendChild(node);
  }
  container.replaceChildren(canvas);
  return canvas;
}

// ── Rows ────────────────────────────────────────────────────────────────────

function heroBlock(tree, ctx) {
  const hero = el("div", "tree-hero");
  const head = tree.head;
  const thumbButton = el("button", "hero-thumb");
  thumbButton.type = "button";
  thumbButton.title = "Play the current version";
  const img = el("img");
  img.alt = "";
  img.loading = "lazy";
  if (head.thumbUrl) img.src = head.thumbUrl;
  img.onerror = () => img.classList.add("missing");
  thumbButton.appendChild(img);
  thumbButton.appendChild(el("span", "hero-play", "▶"));
  thumbButton.addEventListener("click", () => ctx.onPlay(tree, head));
  hero.appendChild(thumbButton);

  const title = el("div", "hero-title");
  const blind = BLIND_FAMILIES.has(tree.family);
  title.append(el("span", "name", blind ? head.gameId : tree.title || head.gameId));
  if (!blind && tree.title && tree.title !== head.gameId) title.append(el("span", "gid", head.gameId));
  hero.appendChild(title);

  const versions = tree.versionCount || 1;
  const branchText = tree.branchCount ? ` · ${tree.branchCount} branch${tree.branchCount === 1 ? "" : "es"}` : "";
  hero.appendChild(
    el(
      "div",
      "hero-sub",
      `${familyLabel(tree.family)} · current v${head.number || 1} · ${versions} version${versions === 1 ? "" : "s"}${branchText}`
    )
  );

  const authors = el("div", "hero-authors");
  const counts = tree.authors || {};
  for (const kind of ["claude", "gpt", "human", "other", "unknown"]) {
    if (!counts[kind]) continue;
    const pill = el("span", "pill");
    pill.append(authorBadge({ kind }), el("span", null, `${AUTHOR_LABELS[kind]} ×${counts[kind]}`));
    authors.appendChild(pill);
  }
  if (tree.lastChangedAt) authors.appendChild(el("span", "pill muted", `changed ${shortDate(tree.lastChangedAt)}`));
  if (authors.childElementCount) hero.appendChild(authors);

  const fb = tree.feedback || {};
  hero.appendChild(
    el(
      "div",
      "hero-fb",
      fb.team || fb.public ? `Feedback: team ${fb.team || 0} · public ${fb.public || 0}` : "No feedback yet"
    )
  );

  const actions = el("div", "hero-actions");
  const play = el("button", "primary sm", "▶ Play");
  play.type = "button";
  play.addEventListener("click", () => ctx.onPlay(tree, head));
  const review = el("button", "sm", "Review");
  review.type = "button";
  review.title = "Play the current version and leave feedback";
  review.addEventListener("click", () => ctx.onReview(tree, head));
  actions.append(play, review);
  hero.appendChild(actions);
  return hero;
}

// One row. Single-version trees render at once from the list data; bigger trees fetch their
// full detail (and, for the team, their change notes) the first time the row scrolls into view.
export function renderTreeRow(tree, ctx) {
  const row = el("article", "tree-row");
  row.dataset.tree = tree.treeId;
  row.appendChild(heroBlock(tree, ctx));
  const scroll = el("div", "tree-scroll");
  row.appendChild(scroll);

  // notes: the team's full notes response ({notes, feedback}) or null. Nodes show its change
  // notes; the drawer also needs its reviews, so it gets the whole response.
  const draw = (detail, notes) => {
    renderTreeCanvas(scroll, detail.versions, {
      notes: notes ? notes.notes : null,
      onSelect: (version) => ctx.onNode(tree, version, detail, notes),
    });
    if ((tree.versionCount || 1) === 1) {
      scroll.appendChild(
        el(
          "p",
          "tree-empty",
          "No revisions yet. When GPT or Claude evolves this game, each new version lands to the right."
        )
      );
    }
  };

  // A one-version tree needs nothing more than the list already sent; the drawer fetches its
  // notes if someone opens it.
  if ((tree.versionCount || 1) === 1) {
    draw({ versions: [{ ...tree.head, isTreeHead: true, isLineHead: true }] }, null);
    return row;
  }
  scroll.appendChild(el("p", "tree-loading", "Loading tree…"));
  ctx.whenVisible(row, async () => {
    try {
      const [detail, notes] = await Promise.all([
        tree.head.static ? { versions: [{ ...tree.head }] } : ctx.loadDetail(tree.treeId),
        ctx.team && !tree.head.static ? ctx.loadNotes(tree.treeId).catch(() => null) : null,
      ]);
      draw(detail, notes);
    } catch (err) {
      scroll.replaceChildren(el("p", "tree-loading", `Could not load this tree (${err.message}).`));
    }
  });
  return row;
}

// ── Version drawer ──────────────────────────────────────────────────────────

const FLAG_LABELS = {
  solved_it: "Worked out what to do",
  never_understood: "Never worked out what to do",
  inputs_did_nothing: "Inputs did nothing",
  felt_broken: "Felt broken",
  felt_impossible: "Felt unfair or impossible",
  enjoyed_it: "Enjoyed it",
  too_easy: "Too easy",
  looks_like_others: "Looks like other games",
  boring: "Boring",
  visual_clutter: "Visually cluttered",
  has_text: "Has text on screen",
};
export const flagLabel = (flag) => FLAG_LABELS[flag] || flag;

function reviewCard(review, { team, onHide }) {
  const card = el("div", `review ${review.reviewerClass}${review.hidden ? " hidden-review" : ""}`);
  const head = el("div", "r-head");
  head.append(
    el("span", `who ${review.reviewerClass}`, review.reviewerClass === "team" ? "Team" : "Public"),
    el("span", null, review.reviewer ? String(review.reviewer).split("@")[0] : review.reviewerClass === "public" ? "anonymous" : ""),
    el("span", "when", longDate(review.createdAt))
  );
  if (review.outcome) head.append(el("span", `outcome ${review.outcome}`, review.outcome.replace("_", " ")));
  card.appendChild(head);

  const facts = [];
  if (review.levelsTotal) facts.push(`levels ${review.levelsCompleted ?? 0}/${review.levelsTotal}`);
  if (review.actions != null) facts.push(`${review.actions} actions`);
  if (review.seconds != null) facts.push(`${Math.round(review.seconds / 60)} min`);
  if (facts.length) card.appendChild(el("div", "r-facts", facts.join(" · ")));

  const ratings = el("div", "ratings");
  for (const [key, label] of [["fun", "Fun"], ["clarity", "Clarity"], ["difficulty", "Difficulty"], ["novelty", "Novelty"]]) {
    if (review[key] != null) ratings.appendChild(el("span", null, `${label} ${review[key]}/5`));
  }
  if (ratings.childElementCount) card.appendChild(ratings);
  if (review.flags && review.flags.length) {
    const flags = el("div", "flags");
    for (const flag of review.flags) flags.appendChild(el("span", "flag", flagLabel(flag)));
    card.appendChild(flags);
  }
  for (const [key, label] of [
    ["goalGuess", "Thought the goal was"],
    ["liked", "Worked"],
    ["disliked", "Didn't work"],
    ["suggestion", "Change next"],
    ["bugs", "Bugs"],
  ]) {
    if (!review[key]) continue;
    const block = el("div", "r-text");
    block.append(el("b", null, `${label}: `), el("span", null, review[key]));
    card.appendChild(block);
  }
  if (review.verdict) card.appendChild(el("div", "r-verdict", `Verdict: ${review.verdict}`));
  if (team && review.reviewerClass === "public") {
    const hide = el("button", "sm link", review.hidden ? "Unhide" : "Hide as spam");
    hide.type = "button";
    hide.addEventListener("click", () => onHide(review, hide));
    card.appendChild(hide);
  }
  return card;
}

export function openVersionDrawer({ tree, version, detail, notes, team, signInUrl, onPlay, onReview, onHide }) {
  const drawer = document.getElementById("versionDrawer");
  const body = drawer.querySelector(".drawer-body");
  const heading = drawer.querySelector(".drawer-title");
  heading.textContent = `${version.gameId} · v${version.number || 1}${version.isTreeHead ? " · current" : ""}`;
  body.replaceChildren();

  const top = el("div", "d-top");
  const img = el("img", "big");
  img.alt = "";
  if (version.thumbUrl) img.src = version.thumbUrl;
  top.appendChild(img);
  const actions = el("div", "d-actions");
  const play = el("button", "primary", "▶ Play this version");
  play.type = "button";
  play.addEventListener("click", () => onPlay(tree, version, detail));
  const review = el("button", null, "Review this version");
  review.type = "button";
  review.addEventListener("click", () => onReview(tree, version, detail));
  actions.append(play, review);
  top.appendChild(actions);
  body.appendChild(top);

  const meta = el("dl", "d-meta");
  const row = (label, value) => {
    if (value === null || value === undefined || value === "") return;
    meta.append(el("dt", null, label), el("dd", null, value));
  };
  const note = notes && notes.notes ? notes.notes[version.versionId] : notes ? notes[version.versionId] : null;
  const author = (note && note.author) || version.author || {};
  row("Made by", [AUTHOR_LABELS[author.kind] || "Unknown", author.model, author.name].filter(Boolean).join(" · "));
  row("Kind", version.kind === "branch" ? "branch (a new game grown from its parent)" : version.kind);
  row("Created", longDate(version.createdAt));
  if (version.parentVersionId) row("Parent", version.parentVersionId);
  row("Family", familyLabel(tree.family));
  if (version.sha256) row("Source", `${version.srcFile} · sha256 ${version.sha256.slice(0, 12)}`);
  body.appendChild(meta);

  if (team && note) {
    const why = el("div", "d-note");
    why.append(el("h3", null, "Why this version"), el("p", null, note.reason));
    if (note.details) why.appendChild(el("pre", "d-details", note.details));
    body.appendChild(why);
  } else if (!team) {
    const hint = el("p", "d-hint");
    hint.append("Change notes and written feedback are visible to the signed-in team. ");
    const link = el("a", null, "Team sign-in");
    link.href = signInUrl;
    hint.appendChild(link);
    body.appendChild(hint);
  }

  const fb = version.feedback || {};
  const summary = el("div", "d-summary");
  summary.appendChild(el("h3", null, "Feedback on this version"));
  const stat = (label, s) => {
    if (!s || !s.count) return el("p", "muted", `${label}: none yet`);
    const bits = [`${s.count} review${s.count === 1 ? "" : "s"}`];
    for (const key of ["fun", "clarity", "difficulty", "novelty"]) if (s[key] != null) bits.push(`${key} ${s[key].toFixed(1)}`);
    if (s.won) bits.push(`${s.won} won`);
    return el("p", null, `${label}: ${bits.join(" · ")}`);
  };
  summary.append(stat("Team", fb.team), stat("Public", fb.public));
  body.appendChild(summary);

  if (team && notes && Array.isArray(notes.feedback)) {
    const mine = notes.feedback.filter((r) => r.versionId === version.versionId);
    const list = el("div", "d-reviews");
    if (!mine.length) list.appendChild(el("p", "muted", "No written reviews for this version yet."));
    for (const review of mine) list.appendChild(reviewCard(review, { team, onHide }));
    body.appendChild(list);
  }

  drawer.hidden = false;
  drawer.querySelector(".drawer-close").focus();
}

export function closeVersionDrawer() {
  const drawer = document.getElementById("versionDrawer");
  if (drawer) drawer.hidden = true;
}
