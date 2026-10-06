/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: Draws the Mode explorer page (docs/mode-explorer.html). Two views share one frozen dock (view tabs, the
  mode chips, the variant switch), which stays pinned under the site tabs while the page scrolls:
  - Prompts: each mode from docs/static/data/modes.json (Stock, Probe, Hypothesize, Execute, Re-examine, Challenge,
    Recover, Level start, plus the user's custom modes) in two variants, "son" (Son's current notebook) and
    "daniel" (Franzen's public notebook), with a side-by-side line diff against Stock or against the other variant.
  - Stuck levels: docs/static/data/stuck-levels.json (built by scripts/stuck_levels_tally.py) as a sortable table,
    hardest first. Opening a game shows its per-level clear rates and a scheme builder: an ordered lane of per-turn
    modes, dragged (or tapped) in from the dock, starting at the game's stuck level and followed by Stock. Every
    slot carries the mode's settings (temperature, thinking, effort, thinking budget, tool calls, action budget),
    editable per slot. Play is shown but disabled until the Spark runner exists (phase 2); no results are faked.
  Custom modes (name, colour, prompt based on Stock, settings) and schemes are saved in localStorage and can be
  exported and imported as JSON, since the site has no backend for them yet. View state lives in the URL
  (?view=&mode=&v=&cmp=&game=) so a view can be linked. The diff is a plain longest-common-subsequence over lines.
SRP/DRY check: Pass — prompt text and default settings live only in modes.json, the tally only in stuck-levels.json;
  mode ids and colours follow RL2's vocabulary (carried per mode as `rl2`/`color` in the JSON); layout classes come
  from rl-shell.css. Checked rl2.js and sprints.js: neither has a drag lane or a local store to reuse.
*/

const $ = (id) => document.getElementById(id);
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const VARIANTS = { son: "Son's version", daniel: "Franzen's version" };
const STORE_KEY = 'arc3-mode-explorer-v1';
const PLAY_TIP = 'Needs the Spark runner (phase 2). Nothing plays from this page yet.';
// The settings every mode and every scheme slot carries; defaults per mode come from modes.json.
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
  view: params.get('view') === 'stuck' ? 'stuck' : 'prompts',
  mode: params.get('mode') || 'probe',
  v: params.get('v') === 'daniel' ? 'daniel' : 'son',
  cmp: params.get('cmp') === 'other' ? 'other' : 'stock',
  game: params.get('game') || null,
  sort: { key: 'hard', dir: 1 },
  sel: -1,          // selected slot in the open scheme
};
let DATA = null;    // modes.json
let STUCK = null;   // stuck-levels.json (null until loaded; false if it failed)
let store = loadStore();

// ---------------------------------------------------------------- local store

function loadStore() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
    return { customModes: Array.isArray(s.customModes) ? s.customModes : [], schemes: s.schemes && typeof s.schemes === 'object' ? s.schemes : {} };
  } catch { return { customModes: [], schemes: {} }; }
}
function saveStore() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); }
  catch (e) { flash(`Could not save in this browser (${e.message}). Use Export to keep your work.`); }
}
function flash(text) {
  const p = $('dockhint'); p.textContent = text; p.hidden = false;
  clearTimeout(flash.t); flash.t = setTimeout(() => { p.hidden = true; renderHint(); }, 4000);
}

// ---------------------------------------------------------------- modes

// A custom mode stored as {id, name, color, purpose, base_variant, prompt, settings, settings_why}, drawn like a built-in.
function asMode(c) {
  const v = { purpose: c.purpose || 'Custom mode.', trigger: 'Your choice: custom mode.', budget: budgetText(c.settings), prompt: c.prompt };
  return { id: c.id, name: c.name, color: c.color, base: 'turn', custom: true, base_variant: c.base_variant,
    settings: { ...FALLBACK_SETTINGS, ...(c.settings || {}) }, settings_why: c.settings_why || '', variants: { son: v, daniel: v } };
}
function allModes() { return DATA.modes.concat(store.customModes.map(asMode)); }
function findMode(id) { return allModes().find(m => m.id === id) || null; }
function modeById(id) { return findMode(id) || DATA.modes[1] || DATA.modes[0]; }
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
  if (state.view === 'stuck') { q.set('view', 'stuck'); if (state.game) q.set('game', state.game); }
  else { q.set('mode', state.mode); q.set('v', state.v); if (state.cmp !== 'stock') q.set('cmp', state.cmp); }
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
    b.draggable = true;
    b.setAttribute('aria-pressed', picked ? 'true' : 'false');
    b.title = (m.variants[state.v].purpose || '') + (state.view === 'stuck' ? ' Drag into the lane, or tap to add.' : '');
    b.onclick = () => onChip(m);
    b.ondragstart = (e) => { e.dataTransfer.setData('text/plain', 'mode:' + m.id); e.dataTransfer.effectAllowed = 'copy'; };
    box.append(b);
  }
  $('promptbar').hidden = state.view !== 'prompts';
  const vb = $('variants'); vb.textContent = '';
  for (const [k, label] of Object.entries(VARIANTS)) {
    const b = h('button', 'mx-seg' + (k === state.v ? ' on' : ''), label);
    b.setAttribute('aria-pressed', k === state.v ? 'true' : 'false');
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
  renderHint();
}

function renderHint() {
  const p = $('dockhint');
  if (state.view === 'stuck') {
    const g = currentGame();
    p.textContent = g ? `Building a scheme for ${g.nickname}: drag a mode into the lane, or tap it to add it at the end.`
      : 'Pick a game below to build a scheme for its stuck level.';
    p.hidden = false;
  } else p.hidden = true;
}

function onChip(m) {
  if (state.view === 'prompts') { state.mode = m.id; render(); return; }
  if (!currentGame()) { flash('Pick a game in the table first.'); return; }
  addSlot(m.id);
}

// ---------------------------------------------------------------- Prompts view

function renderCard(m) {
  const v = m.variants[state.v];
  const card = $('card'); card.textContent = '';
  const head = h('div', 'mx-head');
  const tag = h('span', 'mx-tag', m.name); tag.style.background = m.color;
  head.append(tag);
  if (m.custom) {
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
    ['Built on', m.custom ? `Stock, ${VARIANTS[m.base_variant] || ''}` : DATA.surfaces[m.base]],
    ['Settings', settingsSummary(defaults(m))]];
  if (m.settings_why) rows.push(['Why these settings', m.settings_why]);
  for (const [k, val] of rows) dl.append(h('dt', null, k), h('dd', null, val));
  card.append(dl);
}

function renderDiff(m) {
  const other = state.v === 'son' ? 'daniel' : 'son';
  const leftText = state.cmp === 'other' ? m.variants[other].prompt : DATA.stock[state.v][m.base];
  const rightText = m.variants[state.v].prompt;
  const leftLabel = state.cmp === 'other' ? `${m.name} · ${VARIANTS[other]}` : `Stock · ${VARIANTS[state.v]}`;
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

// ---------------------------------------------------------------- Stuck levels view

function currentGame() { return STUCK && state.game ? STUCK.games.find(g => g.game === state.game) || null : null; }
function scheme(code) { return store.schemes[code] || null; }

const COLS = [
  { key: 'game', label: 'Game', val: g => g.nickname.toLowerCase() },
  { key: 'hard', label: 'Stuck at', val: g => [g.safe_through / g.levels, g.median_levels / g.levels] },
  { key: 'safe', label: 'Safe through', val: g => g.safe_through },
  { key: 'median', label: 'Median cleared', val: g => g.median_levels },
  { key: 'n', label: 'Runs', val: g => g.n },
  { key: 'flags', label: 'Notes', val: g => (g.near_line ? 2 : 0) + (g.clock_shaped ? 1 : 0) },
  { key: 'older', label: 'Older line', val: g => g.older ? g.older.safe_through : -1 },
  { key: 'scheme', label: 'Your scheme', val: g => scheme(g.game) ? scheme(g.game).slots.length : 0 },
];

function cmpVals(a, b) {
  if (Array.isArray(a)) { for (let i = 0; i < a.length; i++) { const c = cmpVals(a[i], b[i]); if (c) return c; } return 0; }
  return a < b ? -1 : a > b ? 1 : 0;
}

function renderStuck() {
  if (STUCK === null) { $('stucksum').textContent = 'loading…'; return; }
  if (STUCK === false) { $('stucksum').textContent = 'Could not load the stuck-level tally.'; return; }
  const meta = STUCK.meta, main = meta.groups.franzen_stock;
  $('stucknote').textContent = `${main.label}: ${main.runs.length} runs. ${main.detail}`;
  $('stucksum').textContent = `Safe through = every level up to it cleared in at least 90% of runs. Stuck at = the next level. ` +
    `Hardest first; click a column to sort, click a game to build a scheme for its stuck level.`;
  $('stuckcaveat').textContent = `${meta.thin_rule} ${meta.survival_note} Soft: ${meta.near_line_rule.replace(/^near_line = /, '')} ` +
    `Clock: ${meta.clock_rule.replace(/^clock_shaped = /, '')} Older line: ${meta.groups.older.detail} ${meta.not_used}`;

  const col = COLS.find(c => c.key === state.sort.key) || COLS[1];
  const games = STUCK.games.slice().sort((a, b) => cmpVals(col.val(a), col.val(b)) * state.sort.dir || a.game.localeCompare(b.game));
  const t = $('stucktable'); t.textContent = '';
  const tr = h('tr');
  for (const c of COLS) {
    const th = h('th', null, c.label);
    th.setAttribute('aria-sort', c.key === col.key ? (state.sort.dir > 0 ? 'ascending' : 'descending') : 'none');
    if (c.key === col.key) th.classList.add('sorted');
    th.tabIndex = 0;
    th.onclick = th.onkeydown = (e) => {
      if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
      state.sort = { key: c.key, dir: state.sort.key === c.key ? -state.sort.dir : 1 }; renderStuck();
    };
    tr.append(th);
  }
  const thead = h('thead'); thead.append(tr); t.append(thead);
  const body = h('tbody');
  for (const g of games) {
    const row = h('tr', g.game === state.game ? 'on' : null);
    row.tabIndex = 0;
    row.onclick = row.onkeydown = (e) => { if (e.type === 'keydown' && e.key !== 'Enter') return; openGame(g.game); };
    const name = h('td', 'mx-gname'); name.append(h('b', null, g.nickname), h('span', 'mx-code', g.game));
    const stuck = h('td', 'mx-stuckcell');
    if (g.stuck_level) {
      stuck.append(h('b', null, `level ${g.stuck_level}`), h('span', 'mx-of', ` of ${g.levels}`));
      stuck.append(rateBar(g.per_level[g.stuck_level - 1]));
    } else stuck.append(h('span', 'mx-clear', `none, all ${g.levels} clear`));
    const flags = h('td');
    if (g.near_line) flags.append(h('span', 'chip mx-flag soft', 'soft'));
    if (g.clock_shaped) flags.append(h('span', 'chip mx-flag clock', 'clock'));
    if (g.thin) flags.append(h('span', 'chip mx-flag thin', 'thin'));
    const sc = scheme(g.game);
    row.append(name, stuck, h('td', null, `${g.safe_through} of ${g.levels}`), h('td', null, String(g.median_levels)),
      h('td', null, String(g.n)), flags,
      h('td', 'muted', g.older ? `safe through ${g.older.safe_through} (${g.older.n} runs)` : '–'),
      h('td', sc && sc.slots.length ? null : 'muted', sc && sc.slots.length ? `${sc.slots.length} turn${sc.slots.length === 1 ? '' : 's'} from level ${sc.start_level}` : '–'));
    body.append(row);
  }
  t.append(body);
  renderBuilder();
}

function rateBar(p) {
  const w = h('span', 'mx-rate'); w.title = `${p.cleared} of ${p.n} runs cleared level ${p.level}`;
  const i = h('i'); i.style.width = `${Math.round(p.rate * 100)}%`; w.append(i);
  const outer = h('span', 'mx-ratewrap'); outer.append(w, h('span', 'mx-ratet', `${p.cleared}/${p.n}`));
  return outer;
}

function openGame(code) {
  state.game = code; state.sel = -1;
  render();
  const b = $('builder');
  if (!b.hidden) b.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function ensureScheme(g) {
  if (!store.schemes[g.game]) store.schemes[g.game] = { start_level: g.stuck_level || g.levels, slots: [], updated: null };
  return store.schemes[g.game];
}
function touch(sc) { sc.updated = new Date().toISOString(); saveStore(); }

function addSlot(modeId, at) {
  const g = currentGame(); if (!g) return;
  const sc = ensureScheme(g);
  const idx = at == null ? sc.slots.length : at;
  sc.slots.splice(idx, 0, { mode: modeId, overrides: {} });
  state.sel = idx; touch(sc); render();
}
function moveSlot(from, to) {
  const sc = scheme(state.game); if (!sc || from === to || from + 1 === to) return;
  const [s] = sc.slots.splice(from, 1);
  const dest = to > from ? to - 1 : to;
  sc.slots.splice(dest, 0, s); state.sel = dest; touch(sc); render();
}
function slotSettings(slot) { const m = findMode(slot.mode); return { ...(m ? defaults(m) : FALLBACK_SETTINGS), ...slot.overrides }; }

function renderBuilder() {
  const b = $('builder'); const g = currentGame();
  b.hidden = !g; b.textContent = '';
  if (!g) return;
  const sc = ensureScheme(g);
  const card = h('div', 'card mx-build');

  const head = h('div', 'mx-head');
  head.append(h('span', 'mx-tag mx-gametag', g.nickname), h('span', 'mx-rl2',
    g.stuck_level ? `stuck at level ${g.stuck_level} of ${g.levels} · safe through ${g.safe_through} · ${g.n} runs` : `every level clears in 90% of ${g.n} runs`));
  const close = h('button', 'mx-tool mx-close', 'Close'); close.onclick = () => { state.game = null; render(); };
  head.append(close);
  card.append(head);

  // per-level clear rates; click a level to start the scheme there
  card.append(h('h3', 'mx-subh', 'How often each level is cleared'));
  const strip = h('div', 'mx-levels');
  for (const p of g.per_level) {
    const cell = h('button', 'mx-lvl' + (p.level === sc.start_level ? ' start' : '') + (p.level === g.stuck_level ? ' stuck' : ''));
    cell.style.setProperty('--r', p.rate);
    cell.title = `Level ${p.level}: cleared in ${p.cleared} of ${p.n} runs. Click to start the scheme here.`;
    cell.append(h('span', 'mx-lvln', `L${p.level}`), h('span', 'mx-lvlr', `${p.cleared}/${p.n}`));
    cell.onclick = () => { sc.start_level = p.level; touch(sc); render(); };
    strip.append(cell);
  }
  card.append(strip);
  const legend = h('p', 'mx-sum');
  legend.textContent = `Outlined: the stuck level. Filled ring: where your scheme starts (level ${sc.start_level}). ` +
    (g.older ? `Older line: safe through ${g.older.safe_through} of ${g.levels} over ${g.older.n} runs.` : '');
  card.append(legend);

  // the lane
  card.append(h('h3', 'mx-subh', `Turn schedule from the first turn on level ${sc.start_level}`));
  const lane = h('ol', 'mx-lane');
  sc.slots.forEach((slot, i) => lane.append(slotNode(slot, i, sc)));
  if (!sc.slots.length) lane.append(h('li', 'mx-empty', 'Drag a mode here from the bar above, or tap a mode to add it.'));
  const tail = h('li', 'mx-slot mx-tail');
  const stock = DATA.modes.find(m => m.id === 'stock');
  const ttag = h('span', 'mx-tag', 'Stock'); ttag.style.background = stock ? stock.color : '#8792a2';
  tail.append(h('span', 'mx-turn', sc.slots.length ? `turn ${sc.slots.length + 1} on` : 'every turn'), ttag,
    h('span', 'mx-slotsum', 'After the schedule runs out, play continues with Stock (the rest of this level and later levels).'));
  lane.append(tail);
  wireLane(lane, sc);
  card.append(lane);

  // settings for the selected slot
  if (state.sel >= 0 && sc.slots[state.sel]) card.append(slotEditor(sc.slots[state.sel], state.sel, sc));

  const foot = h('div', 'mx-buildfoot');
  const clear = h('button', 'mx-tool', 'Clear schedule');
  clear.disabled = !sc.slots.length;
  clear.onclick = () => { if (confirm(`Remove all ${sc.slots.length} turns from the ${g.nickname} schedule?`)) { sc.slots = []; state.sel = -1; touch(sc); render(); } };
  const playWrap = h('span', 'mx-playwrap'); playWrap.title = PLAY_TIP;
  const play = h('button', 'mx-play', 'Play this scheme'); play.disabled = true; play.setAttribute('aria-describedby', 'playnote');
  playWrap.append(play);
  const note = h('span', 'mx-playnote', 'Needs the Spark runner (phase 2) — switched off until it is built.'); note.id = 'playnote';
  foot.append(clear, playWrap, note);
  card.append(foot);
  b.append(card);
}

function slotNode(slot, i, sc) {
  const m = findMode(slot.mode);
  const li = h('li', 'mx-slot' + (i === state.sel ? ' sel' : ''));
  li.draggable = true; li.dataset.idx = i; li.tabIndex = 0;
  li.ondragstart = (e) => { e.dataTransfer.setData('text/plain', 'slot:' + i); e.dataTransfer.effectAllowed = 'move'; li.classList.add('dragging'); };
  li.ondragend = () => li.classList.remove('dragging');
  li.onclick = () => { state.sel = state.sel === i ? -1 : i; render(); };
  li.onkeydown = (e) => { if (e.key === 'Enter') li.onclick(); };
  const tag = h('span', 'mx-tag', m ? m.name : `${slot.mode} (missing)`);
  tag.style.background = m ? m.color : '#6b7280';
  const s = slotSettings(slot);
  const changed = Object.keys(slot.overrides).length;
  li.append(h('span', 'mx-turn', `turn ${i + 1}`), tag, h('span', 'mx-slotsum', settingsSummary(s) + (changed ? ' · edited' : '')));
  const btns = h('span', 'mx-slotbtns');
  for (const [label, title, fn, off] of [
    ['↑', 'Move earlier', () => moveSlot(i, i - 1), i === 0],
    ['↓', 'Move later', () => moveSlot(i, i + 2), i === sc.slots.length - 1],
    ['✕', 'Remove this turn', () => { sc.slots.splice(i, 1); state.sel = -1; touch(sc); render(); }, false]]) {
    const b = h('button', 'mx-mini', label); b.title = title; b.setAttribute('aria-label', title); b.disabled = off;
    b.onclick = (e) => { e.stopPropagation(); fn(); };
    btns.append(b);
  }
  li.append(btns);
  return li;
}

// Drops: a mode chip inserts a new turn, a slot moves; the insertion point is the first slot whose middle is below the pointer.
function wireLane(lane, sc) {
  const slots = () => [...lane.querySelectorAll('.mx-slot:not(.mx-tail)')];
  const indexAt = (y) => { const list = slots(); for (let k = 0; k < list.length; k++) { const r = list[k].getBoundingClientRect(); if (y < r.top + r.height / 2) return k; } return list.length; };
  const mark = (k) => { lane.querySelectorAll('.mx-slot').forEach((el, j) => el.classList.toggle('drop-before', j === k)); };
  lane.ondragover = (e) => { e.preventDefault(); lane.classList.add('over'); mark(indexAt(e.clientY)); };
  lane.ondragleave = (e) => { if (!lane.contains(e.relatedTarget)) { lane.classList.remove('over'); mark(-1); } };
  lane.ondrop = (e) => {
    e.preventDefault(); lane.classList.remove('over');
    const data = e.dataTransfer.getData('text/plain') || '';
    const at = indexAt(e.clientY); mark(-1);
    if (data.startsWith('mode:')) addSlot(data.slice(5), at);
    else if (data.startsWith('slot:')) moveSlot(+data.slice(5), at);
  };
}

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

function slotEditor(slot, i, sc) {
  const m = findMode(slot.mode);
  const box = h('div', 'mx-editor');
  box.append(h('h3', 'mx-subh', `Turn ${i + 1}: ${m ? m.name : slot.mode} settings`));
  const reset = h('button', 'mx-tool', 'Reset to mode defaults');
  box.append(settingsGrid(() => slotSettings(slot), (k, v) => {
    const base = m ? defaults(m) : FALLBACK_SETTINGS;
    if (base[k] === v) delete slot.overrides[k]; else slot.overrides[k] = v;
    touch(sc);
    const edited = Object.keys(slot.overrides).length;
    const sum = document.querySelector(`.mx-slot[data-idx="${i}"] .mx-slotsum`);
    if (sum) sum.textContent = settingsSummary(slotSettings(slot)) + (edited ? ' · edited' : '');
    reset.disabled = !edited;
  }));
  if (m && m.settings_why) box.append(h('p', 'mx-why', `Mode defaults: ${m.settings_why}`));
  reset.disabled = !Object.keys(slot.overrides).length;
  reset.onclick = () => { slot.overrides = {}; touch(sc); render(); };
  box.append(reset);
  return box;
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
  form.append(h('p', 'mx-sum', 'Saved in this browser only. The prompt starts as Stock; add your focus lines where you want them. Use Export to keep or share it.'));

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
      if (!confirm(`Delete ${existing.name}?` + (used ? ` It is used in ${used} scheme(s); those turns will be removed.` : ''))) return;
      store.customModes = store.customModes.filter(c => c.id !== existing.id);
      for (const s of Object.values(store.schemes)) s.slots = s.slots.filter(x => x.mode !== existing.id);
      saveStore(); dlg.close();
      if (state.mode === existing.id) state.mode = 'probe';
      state.sel = -1; render();
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
  const a = h('a'); a.href = url; a.download = `arc3-modes-and-schemes-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function validCustom(c) { return c && typeof c.id === 'string' && typeof c.name === 'string' && c.name.trim() && typeof c.prompt === 'string'; }
function validScheme(s) { return s && Array.isArray(s.slots) && s.slots.every(x => x && typeof x.mode === 'string') && Number.isInteger(s.start_level); }

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
    store.schemes[k] = { start_level: s.start_level, updated: s.updated || null,
      slots: s.slots.map(x => ({ mode: x.mode, overrides: x.overrides && typeof x.overrides === 'object' ? x.overrides : {} })) };
  }
  saveStore();
  render();
  flash(`Imported ${modes.length} custom mode(s) and ${schemes.length} scheme(s).`);
}

// ---------------------------------------------------------------- main

function render() {
  syncUrl();
  renderDock();
  $('view-prompts').hidden = state.view !== 'prompts';
  $('view-stuck').hidden = state.view !== 'stuck';
  if (state.view === 'prompts') {
    const m = modeById(state.mode);
    state.mode = m.id;
    renderCard(m);
    renderDiff(m);
  } else renderStuck();
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
    $('card').textContent = `Could not load the mode prompts (${e.message}).`;
    return;
  }
  $('updated').textContent = `Draft · ${DATA.meta.date}`;
  $('finding').textContent = DATA.meta.finding;
  $('notation').textContent = `${DATA.meta.notation} ${DATA.meta.insert_rule} ${DATA.meta.settings_note || ''}`;
  $('copy').onclick = async () => {
    try { await navigator.clipboard.writeText($('full').textContent); $('copy').textContent = 'Copied'; }
    catch { $('copy').textContent = 'Copy failed'; }
    setTimeout(() => { $('copy').textContent = 'Copy prompt'; }, 1500);
  };
  for (const b of $('tabs').querySelectorAll('.mx-tab')) b.onclick = () => { state.view = b.dataset.view; state.sel = -1; render(); };
  $('newmode').onclick = () => openModeDialog(null);
  $('export').onclick = exportJson;
  $('import').onclick = () => $('importfile').click();
  $('importfile').onchange = (e) => { const f = e.target.files[0]; if (f) importJson(f); e.target.value = ''; };
  render();
  try {
    const r = await fetch('./static/data/stuck-levels.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    STUCK = await r.json();
  } catch { STUCK = false; }
  if (state.game && !currentGame()) state.game = null;
  render();
}

main();
