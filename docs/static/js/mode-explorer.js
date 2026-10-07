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
  exported and imported as JSON. View state lives in the URL (?view=&mode=&v=&cmp=&game=&level=). The diff is a plain
  longest-common-subsequence over lines.
  Game sidebar and level buttons (Son's ask, #arc-3 6-Oct 10:47 ET: "show games on the left side with Thumbnails so
  that it is easy to switch games and levels ... show all the levels as 1, 2, 3, 4, 5, 6 buttons, with how much fill
  depending on how often this level has been conquered"): every public game the runner plays (the eight held-out
  games stay out, as on the runner) with its first-frame picture from static/img/games, nickname and stuck level,
  hardest first; on a phone the list becomes a strip that scrolls sideways. Above the queue, one button per level:
  the fill is the share of stock runs in the tally that cleared it, the thin bar under it the share of Spark samples
  that played it and cleared it (spark-runner.js sparkTally), a dot marks an exact saved start and a ring a fresh or
  rebuilt start; levels Play cannot start from are greyed with the reason. The chosen level is the queue's starting
  level (kept per game with the queue) and the results follow it.
  Board picture (Son, #arc-3 6-Oct 10:47 ET: "at least show the screen at that time as well"): next to the queue and
  Play, the board at the start Play would use for the chosen game, level and wording (start-board.js); it is redrawn
  whenever the game, level or wording changes, and says when it is only the level's opening frame.
  Context (Son, #arc-3 6-Oct 11:50 ET: "Add a 'non-context' mode too"): the Carry context / No context toggle next to
  Play (drawn by spark-runner.js) sets state.context, kept in this browser and in the link (?ctx=none). In No-context
  mode every level with a verified replay is playable, the level buttons' Spark bar counts only No-context jobs, and
  the board picture shows the replayed level start.
  How-to and tips (the Boss, #arc-3 6-Oct 12:52 ET: "Are there tooltips or instructions on the page?"): a short "How to
  use this page" panel under the title, open on a first visit and closed after that unless it was last opened by hand
  (its own localStorage key), and a hover tip plus an accessible label on every control.
  Help tour (Son, #arc-3 6-Oct 13:10 ET: "Have like a 'Help' icon, and do a demo"): the "?" in the dock starts
  mode-tour.js, which walks every control with a spotlight and runs a demo through tourHost below. While it runs,
  saveStore and syncUrl do nothing, so the demo's game, level, queue and settings live in memory only; when it ends
  the person's own store and view are put back from a copy taken at the start, and Play is locked (playCtx.demo).
  Prompt profiles (6-Oct, the Boss approved Astra's notes at 17:07 ET; replaces the lean toggle of 16:39): the runner
  sends the "dedup" prompts for every mode, Stock included: every standing instruction once, in the system prompt;
  the turn message only this turn's facts, then the mode's instructions. A mode is only those instructions
  (instructionsOf; modes saved before 6-Oct stored the whole turn message, and their instructions are the lines they
  added to Stock, as the runner reads them). The Prompts view shows what the model receives in three labelled parts:
  1 System prompt (read-only), 2 This turn (filled in by the harness, read-only; a real example from
  static/data/prompt-profiles.json, rendered by the runner's harness), 3 Mode instructions (the mode's own text,
  edited with the pencil), and "Preview request" shows the exact assembled messages Play would send for the game,
  level, wording and context chosen in the Queue view (spark-runner.js previewRequest). Next to Play a select keeps
  "Original prompts" available only to compare with old runs (state.profile, kept in this browser).
  The mode editor itself (the same three parts, the editable instructions, preview) is in mode-library.js.
SRP/DRY check: Pass — prompt text and default settings live in the shared mode store (seeded from modes.json), the tally only in stuck-levels.json;
  mode ids and colours follow RL2's vocabulary (carried per mode as `rl2`/`color` in the JSON); layout classes come
  from rl-shell.css; Play, polling and results drawing stay in spark-runner.js. The store key and shape are the
  ones the earlier scheme builder used, so saved queues and custom modes carry over.
*/

import { loadRunnerInfo, renderPlayRow, renderResults, levelStart, playRequest, previewRequest, renderPreview, PROFILE_NAME } from './spark-runner.js?v=20261007-watch';
import { renderStartBoard } from './start-board.js?v=20261006-ht1';
import { startTour, flyChip, pause } from './mode-tour.js?v=20261006-dedup1';
import { lib, initLibrary, loadLibrary, openEditor, applySaved, uploadLocal, versionOf, versionTag, whoWhen, loadRuns } from './mode-library.js?v=20261006-dedup1';

const $ = (id) => document.getElementById(id);
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const VARIANTS = { son: "Son's version", daniel: "Franzen's version" };
const STORE_KEY = 'arc3-mode-explorer-v1';
// The settings every mode and every queue item carries; defaults per mode come from modes.json.
const FIELDS = [
  { k: 'temperature', label: 'Temperature', type: 'number', min: 0, max: 2, step: 0.05, tip: 'How much the model varies its answers: lower is steadier, higher tries more different things.' },
  { k: 'thinking', label: 'Thinking', type: 'bool', tip: 'Whether the model thinks privately before it answers this turn.' },
  { k: 'effort', label: 'Effort', type: 'select', options: ['default', 'low', 'medium', 'high'], needsThinking: true, tip: 'How hard the model thinks (only with thinking on).' },
  { k: 'thinking_budget', label: 'Thinking budget (tokens)', type: 'number', min: 0, step: 256, empty: 'no cap', needsThinking: true, tip: 'The most thinking the model may do this turn; empty means no cap (only with thinking on).' },
  { k: 'tool_calls', label: 'Tool calls this turn', type: 'number', min: 0, step: 1, empty: 'no limit', tip: 'The most tool calls the model may make this turn; empty means no limit.' },
  { k: 'actions', label: 'Action budget', type: 'number', min: 0, step: 1, empty: 'no limit', tip: 'The most game moves the model may make this turn; empty means no limit.' },
];
const FALLBACK_SETTINGS = { temperature: 0.6, thinking: true, effort: 'default', thinking_budget: null, tool_calls: null, actions: null };
// Kept out of prompt tuning; the runner refuses them (tools/spark_runner/server.py HELD_OUT), so the sidebar leaves them out.
const HELD_OUT = new Set(['vc33', 'ar25', 'sb26', 're86', 'su15', 'tr87', 'tu93', 'as66']);
// First-frame picture per game, the version the runner plays (its environment_files), as on the Games page.
const THUMBS = { bp35: '0a0ad940', cd82: 'fb555c5d', cn04: '2fe56bfb', dc22: 'fdcac232', ft09: '0d8bbf25', g50t: '5849a774',
  ka59: '38d34dbb', lf52: '271a04aa', lp85: '305b61c3', ls20: '9607627b', m0r0: '492f87ba', r11l: '495a7899', s5i5: '18d95033',
  sc25: '635fd71a', sk48: 'd8078629', sp80: '589a99af', tn36: 'ef4dde99', wa30: 'ee6fef47' };

const params = new URLSearchParams(location.search);
const state = {
  view: params.get('view') === 'prompts' ? 'prompts' : 'queue',
  mode: params.get('mode') || 'probe',
  v: params.get('v') === 'daniel' ? 'daniel' : 'son',
  cmp: params.get('cmp') === 'other' ? 'other' : 'stock',
  game: params.get('game') || null,
  level: Number(params.get('level')) || null,   // from the link only; applied to that game's queue once loaded
  context: null,    // 'carried' | 'none': the link's ?ctx= wins, else this browser's last choice (set below)
  open: -1,         // queue item whose settings are showing
};
const SPARK = {};   // `${game}:${context}` -> { tally: {level: {played, cleared}}, harvest }, from the jobs the results list loads
let DATA = null;    // modes.json
let PROMPTS = null; // prompt-profiles.json: system prompts, tool schema and example turn messages per profile
let STUCK = null;   // stuck-levels.json (null until loaded; false if it failed)
let store = loadStore();
// The guided tour's copy of the person's own store and view (null when no tour runs). While set, nothing is saved.
let TOUR = null;
state.context = params.get('ctx') === 'none' ? 'none' : params.get('ctx') === 'carried' ? 'carried' : store.context;
state.profile = store.profile;

// ---------------------------------------------------------------- local store

function loadStore() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
    return { customModes: Array.isArray(s.customModes) ? s.customModes : [], schemes: s.schemes && typeof s.schemes === 'object' ? s.schemes : {}, game: s.game || null, migrated: s.migrated || null,
      uploaded: Array.isArray(s.uploaded) ? s.uploaded : [], context: s.context === 'none' ? 'none' : 'carried',
      profile: s.profile === 'original' ? 'original' : 'dedup' };
  } catch { return { customModes: [], schemes: {}, game: null, context: 'carried', profile: 'dedup' }; }
}
function saveStore() {
  if (TOUR) return;   // the tour's demo is never saved; the person's own store comes back when it ends
  try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); }
  catch (e) { flash(`Could not save in this browser (${e.message}). Use Export to keep your work.`); }
}
function flash(text) {
  const p = $('dockhint'); p.textContent = text; p.hidden = false;
  clearTimeout(flash.t); flash.t = setTimeout(() => { p.hidden = true; }, 4000);
}

// ---------------------------------------------------------------- modes

// A custom mode stored as {id, name, color, purpose, instructions (or, before 6-Oct, base_variant + prompt), settings,
// settings_why}, drawn like a built-in.
function asMode(c) {
  const v = { purpose: c.purpose || 'Custom mode.', trigger: 'Your choice: custom mode.', budget: budgetText(c.settings), prompt: c.prompt };
  return { id: c.id, name: c.name, color: c.color, base: 'turn', custom: true, base_variant: c.base_variant,
    instructions: typeof c.instructions === 'string' ? c.instructions : undefined,
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
// A mode's turn-only instructions for a wording. Modes saved before 6-Oct stored the whole turn message (the original
// profile's template): their instructions are the lines they added to that wording's Stock text, which is also how
// the runner reads such a slot (tools/spark_runner/sample.py slot_instructions).
function instructionsOf(m, variant) {
  if (!m) return '';
  if (typeof m.instructions === 'string') return m.instructions;
  const v = (m.variants || {})[m.base_variant || variant] || {};
  if (!v.prompt) return '';
  return diffLines(stockText(m.base_variant || variant, m.base || 'turn').split('\n'), v.prompt.split('\n'))
    .filter(([kind]) => kind === 'add' || kind === 'chg').map(([, , r]) => r).join('\n');
}
// What a preview needs from the Queue view: its game and level (else the first game's stuck level), wording, context.
function previewTarget() {
  const g = currentGame() || sidebarGames()[0];
  if (!g) return null;
  const q = queueOf(g);
  return { game: g.game, nickname: g.nickname, level: q.start_level || g.stuck_level || 1, variant: state.v,
    context: state.context, profile: state.profile };
}
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
  if (TOUR) return;
  const q = new URLSearchParams();
  if (state.view === 'prompts') { q.set('view', 'prompts'); q.set('mode', state.mode); if (state.cmp !== 'stock') q.set('cmp', state.cmp); }
  else if (state.game) {
    q.set('game', state.game);
    const g = currentGame();
    if (g) q.set('level', String(levelOf(g)));
    if (state.context === 'none') q.set('ctx', 'none');
  }
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
    b.title = (m.variants[state.v].purpose || '') + (state.view === 'queue' ? ' Drag into the queue, or tap to add it at the end.' : ' Show this mode\'s prompt.');
    b.setAttribute('aria-label', `${m.name}${state.view === 'queue' ? ', add to the queue' : ', show its prompt'}`);
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

  $('compare').hidden = true;   // one instruction text serves both wordings since 6-Oct: nothing to compare
  const vb = $('variants'); vb.textContent = '';
  for (const [k, label] of Object.entries(VARIANTS)) {
    const b = h('button', 'mx-seg' + (k === state.v ? ' on' : ''), label);
    b.setAttribute('aria-pressed', k === state.v ? 'true' : 'false');
    b.title = state.view === 'queue' ? `Play sends ${label.replace("'s version", "'s")} wording of each mode` : `Show ${label.replace("'s version", "'s")} wording`;
    b.onclick = () => { state.v = k; render(); };
    vb.append(b);
  }
  const cb = $('compare'); cb.textContent = '';
  const other = state.v === 'son' ? 'daniel' : 'son';
  for (const [k, label] of [['stock', 'against Stock'], ['other', `against ${VARIANTS[other]}`]]) {
    const b = h('button', 'mx-seg' + (k === state.cmp ? ' on' : ''), label);
    b.setAttribute('aria-pressed', k === state.cmp ? 'true' : 'false');
    b.title = k === 'stock' ? 'Compare this mode with the plain Stock prompt' : `Compare with ${VARIANTS[other]} of the same mode`;
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
    ['Instructions', instructionsOf(m, state.v) ? 'Added as the last part of the turn message on each turn this mode runs' : 'None: Stock sends the turn message as the harness fills it in'],
    ['Settings', settingsSummary(defaults(m))]];
  if (m.settings_why) rows.push(['Why these settings', m.settings_why]);
  for (const [k, val] of rows) dl.append(h('dt', null, k), h('dd', null, val));
  card.append(dl);
}

// What the model receives, in three labelled parts, then the exact request on demand.
const EXAMPLE_FOR = { turn: 'turn', game_over: 'game_over', level_start: 'level_start' };
function renderParts(m) {
  const prof = state.profile === 'original' ? 'original' : 'dedup';
  const P = PROMPTS && PROMPTS.profiles[prof];
  $('profilenote').textContent = prof === 'dedup'
    ? 'Dedup prompts, the default for every mode including Stock: every standing instruction is said once, in the system prompt; the turn message carries only this turn\'s facts and, last, the mode\'s instructions.'
    : 'Original prompts (selected next to Play, only to compare with runs from before 6-Oct): the harness repeats several standing instructions in every turn message, and the mode\'s lines go where the original modes put them.';
  $('sysfull').textContent = P ? P.system[state.v] : 'Could not load the system prompt.';
  $('syshint').textContent = `${VARIANTS[state.v]} · ${P ? P.system[state.v].length.toLocaleString() + ' characters' : ''} · the tool definition sent with it: "${P ? (((P.tools || [])[0] || {}).function || {}).description || '' : ''}"`;
  const ex = P && P.turn_examples[EXAMPLE_FOR[m.base] || 'turn'];
  $('turnex').textContent = ex || '(no example)';
  const meta = PROMPTS && PROMPTS.meta.example;
  $('turnnote').textContent = `${DATA.surfaces[m.base] || ''}. Filled in by the harness every turn; this example is real, from a walk through ${meta ? meta.game : ''} level ${meta ? meta.level : ''} (${prof} prompts). In the sent message the mode's instructions come after these facts and before the board images.`;
  const text = instructionsOf(m, state.v);
  const header = PROMPTS ? PROMPTS.meta.mode_header.replace('{name}', m.name) : '';
  $('modetext').textContent = text ? `${header}\n${text}` : 'Stock adds no instructions: the turn message is only the facts above.';
  $('modetext').classList.toggle('muted', !text);
  $('modenote').textContent = m.shared ? `${versionTag(m)} · ${whoWhen(m.created_by, m.created_at)} · the pencil on the mode edits it (a new version; the old ones stay).` : '';
  const t = previewTarget();
  $('preview').disabled = !t;
  $('preview').textContent = t ? `Preview request · ${t.nickname} level ${t.level}` : 'Preview request';
  $('preview').title = t ? `Build the exact first request Play would send for ${t.nickname} level ${t.level} with ${m.name}, ${VARIANTS[state.v]}, ${t.context === 'none' ? 'no context' : 'context carried'} (the game and level chosen in the Queue view). The runner builds it with its real harness; nothing is played.`
    : 'Pick a game in the Queue view first';
  $('preview').onclick = async () => {
    const out = $('previewout');
    out.textContent = 'Building the request on the runner…';
    try {
      const d = await previewRequest({ ...t, mode: m.id, name: m.name, instructions: prof === 'dedup' || text ? text : '' });
      renderPreview(out, d);
    } catch (e) { out.textContent = `No preview: ${e.message}`; }
  };
}

// ---------------------------------------------------------------- Queue view: game sidebar and level buttons

// The public games the runner plays, hardest first (lowest share of levels safely cleared, then lowest median);
// games with no stuck level (stock clears every level) go last.
function sidebarGames() {
  if (!STUCK) return [];
  const hard = (g) => g.stuck_level ? g.safe_through / g.levels : 2;
  return STUCK.games.filter(g => !HELD_OUT.has(g.game))
    .sort((a, b) => (hard(a) - hard(b)) || (a.median_levels / a.levels - b.median_levels / b.levels) || a.game.localeCompare(b.game));
}
function currentGame() { return STUCK && state.game ? sidebarGames().find(g => g.game === state.game) || null : null; }
function levelOf(g) { return queueOf(g).start_level; }
function thumb(g) { return THUMBS[g.game] ? `./static/img/games/${g.game}-${THUMBS[g.game]}.png` : null; }

function pickGame(code) {
  if (code === state.game) return;
  state.game = code; state.open = -1; store.game = code; saveStore(); render();
}
function pickLevel(g, lv) {
  const q = queueOf(g);
  if (q.start_level === lv) return;
  q.start_level = lv; state.open = -1; touch(q); render();
}

function renderGamebar() {
  const bar = $('gamebar');
  bar.textContent = '';
  if (STUCK === null) { bar.append(h('p', 'mx-sum', 'loading…')); return; }
  if (STUCK === false) { bar.append(h('p', 'mx-sum', 'Could not load the stuck levels.')); return; }
  bar.append(h('div', 'mx-gbhead', 'Games · hardest first'));
  const list = h('div', 'mx-gblist');
  for (const g of sidebarGames()) {
    const on = g.game === state.game;
    const b = h('button', 'mx-gbgame' + (on ? ' on' : ''));
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    const n = (store.schemes[g.game]?.slots || []).length;
    b.title = `${g.nickname}: ${g.levels} levels, ` + (g.stuck_level ? `stuck at level ${g.stuck_level} (stock clears every level before it in at least 90% of runs)` : 'stock clears every level in at least 90% of runs') +
      (n ? `. ${n} mode${n === 1 ? '' : 's'} in your queue.` : '.');
    const src = thumb(g);
    if (src) { const img = h('img', 'mx-gbthumb'); img.src = src; img.alt = ''; img.loading = 'lazy'; img.width = 40; img.height = 40; b.append(img); }
    else b.append(h('span', 'mx-gbthumb mx-gbnothumb'));
    const txt = h('span', 'mx-gbtext');
    txt.append(h('span', 'mx-gbname', g.nickname));
    txt.append(h('span', 'mx-gbsub', `${g.levels} levels${n ? ` · ${n} queued` : ''}`));
    b.append(txt);
    b.append(h('span', 'mx-gbstuck' + (g.stuck_level ? '' : ' none'), g.stuck_level ? `L${g.stuck_level}` : 'all'));
    b.setAttribute('aria-label', `${g.nickname}, ${g.levels} levels` + (g.stuck_level ? `, stuck at level ${g.stuck_level}` : ''));
    b.onclick = () => pickGame(g.game);
    list.append(b);
  }
  bar.append(list);
  // bring the open game into view inside the list (the sidebar on a desktop, the strip on a phone), never the page
  const sel = list.querySelector('.mx-gbgame.on');
  if (sel && !renderGamebar.scrolled) {
    renderGamebar.scrolled = true;
    const sideways = list.scrollWidth > list.clientWidth;
    const box = sideways ? list : bar;
    if (sideways) box.scrollLeft = sel.offsetLeft - list.offsetLeft - 8;
    else if (sel.offsetTop + sel.offsetHeight > box.clientHeight) box.scrollTop = sel.offsetTop - bar.offsetTop - 40;
  }
}

function rate(a, b) { return b ? Math.round((100 * a) / b) : 0; }

function renderLevels() {
  const g = currentGame();
  const box = $('levels'); box.textContent = '';
  $('gametitle').textContent = g ? g.nickname : '';
  const nc = state.context === 'none';
  $('levellegend').textContent = !g ? '' : nc ? 'No context · fill: stock runs that cleared the level · bar under it: No-context Spark runs · ○ replayed level start'
    : 'Fill: stock runs that cleared the level · bar under it: Spark runs · ● exact saved start · ○ fresh or rebuilt start';
  if (!g) { $('gamefact').textContent = ''; return; }
  const sel = levelOf(g);
  const spark = SPARK[`${g.game}:${state.context}`] && SPARK[`${g.game}:${state.context}`].tally || {};
  for (let lv = 1; lv <= g.levels; lv++) {
    const p = g.per_level[lv - 1];
    const sp = spark[lv];
    const ls = levelStart(g, lv, state.v, state.context);
    const off = !ls.ok && !ls.unknown;
    const b = h('button', 'mx-lv' + (lv === sel ? ' on' : '') + (lv === g.stuck_level ? ' stuck' : '') + (off ? ' off' : ''));
    b.setAttribute('aria-pressed', lv === sel ? 'true' : 'false');
    const fill = h('span', 'mx-lvfill'); fill.style.height = `${p ? rate(p.cleared, p.n) : 0}%`;
    b.append(fill, h('span', 'mx-lvnum', String(lv)));
    if (sp && sp.played) { const bar = h('span', 'mx-lvspark'); bar.style.setProperty('--w', `${rate(sp.cleared, sp.played)}%`); b.append(bar); }
    if (ls.ok) b.append(h('span', 'mx-lvmark' + (ls.kind === 'exact' ? ' exact' : ''), ls.kind === 'exact' ? '●' : '○'));
    const lines = [`Level ${lv} of ${g.levels}${lv === g.stuck_level ? ' · the stuck level' : ''}`,
      p ? `${p.cleared} of ${p.n} stock runs cleared it (full runs from the start of the game).` : 'No stock tally for this level.',
      sp && sp.played ? `On the Sparks${nc ? ' without context' : ''}: ${sp.cleared} of ${sp.played} run${sp.played === 1 ? '' : 's'} that played it cleared it.` : `No Spark run has played it${nc ? ' without context' : ''} yet.`,
      ls.ok ? (ls.kind === 'replay' ? "No context: Play replays the board to this level's start and gives the model a clean first turn."
        : ls.kind === 'exact' ? `Play starts from an exact saved start (reached in ${ls.chosen.actions_to_reach} actions${ls.count > 1 ? `, best of ${ls.count}` : ''}).`
        : ls.kind === 'reset' ? 'Play starts a fresh game from its first frame.' : 'Play starts from the snapshot, with the conversation rebuilt from stored transcripts.')
        : ls.why];
    b.title = lines.join('\n');
    b.setAttribute('aria-label', `Level ${lv}${off ? ', no start available' : ''}`);
    // no start: shown greyed with the reason in its tooltip, and not selectable (aria-disabled keeps the tooltip on hover)
    if (off) { b.setAttribute('aria-disabled', 'true'); b.onclick = () => flash(`Level ${lv}: ${ls.why}`); }   // a phone has no hover
    else b.onclick = () => pickLevel(g, lv);
    box.append(b);
  }
  const p = g.per_level[sel - 1], sp = spark[sel];
  const ls = levelStart(g, sel, state.v, state.context);
  $('gamefact').textContent = `Level ${sel}${sel === g.stuck_level ? ', the stuck level' : ''}: stock cleared it in ${p ? `${p.cleared} of ${p.n}` : 'no'} full runs` +
    (sp && sp.played ? `, Spark runs${nc ? ' without context' : ''} in ${sp.cleared} of ${sp.played}.` : `; no Spark run has played it${nc ? ' without context' : ''} yet.`) +
    (ls.ok ? (ls.kind === 'replay' ? ' No context: Play replays the board to this level start and starts a clean conversation.' : ls.kind === 'exact' ? ' Play starts from an exact saved start.' : ls.kind === 'reset' ? ' Play starts a fresh game.' : ' Play starts from the snapshot (conversation rebuilt).') : ' ' + ls.why);
}

// ---------------------------------------------------------------- Queue view: the queue

// One queue per game; start_level is the level Play starts from (the level buttons set it; the stuck level by default).
function queueOf(g) {
  if (!store.schemes[g.game]) store.schemes[g.game] = { start_level: g.stuck_level || 1, slots: [], updated: null };
  const q = store.schemes[g.game];
  if (!Number.isInteger(q.start_level) || q.start_level < 1 || q.start_level > g.levels) q.start_level = g.stuck_level || 1;
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
  if (!g) { $('playrow').textContent = ''; $('startboard').textContent = ''; return; }
  const q = queueOf(g);
  q.slots.forEach((item, i) => list.append(itemNode(item, i)));
  if (!q.slots.length) list.append(h('li', 'mx-qempty', 'Drag modes here from the bar above, or tap a mode to add it. An empty queue plays Stock only.'));
  const tail = h('li', 'mx-qitem mx-qtail');
  const stock = findMode('stock');
  const ttag = h('span', 'mx-tag', q.slots.length ? 'then Stock' : 'Stock'); ttag.style.background = stock ? stock.color : '#8792a2';
  tail.title = 'After the queue runs out, Stock plays every later turn until the level is cleared or a cap is hit.';
  list.title = 'The queue: one mode per turn, in order. Drag modes in from the bar, drag items to reorder, drag one out or press its x to remove it.';
  tail.append(ttag);
  list.append(tail);
  if (state.open >= 0 && q.slots[state.open]) { set.hidden = false; set.append(itemEditor(q.slots[state.open], state.open, q)); }
  renderPlayRow($('playrow'), playCtx(g, q));
  renderStartBoard($('startboard'), { game: g, level: q.start_level, variant: state.v, context: state.context,
    ls: levelStart(g, q.start_level, state.v, state.context) });
  const sub = $('gamebar').querySelector('.mx-gbgame.on .mx-gbsub');
  if (sub) sub.textContent = `${g.levels} levels${q.slots.length ? ` · ${q.slots.length} queued` : ''}`;
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
  reset.title = "Undo this turn's changes and use the mode's own settings again";
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
  const earlier = h('button', 'mx-tool', '← Earlier'); earlier.title = 'Move this turn one place earlier in the queue'; earlier.disabled = i === 0; earlier.onclick = () => moveItem(i, i - 1);
  const later = h('button', 'mx-tool', 'Later →'); later.title = 'Move this turn one place later in the queue'; later.disabled = i === q.slots.length - 1; later.onclick = () => moveItem(i, i + 2);
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
  if (f.tip) { wrap.title = f.tip; input.title = f.tip; }
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
    instructions: '', settings: { ...defaults(DATA.modes[0]) }, settings_why: '',
  };
  if (existing && typeof existing.instructions !== 'string') draft.instructions = instructionsOf(asMode(existing), state.v);
  draft.settings = { ...FALLBACK_SETTINGS, ...draft.settings };
  const dlg = $('modedlg'); dlg.textContent = ''; dlg.className = 'mx-dialog';
  const form = h('form', 'mx-form'); form.method = 'dialog';
  form.append(h('h2', null, existing ? `Edit ${existing.name}` : 'New mode'));
  form.append(h('p', 'mx-sum', 'Saved in this browser only. A mode is its instructions for the turn it runs: what the model should do differently. They go last in the turn message; the system prompt and the turn facts stay as they are.'));

  const row = h('div', 'mx-formrow');
  const name = h('input'); name.required = true; name.maxLength = 32; name.value = draft.name; name.placeholder = 'e.g. Map the board';
  const color = h('input'); color.type = 'color'; color.value = draft.color;
  const lab = (t, el, cls) => { const l = h('label', 'mx-field' + (cls ? ' ' + cls : '')); l.append(h('span', 'mx-flabel', t), el); return l; };
  row.append(lab('Name', name, 'grow'), lab('Colour', color));
  form.append(row);
  const purpose = h('input'); purpose.value = draft.purpose; purpose.placeholder = 'What this turn is for, in one line';
  form.append(lab('Purpose', purpose, 'wide'));
  const prompt = h('textarea', 'mx-prompt'); prompt.value = draft.instructions; prompt.rows = 6; prompt.required = true;
  prompt.placeholder = 'What the model should do differently on the turn this mode runs';
  form.append(lab('Mode instructions (the last part of the turn message)', prompt, 'wide'));
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
      instructions: prompt.value.replace(/\r/g, '').trim(), settings: draft.settings, settings_why: why.value.trim() };
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

function validCustom(c) { return c && typeof c.id === 'string' && typeof c.name === 'string' && c.name.trim() && (typeof c.prompt === 'string' || typeof c.instructions === 'string'); }
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
      instructions: typeof c.instructions === 'string' ? c.instructions : undefined,
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

function playCtx(g, q) {
  const context = state.context;
  return { game: g, level: q.start_level, scheme: q, variant: state.v, context, profile: state.profile, DATA, findMode, slotSettings: itemSettings, defaults, stockText, instructionsOf, versionOf, loadRuns, whoWhen,
    onProfile: (p) => { state.profile = p; store.profile = p; saveStore(); render(); },
    demo: () => !!TOUR,
    onJobs: (game, tally, harvest) => { SPARK[`${game}:${context}`] = { tally, harvest }; if (game === state.game && context === state.context && state.view === 'queue') renderLevels(); },
    onContext: (c) => { state.context = c; store.context = c; saveStore(); state.open = -1; render(); } };
}

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
    if ($('previewout').dataset.mode !== m.id) { $('previewout').textContent = ''; $('previewout').dataset.mode = m.id; }
    renderCard(m);
    renderParts(m);
    return;
  }
  renderGamebar();
  renderLevels();
  renderQueueArea();
  const g = currentGame();
  if (g) renderResults($('results'), playCtx(g, queueOf(g)));
  else $('results').textContent = '';
}

// The dock pins just under the site tabs, whose height changes when they wrap or scroll sideways on a phone.
// The game sidebar pins under both, so it needs the dock's height too.
function trackNav() {
  const nav = document.querySelector('.sitetabs'), dock = $('dock');
  const set = () => {
    document.documentElement.style.setProperty('--navh', `${nav ? nav.offsetHeight : 0}px`);
    document.documentElement.style.setProperty('--dockh', `${dock ? dock.offsetHeight : 0}px`);
  };
  set();
  if ('ResizeObserver' in window) { const ro = new ResizeObserver(set); if (nav) ro.observe(nav); if (dock) ro.observe(dock); }
  else addEventListener('resize', set);
}

// The how-to panel at the top: open on a first visit, closed after that unless it was left open (its own key, so the
// main store's field list stays as it is).
const HOWTO_KEY = 'arc3-mode-explorer-howto';
function setupHowto() {
  const d = $('howto'); if (!d) return;
  let seen = null;
  try { seen = localStorage.getItem(HOWTO_KEY); } catch { /* private mode: open every time */ }
  d.open = seen === null || seen === 'open';
  // after the first visit it starts closed, even if it was never closed by hand
  if (seen === null) try { localStorage.setItem(HOWTO_KEY, 'closed'); } catch { /* private mode */ }
  // only a person's click (or Enter/Space, which clicks) is remembered; setting d.open above also fires 'toggle'
  d.querySelector('summary').addEventListener('click', () => {
    try { localStorage.setItem(HOWTO_KEY, d.open ? 'closed' : 'open'); } catch { /* private mode */ }
  });
}

// ---------------------------------------------------------------- guided tour (mode-tour.js)

// The demo uses Probe, Hypothesize and Execute when they are shown, else the first visible modes after Stock.
function demoModeIds() {
  const shown = allModes().filter(m => m.id !== 'stock');
  const want = ['probe', 'hypothesize', 'execute'].filter(id => shown.some(m => m.id === id));
  for (const m of shown) if (want.length < 3 && !want.includes(m.id)) want.push(m.id);
  return want;
}

const tourHost = {
  ready: () => !!(DATA && STUCK && sidebarGames().length),
  notReady: () => flash(STUCK === false ? 'The tour needs the game list, which did not load.' : 'The page is still loading; try the tour again in a moment.'),
  // a sample game other than the one open (hardest first), its stuck level when Play can start there, else level 1
  begin() {
    TOUR = { store: JSON.stringify(store), state: { view: state.view, game: state.game, open: state.open, context: state.context, v: state.v, mode: state.mode, cmp: state.cmp } };
    const games = sidebarGames();
    const g = games.find(x => x.game !== state.game) || games[0];
    const lv = g.stuck_level && levelStart(g, g.stuck_level, state.v, state.context).ok ? g.stuck_level : 1;
    TOUR.demo = { code: g.game, nickname: g.nickname, level: lv };
    store.schemes[g.game] = { start_level: g.stuck_level || 1, slots: [], updated: null };   // in memory only
    state.view = 'queue'; state.open = -1;
    render();
  },
  end() {
    const t = TOUR; if (!t) return;
    store = JSON.parse(t.store);
    Object.assign(state, t.state);
    TOUR = null;
    renderGamebar.scrolled = false;
    render();
  },
  demo: () => TOUR.demo,
  demoGame() {
    if (!TOUR || state.game === TOUR.demo.code) return;
    renderGamebar.scrolled = false;   // bring the demo game into view in the list
    pickGame(TOUR.demo.code);
  },
  demoLevel() { const g = currentGame(); if (TOUR && g) pickLevel(g, TOUR.demo.level); },
  // Puts the demo modes into the demo queue, each flying in from the bar when animate is set. live() turns false when
  // the person moves to another step (which fills the rest at once) or leaves the tour.
  async fillQueue(live, animate) {
    if (!TOUR) return;
    tourHost.demoGame(); tourHost.demoLevel();
    const q = queueOf(currentGame());
    for (const id of demoModeIds()) {
      if (!TOUR || !live()) return;
      if (q.slots.some(s => s.mode === id)) continue;
      if (animate) {
        await flyChip([...$('modes').querySelectorAll('.mx-mode')].find(b => b.textContent === findMode(id).name), live);
        if (!TOUR || !live() || q.slots.some(s => s.mode === id)) return;
      }
      addItem(id);
      if (animate) await pause(200);
    }
  },
  settings(i) {
    if (!TOUR) return;
    const g = currentGame();
    state.open = g && queueOf(g).slots[i] ? i : -1;
    renderQueueArea();
  },
  // What Play would send for the demo queue, in words (the request itself is built by spark-runner.js)
  playPreview() {
    const g = currentGame(), q = queueOf(g);
    let req;
    try { req = playRequest(playCtx(g, q)); } catch (e) { return [`Nothing: ${e.message}`]; }
    return [`Game: ${g.nickname}, starting at level ${req.stuck_level}`,
      `${req.context === 'none' ? 'No context' : 'Carry context'}, ${req.variant === 'daniel' ? "Franzen's" : "Son's"} wording`,
      `Queue: ${req.scheme.map(s => s.name + (s.version ? ` v${s.version.version}` : '')).join(', ') || 'empty'}, then ${req.stock.name}${req.stock.version ? ` v${req.stock.version.version}` : ''}`,
      `${req.samples} samples, up to ${req.max_turns} turns each`];
  },
};

async function main() {
  setupHowto();
  $('tourhelp').onclick = () => startTour(tourHost);
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
  try {
    const r = await fetch('./static/data/prompt-profiles.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    PROMPTS = await r.json();
  } catch { PROMPTS = null; }
  initLibrary({ h, settingsGrid, diffLines, lineNode, settingsSummary, FALLBACK_SETTINGS, stockText, instructionsOf,
    prompts: () => PROMPTS, profile: () => state.profile, previewTarget, previewRequest, renderPreview, surfaces: () => DATA.surfaces });
  await loadLibrary();
  $('updated').textContent = lib.ok ? 'Shared modes · anyone signed in can edit; every save is a new version'
    : `Draft prompts · ${DATA.meta.date} · shared modes could not load (${lib.error}), showing the built-in drafts`;
  $('storenote').textContent = lib.ok ? 'Modes are shared with everyone signed in, and every save keeps a new version. Your queues, chosen levels and the context choice are saved in this browser only.'
    : 'The shared modes could not be reached, so custom modes made now, queues, chosen levels and the context choice are saved in this browser only.';
  $('finding').textContent = DATA.meta.finding;
  $('copy').onclick = async () => {
    try { await navigator.clipboard.writeText($('modetext').textContent); $('copy').textContent = 'Copied'; }
    catch { $('copy').textContent = 'Copy failed'; }
    setTimeout(() => { $('copy').textContent = 'Copy instructions'; }, 1500);
  };
  for (const b of $('tabs').querySelectorAll('.mx-tab')) b.title = b.dataset.view === 'queue' ? 'Build a queue of modes and play it on the Sparks' : 'See what the model receives: the system prompt, this turn\'s facts and each mode\'s instructions';
  $('copy').title = 'Copy this mode\'s instructions';
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
  if (!currentGame()) state.game = sidebarGames()[0]?.game || null;
  const g0 = currentGame();
  if (g0 && state.level && state.level <= g0.levels && Number.isInteger(state.level)) queueOf(g0).start_level = state.level;
  render();
  migrateLocal();
  await loadRunnerInfo();
  // the results header lists exact starts, so it is redrawn too once the runner has answered
  if (state.view === 'queue' && currentGame()) { renderLevels(); renderQueueArea(); renderResults($('results'), playCtx(currentGame(), queueOf(currentGame()))); }
}

main();
