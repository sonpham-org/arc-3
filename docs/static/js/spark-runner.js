/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: The Mode explorer's Play button and results panel (docs/mode-explorer.html, Stuck levels view). Talks only
  to the site's own relay, /api/v1/spark-runner/* (railway/spark_runner.py), which forwards over the ARC tailnet to
  the Spark runner on Jethro (tools/spark_runner/server.py) and keeps every job it sees in the site's database.
  - Play sends the open game's scheme (each slot's mode text, the Stock text it is diffed against, and its settings),
    the Stock tail, the variant, the number of samples and the per-sample caps. It needs the runner key, asked once
    and kept in this browser (localStorage); the key is checked by the runner, never stored on the site.
  - The panel lists every job for the game, newest first, for anyone signed in to the site: queued / running /
    done, per-sample progress (turn, mode, actions, level) and, when done, the results table (cleared or not,
    levels gained, actions, turns, modes that ran), compared with the stock tally's clear rate for that level.
    While anything is queued or running it refreshes every few seconds.
  - Only games whose starting point exists and passed its replay check can be played, and only from the stuck level.
SRP/DRY check: Pass - mode text and settings come from mode-explorer.js (modes.json + the scheme); the tally from
  stuck-levels.json; this file only sends, polls and draws. No results are invented: empty states say nothing ran.
*/

const API = new URL('../../api/v1/spark-runner/', import.meta.url);
const KEY_STORE = 'arc3-spark-runner-key';
const POLL_MS = 5000;
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

let stuckPoints = null;      // from /stuck-points, null until loaded, false if the runner cannot be reached
let health = null;
let pollTimer = null;
const jobsByGame = new Map();
// Play options survive the page's frequent redraws (every scheme edit redraws the builder).
const opts = { variant: null, samples: 10, max_turns: 20, max_actions: 250, max_minutes: 120, label: '' };

function runnerKey() { try { return localStorage.getItem(KEY_STORE) || ''; } catch { return ''; } }
function setRunnerKey(v) { try { v ? localStorage.setItem(KEY_STORE, v) : localStorage.removeItem(KEY_STORE); } catch { /* private mode */ } }

async function call(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { Accept: 'application/json' };
  if (body) headers['Content-Type'] = 'application/json';
  if (auth) headers.Authorization = `Bearer ${runnerKey()}`;
  const r = await fetch(new URL(path, API), { method, headers, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' });
  const type = r.headers.get('Content-Type') || '';
  if (r.redirected || !type.includes('json')) throw new Error(r.status === 401 || r.redirected ? 'sign in to the site again' : `HTTP ${r.status}`);
  const data = await r.json();
  if (!r.ok) {
    const d = data.detail;
    const msg = Array.isArray(d) ? d.map(x => `${(x.loc || []).slice(1).join('.')}: ${x.msg}`).join('; ') : (d || data.message || data.error || `HTTP ${r.status}`);
    const err = new Error(msg); err.status = r.status; throw err;
  }
  return data;
}

export async function loadRunnerInfo() {
  try { health = await call('health'); } catch (e) { health = { ok: false, message: e.message }; }
  try { stuckPoints = (await call('stuck-points')).stuck_points || []; } catch { stuckPoints = false; }
}

async function loadJobs(game) {
  const data = await call(`jobs?game=${encodeURIComponent(game)}`);
  jobsByGame.set(game, data);
  return data;
}

function pct(a, b) { return b ? `${Math.round((100 * a) / b)}%` : '–'; }

// ---------------------------------------------------------------- key dialog

function askKey(onDone) {
  const dlg = document.getElementById('runnerdlg');
  dlg.textContent = '';
  const form = h('form', 'mx-form'); form.method = 'dialog';
  form.append(h('h2', null, 'Spark runner key'));
  form.append(h('p', 'mx-sum', 'Playing runs real games on the two DGX Sparks, so it needs the runner key. Ask Son or the Boss for it. ' +
    'It is kept in this browser only and sent with Play and Cancel; anyone signed in can watch results without it.'));
  const input = h('input'); input.type = 'password'; input.autocomplete = 'off'; input.required = true; input.value = runnerKey();
  input.placeholder = 'runner key';
  const lab = h('label', 'mx-field wide'); lab.append(h('span', 'mx-flabel', 'Key'), input);
  form.append(lab);
  const btns = h('div', 'mx-formbtns');
  const save = h('button', 'mx-play', 'Save key'); save.type = 'submit';
  const cancel = h('button', 'mx-tool', 'Cancel'); cancel.type = 'button'; cancel.onclick = () => dlg.close();
  const forget = h('button', 'mx-tool mx-danger', 'Forget key'); forget.type = 'button';
  forget.onclick = () => { setRunnerKey(''); dlg.close(); onDone(false); };
  btns.append(save, cancel); if (runnerKey()) btns.append(forget);
  form.append(btns);
  form.onsubmit = (e) => { e.preventDefault(); const v = input.value.trim(); if (!v) return; setRunnerKey(v); dlg.close(); onDone(true); };
  dlg.append(form);
  dlg.showModal();
  input.focus();
}

// ---------------------------------------------------------------- play

function clampSettings(s) {
  const n = (v) => (v == null || v === '' ? null : Number(v));
  return {
    temperature: n(s.temperature), thinking: !!s.thinking, effort: s.effort || 'default',
    thinking_budget: n(s.thinking_budget) && n(s.thinking_budget) >= 256 ? n(s.thinking_budget) : null,
    tool_calls: n(s.tool_calls) == null ? null : Math.max(1, n(s.tool_calls)),
    actions: n(s.actions) == null ? null : Math.max(1, n(s.actions)),
  };
}

function buildRequest(ctx, opts) {
  const v = opts.variant;
  const slotFor = (mode, settings) => {
    const custom = !!mode.custom;
    const prompt = mode.variants[v].prompt;
    const base = custom ? 'turn' : mode.base;
    const stockTemplate = custom ? ctx.DATA.stock[mode.base_variant || v].turn : ctx.DATA.stock[v][base];
    return { mode: mode.id, name: mode.name, base, prompt, stock_template: stockTemplate, settings: clampSettings(settings) };
  };
  const scheme = ctx.scheme.slots.map((slot) => {
    const m = ctx.findMode(slot.mode);
    if (!m) throw new Error(`the scheme uses a mode that no longer exists (${slot.mode})`);
    return slotFor(m, ctx.slotSettings(slot));
  });
  const stock = ctx.DATA.modes.find(m => m.id === 'stock');
  return {
    game: ctx.game.game, stuck_level: ctx.scheme.start_level, variant: v, scheme,
    stock: slotFor(stock, ctx.defaults(stock)), samples: opts.samples, max_turns: opts.max_turns,
    max_actions: opts.max_actions, max_minutes: opts.max_minutes, label: opts.label || null,
  };
}

// ---------------------------------------------------------------- panel

export function renderRunnerPanel(box, ctx) {
  box.textContent = '';
  const g = ctx.game, sc = ctx.scheme;
  const point = Array.isArray(stuckPoints) ? stuckPoints.find(p => p.game === g.game) : null;
  const head = h('div', 'mx-runhead');
  head.append(h('h3', 'mx-subh', 'Play on the Sparks'));
  const status = h('span', 'mx-runstatus');
  if (!health) status.textContent = 'checking the runner…';
  else if (health.ok === false) status.textContent = health.message || 'The Spark runner cannot be reached right now.';
  else {
    const m = health.model || {};
    status.textContent = (m.reachable && m.serves_expected_model ? 'Runner up, model server answering' : 'Runner up, but the model server is not answering')
      + ` · ${health.samples_running} sample(s) running, ${health.samples_queued} queued`;
  }
  head.append(status);
  box.append(head);

  // why Play may be off
  let why = '';
  if (stuckPoints === false) why = 'The Spark runner cannot be reached from the site right now, so nothing can start. Results already stored still show below.';
  else if (stuckPoints === null) why = 'Checking which starting points exist…';
  else if (!point) why = `No starting point exists for ${g.nickname}${g.stuck_level ? '' : ' (every level clears, so there is no stuck level)'}.`;
  else if (!point.replay_verified) why = `The starting point for ${g.nickname} has not passed its replay check.`;
  else if (point.held_out && !point.playable) why = `${g.nickname} is one of the eight held-out games; the runner keeps them out of prompt tuning, so it does not play them.`;
  else if (sc.start_level !== point.stuck_level) why = `Only the stuck level (level ${point.stuck_level}) has a starting point. Click it in the level strip to play from there.`;

  const form = h('div', 'mx-runform');
  const field = (label, el) => { const l = h('label', 'mx-field'); l.append(h('span', 'mx-flabel', label), el); return l; };
  const variant = h('select');
  for (const [k, t] of [['son', "Son's version"], ['daniel', "Franzen's version"]]) { const o = h('option', null, t); o.value = k; variant.append(o); }
  variant.value = opts.variant || ctx.variant;
  variant.onchange = () => { opts.variant = variant.value; };
  const num = (val, min, max) => { const i = h('input'); i.type = 'number'; i.min = min; i.max = max; i.step = 1; i.value = val; i.inputMode = 'numeric'; return i; };
  const samples = num(opts.samples, 1, 20), maxTurns = num(opts.max_turns, 1, 60), maxActions = num(opts.max_actions, 10, 1000),
    maxMinutes = num(opts.max_minutes, 5, 180);
  const label = h('input'); label.maxLength = 120; label.placeholder = 'optional note, e.g. probe twice then execute'; label.value = opts.label;
  samples.onchange = () => { opts.samples = +samples.value; };
  maxTurns.onchange = () => { opts.max_turns = +maxTurns.value; };
  maxActions.onchange = () => { opts.max_actions = +maxActions.value; };
  maxMinutes.onchange = () => { opts.max_minutes = +maxMinutes.value; };
  label.oninput = () => { opts.label = label.value; };
  form.append(field('Version', variant), field('Samples', samples), field('Turns per sample', maxTurns),
    field('Action cap per sample', maxActions),
    field('Minutes per sample', maxMinutes));
  const lab = field('Note', label); lab.classList.add('grow'); form.append(lab);
  box.append(form);

  const foot = h('div', 'mx-buildfoot');
  const play = h('button', 'mx-play', 'Play this scheme');
  play.disabled = !!why;
  const keyBtn = h('button', 'mx-tool', runnerKey() ? 'Runner key ✓' : 'Runner key');
  keyBtn.onclick = () => askKey(() => renderRunnerPanel(box, ctx));
  const note = h('span', 'mx-playnote', why || (sc.slots.length
    ? `Plays ${sc.slots.length} scheduled turn${sc.slots.length === 1 ? '' : 's'} from the start of level ${sc.start_level}, then Stock until the level is cleared or a cap is hit.`
    : `Empty schedule: this plays Stock only from level ${sc.start_level}, a baseline from the same starting point.`));
  play.onclick = async () => {
    if (!runnerKey()) { askKey((ok) => { if (ok) play.onclick(); }); return; }
    let req;
    try {
      req = buildRequest(ctx, { variant: variant.value, samples: +samples.value, max_turns: +maxTurns.value,
        max_actions: +maxActions.value,
        max_minutes: +maxMinutes.value, label: label.value.trim() });
    } catch (e) { note.textContent = `Not sent: ${e.message}`; return; }
    play.disabled = true; note.textContent = 'Sending to the runner…';
    try {
      const r = await call('play', { method: 'POST', body: req, auth: true });
      note.textContent = `Queued: job ${r.job}, ${r.queued_samples} sample(s).`;
      await refreshJobs(box.querySelector('.mx-jobs'), ctx);
    } catch (e) {
      note.textContent = e.status === 401 ? 'The runner refused the key. Check it with Son or the Boss, then set it again.' : `Not started: ${e.message}`;
    } finally { play.disabled = !!why; }
  };
  foot.append(play, keyBtn, note);
  box.append(foot);

  if (point) {
    const src = point.source || {};
    box.append(h('p', 'mx-why', point.source.kind === 'game_start'
      ? `Starting point: the start of the game (stuck at level 1), no earlier conversation.`
      : `Starting point: the board, history and retained functions of a recorded stock run (${src.run}) at the start of level ${point.stuck_level}, ` +
        `replayed in the game engine and checked against the recorded board. The model's earlier conversation is rebuilt from that run's ` +
        `stored transcripts (${point.turns} turn${point.turns === 1 ? '' : 's'}), so it is close to, not exactly, what the model saw.`));
  }

  const jobs = h('div', 'mx-jobs');
  box.append(jobs);
  refreshJobs(jobs, ctx);
}

async function refreshJobs(box, ctx) {
  if (!box) return;
  clearTimeout(pollTimer);
  let data;
  try { data = await loadJobs(ctx.game.game); }
  catch (e) { box.textContent = ''; box.append(h('p', 'mx-sum', `Could not load results: ${e.message}`)); return; }
  if (!box.isConnected) return;
  drawJobs(box, ctx, data);
  const live = (data.jobs || []).some(j => j.status === 'queued' || j.status === 'running');
  if (live) pollTimer = setTimeout(() => refreshJobs(box, ctx), POLL_MS);
}

function stockLine(g, level) {
  const p = (g.per_level || []).find(x => x.level === level);
  return p ? `Stock tally for level ${level}: cleared in ${p.cleared} of ${p.n} full runs (${pct(p.cleared, p.n)}).` : '';
}

function drawJobs(box, ctx, data) {
  box.textContent = '';
  const jobs = data.jobs || [];
  box.append(h('h3', 'mx-subh', `Runs on the Sparks for ${ctx.game.nickname}`));
  if (data.from_storage) box.append(h('p', 'mx-sum', `${data.message} Showing the results the site stored earlier.`));
  if (!jobs.length) { box.append(h('p', 'mx-empty', 'Nothing has run for this game yet.')); return; }
  for (const j of jobs) box.append(jobCard(j, ctx));
}

const OUTCOME = { cleared: 'cleared', won: 'cleared', action_cap: 'action cap', turn_cap: 'turn cap', time_cap: 'time cap', stopped: 'stopped', error: 'error' };

function jobCard(j, ctx) {
  const card = h('div', 'card mx-job');
  const top = h('div', 'mx-jobtop');
  const when = new Date(j.created);
  top.append(h('span', `chip mx-js ${j.status}`, j.status),
    h('b', null, `${j.scheme_summary.length ? j.scheme_summary.map(s => s.name || s.mode).join(' → ') + ' → Stock' : 'Stock only'}`),
    h('span', 'mx-of', ` · level ${j.stuck_level} · ${j.variant === 'son' ? "Son's version" : "Franzen's version"} · ${j.samples} sample${j.samples === 1 ? '' : 's'} · ` +
      `${isNaN(when) ? j.created : when.toLocaleString()}${j.by ? ' · ' + j.by : ''}`));
  card.append(top);
  if (j.label) card.append(h('p', 'mx-sum', j.label));

  const s = j.summary || {};
  const done = s.finished_samples || 0;
  const line = h('p', 'mx-jobsum');
  line.textContent = done
    ? `Cleared level ${j.stuck_level} in ${s.cleared} of ${done} finished sample${done === 1 ? '' : 's'} (${pct(s.cleared, done)}); ` +
      `levels gained ${s.levels_gained}; mean actions ${s.mean_actions}${s.errors ? `; ${s.errors} sample(s) ended in an error` : ''}. ` + stockLine(ctx.game, j.stuck_level)
    : 'No sample has finished yet. ' + stockLine(ctx.game, j.stuck_level);
  card.append(line);

  const table = h('table', 'mx-table mx-results');
  const tr = h('tr');
  for (const c of ['Sample', 'State', 'Outcome', 'Levels gained', 'Actions', 'Turns', 'Modes that ran', 'Time']) tr.append(h('th', null, c));
  const thead = h('thead'); thead.append(tr); table.append(thead);
  const body = h('tbody');
  for (const row of j.sample_rows || []) {
    const r = row.result, p = row.progress || {};
    const t = h('tr');
    t.append(h('td', null, String(row.sample + 1)));
    const live = row.state === 'running' ? `${p.status || 'running'} · turn ${p.turn ?? 0}${p.mode ? ' · ' + p.mode : ''} · ${p.actions ?? 0} actions · level ${p.level ?? '–'}` : row.state;
    t.append(h('td', null, live));
    t.append(h('td', r ? `mx-out ${r.outcome}` : 'muted', r ? (OUTCOME[r.outcome] || r.outcome) + (r.error ? `: ${r.error.slice(0, 120)}` : '') : '–'));
    t.append(h('td', null, r ? String(r.levels_cleared) : '–'));
    t.append(h('td', null, r ? String(r.actions_used) : (row.state === 'running' ? String(p.actions ?? 0) : '–')));
    t.append(h('td', null, r ? String(r.turns) : '–'));
    t.append(h('td', null, r ? (r.modes_run || []).join(', ') : '–'));
    t.append(h('td', null, r ? `${Math.round((r.seconds || 0) / 60)} min` : '–'));
    body.append(t);
  }
  table.append(body);
  const wrap = h('div', 'mx-tablewrap'); wrap.append(table);
  card.append(wrap);

  if (j.status === 'queued' || j.status === 'running') {
    const cancel = h('button', 'mx-tool mx-danger', 'Cancel this job');
    cancel.onclick = async () => {
      if (!runnerKey()) { askKey(() => {}); return; }
      if (!confirm('Cancel the samples of this job that have not finished?')) return;
      try { await call(`jobs/${j.id}/cancel`, { method: 'POST', body: {}, auth: true }); await refreshJobs(card.parentElement, ctx); }
      catch (e) { alert(`Cancel failed: ${e.message}`); }
    };
    card.append(cancel);
  }
  return card;
}
