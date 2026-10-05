/*
Author: Claude Opus 5.5
Date: 05-October-2026
PURPOSE: Draws the Sprints tab (docs/sprints.html) from docs/static/data/sprints.json, the weekly plan to the
  ARC Prize 2026 ARC-AGI-3 Kaggle close. Shows a countdown to the deadline instant in the JSON, picks the current
  sprint by comparing today's local date with each sprint's start/end (ISO date strings, end inclusive), and renders
  one card per track (Son's model track, Boss + Bubba's harness track) with each item's status chip and "done means"
  line. Draft sprints carry a visible Draft chip. A standing tile reads our row from the leaderboard snapshot
  (ARC Explainer's /api/kaggle/<competition>/board, positional rows as in its shared/types.ts KaggleBoardRow) and is hidden if that fails.
SRP/DRY check: Pass — the plan lives only in sprints.json; leaderboard row layout and medal ranks follow
  the Explainer board format (rows[k-1] for a rank, r[1] team id, r[4] score); layout classes come from rl-shell.css.
*/

const $ = (id) => document.getElementById(id);
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const STATUS = { 'planned': '', 'in progress': 'active', 'done': 'done', 'dropped': 'dropped' };

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function fmtDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}

function tile(k, v, s, small) {
  const d = h('div', 'stat'); d.append(h('div', 'k', k));
  const vv = h('div', 'v', v); if (small) vv.append(h('small', null, small)); d.append(vv); d.append(h('div', 's', s));
  return d;
}

function countdown(deadline) {
  const ms = Date.parse(deadline) - Date.now();
  if (ms <= 0) return ['closed', '', 'The competition has closed.'];
  const days = Math.floor(ms / 86400000), hours = Math.floor((ms % 86400000) / 3600000);
  return [String(days), `d ${hours}h`, 'to the close, 23:59 UTC'];
}

function item(it) {
  const st = it.status || 'planned';
  const row = h('div', `sp-item ${st.replace(' ', '-')}`);
  const t = h('div', 't'); t.append(h('span', null, it.title)); t.append(h('span', `chip ${STATUS[st] ?? ''}`, st)); row.append(t);
  const d = h('div', 'd'); d.append(h('b', null, 'Done means: ')); d.append(document.createTextNode(it.done)); row.append(d);
  if (it.source) row.append(h('div', 'src', it.source));
  return row;
}

function sprint(sp, tracks, today) {
  const cur = today >= sp.start && today <= sp.end, past = today > sp.end;
  const sec = h('section', cur ? 'sp-cur' : past ? 'sp-past' : null);
  const head = h('div', 'sp-head');
  head.append(h('h2', null, `Sprint ${sp.n}${sp.final ? ' · final week' : ''}`));
  head.append(h('span', 'sp-dates', `${fmtDate(sp.start)} – ${fmtDate(sp.end)}`));
  if (cur) head.append(h('span', 'chip now', 'this week'));
  if (sp.draft) head.append(h('span', 'chip draft', 'draft'));
  sec.append(head);
  sec.append(h('p', 'sp-goal', sp.goal));
  const grid = h('div', 'sp-tracks');
  for (const tr of tracks) {
    const card = h('div', 'card');
    card.append(h('h3', null, tr.title));
    card.append(h('div', 'sp-owner', `${tr.owner} · ${tr.blurb}`));
    const list = sp.items[tr.id] || [];
    if (!list.length) card.append(h('div', 'empty', 'Nothing planned yet.'));
    list.forEach((it) => card.append(item(it)));
    grid.append(card);
  }
  sec.append(grid);
  return sec;
}

async function standing() {
  try {
    // The leaderboard data moved to ARC Explainer on 05-Oct-2026 (no longer committed here).
    const r = await fetch('https://arc.markbarney.net/api/kaggle/arc-prize-2026-arc-agi-3/board');
    if (!r.ok) return null;
    const lb = (await r.json()).latest;
    if (!lb) return null;
    const us = lb.rows.find((x) => x[1] === lb.ourTeamId);
    const silver = lb.rows[lb.medalRanks.silver - 1];
    if (!us) return null;
    return { lb, us, silver };
  } catch (e) { return null; }
}

async function load() {
  const r = await fetch('./static/data/sprints.json', { cache: 'no-store' });
  if (!r.ok) { $('sprints').append(h('div', 'empty', `Could not load the plan (HTTP ${r.status}).`)); return; }
  const plan = await r.json();
  const today = todayISO();
  const cur = plan.sprints.find((s) => today >= s.start && today <= s.end);
  $('updated').textContent = `Plan updated ${fmtDate(plan.updated)}`;
  $('base').textContent = plan.base;

  const box = $('tiles');
  const [cv, cs, cn] = countdown(plan.deadline);
  box.append(tile('Time left', cv, cn, cs));
  box.append(cur
    ? tile('This week', `Sprint ${cur.n}`, `${fmtDate(cur.start)} – ${fmtDate(cur.end)}${cur.draft ? ' · draft' : ''}`)
    : tile('This week', '—', today < plan.sprints[0].start ? 'Sprints have not started.' : 'All sprints are over.'));

  const st = await standing();
  if (st) {
    const { lb, us, silver } = st;
    box.append(tile('Kaggle standing', `#${us[0]}`, `${us[4].toFixed(2)} public · of ${lb.teams.toLocaleString()} teams`));
    if (silver) {
      const gap = silver[4] - us[4];
      box.append(tile('To the silver line', gap > 0 ? `+${gap.toFixed(2)}` : 'inside', `silver is rank ${lb.medalRanks.silver}, now ${silver[4].toFixed(2)}`));
    }
    $('lbnote').textContent = `Standing from the leaderboard snapshot of ${new Date(lb.fetched).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}.`;
  }

  const list = $('sprints');
  plan.sprints.forEach((sp) => list.append(sprint(sp, plan.tracks, today)));
}

load();
