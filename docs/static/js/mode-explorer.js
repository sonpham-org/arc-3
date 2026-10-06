/*
Author: Claude Opus 5.5
Date: 05-October-2026
PURPOSE: Draws the Mode explorer tab (docs/mode-explorer.html) from docs/static/data/modes.json. Each mode
  (Stock, Probe, Hypothesize, Execute, Re-examine, Challenge, Recover, Level start) has two variants: "son",
  built on the per-turn user prompt of Son's current notebook, and "daniel", built on Daniel Franzen's current
  public notebook. The page shows the picked mode's purpose, trigger and action budget, then a side-by-side line
  diff of its full prompt against the Stock prompt of the same surface and variant (or against the same mode's
  other variant). Placeholders ({like_this}) and sometimes-only lines ([when ...]) are marked. State lives in the
  URL (?mode=&v=&cmp=) so a view can be linked. The diff is a plain longest-common-subsequence over lines.
SRP/DRY check: Pass — all prompt text lives only in modes.json; mode ids and colours follow RL2's vocabulary
  (rl2.js MODE_COLORS, carried per mode as `rl2`/`color` in the JSON); layout classes come from rl-shell.css.
*/

const $ = (id) => document.getElementById(id);
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const VARIANTS = { son: "Son's version", daniel: "Franzen's version" };
const params = new URLSearchParams(location.search);
const state = { mode: params.get('mode') || 'probe', v: params.get('v') === 'daniel' ? 'daniel' : 'son', cmp: params.get('cmp') === 'other' ? 'other' : 'stock' };
let DATA = null;

function syncUrl() {
  const q = new URLSearchParams({ mode: state.mode, v: state.v });
  if (state.cmp !== 'stock') q.set('cmp', state.cmp);
  history.replaceState(null, '', '?' + q.toString());
}

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

function modeById(id) { return DATA.modes.find(m => m.id === id) || DATA.modes[1] || DATA.modes[0]; }

function renderPickers() {
  const box = $('modes'); box.textContent = '';
  for (const m of DATA.modes) {
    const b = h('button', 'mx-mode' + (m.id === state.mode ? ' on' : ''), m.name);
    b.style.setProperty('--mc', m.color);
    b.setAttribute('aria-pressed', m.id === state.mode ? 'true' : 'false');
    b.title = m.variants[state.v].purpose;
    b.onclick = () => { state.mode = m.id; render(); };
    box.append(b);
  }
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
}

function renderCard(m) {
  const v = m.variants[state.v];
  const card = $('card'); card.textContent = '';
  const head = h('div', 'mx-head');
  const tag = h('span', 'mx-tag', m.name); tag.style.background = m.color;
  head.append(tag, h('span', 'chip draft', 'Draft'));
  if (m.rl2) head.append(h('span', 'mx-rl2', m.rl2 === m.id ? 'same name on RL2' : `on RL2: ${m.rl2}`));
  else head.append(h('span', 'mx-rl2', 'new, no RL2 twin'));
  card.append(head);
  const dl = h('dl', 'mx-facts');
  for (const [k, val] of [['Purpose', v.purpose], ['When to use', v.trigger], ['Action budget', v.budget],
    ['Built on', DATA.surfaces[m.base]]]) { dl.append(h('dt', null, k), h('dd', null, val)); }
  card.append(dl);
}

function renderDiff(m) {
  const other = state.v === 'son' ? 'daniel' : 'son';
  const leftText = state.cmp === 'other' ? m.variants[other].prompt : DATA.stock[state.v][m.base];
  const rightText = m.variants[state.v].prompt;
  const leftLabel = state.cmp === 'other' ? `${m.name} · ${VARIANTS[other]}` : `Stock · ${VARIANTS[state.v]}`;
  const rightLabel = `${m.name} · ${VARIANTS[state.v]}`;
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

function render() {
  syncUrl();
  renderPickers();
  const m = modeById(state.mode);
  state.mode = m.id;
  renderCard(m);
  renderDiff(m);
}

async function main() {
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
  $('notation').textContent = `${DATA.meta.notation} ${DATA.meta.insert_rule}`;
  $('copy').onclick = async () => {
    try { await navigator.clipboard.writeText($('full').textContent); $('copy').textContent = 'Copied'; }
    catch { $('copy').textContent = 'Copy failed'; }
    setTimeout(() => { $('copy').textContent = 'Copy prompt'; }, 1500);
  };
  render();
}

main();
