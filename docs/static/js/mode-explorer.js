/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: Draws the Mode explorer page (docs/mode-explorer.html). A slim title line, then one frozen dock (view tabs,
  the mode bar with a small "+ New mode" button, the version switch) pinned under the site tabs while the page scrolls.
  Two views:
  - Queue (default; Son's ask, #arc-3 6-Oct 08:26 ET: "The mode setup should just be a queue"): pick a game from
    docs/static/data/stuck-levels.json, then build one queue of per-turn modes for that game's stuck level. Modes are
    dragged in from the mode bar (or tapped in), dragged within the queue to reorder, and dragged out of it (or
    removed with x) to drop them. Pointer events drive the drag, so the same code works with a mouse and on a
    phone (where queue items drag by their grip and mode chips are tapped in, because the bar scrolls sideways).
    Every item uses its mode's default settings from modes.json; a small settings toggle per item opens per-item
    overrides. "then Stock" is drawn as the implicit tail. Play and the results for that level come from
    spark-runner.js, drawn right under the queue.
  - Prompts: each mode from modes.json (Stock, Probe, Hypothesize, Execute, Re-examine, Challenge, Recover, Level
    start, plus the user's custom modes) in two variants, "son" and "daniel" (Franzen's public notebook), with a
    side-by-side line diff against Stock or against the other variant.
  Modes are shared (Son's ask, #arc-3 6-Oct 08:42 ET): they come from the site's database through mode-library.js,
  the same for everyone signed in; the pencil on each chip (and "+ New mode") opens the editor there, every save is a
  new version, and Play sends each slot's version so the job keeps the exact wording. If the database cannot be
  reached the page falls back to modes.json plus this browser's own custom modes, as before. Queues stay in
  localStorage; custom modes from the old browser store are offered for upload once. Queues and modes can be
  exported and imported as JSON. View state lives in the URL (?view=&mode=&v=&cmp=&game=). The diff is a plain
  longest-common-subsequence over lines.
SRP/DRY check: Pass — prompt text and default settings live in the shared mode store (seeded from modes.json), the tally only in stuck-levels.json;
  mode ids and colours follow RL2's vocabulary (carried per mode as `rl2`/`color` in the JSON); layout classes come
  from rl-shell.css; Play, polling and results drawing stay in spark-runner.js. The store key and shape are the
  ones the earlier scheme builder used, so saved queues and custom modes carry over.
*/

import { loadRunnerInfo, renderPlayRow, renderResults } from './spark-runner.js?v=20261006-m1';
import { lib, initLibrary, loadLibrary, openEditor, applySaved, uploadLocal, versionOf, versionTag, whoWhen, loadRuns } from './mode-library.js?v=20261006-m1';

const $ = (id) => document.getElementById(id);
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const VARIANTS = { son: "Son's version", daniel: "Franzen's version" };
const STORE_KEY = 'arc3-mode-explorer-v1';
// The settings every mode and every queue item carries; defaults per mode come from modes.json.
const FIELDS = [
  { k: 'temperature', label: 'Temperature', type: 'number', min: 0, max: 2, step: 0.05 },
  { k: 'thinking', label: 'Thinking', type: 'bool' },
  { k: 'effort', label: 'Effort', type: 'select', options: ['default', 'low', 'medium', 'high'], needsThinking: true },
  { k: 'thinking_budget', label: 'Thinking budget (tokens)', type: 'number', min: 0, step: 256, empty: 'no cap', needsThinking: true },
  { k: 'tool_calls', label: 'Tool calls this turn', type: 'number', min: 0, step: 1, empty: 'no limit' },
  { k: 'actions', label: 'Action budget', type: 'number', min: 0, step: 1, empty: 'no limit' },
];
const FALLBACK_SETTINGS = { temperature: 0.6, thinking: true, effort: 'default', thinking_budget: null, tool_calls: null, actions: null };

const params = new URLSearchParams(location.search);
const state = {
  view: params.get('view') === 'prompts' ? 'prompts' : 'queue',
  mode: params.get('mode') || 'probe',
  v: params.get('v') === 'daniel' ? 'daniel' : 'son',
  cmp: params.get('cmp') === 'other' ? 'other' : 'stock',
  game: params.get('game') || null,
  open: -1,         // queue item whose settings are showing
};
let DATA = null;    // modes.json
let STUCK = null;   // stuck-levels.json (null until loaded; false if it failed)
let store = loadStore();

// ---------------------------------------------------------------- local store

function loadStore() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
    return { customModes: Array.isArray(s.customModes) ? s.customModes : [], schemes: s.schemes && typeof s.schemes === 'object' ? s.schemes : {}, game: s.game || null, migrated: s.migrated || null,
      uploaded: Array.isArray(s.uploaded) ? s.uploaded : [] };
  } catch { return { customModes: [], schemes: {}, game: null }; }
}
function saveStore() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); }
  catch (e) { flash(`Could not save in this browser (${e.message}). Use Export to keep your work.`); }
}
function flash(text) {
  const p = $('dockhint'); p.textContent = text; p.hidden = false;
  clearTimeout(flash.t); flash.t = setTimeout(() => { p.hidden = true; }, 4000);
}

// ---------------------------------------------------------------- modes

// A custom mode stored as {id, name, color, purpose, base_variant, prompt, settings, settings_why}, drawn like a built-in.
function asMode(c) {
  const v = { purpose: c.purpose || 'Custom mode.', trigger: 'Your choice: custom mode.', budget: budgetText(c.settings), prompt: c.prompt };
  return { id: c.id, name: c.name, color: c.color, base: 'turn', custom: true, base_variant: c.base_variant,
    settings: { ...FALLBACK_SETTINGS, ...(c.settings || {}) }, settings_why: c.settings_why || '', variants: { son: v, daniel: v } };
}
// Shared modes from the site's database when it answers (everyone sees the same ones); otherwise modes.json plus this
// browser's own custom modes, read-only for the built-ins, as before.
function allModes() { return lib.ok ? lib.modes.filter(m => !m.hidden) : DATA.modes.concat(store.customModes.map(asMode)); }
// deleted (hidden) shared modes still resolve, so queues and past results keep their names and colours
function findMode(id) { return (lib.ok ? lib.modes : allModes()).find(m => m.id === id) || null; }
function modeById(id) { const all = allModes(); return all.find(m => m.id === id) || all[1] || all[0]; }
// The harness's own Stock text for a surface: what the diff is drawn against and what the runner diffs against.
function stockText(variant, base) { return DATA.stock[variant][base]; }
function defaults(m) { return { ...FALLBACK_SETTINGS, ...(m.settings || {}) }; }
function budgetText(s) { return s && s.actions != null ? `up to ${s.actions} action${s.actions === 1 ? '' : 's'}` : 'no limit'; }

function settingsSummary(s) {
  const parts = [`temp ${s.temperature}`];
  if (s.thinking) {
    parts.push(s.thinking_budget != null ? `think ≤${s.thinking_budget >= 1024 ? (s.thinking_budget / 1024).toFixed(s.thinking_budget % 1024 ? 1 : 0) + 'k' : s.thinking_budget}` : 'think');
    if (s.effort && s.effort !== 'default') parts.push(`${s.effort} effort`);
  } else parts.push('no thinking');
  if (s.tool_calls != null) parts.push(`${s.tool_calls} tool call${s.tool_calls === 1 ? '' : 's'}`);
  parts.push(s.actions != null ? `≤${s.actions} action${s.actions === 1 ? '' : 's'}` : 'any actions');
  return parts.join(' · ');
}

// ---------------------------------------------------------------- URL

function syncUrl() {
  const q = new URLSearchParams();
  if (state.view === 'prompts') { q.set('view', 'prompts'); q.set('mode', state.mode); if (state.cmp !== 'stock') q.set('cmp', state.cmp); }
  else if (state.game) q.set('game', state.game);
  if (state.v !== 'son') q.set('v', state.v);
  history.replaceState(null, '', '?' + q.toString());
}

// ---------------------------------------------------------------- diff (Prompts view)

// Line diff: longest common subsequence, then walk it into rows of [kind, left, right].
// kind is 'same', 'del' (left only), 'add' (right only); a del followed by an add pairs up as 'chg'.
function diffLines(a, b) {
  const n = a.length, m = b.length;
  const L = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const ops = [];
  let i = 0, j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) { ops.push(['same', a[i++], b[j++]]); }
    else if (j < m && (i === n || L[i][j + 1] >= L[i + 1][j])) ops.push(['add', null, b[j++]]);
    else ops.push(['del', a[i++], null]);
  }
  // pair runs of deletions with the additions right after them, so a replaced line sits beside its replacement
  const rows = [];
  for (let k = 0; k < ops.length;) {
    if (ops[k][0] === 'same') { rows.push(ops[k++]); continue; }
    const dels = [], adds = [];
    while (k < ops.length && ops[k][0] === 'del') dels.push(ops[k++][1]);
    while (k < ops.length && ops[k][0] === 'add') adds.push(ops[k++][2]);
    for (let x = 0; x < Math.max(dels.length, adds.length); x++) {
      const l = dels[x] ?? null, r = adds[x] ?? null;
      rows.push([l !== null && r !== null ? 'chg' : l !== null ? 'del' : 'add', l, r]);
    }
  }
  return rows;
}

// One prompt line as text with {placeholders} and a leading [when ...] condition picked out.
function lineNode(text) {
  const d = h('div', 'mx-text');
  if (text === null) return d;
  if (text === '') { d.innerHTML = '&nbsp;'; return d; }
  let rest = text;
  const cond = /^\[when [^\]]*\]\s*/.exec(rest);
  if (cond) { d.append(h('span', 'mx-cond', cond[0].trim())); d.append(' '); rest = rest.slice(cond[0].length); }
  for (const part of rest.split(/(\{[^{}\s]+\})/)) {
    if (!part) continue;
    d.append(/^\{[^{}\s]+\}$/.test(part) ? h('span', 'mx-ph', part) : document.createTextNode(part));
  }
  return d;
}

// ---------------------------------------------------------------- dock

function renderDock() {
  for (const b of $('tabs').querySelectorAll('.mx-tab')) {
    const on = b.dataset.view === state.view;
    b.classList.toggle('on', on); b.setAttribute('aria-selected', on ? 'true' : 'false');
  }
  const box = $('modes'); box.textContent = '';
  for (const m of allModes()) {
    const picked = state.view === 'prompts' && m.id === state.mode;
    const b = h('button', 'mx-mode' + (picked ? ' on' : '') + (m.custom ? ' custom' : ''), m.name);
    b.style.setProperty('--mc', m.color);
    b.setAttribute('aria-pressed', picked ? 'true' : 'false');
    b.title = (m.variants[state.v].purpose || '') + (state.view === 'queue' ? ' Drag into the queue, or tap to add it at the end.' : '');
    b.onclick = () => { if (drag.suppressClick) return; onChip(m); };
    // a finger on the bar scrolls it sideways, so on touch a chip is tapped in rather than dragged
    if (state.view === 'queue') b.onpointerdown = (e) => { if (e.pointerType === 'mouse') startDrag(e, { kind: 'mode', id: m.id, el: b }); };
    if (!lib.ok) { box.append(b); continue; }
    const wrap = h('span', 'mx-chip' + (picked ? ' on' : ''));
    wrap.style.setProperty('--mc', m.color);
    const ed = h('button', 'mx-chipedit', '✎');
    ed.title = `Edit ${m.name} (${versionTag(m)}, ${whoWhen(m.created_by, m.created_at)}); saving makes a new version`;
    ed.setAttribute('aria-label', `Edit ${m.name}`);
    ed.onclick = () => editMode(m.id);
    wrap.append(b, ed);
    box.append(wrap);
  }
  const add = h('button', 'mx-mode mx-newmode', '+ New mode');
  add.title = lib.ok ? 'Add a mode for everyone: starts from Stock; you set the name, colour, wording and settings.'
    : 'Make your own mode: a name, a colour, a prompt based on Stock, and settings. Saved in this browser.';
  add.onclick = () => (lib.ok ? editMode(null) : openModeDialog(null));
  box.append(add);

  $('compare').hidden = state.view !== 'prompts';
  const vb = $('variants'); vb.textContent = '';
  for (const [k, label] of Object.entries(VARIANTS)) {
    const b = h('button', 'mx-seg' + (k === state.v ? ' on' : ''), label);
    b.setAttribute('aria-pressed', k === state.v ? 'true' : 'false');
    b.title = state.view === 'queue' ? `Play sends ${label.replace("'s version", "'s")} wording of each mode` : '';
    b.onclick = () => { state.v = k; render(); };
    vb.append(b);
  }
  const cb = $('compare'); cb.textContent = '';
  const other = state.v === 'son' ? 'daniel' : 'son';
  for (const [k, label] of [['stock', 'against Stock'], ['other', `against ${VARIANTS[other]}`]]) {
    const b = h('button', 'mx-seg' + (k === state.cmp ? ' on' : ''), label);
    b.setAttribute('aria-pressed', k === state.cmp ? 'true' : 'false');
    b.onclick = () => { state.cmp = k; render(); };
    cb.append(b);
  }
}

function onChip(m) {
  if (state.view === 'prompts') { state.mode = m.id; render(); return; }
  if (!currentGame()) { flash('Pick a game first.'); return; }
  addItem(m.id);
}

// ---------------------------------------------------------------- Prompts view

function renderCard(m) {
  const v = m.variants[state.v];
  const card = $('card'); card.textContent = '';
  const head = h('div', 'mx-head');
  const tag = h('span', 'mx-tag', m.name); tag.style.background = m.color;
  head.append(tag);
  if (m.shared) {
    head.append(h('span', 'chip draft', versionTag(m)), h('span', 'mx-rl2', `${m.version > 1 ? 'edited by' : m.builtin ? 'draft,' : 'added by'} ${whoWhen(m.created_by, m.created_at)}`));
    const edit = h('button', 'mx-tool', 'Edit mode'); edit.onclick = () => editMode(m.id);
    head.append(edit);
  } else if (m.custom) {
    head.append(h('span', 'chip draft', 'Custom'), h('span', 'mx-rl2', `yours, built on ${VARIANTS[m.base_variant] || 'Stock'}, saved in this browser`));
    const edit = h('button', 'mx-tool', 'Edit mode'); edit.onclick = () => openModeDialog(m.id);
    head.append(edit);
  } else {
    head.append(h('span', 'chip draft', 'Draft'));
    if (m.rl2) head.append(h('span', 'mx-rl2', m.rl2 === m.id ? 'same name on RL2' : `on RL2: ${m.rl2}`));
    else head.append(h('span', 'mx-rl2', 'new, no RL2 twin'));
  }
  card.append(head);
  const dl = h('dl', 'mx-facts');
  const rows = [['Purpose', v.purpose], ['When to use', v.trigger], ['Action budget', v.budget],
    ['Built on', m.base_variant ? `${DATA.surfaces[m.base]}, ${VARIANTS[m.base_variant]} only` : DATA.surfaces[m.base]],
    ['Settings', settingsSummary(defaults(m))]];
  if (m.settings_why) rows.push(['Why these settings', m.settings_why]);
  for (const [k, val] of rows) dl.append(h('dt', null, k), h('dd', null, val));
  card.append(dl);
}

function renderDiff(m) {
  const other = state.v === 'son' ? 'daniel' : 'son';
  const leftText = state.cmp === 'other' ? m.variants[other].prompt : stockText(m.base_variant || state.v, m.base);
  const rightText = m.variants[state.v].prompt;
  const leftLabel = state.cmp === 'other' ? `${m.name} · ${VARIANTS[other]}` : `Harness Stock · ${VARIANTS[m.base_variant || state.v]}`;
  const rightLabel = `${m.name} · ${m.custom ? 'your prompt' : VARIANTS[state.v]}`;
  const rows = diffLines(leftText.split('\n'), rightText.split('\n'));
  const counts = { add: 0, del: 0, chg: 0 };
  rows.forEach(r => { if (r[0] in counts) counts[r[0]]++; });
  const changed = counts.add + counts.del + counts.chg;
  $('diffsum').textContent = changed ? `${counts.add + counts.chg} line(s) added or changed, ${counts.del + counts.chg} removed or replaced.` : 'The two prompts are the same text.';

  const grid = $('diff'); grid.textContent = '';
  grid.append(h('div', 'mx-colh', leftLabel), h('div', 'mx-colh', rightLabel));
  for (const [kind, l, r] of rows) {
    const L = lineNode(l), R = lineNode(r);
    L.classList.add('mx-l'); R.classList.add('mx-r');
    if (kind === 'del' || kind === 'chg') L.classList.add('mx-del');
    if (kind === 'add' || kind === 'chg') R.classList.add('mx-add');
    if (kind === 'add') L.classList.add('mx-gap');
    if (kind === 'del') R.classList.add('mx-gap');
    grid.append(L, R);
  }
  $('full').textContent = rightText;
  $('fullh').textContent = `Full prompt · ${rightLabel}`;
}

// ---------------------------------------------------------------- Queue view: game picker

// Games with a stuck level, hardest first (lowest share of levels safely cleared, then lowest median).
function stuckGames() {
  if (!STUCK) return [];
  return STUCK.games.filter(g => g.stuck_level)
    .sort((a, b) => (a.safe_through / a.levels - b.safe_through / b.levels) || (a.median_levels / a.levels - b.median_levels / b.levels) || a.game.localeCompare(b.game));
}
function currentGame() { return STUCK && state.game ? stuckGames().find(g => g.game === state.game) || null : null; }

function renderPicker() {
  const sel = $('gamepick'); sel.textContent = '';
  if (STUCK === null) { sel.append(h('option', null, 'loading…')); sel.disabled = true; return; }
  if (STUCK === false) { sel.append(h('option', null, 'could not load the stuck levels')); sel.disabled = true; return; }
  sel.disabled = false;
  for (const g of stuckGames()) {
    const n = (store.schemes[g.game]?.slots || []).length;
    const o = h('option', null, `${g.nickname} · stuck at level ${g.stuck_level} of ${g.levels}${n ? ` · ${n} in queue` : ''}`);
    o.value = g.game;
    sel.append(o);
  }
  sel.value = state.game || '';
  sel.onchange = () => { state.game = sel.value; state.open = -1; store.game = sel.value; saveStore(); render(); };
  const g = currentGame();
  const p = g && g.per_level[g.stuck_level - 1];
  $('gamefact').textContent = g ? `Every run starts from a recorded stock run's position at the start of level ${g.stuck_level}. ` +
    (p ? `Stock alone clears that level in ${p.cleared} of ${p.n} full runs.` : '') : '';
}

// ---------------------------------------------------------------- Queue view: the queue

function queueOf(g) {
  // start_level stays in the stored record for exports and older copies of the page; Play always uses the stuck level
  if (!store.schemes[g.game]) store.schemes[g.game] = { start_level: g.stuck_level, slots: [], updated: null };
  const q = store.schemes[g.game];
  q.start_level = g.stuck_level;
  return q;
}
function touch(q) { q.updated = new Date().toISOString(); saveStore(); }
function itemSettings(item) { const m = findMode(item.mode); return { ...(m ? defaults(m) : FALLBACK_SETTINGS), ...item.overrides }; }

function addItem(modeId, at) {
  const g = currentGame(); if (!g) return;
  const q = queueOf(g);
  q.slots.splice(at == null ? q.slots.length : at, 0, { mode: modeId, overrides: {} });
  state.open = -1; touch(q); renderQueueArea();
}
function moveItem(from, to) {
  const q = queueOf(currentGame());
  const dest = to > from ? to - 1 : to;
  if (dest === from) return;
  const [it] = q.slots.splice(from, 1);
  q.slots.splice(dest, 0, it);
  if (state.open === from) state.open = dest;
  else if (state.open >= 0) state.open = -1;
  touch(q); renderQueueArea();
}
function removeItem(i) {
  const q = queueOf(currentGame());
  q.slots.splice(i, 1);
  state.open = -1; touch(q); renderQueueArea();
}

// Redraws only the queue, its settings panel and the Play row; the results list keeps its own refresh cycle.
function renderQueueArea() {
  const g = currentGame();
  const list = $('queue'); list.textContent = '';
  const set = $('slotset'); set.textContent = ''; set.hidden = true;
  if (!g) { $('playrow').textContent = ''; return; }
  const q = queueOf(g);
  q.slots.forEach((item, i) => list.append(itemNode(item, i)));
  if (!q.slots.length) list.append(h('li', 'mx-qempty', 'Drag modes here from the bar above, or tap a mode to add it. An empty queue plays Stock only.'));
  const tail = h('li', 'mx-qitem mx-qtail');
  const stock = findMode('stock');
  const ttag = h('span', 'mx-tag', q.slots.length ? 'then Stock' : 'Stock'); ttag.style.background = stock ? stock.color : '#8792a2';
  tail.title = 'After the queue runs out, Stock plays every later turn until the level is cleared or a cap is hit.';
  tail.append(ttag);
  list.append(tail);
  if (state.open >= 0 && q.slots[state.open]) { set.hidden = false; set.append(itemEditor(q.slots[state.open], state.open, q)); }
  renderPlayRow($('playrow'), playCtx(g, q));
  const opt = $('gamepick').selectedOptions[0];
  if (opt) opt.textContent = `${g.nickname} · stuck at level ${g.stuck_level} of ${g.levels}${q.slots.length ? ` · ${q.slots.length} in queue` : ''}`;
}

function itemNode(item, i) {
  const m = findMode(item.mode);
  const edited = Object.keys(item.overrides).length;
  const li = h('li', 'mx-qitem' + (i === state.open ? ' open' : ''));
  li.dataset.idx = i;
  li.style.setProperty('--mc', m ? m.color : '#6b7280');
  const grip = h('span', 'mx-grip', '⠿'); grip.title = 'Drag to reorder, or drag out of the queue to remove';
  grip.setAttribute('aria-hidden', 'true');
  li.append(grip, h('span', 'mx-qn', String(i + 1)), h('span', 'mx-qname', m ? m.name + (m.hidden ? ' (deleted)' : '') : `${item.mode} (missing)`));
  li.title = settingsSummary(itemSettings(item)) + (edited ? ' (edited)' : ' (mode defaults)');
  const gear = h('button', 'mx-qbtn' + (edited ? ' edited' : ''), '⚙');
  gear.title = edited ? 'Settings (changed from the mode defaults)' : 'Settings';
  gear.setAttribute('aria-label', `Settings for turn ${i + 1}`);
  gear.setAttribute('aria-expanded', i === state.open ? 'true' : 'false');
  gear.onclick = (e) => { e.stopPropagation(); state.open = state.open === i ? -1 : i; renderQueueArea(); };
  const x = h('button', 'mx-qbtn', '✕');
  x.title = 'Remove from the queue'; x.setAttribute('aria-label', `Remove turn ${i + 1}`);
  x.onclick = (e) => { e.stopPropagation(); removeItem(i); };
  li.append(gear, x);
  // mouse: the whole item drags; touch: only the grip, so the page still scrolls under a finger
  li.onpointerdown = (e) => {
    if (e.target.closest('button')) return;
    if (e.pointerType !== 'mouse' && e.target !== grip) return;
    startDrag(e, { kind: 'item', idx: i, el: li });
  };
  return li;
}

function itemEditor(item, i, q) {
  const m = findMode(item.mode);
  const box = h('div', 'mx-editor');
  const head = h('div', 'mx-edhead');
  head.append(h('b', null, `Turn ${i + 1}: ${m ? m.name : item.mode}`), h('span', 'mx-rl2', 'starts from the mode defaults'));
  const close = h('button', 'mx-qbtn', '✕'); close.title = 'Close settings'; close.setAttribute('aria-label', 'Close settings');
  close.onclick = () => { state.open = -1; renderQueueArea(); };
  head.append(close);
  box.append(head);
  const reset = h('button', 'mx-tool', 'Reset to mode defaults');
  box.append(settingsGrid(() => itemSettings(item), (k, v) => {
    const base = m ? defaults(m) : FALLBACK_SETTINGS;
    if (base[k] === v) delete item.overrides[k]; else item.overrides[k] = v;
    touch(q);
    const edited = Object.keys(item.overrides).length;
    const gear = $('queue').querySelector(`.mx-qitem[data-idx="${i}"] .mx-qbtn`);
    if (gear) gear.classList.toggle('edited', !!edited);
    reset.disabled = !edited;
  }));
  if (m && m.settings_why) box.append(h('p', 'mx-why', `Mode defaults: ${m.settings_why}`));
  const btns = h('div', 'mx-edbtns');
  reset.disabled = !Object.keys(item.overrides).length;
  reset.onclick = () => { item.overrides = {}; touch(q); renderQueueArea(); };
  const earlier = h('button', 'mx-tool', '← Earlier'); earlier.disabled = i === 0; earlier.onclick = () => moveItem(i, i - 1);
  const later = h('button', 'mx-tool', 'Later →'); later.disabled = i === q.slots.length - 1; later.onclick = () => moveItem(i, i + 2);
  btns.append(reset, earlier, later);
  box.append(btns);
  return box;
}

// ---------------------------------------------------------------- drag (pointer events: mouse and touch)

// One drag at a time. A mode chip dropped on the queue inserts a new item there; a queue item dropped on the queue
// moves, dropped anywhere else it is removed. A press that never moves past the threshold stays a click.
const drag = { on: null, suppressClick: false };

function startDrag(e, src) {
  if (e.button > 0) return;
  const d = { src, x0: e.clientX, y0: e.clientY, ghost: null, at: -1, pid: e.pointerId };
  drag.on = d;
  const move = (ev) => {
    if (ev.pointerId !== d.pid) return;
    if (!d.ghost) {
      if (Math.hypot(ev.clientX - d.x0, ev.clientY - d.y0) < 6) return;
      d.ghost = src.el.cloneNode(true);
      d.ghost.classList.add('mx-ghost'); d.ghost.removeAttribute('data-idx');
      document.body.append(d.ghost);
      src.el.classList.add('dragging');
      document.body.classList.add('mx-dragging');
    }
    ev.preventDefault();
    d.ghost.style.transform = `translate(${ev.clientX + 8}px, ${ev.clientY + 8}px)`;
    const over = overQueue(ev.clientX, ev.clientY);
    d.at = over ? dropIndex(ev.clientX, ev.clientY) : -1;
    markDrop(d.at, src.kind === 'item' && !over);
  };
  const end = (ev) => {
    if (ev.pointerId !== d.pid) return;
    removeEventListener('pointermove', move); removeEventListener('pointerup', end); removeEventListener('pointercancel', end);
    drag.on = null;
    if (!d.ghost) return;                       // a plain click
    d.ghost.remove(); src.el.classList.remove('dragging'); document.body.classList.remove('mx-dragging'); markDrop(-1, false);
    drag.suppressClick = true; setTimeout(() => { drag.suppressClick = false; }, 0);
    if (ev.type === 'pointercancel') return;
    if (src.kind === 'mode') { if (d.at >= 0) addItem(src.id, d.at); }
    else if (d.at >= 0) moveItem(src.idx, d.at);
    else removeItem(src.idx);
  };
  addEventListener('pointermove', move, { passive: false });
  addEventListener('pointerup', end); addEventListener('pointercancel', end);
}

function overQueue(x, y) {
  const r = $('queue').getBoundingClientRect();
  return x >= r.left - 12 && x <= r.right + 12 && y >= r.top - 12 && y <= r.bottom + 12;
}
// Items flow left to right and wrap: the drop goes before the first item the pointer is above or left of the middle of.
function dropIndex(x, y) {
  const items = [...$('queue').querySelectorAll('.mx-qitem:not(.mx-qtail)')];
  for (let k = 0; k < items.length; k++) {
    const r = items[k].getBoundingClientRect();
    if (y < r.top || (y <= r.bottom && x < r.left + r.width / 2)) return k;
  }
  return items.length;
}
function markDrop(at, removing) {
  const list = $('queue');
  list.classList.toggle('over', at >= 0);
  list.querySelectorAll('.mx-qitem').forEach((el, j) => el.classList.toggle('drop-before', j === at));
  const src = drag.on && drag.on.src;
  if (src && src.kind === 'item') src.el.classList.toggle('removing', removing);
}

// ---------------------------------------------------------------- settings inputs (queue items and the mode dialog)

function fieldInput(f, value, onChange, disabled) {
  const wrap = h('label', 'mx-field');
  wrap.append(h('span', 'mx-flabel', f.label));
  let input;
  if (f.type === 'bool') {
    input = h('select');
    for (const [v, t] of [['true', 'on'], ['false', 'off']]) { const o = h('option', null, t); o.value = v; input.append(o); }
    input.value = String(!!value);
    input.onchange = () => onChange(input.value === 'true');
  } else if (f.type === 'select') {
    input = h('select');
    for (const v of f.options) { const o = h('option', null, v); o.value = v; input.append(o); }
    input.value = value || 'default';
    input.onchange = () => onChange(input.value);
  } else {
    input = h('input'); input.type = 'number'; input.inputMode = 'decimal';
    for (const a of ['min', 'max', 'step']) if (f[a] != null) input[a] = f[a];
    input.value = value == null ? '' : value;
    if (f.empty) input.placeholder = f.empty;
    input.onchange = () => {
      const raw = input.value.trim();
      if (raw === '' && f.empty) return onChange(null);
      const n = Number(raw);
      if (raw === '' || !Number.isFinite(n) || (f.min != null && n < f.min) || (f.max != null && n > f.max)) { input.value = value == null ? '' : value; return; }
      onChange(f.step >= 1 ? Math.round(n) : n);
    };
  }
  input.disabled = !!disabled;
  wrap.append(input);
  return wrap;
}

function settingsGrid(get, set) {
  const grid = h('div', 'mx-fields');
  const draw = () => {
    grid.textContent = '';
    const s = get();
    for (const f of FIELDS) grid.append(fieldInput(f, s[f.k], (v) => { set(f.k, v); draw(); }, f.needsThinking && !s.thinking));
  };
  draw();
  return grid;
}

// ---------------------------------------------------------------- custom modes

function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 24) || 'mode'; }

function openModeDialog(id) {
  const existing = id ? store.customModes.find(c => c.id === id) : null;
  const draft = existing ? JSON.parse(JSON.stringify(existing)) : {
    id: null, name: '', color: '#0e7490', purpose: '', base_variant: state.v,
    prompt: DATA.stock[state.v].turn, settings: { ...defaults(DATA.modes[0]) }, settings_why: '',
  };
  draft.settings = { ...FALLBACK_SETTINGS, ...draft.settings };
  let promptTouched = !!existing;
  const dlg = $('modedlg'); dlg.textContent = '';
  const form = h('form', 'mx-form'); form.method = 'dialog';
  form.append(h('h2', null, existing ? `Edit ${existing.name}` : 'New mode'));
  form.append(h('p', 'mx-sum', 'Saved in this browser only. The prompt starts as Stock; add your focus lines where you want them. It shows up in the mode bar, ready to drag into a queue.'));

  const row = h('div', 'mx-formrow');
  const name = h('input'); name.required = true; name.maxLength = 32; name.value = draft.name; name.placeholder = 'e.g. Map the board';
  const color = h('input'); color.type = 'color'; color.value = draft.color;
  const variant = h('select');
  for (const [k, label] of Object.entries(VARIANTS)) { const o = h('option', null, `Stock, ${label}`); o.value = k; variant.append(o); }
  variant.value = draft.base_variant;
  const lab = (t, el, cls) => { const l = h('label', 'mx-field' + (cls ? ' ' + cls : '')); l.append(h('span', 'mx-flabel', t), el); return l; };
  row.append(lab('Name', name, 'grow'), lab('Colour', color), lab('Built on', variant));
  form.append(row);
  const purpose = h('input'); purpose.value = draft.purpose; purpose.placeholder = 'What this turn is for, in one line';
  form.append(lab('Purpose', purpose, 'wide'));
  const prompt = h('textarea', 'mx-prompt'); prompt.value = draft.prompt; prompt.rows = 14; prompt.required = true;
  prompt.oninput = () => { promptTouched = true; };
  variant.onchange = () => {
    if (!promptTouched || confirm('Replace the prompt text with the Stock prompt of this version?')) { prompt.value = DATA.stock[variant.value].turn; promptTouched = false; }
  };
  form.append(lab('Prompt (sent as the turn message)', prompt, 'wide'));
  form.append(h('h3', 'mx-subh', 'Default settings'));
  form.append(settingsGrid(() => draft.settings, (k, v) => { draft.settings[k] = v; }));
  const why = h('textarea'); why.rows = 2; why.value = draft.settings_why; why.placeholder = 'Why these settings (optional)';
  form.append(lab('Why these settings', why, 'wide'));

  const btns = h('div', 'mx-formbtns');
  const save = h('button', 'mx-play', existing ? 'Save changes' : 'Create mode'); save.type = 'submit';
  const cancel = h('button', 'mx-tool', 'Cancel'); cancel.type = 'button'; cancel.onclick = () => dlg.close();
  btns.append(save, cancel);
  if (existing) {
    const del = h('button', 'mx-tool mx-danger', 'Delete mode'); del.type = 'button';
    del.onclick = () => {
      const used = Object.values(store.schemes).filter(s => s.slots.some(x => x.mode === existing.id)).length;
      if (!confirm(`Delete ${existing.name}?` + (used ? ` It is used in ${used} queue(s); it will be taken out of them.` : ''))) return;
      store.customModes = store.customModes.filter(c => c.id !== existing.id);
      for (const s of Object.values(store.schemes)) s.slots = s.slots.filter(x => x.mode !== existing.id);
      saveStore(); dlg.close();
      if (state.mode === existing.id) state.mode = 'probe';
      state.open = -1; render();
    };
    btns.append(del);
  }
  form.append(btns);
  form.onsubmit = (e) => {
    e.preventDefault();
    const nm = name.value.trim();
    if (!nm) { name.focus(); return; }
    if (!prompt.value.trim()) { prompt.focus(); return; }
    if (allModes().some(m => m.name.toLowerCase() === nm.toLowerCase() && m.id !== draft.id)) { name.setCustomValidity(`A mode called ${nm} already exists.`); name.reportValidity(); name.oninput = () => name.setCustomValidity(''); return; }
    const rec = { id: draft.id || `custom-${slug(nm)}-${Date.now().toString(36)}`, name: nm, color: color.value, purpose: purpose.value.trim(),
      base_variant: variant.value, prompt: prompt.value, settings: draft.settings, settings_why: why.value.trim() };
    const k = store.customModes.findIndex(c => c.id === rec.id);
    if (k >= 0) store.customModes[k] = rec; else store.customModes.push(rec);
    saveStore(); dlg.close();
    if (state.view === 'prompts') state.mode = rec.id;
    render();
  };
  dlg.append(form);
  dlg.showModal();
  name.focus();
}

// ---------------------------------------------------------------- export / import

function exportJson() {
  const doc = { kind: 'arc3-mode-explorer', version: 1, exported: new Date().toISOString(), customModes: store.customModes, schemes: store.schemes };
  const url = URL.createObjectURL(new Blob([JSON.stringify(doc, null, 1)], { type: 'application/json' }));
  const a = h('a'); a.href = url; a.download = `arc3-modes-and-queues-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function validCustom(c) { return c && typeof c.id === 'string' && typeof c.name === 'string' && c.name.trim() && typeof c.prompt === 'string'; }
function validScheme(s) { return s && Array.isArray(s.slots) && s.slots.every(x => x && typeof x.mode === 'string'); }

async function importJson(file) {
  let doc;
  try { doc = JSON.parse(await file.text()); } catch { flash('That file is not JSON.'); return; }
  if (!doc || doc.kind !== 'arc3-mode-explorer') { flash('That file is not a Mode explorer export.'); return; }
  const modes = (Array.isArray(doc.customModes) ? doc.customModes : []).filter(validCustom);
  const schemes = Object.entries(doc.schemes && typeof doc.schemes === 'object' ? doc.schemes : {}).filter(([k, s]) => /^\w{4}$/.test(k) && validScheme(s));
  for (const c of modes) {
    const rec = { id: c.id, name: c.name.trim().slice(0, 32), color: /^#[0-9a-f]{6}$/i.test(c.color || '') ? c.color : '#0e7490',
      purpose: String(c.purpose || ''), base_variant: c.base_variant === 'daniel' ? 'daniel' : 'son', prompt: c.prompt,
      settings: { ...FALLBACK_SETTINGS, ...(c.settings && typeof c.settings === 'object' ? c.settings : {}) }, settings_why: String(c.settings_why || '') };
    const k = store.customModes.findIndex(x => x.id === rec.id);
    if (k >= 0) store.customModes[k] = rec; else store.customModes.push(rec);
  }
  for (const [k, s] of schemes) {
    store.schemes[k] = { start_level: Number.isInteger(s.start_level) ? s.start_level : null, updated: s.updated || null,
      slots: s.slots.map(x => ({ mode: x.mode, overrides: x.overrides && typeof x.overrides === 'object' ? x.overrides : {} })) };
  }
  saveStore();
  if (lib.ok && modes.length) {
    const up = await uploadLocal(store.customModes.filter(c => modes.some(x => x.id === c.id)));
    remapQueues(up.ids);
    render();
    flash(`Imported ${schemes.length} queue(s); ${Object.keys(up.ids).length} mode(s) added to the shared modes.` + (up.failed.length ? ` Not added: ${up.failed.join(', ')}.` : ''));
    return;
  }
  render();
  flash(`Imported ${modes.length} custom mode(s) and ${schemes.length} queue(s).`);
}

// ---------------------------------------------------------------- main

function playCtx(g, q) { return { game: g, scheme: q, variant: state.v, DATA, findMode, slotSettings: itemSettings, defaults, stockText, versionOf, loadRuns, whoWhen }; }

// ---------------------------------------------------------------- shared modes

function editMode(id) {
  openEditor(id, { variant: state.v, stockMode: findMode('stock'), onSaved: (row) => {
    const m = applySaved(row);
    flash(m.hidden ? `${m.name} deleted for everyone; its history is kept.` : `${m.name} saved as version ${m.version}, shared with everyone.`);
    if (state.view === 'prompts' && !m.hidden) state.mode = m.id;
    render();
  } });
}

function remapQueues(ids) {
  for (const q of Object.values(store.schemes)) for (const x of q.slots) if (ids[x.mode]) x.mode = ids[x.mode];
  saveStore();
}

// Custom modes made before modes were shared live only in this browser. Offer once to upload them; keep the copy.
async function migrateLocal() {
  const uploaded = store.uploaded || (store.uploaded = []);
  const todo = store.customModes.filter(c => !uploaded.includes(c.id));
  if (!lib.ok || store.migrated || !todo.length) return;
  const names = todo.map(c => c.name).join(', ');
  const yes = confirm(`This browser has ${todo.length === 1 ? 'a custom mode' : todo.length + ' custom modes'} saved only here (${names}). ` +
    'Modes are now shared with everyone signed in. Upload them so everyone sees them? Your queues will keep using them.');
  store.migrated = yes ? 'uploaded' : 'declined';
  saveStore();
  if (!yes) return;
  const up = await uploadLocal(todo);
  uploaded.push(...Object.keys(up.ids));          // a retry after a partial failure skips what already went up
  remapQueues(up.ids);
  if (up.failed.length) { store.migrated = null; saveStore(); }
  flash(`Uploaded ${Object.keys(up.ids).length} mode(s) to the shared modes.` + (up.failed.length ? ` Not uploaded: ${up.failed.join(', ')} (asked again next time).` : ''));
  render();
}

function render() {
  syncUrl();
  renderDock();
  $('view-prompts').hidden = state.view !== 'prompts';
  $('view-queue').hidden = state.view !== 'queue';
  if (state.view === 'prompts') {
    const m = modeById(state.mode);
    state.mode = m.id;
    renderCard(m);
    renderDiff(m);
    return;
  }
  renderPicker();
  renderQueueArea();
  const g = currentGame();
  if (g) renderResults($('results'), playCtx(g, queueOf(g)));
  else $('results').textContent = '';
}

// The dock pins just under the site tabs, whose height changes when they wrap or scroll sideways on a phone.
function trackNav() {
  const nav = document.querySelector('.sitetabs');
  const set = () => document.documentElement.style.setProperty('--navh', `${nav ? nav.offsetHeight : 0}px`);
  set();
  if (nav && 'ResizeObserver' in window) new ResizeObserver(set).observe(nav);
  else addEventListener('resize', set);
}

async function main() {
  trackNav();
  try {
    const r = await fetch('./static/data/modes.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    DATA = await r.json();
  } catch (e) {
    $('updated').textContent = `Could not load the mode prompts (${e.message}).`;
    $('card').textContent = `Could not load the mode prompts (${e.message}).`;
    return;
  }
  initLibrary({ h, settingsGrid, diffLines, settingsSummary, FALLBACK_SETTINGS, stockText });
  await loadLibrary();
  $('updated').textContent = lib.ok ? 'Shared modes · anyone signed in can edit; every save is a new version'
    : `Draft prompts · ${DATA.meta.date} · shared modes could not load (${lib.error}), showing the built-in drafts`;
  $('storenote').textContent = lib.ok ? 'Modes are shared and versioned for everyone signed in. Queues are saved in this browser only.'
    : 'Custom modes and queues are saved in this browser only.';
  $('finding').textContent = DATA.meta.finding;
  $('notation').textContent = `${DATA.meta.notation} ${DATA.meta.insert_rule} ${DATA.meta.settings_note || ''}`;
  $('copy').onclick = async () => {
    try { await navigator.clipboard.writeText($('full').textContent); $('copy').textContent = 'Copied'; }
    catch { $('copy').textContent = 'Copy failed'; }
    setTimeout(() => { $('copy').textContent = 'Copy prompt'; }, 1500);
  };
  for (const b of $('tabs').querySelectorAll('.mx-tab')) b.onclick = () => { state.view = b.dataset.view; state.open = -1; render(); };
  $('export').onclick = exportJson;
  $('import').onclick = () => $('importfile').click();
  $('importfile').onchange = (e) => { const f = e.target.files[0]; if (f) importJson(f); e.target.value = ''; };
  render();
  try {
    const r = await fetch('./static/data/stuck-levels.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    STUCK = await r.json();
  } catch { STUCK = false; }
  // open the game from the link, else the last one used here, else the hardest
  if (!currentGame()) state.game = store.game;
  if (!currentGame()) state.game = stuckGames()[0]?.game || null;
  render();
  migrateLocal();
  await loadRunnerInfo();
  if (state.view === 'queue' && currentGame()) renderQueueArea();
}

main();
