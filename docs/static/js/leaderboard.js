// Leaderboard tab: reads data/leaderboard/latest.json + history.json (written by scripts/leaderboard_snapshot.py).
const NS = 'http://www.w3.org/2000/svg';
const $ = (id) => document.getElementById(id);
const PAGE = 100;
let DATA, HIST, shown = PAGE;

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
  [DATA, HIST] = await Promise.all([get('latest.json'), get('history.json')]);
  $('updated').textContent = `Saved ${ago(DATA.fetched)} · ${DATA.teams.toLocaleString()} teams`;
  tiles(); curve(); trend(); table();
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
  box.append(tile('Gold line', fmt(g[4]), `rank ${DATA.medalRanks.gold}: ${g[2]}`));
  box.append(tile('Silver line', fmt(s[4]), `rank ${DATA.medalRanks.silver}`));
  box.append(tile('Bronze line', fmt(b[4]), `rank ${DATA.medalRanks.bronze}`));
  box.append(tile('Leader', fmt(DATA.rows[0][4]), DATA.rows[0][2]));
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
  const snaps = HIST.snaps;
  if (snaps.length < 2) {
    note.textContent = 'History starts the first time we saved the board, so there is only one point so far. This fills in as snapshots accumulate.';
    host.style.display = 'none'; return;
  }
  host.style.display = '';
  const t0 = Date.parse(snaps[0].t), t1 = Date.parse(snaps[snaps.length - 1].t);
  note.textContent = `Top score, the three medal lines and our own score, from ${new Date(t0).toLocaleDateString()} on.`;
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
    pts.push([t1, pts[pts.length - 1][1]]);
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

function table() {
  const t = $('table'); t.textContent = '';
  const q = $('q').value.trim().toLowerCase(), moversOnly = $('moversOnly').checked;
  let rows = DATA.rows.filter((r) => (!q || r[2].toLowerCase().includes(q) || r[6].toLowerCase().includes(q)) && (!moversOnly || (r[7] != null && r[7] !== r[0])));
  const head = h('tr');
  for (const [name, cls] of [['Rank', 'num'], ['Today', 'num'], ['Team', ''], ['Score', 'num'], ['Subs', 'num'], ['Last submission', ''], ['Members', 'mem']]) head.append(Object.assign(h('th', cls, name)));
  t.append(head);
  const edges = new Set([DATA.medalRanks.gold, DATA.medalRanks.silver, DATA.medalRanks.bronze]);
  const page = rows.slice(0, shown);
  const mine = DATA.rows.find((r) => r[1] === DATA.ourTeamId);
  if (mine && !q && !moversOnly && !page.includes(mine)) page.unshift(mine);   // keep us pinned on top
  for (const r of page) {
    const tr = h('tr', r[1] === DATA.ourTeamId ? 'us' : '');
    if (edges.has(r[0])) { tr.classList.add('edge'); tr.style.setProperty('--edgec', css(`--m-${medalOf(r[0])}`)); }
    const rk = h('td', 'num'); const m = medalOf(r[0]);
    if (m) { const d = h('span', 'lb-medal'); d.style.background = css(`--m-${m}`); rk.append(d); }
    rk.append(String(r[0]));
    const mv = h('td', 'num'); const dlt = r[7] != null ? r[7] - r[0] : 0;
    if (dlt) { mv.className = 'num ' + (dlt > 0 ? 'up' : 'down'); mv.textContent = `${dlt > 0 ? '▲' : '▼'} ${Math.abs(dlt)}`; }
    tr.append(rk, mv, h('td', 'team', r[2]), h('td', 'num', fmt(r[4])), h('td', 'num', String(r[5])), h('td', null, r[3].slice(0, 16).replace('T', ' ')), h('td', 'mem', r[6].replaceAll(',', ', ')));
    t.append(tr);
  }
  $('more').style.display = rows.length > shown ? '' : 'none';
  $('more').textContent = `Show more (${(rows.length - shown).toLocaleString()} left)`;
}

$('q').addEventListener('input', () => { shown = PAGE; table(); });
$('moversOnly').addEventListener('change', () => { shown = PAGE; table(); });
$('more').addEventListener('click', () => { shown += 200; table(); });
new MutationObserver(() => { if (DATA) { curve(); trend(); table(); } }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
load().catch((e) => { $('updated').textContent = 'Could not load'; const d = h('p', 'err', `Leaderboard data failed to load: ${e.message}`); $('tiles').after(d); });
