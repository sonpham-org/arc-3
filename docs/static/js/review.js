// Trace review (docs/review.html). Raters compare paths forward from the same point in a game and say which is
// better; they can mark single turns good or bad with a note. Server: railway/rl_review.py.
//   team (signed in):  /api/v1/review/*            identity from the sign-in
//   outside raters:    /api/v1/public/review/*     X-Review-Key from the invite link (review.html#k=...)
// Game ids only, never titles. LEFT / RIGHT order is shuffled per rater on the server; models stay hidden until
// the rating is in.

import { draw, el, outcomeText, pathView } from "./review-ui.js?v=20261003-note";

const LETTERS = ["LEFT", "RIGHT", "C", "D"];
const KEY_STORE = "arc3-review-key";
const $ = id => document.getElementById(id);

const state = {
  mode: null, key: null, me: null, view: null, contents: {}, skip: [],
  marks: {}, scores: {}, choice: null, confidence: null, started: 0, players: [], lists: [], step: 0,
};

/* ------------------------------------------------------------------ talking to the server */
function readKey() {
  const m = location.hash.match(/(?:^#|&)k=([A-Za-z0-9_-]{20,100})/);
  if (m) {
    try { localStorage.setItem(KEY_STORE, m[1]); } catch (e) { /* private window: keep it for this visit only */ }
    history.replaceState(null, "", location.pathname + location.search);   // the key stays out of the address bar
    return m[1];
  }
  try { return localStorage.getItem(KEY_STORE); } catch (e) { return null; }
}
async function api(path, opts = {}) {
  const base = state.mode === "public" ? "/api/v1/public/review" : "/api/v1/review";
  const headers = { Accept: "application/json" };
  if (state.mode === "public") headers["X-Review-Key"] = state.key;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(base + path, {
    method: opts.method || "GET", headers, credentials: "same-origin", cache: "no-store", redirect: "manual",
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (r.type === "opaqueredirect" || r.status === 0) throw { status: 401, error: "sign_in_required" };
  const type = r.headers.get("content-type") || "";
  const data = type.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw Object.assign({ status: r.status }, typeof data === "object" ? data : { message: String(data) });
  return data;
}
function banner(text, err) {
  const b = $("banner");
  b.hidden = !text;
  b.className = "rv-banner" + (err ? " err" : "");
  b.textContent = text || "";
}
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 5000);
}

async function content(pathId) {
  if (!state.contents[pathId]) state.contents[pathId] = await api(`/path?id=${encodeURIComponent(pathId)}`);
  return state.contents[pathId];
}

/* ------------------------------------------------------------------ rendering a split */
async function renderSplit(view) {
  state.view = view;
  state.marks = {}; state.scores = {}; state.choice = null; state.confidence = null; state.started = Date.now();
  const mine = view.mine;
  if (mine) {
    state.choice = mine.choice; state.confidence = mine.confidence; state.scores = { ...(mine.scores || {}) };
    for (const m of mine.marks || []) ((state.marks[m.path] = state.marks[m.path] || {})[m.step] = { verdict: m.verdict, note: m.note || "" });
  }
  $("comment").value = mine && mine.comment || "";
  $("empty").hidden = true;
  const node = view.node, paths = view.paths;
  const contents = await Promise.all(paths.map(p => content(p.id)));

  // the shared point: a small board and one line, kept in the header so the paths start at the top of the screen
  const startRows = (node.meta && node.meta.start) || contents[0].start;
  const ctxCanvas = el("canvas", { width: 120, height: 120 });
  const hist = el("div", { class: "rv-hist", hidden: true });
  const earlier = paths.map(p => (p.meta && p.meta.earlier) || []);
  const histPick = node.level > 1 && earlier.some(e => e.length) ? el("div", { class: "rv-hist-pick" },
    el("span", { class: "muted" }, "How they got here:"),
    ...paths.map((p, i) => earlier[i].length ? el("button", { type: "button", onclick: () => showHistory(hist, earlier[i], LETTERS[i]) },
      node.level === 2 ? `${LETTERS[i]}'s level 1` : `${LETTERS[i]}'s levels 1-${node.level - 1}`) : null)) : null;
  $("deck").hidden = false;
  $("context").replaceChildren(
    ctxCanvas,
    el("div", { class: "rv-ctx-info" },
      el("div", { class: "rv-ctx-head" },
        el("span", { class: "game" }, node.game),
        el("span", { class: "rv-tag" }, node.kind === "level_start" ? `start of level ${node.level}` : `turn branch · level ${node.level}`)),
      el("div", { class: "muted" }, `${view.split.ratings} rating${view.split.ratings === 1 ? "" : "s"} on this pair so far`),
      histPick),
    hist);
  requestAnimationFrame(() => draw(ctxCanvas, startRows));

  // the options
  state.players = []; state.lists = []; state.step = 0;
  const opts = $("options");
  opts.className = `rv-options n${paths.length}`;
  opts.replaceChildren(...paths.map((p, i) => {
    const { player: pl, list } = pathView(contents[i], p.id, state.marks, ti => { if (ti !== state.step) setStep(ti, i); });
    state.players.push(pl);
    state.lists.push(list);
    const stars = el("div", { class: "rv-stars" }, el("span", { class: "muted" }, "this path, 1-5:"),
      ...[1, 2, 3, 4, 5].map(n => el("button", { type: "button", class: state.scores[p.id] === n ? "on" : "",
        onclick: e => {
          state.scores[p.id] = state.scores[p.id] === n ? undefined : n;
          [...e.currentTarget.parentNode.querySelectorAll("button")].forEach((b, k) => b.classList.toggle("on", state.scores[p.id] === k + 1));
        } }, n)));
    return el("article", { class: "rv-opt", "data-i": i },
      el("div", { class: "rv-opt-head" },
        el("span", { class: "rv-letter" }, LETTERS[i]),
        el("span", { class: "rv-outcome" + (p.cleared ? " ok" : "") }, outcomeText(p)),
        el("span", { class: "rv-model rv-tag", hidden: true }, p.model)),
      pl.node, list, el("div", { class: "rv-ended", hidden: true }, `${LETTERS[i]} had no turn here: its play was already over.`), stars);
  }));
  const longest = Math.max(...contents.map(c => c.turns.length));
  $("stepper").hidden = false;
  $("stepbar").max = Math.max(0, longest - 1);
  setStep(0);

  // the verdict
  const choices = [...paths.map((p, i) => [p.id, LETTERS[i], String(i + 1)]), ["tie", "about the same", "T"], ["neither", "both bad", "N"]];
  $("choices").replaceChildren(...choices.map(([value, label, hint]) => el("button", {
    type: "button", "data-choice": value, class: state.choice === value ? "on" : "",
    onclick: () => pick(value) }, label, " ", el("kbd", {}, hint))));
  [...$("conf").querySelectorAll("button")].forEach(b => b.classList.toggle("on", +b.dataset.conf === state.confidence));
  pick(state.choice, true);
}

// one turn at a time, the same turn of every path side by side; a path that is shorter shows its last board and a note
function setStep(k, from) {
  const turns = state.view ? state.view.paths.map((p, i) => state.lists[i] ? state.lists[i].children.length : 0) : [];
  const longest = Math.max(0, ...turns);
  k = Math.max(0, Math.min(longest - 1, k));
  state.step = k;
  $("stepbar").value = k;
  $("steplabel").textContent = `Turn ${k + 1} of ${turns.join(" / ")}`;
  state.lists.forEach((list, i) => {
    const over = k >= list.children.length;
    [...list.children].forEach((li, j) => { li.hidden = j !== k; });
    list.parentNode.querySelector(".rv-ended").hidden = !over;
    if (i === from) return;
    if (over) state.players[i].last(); else state.players[i].jumpToTurn(k);
  });
}

function pick(value, quiet) {
  state.choice = value;
  [...$("choices").querySelectorAll("button")].forEach(b => b.classList.toggle("on", b.dataset.choice === value));
  [...$("options").children].forEach((o, i) => o.classList.toggle("picked", state.view && state.view.paths[i] && state.view.paths[i].id === value));
  $("submit").disabled = !value;
  if (!quiet && value) $("comment").focus({ preventScroll: true });
}

async function showHistory(box, pathIds, who) {
  box.hidden = false;
  box.replaceChildren(el("p", { class: "muted" }, "loading…"));
  try {
    const cs = await Promise.all(pathIds.map(content));
    box.replaceChildren(el("p", { class: "muted" }, `${who}'s play before this point (one row of turns per level):`),
      ...cs.map(c => {
        const { player: pl, list } = pathView(c, null, null);
        return el("details", { class: "rv-code" }, el("summary", {}, `level ${c.level}: ${c.turns.length} turns`),
          el("div", { class: "rv-opt" }, pl.node, list));
      }));
  } catch (e) {
    box.replaceChildren(el("p", { class: "muted" }, "could not load the earlier levels"));
  }
}

/* ------------------------------------------------------------------ flow */
async function loadNext() {
  banner("");
  try {
    const view = await api(`/next?skip=${encodeURIComponent(state.skip.join(","))}`);
    if (view.done) {
      $("deck").hidden = true; $("stepper").hidden = true; $("options").replaceChildren();
      $("empty").hidden = false;
      $("empty").textContent = `You have rated every pair in the pool (${view.rated} so far). New pairs arrive as runs finish; come back later.`;
      return;
    }
    await renderSplit(view);
    window.scrollTo({ top: 0 });
  } catch (e) {
    showError(e);
  } finally {
    refreshWho();   // also when the pool is empty: the team panel is where raters get invited
  }
}

async function submit() {
  const v = state.view;
  if (!v || !state.choice) return;
  const marks = [];
  for (const [path, steps] of Object.entries(state.marks)) for (const [step, m] of Object.entries(steps))
    if (m.verdict || (m.note && m.note.trim())) marks.push({ path, step: +step, verdict: m.verdict || null, note: (m.note || "").trim() || null });
  const scores = {};
  for (const [k, n] of Object.entries(state.scores)) if (n) scores[k] = n;
  $("submit").disabled = true;
  try {
    await api("/rating", { method: "POST", body: {
      split: v.split.id, choice: state.choice, confidence: state.confidence, scores, marks,
      comment: $("comment").value.trim() || null, seconds: Math.round((Date.now() - state.started) / 1000) } });
    if (state.mode === "team") toast("Saved. " + v.paths.map((p, i) => `${LETTERS[i]} was ${p.model}`).join(", ") + ".");
    else toast("Saved, thank you.");
    state.skip = state.skip.filter(s => s !== v.split.id);
    await loadNext();
  } catch (e) {
    $("submit").disabled = false;
    showError(e);
  }
}

function showError(e) {
  if (e && (e.status === 401 || e.error === "sign_in_required" || e.error === "invalid_key")) {
    if (state.mode === "public") banner("This invite link is not active any more. Ask for a new one.", true);
    else banner("Sign in with your team account (top of any internal page), or open the invite link you were sent.", true);
  } else if (e && e.status === 403) {
    banner("This Google account is not on the team list. Outside raters use their invite link.", true);
  } else if (e && e.status === 429) {
    banner("That is a lot of ratings in a short time; take a short break and come back.", true);
  } else {
    banner(`Something went wrong: ${(e && (e.message || e.error)) || e}`, true);
  }
}

async function refreshWho() {
  try {
    const me = await api("/me");
    state.me = me;
    $("who").textContent = `${me.rated} rated of ${me.splits}`;
    if (me.team) renderTeam();
  } catch (e) {
    $("who").textContent = "";
  }
}

/* ------------------------------------------------------------------ team: pool and raters */
async function renderTeam() {
  const box = $("team");
  try {
    const [stats, raters] = await Promise.all([api("/stats"), api("/raters")]);
    const open = box.querySelector("details") ? box.querySelector("details").open : false;
    const linkBox = el("div");
    const nameInput = el("input", { placeholder: "rater's name, e.g. Ada (outside)", maxlength: 80 });
    const invite = async () => {
      const name = nameInput.value.trim();
      if (!name) return;
      try {
        const r = await api("/raters", { method: "POST", body: { name } });
        const link = `${location.origin}/review.html#k=${r.key}`;
        linkBox.replaceChildren(el("div", { class: "rv-link" }, link),
          el("div", { class: "muted" }, "Shown once: copy it now and send it to the rater. They need no sign-in."));
        try { await navigator.clipboard.writeText(link); toast("Invite link copied."); } catch (e) { /* copy by hand */ }
        nameInput.value = "";
        renderTeam();
      } catch (e) { showError(e); }
    };
    box.hidden = false;
    box.replaceChildren(el("details", { open: open || null },
      el("summary", {}, `Pool and raters: ${stats.splits} pairs from ${stats.paths} paths at ${stats.nodes} points · ${stats.ratings} ratings`),
      el("div", { class: "grid" },
        el("div", {},
          el("div", { class: "kpi" },
            ...[["points", stats.nodes], ["paths", stats.paths], ["pairs", stats.splits], ["ratings", stats.ratings],
              ["pairs rated 2+", stats.agreement.splits], ["all agreed", stats.agreement.agreed]]
              .map(([k, v]) => el("div", {}, el("b", {}, v), k))),
          el("table", {}, el("tr", {}, ...["game", "points", "paths", "pairs", "ratings"].map(h => el("th", {}, h))),
            ...stats.games.map(g => el("tr", {}, ...[g.game, g.nodes, g.paths, g.splits, g.ratings].map(v => el("td", {}, v)))))),
        el("div", {},
          el("b", {}, "Raters"),
          el("table", {}, el("tr", {}, ...["name", "ratings", "last", ""].map(h => el("th", {}, h))),
            ...raters.raters.map(r => el("tr", {}, el("td", {}, r.name), el("td", {}, r.ratings),
              el("td", {}, r.last ? new Date(r.last).toLocaleString() : "–"),
              el("td", {}, el("button", { type: "button", onclick: async () => {
                await api(r.active ? "/raters/revoke" : "/raters/restore", { method: "POST", body: { raterId: r.rater_id } });
                renderTeam(); } }, r.active ? "revoke" : "restore"))))),
          el("div", { class: "rv-invite" }, nameInput, el("button", { type: "button", onclick: invite }, "Invite a rater")),
          linkBox),
        el("div", {},
          el("b", {}, "Latest ratings"),
          el("table", {}, ...stats.recent.slice(0, 12).map(r => el("tr", {},
            el("td", {}, r.name), el("td", {}, r.node_id.split(":").slice(0, 2).join(" ")),
            el("td", {}, r.choice.includes(":") ? r.choice.split(":")[1] : r.choice), el("td", {}, r.comment || "")))),
          el("p", { class: "muted", style: "margin-top:6px" }, "Each pair shows paths from one point; the server pairs new paths as runs are published (base against LoRA first).")))));
  } catch (e) {
    box.hidden = true;
  }
}

/* ------------------------------------------------------------------ start */
function keys(e) {
  if (e.target.closest("input, textarea")) return;
  const v = state.view;
  if (!v || $("deck").hidden) return;
  if (e.key === "ArrowRight" || e.key === "l") { setStep(state.step + 1); e.preventDefault(); }
  else if (e.key === "ArrowLeft" || e.key === "h") { setStep(state.step - 1); e.preventDefault(); }
  else if (/^[1-4]$/.test(e.key) && v.paths[+e.key - 1]) pick(v.paths[+e.key - 1].id);
  else if (e.key === "t") pick("tie");
  else if (e.key === "n") pick("neither");
  else if (e.key === "Enter" && state.choice) submit();
}

async function main() {
  state.key = readKey();
  state.mode = state.key ? "public" : "team";
  $("submit").addEventListener("click", submit);
  $("skip").addEventListener("click", () => { if (state.view) state.skip.push(state.view.split.id); loadNext(); });
  $("conf").addEventListener("click", e => {
    const b = e.target.closest("button[data-conf]");
    if (!b) return;
    state.confidence = state.confidence === +b.dataset.conf ? null : +b.dataset.conf;
    [...$("conf").querySelectorAll("button")].forEach(x => x.classList.toggle("on", +x.dataset.conf === state.confidence));
  });
  $("stepbar").addEventListener("input", () => setStep(+$("stepbar").value));
  $("stepprev").addEventListener("click", () => setStep(state.step - 1));
  $("stepnext").addEventListener("click", () => setStep(state.step + 1));
  document.addEventListener("keydown", keys);
  window.addEventListener("resize", () => state.players.forEach(p => p.redraw()));
  const direct = new URLSearchParams(location.search).get("split");
  if (direct) {
    try { await renderSplit(await api(`/split?id=${encodeURIComponent(direct)}`)); refreshWho(); return; }
    catch (e) { showError(e); }
  }
  await loadNext();
}
main();
