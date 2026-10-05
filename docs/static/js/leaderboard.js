// Leaderboard tab: reads data/leaderboard/latest.json + history.json (written by scripts/leaderboard_snapshot.py).
const NS = 'http://www.w3.org/2000/svg';
const $ = (id) => document.getElementById(id);
const PAGE = 100;
let DATA, HIST, EVENTS = [], shown = PAGE, feedShown = 30;
const CLOSE = Date.parse('2026-11-02T00:00:00Z');   // competition close; medals settle on the private board then
const PALETTE = ['#e07a5f', '#3d9970', '#b07cd8', '#d99a1e', '#2ba3b5', '#d0587e', '#7a8f2e', '#6c7ae0', '#c4673a', '#4f9d8e'];

function el(tag, attrs = {}, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
const fmt = (n) => n.toFixed(2);
const medalOf = (rank) => rank <= DATA.medalRanks.gold ? 'gold' : rank <= DATA.medalRanks.silver ? 'silver' : rank <= DATA.medalRanks.bronze ? 'bronze' : null;
const css = (n) => getComputedStyle(document.querySelector('.lb')).getPropertyValue(n).trim();

function ago(iso) {
  const m = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  return m < 2 ? 'just now' : m < 90 ? `${m} minutes ago` : m < 2880 ? `${Math.round(m / 60)} hours ago` : `${Math.round(m / 1440)} days ago`;
}

async function load() {
  const get = async (f) => { const r = await fetch(`./static/data/leaderboard/${f}`, { cache: 'no-store' }); if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`); return r.json(); };
  let back, evs;
  [DATA, HIST, back, evs] = await Promise.all([get('latest.json'), get('history.json'), get('backfill.json').catch(() => null), get('events.json').catch(() => [])]);
  merge(back, evs);
  $('updated').textContent = `Saved ${ago(DATA.fetched)} · ${DATA.teams.toLocaleString()} teams`;
  tiles(); curve(); recap(); watch(); feed(); trend(); table();
}

// Past days come from backfill.json; our own half-hourly snapshots take over from the first one we saved.
function merge(back, evs) {
  EVENTS = evs.slice();
  if (!back) return;
  const own0 = HIST.snaps.length ? HIST.snaps[0].t : '9999';
  HIST.snaps = back.snaps.filter((x) => x.t < own0).concat(HIST.snaps);
  for (const [id, tr] of Object.entries(back.trails)) {
    const mine = HIST.trails[id] || { name: tr.name, pts: [] };
    const first = mine.pts.length ? mine.pts[0][0] : '9999';
    mine.pts = tr.pts.filter((p) => p[0] < first).concat(mine.pts);
    HIST.trails[id] = mine;
  }
  const ownE = EVENTS.length ? EVENTS[0].t : '9999';
  EVENTS = back.events.filter((e) => e.t < ownE).concat(EVENTS);
}

function tile(k, v, s, small) {
  const d = h('div', 'stat'); d.append(h('div', 'k', k));
  const vv = h('div', 'v', v); if (small) vv.append(h('small', null, small)); d.append(vv); d.append(h('div', 's', s));
  return d;
}

function tiles() {
  const us = DATA.rows.find((r) => r[1] === DATA.ourTeamId);
  const box = $('tiles'); box.textContent = '';
  const byRank = (k) => DATA.rows[k - 1];
  const g = byRank(DATA.medalRanks.gold), s = byRank(DATA.medalRanks.silver), b = byRank(DATA.medalRanks.bronze);
  if (us) {
    const med = medalOf(us[0]);
    const gap = g[4] - us[4];
    const moved = us[7] != null ? us[7] - us[0] : 0;
    box.append(tile('Our rank', `#${us[0]}`, `${fmt(us[4])} points, ${us[5]} submissions` + (moved ? ` · ${moved > 0 ? 'up' : 'down'} ${Math.abs(moved)} today` : ''), ` of ${DATA.teams.toLocaleString()}`));
    box.append(tile('To gold', gap > 0 ? `+${fmt(gap)}` : 'In the zone', gap > 0 ? `points needed to pass the gold line (${fmt(g[4])})` : `${med === 'gold' ? 'currently gold' : ''}`));
  }
  const wk = weekAgo();
  if (wk && wk.gold != null) {
    const dg = g[4] - wk.gold, mine = us ? us[4] - (weekAgoScore(DATA.ourTeamId) ?? us[4]) : 0;
    box.append(tile('Gold line, past week', `${dg >= 0 ? '+' : ''}${fmt(dg)}`, `the gold line ${dg >= 0 ? 'rose' : 'fell'} from ${fmt(wk.gold)} to ${fmt(g[4])}` + (us ? ` · we ${mine >= 0 ? 'gained' : 'lost'} ${fmt(Math.abs(mine))}` : '')));
  }
  box.append(tile('Gold line', fmt(g[4]), `rank ${DATA.medalRanks.gold}: ${g[2]}`));
  box.append(tile('Silver line', fmt(s[4]), `rank ${DATA.medalRanks.silver}`));
  box.append(tile('Bronze line', fmt(b[4]), `rank ${DATA.medalRanks.bronze}`));
  box.append(tile('Leader', fmt(DATA.rows[0][4]), DATA.rows[0][2]));
}

// The snapshot closest to a week ago, and our score then.
function weekAgo() {
  const want = Date.now() - 7 * 864e5;
  return HIST.snaps.length ? HIST.snaps.reduce((a, b) => (Math.abs(Date.parse(b.t) - want) < Math.abs(Date.parse(a.t) - want) ? b : a)) : null;
}
function weekAgoScore(id) {
  const want = Date.now() - 7 * 864e5; let v = null;
  for (const p of HIST.trails[id]?.pts || []) { if (Date.parse(p[0]) <= want) v = p[1]; else break; }
  return v;
}

function tipAt(tip, host, html, x, y) {
  tip.textContent = ''; tip.append(...html); tip.style.display = 'block';
  const w = host.clientWidth;
  tip.style.left = Math.min(Math.max(4, x + 12), w - tip.offsetWidth - 4) + 'px';
  tip.style.top = Math.max(4, y - tip.offsetHeight - 10) + 'px';
}

function curve() {
  const host = $('curve'), tip = $('curveTip');
  host.querySelector('svg')?.remove();
  const W = 960, H = 380, L = 48, R = 16, T = 14, B = 34, n = DATA.teams;
  const x = (rank) => L + (Math.log(rank) / Math.log(n)) * (W - L - R);
  const ymax = Math.ceil(DATA.rows[0][4] / 10) * 10;
  const y = (sc) => T + (1 - sc / ymax) * (H - T - B);
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Score by rank' });
  const mr = DATA.medalRanks;
  for (const [name, a, b] of [['gold', 1, mr.gold], ['silver', mr.gold, mr.silver], ['bronze', mr.silver, mr.bronze]]) {
    svg.append(el('rect', { x: x(a), y: T, width: x(b) - x(a), height: H - T - B, fill: css(`--m-${name}`), opacity: 0.13 }));
    svg.append(el('text', { x: (x(a) + x(b)) / 2, y: T + 12, 'text-anchor': 'middle' }, name));
  }
  for (let v = 0; v <= ymax; v += 10) {
    svg.append(el('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: css('--l-grid') }));
    svg.append(el('text', { x: L - 6, y: y(v) + 4, 'text-anchor': 'end' }, v));
  }
  for (const t of [1, 10, 100, 1000, n]) {
    if (t > n) continue;
    svg.append(el('line', { x1: x(t), x2: x(t), y1: H - B, y2: H - B + 4, stroke: css('--l-axis') }));
    svg.append(el('text', { x: x(t), y: H - B + 17, 'text-anchor': t === n ? 'end' : 'middle' }, t === n ? n.toLocaleString() : t.toLocaleString()));
  }
  svg.append(el('text', { x: (L + W - R) / 2, y: H - 2, 'text-anchor': 'middle' }, 'rank (log scale)'));
  const dot = css('--l-dot');
  const pts = DATA.rows.filter((r) => r[1] !== DATA.ourTeamId);
  const g = el('g', { fill: dot, opacity: 0.55 });
  for (const r of pts) g.append(el('circle', { cx: x(r[0]), cy: y(r[4]), r: 2.1 }));
  svg.append(g);
  const us = DATA.rows.find((r) => r[1] === DATA.ourTeamId);
  if (us) {
    svg.append(el('circle', { cx: x(us[0]), cy: y(us[4]), r: 7, fill: css('--l-us'), stroke: css('--l-surface'), 'stroke-width': 2 }));
    svg.append(el('text', { x: x(us[0]) + 12, y: y(us[4]) - 8, class: 't-us' }, `us · #${us[0]} · ${fmt(us[4])}`));
  }
  const hit = el('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent' });
  hit.addEventListener('mousemove', (e) => {
    const bb = svg.getBoundingClientRect(), k = W / bb.width;
    const gx = (e.clientX - bb.left) * k;
    const rank = Math.min(n, Math.max(1, Math.round(Math.exp(((gx - L) / (W - L - R)) * Math.log(n)))));
    const r = DATA.rows[rank - 1];
    tipAt(tip, host, [h('b', null, r[2]), h('span', null, `#${r[0]} · ${fmt(r[4])} points · ${r[5]} submissions`)], e.clientX - bb.left, e.clientY - bb.top);
  });
  hit.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  svg.append(hit);
  host.prepend(svg);
}

function trend() {
  const host = $('trend'), tip = $('trendTip'), note = $('trendNote'), leg = $('trendLegend');
  host.querySelector('svg')?.remove(); leg.textContent = '';
  const snaps = HIST.snaps.filter((x) => x.t >= '2026-06-01');
  if (snaps.length < 2) {
    note.textContent = 'History starts the first time we saved the board, so there is only one point so far. This fills in as snapshots accumulate.';
    host.style.display = 'none'; return;
  }
  host.style.display = '';
  const t0 = Date.parse(snaps[0].t), tLast = Date.parse(snaps[snaps.length - 1].t), t1 = Math.max(tLast, CLOSE);
  note.textContent = `Top score, the three medal lines and our own score since ${new Date(t0).toLocaleDateString(undefined, { month: 'long', day: 'numeric' })}. The right edge is the close (${new Date(CLOSE).toLocaleDateString(undefined, { month: 'long', day: 'numeric' })}).`;
  const W = 960, H = 320, L = 48, R = 16, T = 12, B = 30;
  const ymax = Math.ceil(Math.max(...snaps.map((s) => s.top)) / 10) * 10;
  const x = (t) => L + ((t - t0) / Math.max(1, t1 - t0)) * (W - L - R);
  const y = (v) => T + (1 - v / ymax) * (H - T - B);
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Score over time' });
  for (let v = 0; v <= ymax; v += 10) {
    svg.append(el('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: css('--l-grid') }));
    svg.append(el('text', { x: L - 6, y: y(v) + 4, 'text-anchor': 'end' }, v));
  }
  for (const f of [0, 0.25, 0.5, 0.75, 1]) {
    const t = t0 + f * (t1 - t0);
    svg.append(el('text', { x: x(t), y: H - 8, 'text-anchor': f === 0 ? 'start' : f === 1 ? 'end' : 'middle' }, new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })));
  }
  const line = (pts, color, w, dash) => {
    if (pts.length < 2) return;
    svg.append(el('polyline', { points: pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(' '), fill: 'none', stroke: color, 'stroke-width': w, 'stroke-dasharray': dash || '', 'stroke-linejoin': 'round' }));
  };
  const series = [
    ['Leader', css('--l-text'), (s) => s.top, 2],
    ['Gold line', css('--m-gold'), (s) => s.gold, 2],
    ['Silver line', css('--m-silver'), (s) => s.silver, 2],
    ['Bronze line', css('--m-bronze'), (s) => s.bronze, 2],
  ];
  for (const [name, color, get, w] of series) {
    line(snaps.map((s) => [Date.parse(s.t), get(s)]).filter((p) => p[1] != null), color, w);
    const i = h('span'); i.append(Object.assign(h('span', 'sw'), { style: `border-color:${color}` }), name); leg.append(i);
  }
  const us = HIST.trails[DATA.ourTeamId];
  if (us) {
    const pts = us.pts.map((p) => [Date.parse(p[0]), p[1]]);
    pts.push([tLast, pts[pts.length - 1][1]]);
    line(pts, css('--l-us'), 3);
    const i = h('span'); i.append(Object.assign(h('span', 'sw'), { style: `border-color:${css('--l-us')}` }), 'Us'); leg.append(i);
  }
  const hit = el('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent' });
  hit.addEventListener('mousemove', (e) => {
    const bb = svg.getBoundingClientRect(), k = W / bb.width;
    const t = t0 + (((e.clientX - bb.left) * k - L) / (W - L - R)) * (t1 - t0);
    const s = snaps.reduce((a, b) => (Math.abs(Date.parse(b.t) - t) < Math.abs(Date.parse(a.t) - t) ? b : a));
    tipAt(tip, host, [h('b', null, new Date(s.t).toLocaleString()), h('span', null, `Leader ${fmt(s.top)} · gold ${fmt(s.gold)} · silver ${fmt(s.silver)} · bronze ${fmt(s.bronze)}`)], e.clientX - bb.left, e.clientY - bb.top);
  });
  hit.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  svg.append(hit); host.prepend(svg);
}

// "Today so far": biggest movers against the end of the previous UTC day.
function recap() {
  const box = $('recap'); box.textContent = '';
  const g = DATA.medalRanks.gold;
  $('recapNote').textContent = 'Everything here compares the board now with where it stood at the end of the previous day (UTC).';
  const list = (title, items, fmtR) => {
    const d = h('div'); d.append(h('h3', null, title));
    if (!items.length) { d.append(h('div', 'empty', 'Nobody yet.')); box.append(d); return; }
    const ol = h('ol');
    for (const r of items) { const li = h('li'); li.append(h('span', null, r[2]), h('span', null, fmtR(r))); ol.append(li); }
    d.append(ol); box.append(d);
  };
  const known = DATA.rows.filter((r) => r[7] != null);
  list('Biggest point gains', known.filter((r) => r[4] - r[8] > 0.005).sort((a, b) => (b[4] - b[8]) - (a[4] - a[8])).slice(0, 6), (r) => `+${fmt(r[4] - r[8])} → ${fmt(r[4])}`);
  list('Biggest climbers', known.filter((r) => r[7] - r[0] > 0).sort((a, b) => (b[7] - b[0]) - (a[7] - a[0])).slice(0, 6), (r) => `▲ ${r[7] - r[0]} → #${r[0]}`);
  list('Into the gold zone', known.filter((r) => r[7] > g && r[0] <= g), (r) => `#${r[7]} → #${r[0]}`);
  list('New in the top 500', DATA.rows.filter((r) => r[7] == null && r[0] <= 500).slice(0, 6), (r) => `#${r[0]} · ${fmt(r[4])}`);
}

// Watchlist: starred teams drawn as step lines of score over time.
function watchIds() {
  let ids = null;
  try { ids = JSON.parse(localStorage.getItem('arc3-lb-watch')); } catch (_) { /* private window */ }
  if (Array.isArray(ids)) return ids;
  const i = DATA.rows.findIndex((r) => r[1] === DATA.ourTeamId);
  const near = i < 0 ? [] : [DATA.rows[i - 1], DATA.rows[i], DATA.rows[i + 1]].filter(Boolean).map((r) => r[1]);
  return [...new Set([...DATA.rows.slice(0, 5).map((r) => r[1]), ...near])];
}
function saveWatch(ids) { try { localStorage.setItem('arc3-lb-watch', JSON.stringify(ids)); } catch (_) { /* ignore */ } }
function toggleWatch(id) {
  const ids = watchIds(), k = ids.indexOf(id);
  if (k >= 0) ids.splice(k, 1); else ids.push(id);
  saveWatch(ids); watch(); table();
}
const nameOf = (id) => (DATA.rows.find((r) => r[1] === id) || [0, 0, HIST.trails[id]?.name || id])[2];

function watch() {
  const host = $('watch'), tip = $('watchTip'), chips = $('watchChips');
  host.querySelector('svg')?.remove(); chips.textContent = '';
  const ids = watchIds().filter((id) => HIST.trails[id] && DATA.rows.some((r) => r[1] === id));
  if (!ids.length) { host.style.display = 'none'; chips.textContent = 'No teams starred yet.'; return; }
  host.style.display = '';
  const now = Date.parse(DATA.fetched), t0 = now - 75 * 864e5;
  const colors = new Map(ids.map((id, i) => [id, id === DATA.ourTeamId ? css('--l-us') : PALETTE[i % PALETTE.length]]));
  const valAt = (id, t) => { let v = null; for (const p of HIST.trails[id].pts) { if (Date.parse(p[0]) <= t) v = p; else break; } return v; };
  const W = 960, H = 340, L = 48, R = 16, T = 12, B = 30;
  const ymax = Math.max(10, Math.ceil(Math.max(...ids.map((id) => DATA.rows.find((r) => r[1] === id)[4])) / 10) * 10);
  const x = (t) => L + ((t - t0) / (now - t0)) * (W - L - R), y = (v) => T + (1 - v / ymax) * (H - T - B);
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Watched teams, score over time' });
  for (let v = 0; v <= ymax; v += 10) {
    svg.append(el('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: css('--l-grid') }));
    svg.append(el('text', { x: L - 6, y: y(v) + 4, 'text-anchor': 'end' }, v));
  }
  for (const f of [0, 0.25, 0.5, 0.75, 1]) {
    const t = t0 + f * (now - t0);
    svg.append(el('text', { x: x(t), y: H - 8, 'text-anchor': f === 0 ? 'start' : f === 1 ? 'end' : 'middle' }, new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })));
  }
  for (const id of ids) {
    const col = colors.get(id), pts = HIST.trails[id].pts.map((p) => [Date.parse(p[0]), p[1]]);
    const path = []; let last = null;
    for (const [t, v] of pts) {
      if (t < t0) { last = v; continue; }
      if (!path.length && last != null) path.push([t0, last]);
      if (path.length) path.push([t, path[path.length - 1][1]]);
      path.push([t, v]);
    }
    if (!path.length && last != null) path.push([t0, last]);
    if (path.length) path.push([now, path[path.length - 1][1]]);
    if (path.length > 1) svg.append(el('polyline', { points: path.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(' '), fill: 'none', stroke: col, 'stroke-width': id === DATA.ourTeamId ? 3 : 2, 'stroke-linejoin': 'round' }));
    const chip = h('span', 'chip'); const sw = h('span', 'sw'); sw.style.borderColor = col;
    const cur = DATA.rows.find((r) => r[1] === id);
    chip.append(sw, `${cur[2]} · #${cur[0]} · ${fmt(cur[4])}`);
    const x_ = h('button', null, '×'); x_.title = 'Stop watching'; x_.addEventListener('click', () => toggleWatch(id)); chip.append(x_);
    chips.append(chip);
  }
  const hit = el('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent' });
  hit.addEventListener('mousemove', (e) => {
    const bb = svg.getBoundingClientRect(), t = t0 + ((((e.clientX - bb.left) * (W / bb.width)) - L) / (W - L - R)) * (now - t0);
    const rows = ids.map((id) => [id, valAt(id, t)]).filter((r) => r[1]).sort((a, b) => b[1][1] - a[1][1]);
    tipAt(tip, host, [h('b', null, new Date(t).toLocaleDateString()), ...rows.map(([id, p]) => h('div', null, `${nameOf(id)}: ${fmt(p[1])} (#${p[2]})`))], e.clientX - bb.left, e.clientY - bb.top);
  });
  hit.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  svg.append(hit); host.prepend(svg);
}

// Feed of score changes, newest first.
function whenText(iso) {
  if (iso.endsWith('T23:59:00Z')) return new Date(iso.slice(0, 10) + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  return ago(iso);
}
function feed() {
  const box = $('feed'); box.textContent = '';
  const top = $('feedTop').checked, cuts = DATA.medalRanks;
  const evs = EVENTS.filter((e) => !top || e.rankTo <= 50 || e.id === DATA.ourTeamId).slice().reverse();
  for (const e of evs.slice(0, feedShown)) {
    const d = h('div', 'ev' + (e.id === DATA.ourTeamId ? ' us' : ''));
    const gain = e.from == null ? null : e.to - e.from;
    d.append(h('span', 'w', whenText(e.t)), h('span', 'n', e.name),
      h('span', 'd', e.from == null ? `new at ${fmt(e.to)}` : `${fmt(e.from)} → ${fmt(e.to)} (${gain >= 0 ? '+' : ''}${fmt(gain)})`),
      h('span', 'd', e.rankFrom == null ? `#${e.rankTo}` : e.rankFrom === e.rankTo ? `#${e.rankTo}` : `#${e.rankFrom} → #${e.rankTo}`));
    if (e.rankFrom != null && e.rankFrom > cuts.gold && e.rankTo <= cuts.gold) d.append(h('span', 'tag', 'into gold zone'));
    else if (e.rankFrom != null && e.rankFrom > cuts.silver && e.rankTo <= cuts.silver) d.append(h('span', 'tag', 'into silver zone'));
    else if (e.rankFrom != null && e.rankFrom > cuts.bronze && e.rankTo <= cuts.bronze) d.append(h('span', 'tag', 'into bronze zone'));
    box.append(d);
  }
  if (!evs.length) box.append(h('div', 'empty', 'No moves recorded yet.'));
  $('feedMore').style.display = evs.length > feedShown ? '' : 'none';
}

function table() {
  const t = $('table'); t.textContent = '';
  const q = $('q').value.trim().toLowerCase(), moversOnly = $('moversOnly').checked;
  let rows = DATA.rows.filter((r) => (!q || r[2].toLowerCase().includes(q) || r[6].toLowerCase().includes(q)) && (!moversOnly || (r[7] != null && r[7] !== r[0])));
  const head = h('tr');
  for (const [name, cls] of [['', ''], ['Rank', 'num'], ['Today', 'num'], ['Team', ''], ['Score', 'num'], ['Subs', 'num'], ['Last submission', ''], ['Members', 'mem']]) head.append(Object.assign(h('th', cls, name)));
  t.append(head);
  const edges = new Set([DATA.medalRanks.gold, DATA.medalRanks.silver, DATA.medalRanks.bronze]);
  const page = rows.slice(0, shown);
  const mine = DATA.rows.find((r) => r[1] === DATA.ourTeamId);
  if (mine && !q && !moversOnly && !page.includes(mine)) page.unshift(mine);   // keep us pinned on top
  for (const r of page) {
    const tr = h('tr', r[1] === DATA.ourTeamId ? 'us' : '');
    if (edges.has(r[0])) { tr.classList.add('edge'); tr.style.setProperty('--edgec', css(`--m-${medalOf(r[0])}`)); }
    const starTd = h('td'); const wid = watchIds();
    const star = h('button', 'lb-star' + (wid.includes(r[1]) ? ' on' : ''), wid.includes(r[1]) ? '★' : '☆');
    if (HIST.trails[r[1]]) { star.title = 'Watch this team'; star.addEventListener('click', () => toggleWatch(r[1])); } else { star.disabled = true; star.title = 'Only the top 300 and our team are tracked over time'; }
    starTd.append(star);
    const rk = h('td', 'num'); const m = medalOf(r[0]);
    if (m) { const d = h('span', 'lb-medal'); d.style.background = css(`--m-${m}`); rk.append(d); }
    rk.append(String(r[0]));
    const mv = h('td', 'num'); const dlt = r[7] != null ? r[7] - r[0] : 0;
    if (dlt) { mv.className = 'num ' + (dlt > 0 ? 'up' : 'down'); mv.textContent = `${dlt > 0 ? '▲' : '▼'} ${Math.abs(dlt)}`; }
    tr.append(starTd, rk, mv, h('td', 'team', r[2]), h('td', 'num', fmt(r[4])), h('td', 'num', String(r[5])), h('td', null, r[3].slice(0, 16).replace('T', ' ')), h('td', 'mem', r[6].replaceAll(',', ', ')));
    t.append(tr);
  }
  $('more').style.display = rows.length > shown ? '' : 'none';
  $('more').textContent = `Show more (${(rows.length - shown).toLocaleString()} left)`;
}

$('q').addEventListener('input', () => { shown = PAGE; table(); });
$('moversOnly').addEventListener('change', () => { shown = PAGE; table(); });
$('feedTop').addEventListener('change', () => { feedShown = 30; feed(); });
$('feedMore').addEventListener('click', () => { feedShown += 60; feed(); });
$('more').addEventListener('click', () => { shown += 200; table(); });
new MutationObserver(() => { if (DATA) { curve(); watch(); trend(); table(); } }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
load().catch((e) => { $('updated').textContent = 'Could not load'; const d = h('p', 'err', `Leaderboard data failed to load: ${e.message}`); $('tiles').after(d); });
