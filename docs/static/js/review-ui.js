// Shared pieces of the RL pages (review.js, tree.js): boards, the move-by-move player, the turn list.
// A path's content (railway/rl_review.py, scripts/trace_review_index.py): {level, start: 64 hex rows, system?,
// turns: [{step, thinking, said, code: [...], input?, parts?: [{kind, text, tool?}],
//          moves: [{n, action, changed, level_up, diff: {row: hex row}}]}]}.
// Author: Claude Opus 5.5 for Bubba, 4-Oct-2026 (Son: show each turn's input; all turn text monospace, tool calls
// and results set apart). turnList(..., {full: true}) draws a turn as its input (folded) then every part in order;
// paths published before input was kept fall back to their thinking, split at the tool call and result markers.
// SRP/DRY check: Pass - the review page's one turn reader; the Tree and RL2 pages keep the compact form.

export const PALETTE = ["#FFFFFF", "#CCCCCC", "#999999", "#666666", "#333333", "#000000", "#E53AA3", "#FF7BCC",
  "#F93C31", "#1E93FF", "#88D8F1", "#FFDC00", "#FF851B", "#921231", "#4FCC30", "#A356D6"];
const RGB = PALETTE.map(h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)));

export function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false)
    e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return e;
}

export function frames(content) {
  // [{rows, turn index, move}]: the start board, then the board after every move
  let cur = content.start.slice();
  const out = [{ rows: cur, turn: -1, move: null }];
  content.turns.forEach((t, ti) => t.moves.forEach(m => {
    cur = cur.slice();
    for (const [r, row] of Object.entries(m.diff || {})) cur[+r] = row;
    out.push({ rows: cur, turn: ti, move: m });
  }));
  return out;
}

export function draw(canvas, rows) {
  const h = rows.length, w = rows[0].length;
  const img = new ImageData(w, h);
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) {
    const [R, G, B] = RGB[parseInt(rows[r][c], 16)] || [0, 0, 0];
    const i = 4 * (r * w + c);
    img.data[i] = R; img.data[i + 1] = G; img.data[i + 2] = B; img.data[i + 3] = 255;
  }
  const off = document.createElement("canvas");
  off.width = w; off.height = h;
  off.getContext("2d").putImageData(img, 0, 0);
  const px = Math.max(1, Math.round((canvas.clientWidth || 200) * (window.devicePixelRatio || 1)));
  canvas.width = px; canvas.height = Math.round(px * h / w);
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
}

export const moveLabel = m => (m ? String(m.action || "?") : "start");

export function outcomeText(p) {
  return p.cleared ? `cleared level ${p.level} in ${p.turns} turns, ${p.actions} moves`
    : `did not clear level ${p.level}: ${p.turns} turns, ${p.actions} moves`;
}

export function player(content, onTurn) {
  const fs = frames(content);
  const canvas = el("canvas", { width: 200, height: 200, "aria-label": "board" });
  const range = el("input", { type: "range", min: 0, max: fs.length - 1, value: 0, "aria-label": "move" });
  const pos = el("div", { class: "rv-pos" });
  let i = 0, timer = null;
  const show = k => {
    i = Math.max(0, Math.min(fs.length - 1, k));
    range.value = i;
    draw(canvas, fs[i].rows);
    const f = fs[i];
    pos.replaceChildren(f.turn < 0 ? "start of this stretch" : el("span", {},
      el("b", {}, `T${content.turns[f.turn].step}`), ` · move ${i} of ${fs.length - 1} · ${moveLabel(f.move)}`,
      f.move && f.move.level_up ? " · level cleared" : ""));
    onTurn(f.turn);
  };
  const play = btn => {
    if (timer) { clearInterval(timer); timer = null; btn.textContent = "▶ play"; return; }
    if (i >= fs.length - 1) show(0);
    btn.textContent = "❚❚ pause";
    timer = setInterval(() => { if (i >= fs.length - 1) { play(btn); return; } show(i + 1); }, 260);
  };
  const playBtn = el("button", { type: "button", onclick: e => play(e.currentTarget) }, "▶ play");
  range.addEventListener("input", () => show(+range.value));
  const node = el("div", { class: "rv-player" }, canvas,
    el("div", { class: "rv-scrub" },
      el("div", { class: "row" },
        el("button", { type: "button", title: "start", onclick: () => show(0) }, "⏮"),
        el("button", { type: "button", title: "previous move", onclick: () => show(i - 1) }, "◀"),
        playBtn,
        el("button", { type: "button", title: "next move", onclick: () => show(i + 1) }, "▶|"),
        el("button", { type: "button", title: "end", onclick: () => show(fs.length - 1) }, "⏭")),
      range, pos));
  const jumpToTurn = ti => { const k = fs.findIndex(f => f.turn === ti); if (k >= 0) show(k); };
  requestAnimationFrame(() => show(0));
  return { node, jumpToTurn, last: () => show(fs.length - 1), redraw: () => show(i) };
}

/* ------------------------------------------------------------------ a turn in full: input, then what it did */
const PART_LABEL = { thinking: "thinking", said: "said", call: "tool call", result: "tool result" };
const TOOL_MARK = /^\[(TOOL CALL|TOOL RESULT)(?::\s*([^\]\n]*))?\]\s*$/m;
const INPUT_STORE = "arc3-review-input-open";

// the code a tool call ran, out of its <tool_call><function=..><parameter=code> wrapping
const callCode = text => { const m = text.match(/<parameter=code>\n?([\s\S]*?)\n?<\/parameter>/); return m ? m[1] : text; };

// older paths keep one thinking text that runs on into the first tool call and its result: cut it at those markers
function legacyParts(t) {
  const parts = [], bits = (t.thinking || t.said || "").split(TOOL_MARK);
  // split with two groups: [text, name, tool, text, name, tool, text, ...]
  if (bits[0].trim()) parts.push({ kind: "thinking", text: bits[0].trim() });
  for (let k = 1; k < bits.length; k += 3) {
    const kind = bits[k] === "TOOL CALL" ? "call" : "result", text = (bits[k + 2] || "").trim();
    parts.push({ kind, tool: (bits[k + 1] || "").trim(), text: kind === "call" ? callCode(text) : text });
  }
  return parts;
}

function partNode(p) {
  const label = PART_LABEL[p.kind] || p.kind;
  return el("div", { class: `rv-part rv-p-${p.kind}` },
    el("div", { class: "rv-part-label" }, p.tool && p.kind !== "thinking" ? `${label} · ${p.tool}` : label),
    el("pre", { class: "rv-part-text" }, p.text || (p.kind === "result" ? "(no output)" : "")));
}

// the input folds; opening or closing it does the same on every path on the page and is remembered
function inputOpen() { try { return localStorage.getItem(INPUT_STORE) === "1"; } catch (e) { return false; } }
function inputNode(content, t) {
  const text = (t.input || "").trim();
  const lines = text.split("\n").filter(l => l.trim());
  const box = el("details", { class: "rv-input", open: text && inputOpen() || null },
    el("summary", {}, el("span", { class: "rv-part-label" }, "input"),
      el("span", { class: "rv-input-peek" }, text ? lines.slice(0, 2).join("  ·  ") : "not in this path's data yet (paths published from now on carry it)")),
    text ? el("pre", { class: "rv-part-text" }, text) : null,
    text && content.system ? el("details", { class: "rv-system" }, el("summary", {}, "system prompt (the same every turn)"),
      el("pre", { class: "rv-part-text" }, content.system)) : null);
  if (!text) box.addEventListener("click", e => e.preventDefault());
  box.addEventListener("toggle", () => {
    if (!text) return;
    try { localStorage.setItem(INPUT_STORE, box.open ? "1" : "0"); } catch (e) { /* private window */ }
    document.querySelectorAll(".rv-input.has").forEach(d => { if (d !== box && d.open !== box.open) d.open = box.open; });
  });
  if (text) box.classList.add("has");
  return box;
}

function fullTurn(content, t) {
  const parts = Array.isArray(t.parts) && t.parts.length ? t.parts : legacyParts(t);
  return [inputNode(content, t),
    el("div", { class: "rv-parts" }, parts.length ? parts.map(partNode) : el("div", { class: "muted" }, "(no thinking text this turn)"))];
}

// marks: null (read only) or the page's store {pathId: {step: {verdict, note}}}, written as the rater clicks
// onMark (optional): called as onMark(step) after a good/bad click or a note edit; may return a promise (saved or not)
// opts.full: draw each turn whole (input, thinking, tool calls and results); otherwise the compact thinking + code
export function turnList(content, pathId, marks, onMark, opts = {}) {
  const items = content.turns.map((t, ti) => {
    const mark = marks ? (marks[pathId] || {})[t.step] || {} : {};
    const note = el("textarea", { class: "rv-note", placeholder: "Why? (optional)", maxlength: 2000 });
    note.value = mark.note || "";
    const slot = () => ((marks[pathId] = marks[pathId] || {})[t.step] = marks[pathId][t.step] || {});
    const setMark = verdict => {
      const m = slot();
      m.verdict = m.verdict === verdict ? null : verdict;
      good.classList.toggle("on", m.verdict === "up");
      bad.classList.toggle("on", m.verdict === "down");
      if (m.verdict) note.focus();
      save(t.step);
    };
    const status = el("span", { class: "rv-saved muted" });
    let timer = null;
    const save = (step, wait = 0) => {
      if (!onMark) return;
      status.textContent = "saving…";
      clearTimeout(timer);
      timer = setTimeout(() => Promise.resolve(onMark(step)).then(
        () => { status.textContent = "saved"; }, () => { status.textContent = "NOT saved"; }), wait);
    };
    const good = el("button", { type: "button", class: "good" + (mark.verdict === "up" ? " on" : ""), title: "this turn was right",
      onclick: e => { e.stopPropagation(); setMark("up"); } }, "good");
    const bad = el("button", { type: "button", class: "bad" + (mark.verdict === "down" ? " on" : ""), title: "this turn was wrong",
      onclick: e => { e.stopPropagation(); setMark("down"); } }, "bad");
    note.addEventListener("input", () => { slot().note = note.value; save(t.step, 600); });
    const think = el("div", { class: "rv-think clamp", title: "click to read all" }, (t.thinking || t.said || "").trim());
    think.addEventListener("click", () => think.classList.toggle("clamp"));
    const code = (t.code || []).filter(Boolean);
    return el("li", { class: "rv-turn", "data-ti": ti },
      el("div", { class: "rv-turn-head", "data-ti": ti },
        el("span", { class: "rv-t" }, `T${t.step}`),
        // RL v2 turn coach: the mode this turn was played in (only coached runs carry it)
        t.coach ? el("span", { class: "rv-tag rv-coach" + (t.coach === "stock" ? " stock" : ""),
          title: "turn coach mode for this turn" }, t.coach) : null,
        el("span", { class: "rv-moves" }, t.moves.length ? t.moves.map(m => el("span", {
          class: "rv-move" + (m.level_up ? " up" : "") + (m.changed ? "" : " still"),
          title: m.level_up ? "cleared the level" : m.changed ? "" : "board did not change" }, moveLabel(m)))
          : el("span", { class: "muted" }, "no move this turn")),
        null),
      ...(opts.full ? fullTurn(content, t) : [think,
        code.length ? el("details", { class: "rv-code" }, el("summary", {}, `code it ran (${code.length})`),
          ...code.map(c => el("pre", {}, c))) : null]),
      marks ? el("div", { class: "rv-rate" }, el("span", { class: "rv-thumbs" }, good, bad), note, status) : null);
  });
  return el("ol", { class: "rv-turns" }, ...items);
}

// a player and its turn list kept in step: the board follows the turn clicked, the list follows the board
// onTurn (optional): called with the turn index whenever the board lands on a turn (the review page steps both paths with it)
export function pathView(content, pathId, marks, onTurn, onMark, opts) {
  const list = turnList(content, pathId, marks, onMark, opts);
  const lis = [...list.children];
  const pl = player(content, ti => { lis.forEach((li, k) => li.classList.toggle("now", k === ti)); if (onTurn && ti >= 0) onTurn(ti); });
  list.addEventListener("click", e => {
    const head = e.target.closest(".rv-turn-head");
    if (head && !e.target.closest("button")) pl.jumpToTurn(+head.dataset.ti);
  });
  return { player: pl, list };
}
