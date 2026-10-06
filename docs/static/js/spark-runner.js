/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: The Mode explorer's Play row and results list (docs/mode-explorer.html, Queue view). Talks only to the
  site's own relay, /api/v1/spark-runner/* (railway/spark_runner.py), which forwards over the ARC tailnet to the
  Spark runner on Jethro (tools/spark_runner/server.py) and keeps every job it sees in the site's database.
  - renderPlayRow: the Play button with two small inline fields (samples, turn cap) next to it, the runner key
    button, and one line saying what Play will do or why it is off (runner unreachable, no starting point, replay
    not verified, held-out game). Play sends the queue (each item's mode text, the Stock text it is diffed against,
    and its settings), the Stock tail, the version, samples and caps; the action and minute caps keep their
    defaults. It needs the runner key, asked once and kept in this browser; the runner checks it.
  - renderResults: everything that ran for the open game's stuck level, newest first, for anyone signed in: the
    live job (queued / running, per-sample turn, mode, actions, level) and every past job from the runner or, when
    the Sparks are off, from the site's storage — the queue that was run, samples cleared vs not, levels gained,
    actions, turns, next to the stock tally for that level. While anything is live it refreshes every few seconds.
  Each slot also carries the mode version it came from; the site stores the exact text and versions with the job,
  and every job card shows them (versions on the queue tags, the full wording in a fold-out).
  - Exact starts (added 6-Oct, Son): every job says whether it started from an EXACT level-start checkpoint (the
    request body, harness state and actions saved when some run cleared the level before) or from the snapshot
    whose conversation was rebuilt from stored transcripts; exact samples also say whether their first request
    matched the saved one. The Play note says which start Play will use (the chosen checkpoint: fewest actions from
    RESET, then fewest tokens) and the results header lists this game's levels that have exact starts. The runner
    line shows harvest (idle-time Stock runs that collect exact starts).
SRP/DRY check: Pass - mode text and settings come from mode-explorer.js (shared modes + the queue); the tally from
  stuck-levels.json; this file only sends, polls and draws. No results are invented: empty states say nothing ran.
*/

const API = new URL('../../api/v1/spark-runner/', import.meta.url);
const KEY_STORE = 'arc3-spark-runner-key';
const POLL_MS = 5000;
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

let stuckPoints = null;      // from /stuck-points, null until loaded, false if the runner cannot be reached
let health = null;
let pollTimer = null;
let resultsGame = null;      // the game the results box is showing; a poll for another game is dropped
// Play options survive the page's redraws (every queue edit redraws the Play row).
const opts = { samples: 10, max_turns: 20, max_actions: 250, max_minutes: 120 };

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

function pct(a, b) { return b ? `${Math.round((100 * a) / b)}%` : '–'; }
function plural(n, word) { return `${n} ${word}${n === 1 ? '' : 's'}`; }

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

function buildRequest(ctx) {
  const v = ctx.variant;
  // A mode with one wording is diffed against the Stock of that wording (base_variant), as custom modes always were.
  // `version` names the stored mode version the text came from; the site keeps it with the job (modes_store.py).
  const slotFor = (mode, settings) => {
    const base = mode.base || 'turn';
    const prompt = mode.variants[v].prompt;
    const stockTemplate = ctx.stockText(mode.base_variant || v, base);
    return { mode: mode.id, name: mode.name, base, prompt, stock_template: stockTemplate, settings: clampSettings(settings),
      version: ctx.versionOf(mode, v) };
  };
  const scheme = ctx.scheme.slots.map((slot) => {
    const m = ctx.findMode(slot.mode);
    if (!m) throw new Error(`the queue uses a mode that no longer exists (${slot.mode})`);
    return slotFor(m, ctx.slotSettings(slot));
  });
  const stock = ctx.findMode('stock');
  return {
    game: ctx.game.game, stuck_level: ctx.game.stuck_level, variant: v, scheme,
    stock: slotFor(stock, ctx.defaults(stock)), samples: opts.samples, max_turns: opts.max_turns,
    max_actions: opts.max_actions, max_minutes: opts.max_minutes, label: null,
  };
}

// Why Play is off for this game, or '' when it can run.
function exactStart(g, variant) {
  const point = Array.isArray(stuckPoints) ? stuckPoints.find(p => p.game === g.game) : null;
  const row = point && (point.exact_levels || []).find(x => x.level === g.stuck_level && x.variant === variant);
  return row ? row.chosen : null;
}

function blocked(g, variant) {
  const point = Array.isArray(stuckPoints) ? stuckPoints.find(p => p.game === g.game) : null;
  if (point && exactStart(g, variant) && (point.playable || !point.held_out)) return '';
  if (stuckPoints === false) return health && health.message ? `${health.message} Nothing can start; past results still show below.`
    : 'The Spark runner cannot be reached from the site right now, so nothing can start. Past results still show below.';
  if (stuckPoints === null) return 'Checking the Spark runner…';
  if (!point) return `No starting point exists for ${g.nickname} yet, so it cannot be played.`;
  if (!point.replay_verified) return `The starting point for ${g.nickname} has not passed its replay check, so it cannot be played.`;
  if (point.held_out && !point.playable) return `${g.nickname} is one of the eight held-out games, kept out of prompt tuning, so the runner does not play it.`;
  if (point.stuck_level !== g.stuck_level) return `The runner's starting point is level ${point.stuck_level}, not level ${g.stuck_level}; it needs rebuilding before this game can be played.`;
  return '';
}

function runnerLine() {
  if (!health) return '';
  if (health.ok === false) return '';
  const m = health.model || {};
  const busy = health.samples_running || health.samples_queued
    ? ` · ${health.samples_running} running, ${health.samples_queued} waiting` : ' · idle';
  const hv = health.harvest;
  const harvest = !hv ? '' : !hv.enabled ? ' · harvest off'
    : (hv.running || []).length ? ` · harvesting exact starts (${hv.running.map(r => r.game).join(', ')})` : '';
  return (m.reachable && m.serves_expected_model ? 'Sparks ready' : 'Runner up, model server not answering') + busy + harvest;
}

export function renderPlayRow(box, ctx) {
  box.textContent = '';
  const g = ctx.game, q = ctx.scheme;
  const why = blocked(g, ctx.variant);
  const ex = exactStart(g, ctx.variant);
  const play = h('button', 'mx-play', 'Play');
  play.disabled = !!why;
  const num = (label, key, min, max, title) => {
    const l = h('label', 'mx-inl'); l.title = title;
    const i = h('input'); i.type = 'number'; i.min = min; i.max = max; i.step = 1; i.value = opts[key]; i.inputMode = 'numeric';
    i.onchange = () => { const n = Math.round(+i.value); if (Number.isFinite(n) && n >= min && n <= max) opts[key] = n; else i.value = opts[key]; };
    l.append(i, h('span', null, label));
    return l;
  };
  const samples = num('samples', 'samples', 1, 20, 'How many times to play the level from the same starting point');
  const turns = num('turns max', 'max_turns', 1, 60, 'Model turns per sample before it stops (the queue counts toward this)');
  const keyBtn = h('button', 'mx-tool mx-keybtn', runnerKey() ? 'Key ✓' : 'Key');
  keyBtn.title = 'The Spark runner key, kept in this browser';
  keyBtn.onclick = () => askKey(() => renderPlayRow(box, ctx));
  const status = h('span', 'mx-runstatus', runnerLine());
  const row = h('div', 'mx-playline');
  row.append(play, samples, turns, keyBtn, status);
  box.append(row);
  const version = ctx.variant === 'son' ? "Son's" : "Franzen's";
  const note = h('p', 'mx-playnote', why || (q.slots.length
    ? `Plays the queue, one mode per turn from the start of level ${g.stuck_level}, then Stock until the level is cleared or a cap is hit. Uses ${version} wording.`
    : `Empty queue: Play runs Stock only from level ${g.stuck_level}, a baseline from the same starting point.`) +
    (why ? '' : ex ? ` Exact start: the conversation, board pictures and tool state saved when a run reached this level in ${ex.actions_to_reach} actions.`
      : ' Start: the snapshot, with the conversation rebuilt from stored transcripts (no exact start for this level yet).'));
  box.append(note);
  play.onclick = async () => {
    if (!runnerKey()) { askKey((ok) => { if (ok) play.onclick(); }); return; }
    // (exact or rebuilt is decided by the runner when the job is queued; the job card shows which)
    let req;
    try { req = buildRequest(ctx); } catch (e) { note.textContent = `Not sent: ${e.message}`; return; }
    play.disabled = true; note.textContent = 'Sending to the runner…';
    try {
      const r = await call('play', { method: 'POST', body: req, auth: true });
      note.textContent = `Queued on the Sparks: ${plural(r.queued_samples, 'sample')}. Watch it below.`;
      const res = document.getElementById('results');
      if (res) await refreshResults(res, ctx);
    } catch (e) {
      note.textContent = e.status === 401 ? 'The runner refused the key. Check it with Son or the Boss, then set it again.' : `Not started: ${e.message}`;
    } finally { play.disabled = !!blocked(g, ctx.variant); }
  };
}

// ---------------------------------------------------------------- results

export function renderResults(box, ctx) {
  if (resultsGame !== ctx.game.game) {
    box.textContent = '';
    box.append(h('h2', 'mx-resh', `Results · ${ctx.game.nickname}, level ${ctx.game.stuck_level}`), h('p', 'mx-sum', 'loading…'));
  }
  resultsGame = ctx.game.game;
  refreshResults(box, ctx);
}

async function refreshResults(box, ctx) {
  clearTimeout(pollTimer);
  const game = ctx.game.game;
  let data;
  const runs = ctx.loadRuns ? ctx.loadRuns(game) : Promise.resolve({});
  try { data = await call(`jobs?game=${encodeURIComponent(game)}`); data.records = await runs; }
  catch (e) {
    if (resultsGame !== game) return;
    box.textContent = '';
    box.append(h('h2', 'mx-resh', `Results · ${ctx.game.nickname}, level ${ctx.game.stuck_level}`), h('p', 'mx-sum', `Could not load results: ${e.message}`));
    return;
  }
  if (resultsGame !== game || !box.isConnected) return;
  drawResults(box, ctx, data);
  const live = (data.jobs || []).some(j => j.status === 'queued' || j.status === 'running');
  if (live) pollTimer = setTimeout(() => { if (resultsGame === game) refreshResults(box, ctx); }, POLL_MS);
}

function stockTally(g) {
  const p = (g.per_level || []).find(x => x.level === g.stuck_level);
  return p ? { cleared: p.cleared, n: p.n } : null;
}

function drawResults(box, ctx, data) {
  const g = ctx.game;
  box.textContent = '';
  box.append(h('h2', 'mx-resh', `Results · ${g.nickname}, level ${g.stuck_level}`));
  const st = stockTally(g);
  if (st) box.append(h('p', 'mx-sum', `Stock tally for this level: cleared in ${st.cleared} of ${st.n} full runs (${pct(st.cleared, st.n)}). Each run below starts at this level, so compare its cleared share with that.`));
  if (data.from_storage) box.append(h('p', 'mx-sum mx-warnline', `${data.message} Showing what the site stored earlier.`));
  const point = Array.isArray(stuckPoints) ? stuckPoints.find(p => p.game === g.game) : null;
  const exact = point ? (point.exact_levels || []).filter(x => x.variant === ctx.variant).sort((a, b) => a.level - b.level) : [];
  box.append(h('p', 'mx-sum', exact.length
    ? `Exact starts for ${g.nickname}: ${exact.map(x => `level ${x.level} (${x.chosen.actions_to_reach} actions from reset${x.count > 1 ? `, best of ${x.count}` : ''})`).join(', ')}.`
    : `No exact starts for ${g.nickname} yet; idle Spark time collects them.`));
  const all = (data.jobs || []).slice().sort((a, b) => String(b.created).localeCompare(String(a.created)));
  const jobs = all.filter(j => j.stuck_level === g.stuck_level);
  if (!jobs.length) box.append(h('p', 'mx-qempty mx-noruns', `Nothing has run on ${g.nickname} level ${g.stuck_level} yet. Build a queue and press Play.`));
  for (const j of jobs) box.append(jobCard(j, ctx, (data.records || {})[j.id]));
  const other = all.length - jobs.length;
  if (other) box.append(h('p', 'mx-sum', `${plural(other, 'other job')} for ${g.nickname} started from a different level and ${other === 1 ? 'is' : 'are'} not shown.`));
}

const OUTCOME = { cleared: 'cleared', won: 'cleared', action_cap: 'action cap', turn_cap: 'turn cap', time_cap: 'time cap', stopped: 'stopped', error: 'error' };

function queueTags(j, ctx, rec) {
  const wrap = h('span', 'mx-jobq');
  const tag = (name, id, slot) => {
    const m = ctx.findMode(id);
    const t = h('span', 'mx-jtag', name + (slot && slot.version ? ` v${slot.version}` : ''));
    t.style.setProperty('--mc', m ? m.color : '#6b7280');
    return t;
  };
  (j.scheme_summary || []).forEach((s, i) => wrap.append(tag(s.name || s.mode, s.mode, rec && rec.scheme[i]), h('span', 'mx-arrow', '→')));
  wrap.append(tag(j.scheme_summary && j.scheme_summary.length ? 'then Stock' : 'Stock only', 'stock', rec && rec.stock));
  return wrap;
}

// The exact wording a job ran, as recorded by the site when Play was pressed: each slot's mode version, who saved
// that version and when, its settings and full prompt text. Jobs from before recording started say so.
function wordingBlock(rec, ctx) {
  const det = h('details', 'mx-wording');
  if (!rec) { det.append(h('summary', 'muted', 'Wording: not recorded (started before mode versions were kept)')); return det; }
  const slots = rec.scheme.concat([{ ...rec.stock, name: (rec.scheme.length ? 'then ' : '') + (rec.stock.name || 'Stock') }]);
  const label = (s) => `${s.name || s.mode}${s.version ? ' v' + s.version : ''}`;
  const odd = slots.some(s => s.version_check === 'differs');
  det.append(h('summary', null, `Wording sent: ${slots.map(label).join(' → ')}${odd ? ' (some text differed from the saved version; the text below is what ran)' : ''}`));
  for (const s of slots) {
    const box = h('div', 'mx-wslot');
    const who = s.edited_by ? ctx.whoWhen(s.edited_by, s.edited_at) : 'not a saved version';
    box.append(h('div', 'mx-whead', `${label(s)} · ${who}${s.version_check === 'differs' ? ' · text differs from that saved version' : ''}`));
    const st = s.settings || {};
    box.append(h('div', 'mx-wset', `temp ${st.temperature ?? '–'} · ${st.thinking ? 'thinking' + (st.effort && st.effort !== 'default' ? ', ' + st.effort + ' effort' : '') + (st.thinking_budget ? ', ≤' + st.thinking_budget + ' tokens' : '') : 'no thinking'}` +
      ` · ${st.tool_calls != null ? st.tool_calls + ' tool calls' : 'any tool calls'} · ${st.actions != null ? '≤' + st.actions + ' actions' : 'any actions'}`));
    const pre = h('pre', 'mx-wtext', s.prompt || '');
    box.append(pre);
    det.append(box);
  }
  return det;
}

function jobCard(j, ctx, rec) {
  const card = h('div', 'card mx-job');
  const top = h('div', 'mx-jobtop');
  const when = new Date(j.created);
  const startKind = j.start_kind || (j.conversation_exact ? 'exact' : 'rebuilt');
  const sk = h('span', `chip mx-js ${startKind === 'rebuilt' ? 'queued' : 'done'}`, startKind === 'rebuilt' ? 'conversation rebuilt' : startKind === 'reset' ? 'from reset' : 'exact start');
  sk.title = startKind === 'rebuilt' ? 'Started from the snapshot: the game state is exact, the conversation was rebuilt from stored transcripts'
    : startKind === 'reset' ? 'Started from the first frame of the game' : `Started from an exact checkpoint${j.start_checkpoint ? ' (' + j.start_checkpoint + ')' : ''}: the saved request, harness state and actions`;
  top.append(h('span', `chip mx-js ${j.status}`, j.status), sk, queueTags(j, ctx, rec));
  card.append(top);
  const caps = j.caps || {};
  const meta = [isNaN(when) ? j.created : when.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }),
    j.variant === 'daniel' ? "Franzen's wording" : "Son's wording", plural(j.samples, 'sample')];
  if (caps.max_turns) meta.push(`up to ${caps.max_turns} turns`);
  if (j.by) meta.push(j.by);
  card.append(h('p', 'mx-jobmeta', meta.join(' · ')));
  if (j.label) card.append(h('p', 'mx-sum', j.label));
  card.append(wordingBlock(rec, ctx));

  const rows = j.sample_rows || [];
  const results = rows.map(r => r.result).filter(Boolean);
  const s = j.summary || {};
  const done = s.finished_samples ?? results.length;
  const st = stockTally(ctx.game);
  const line = h('p', 'mx-jobsum');
  if (done) {
    const cleared = s.cleared ?? results.filter(r => r.outcome === 'cleared' || r.outcome === 'won').length;
    const turns = results.length ? results.reduce((a, r) => a + (r.turns || 0), 0) / results.length : null;
    const b = h('b', null, `Cleared in ${cleared} of ${done} (${pct(cleared, done)})`);
    line.append(b, document.createTextNode(
      (st ? ` vs stock ${pct(st.cleared, st.n)}` : '') +
      ` · levels gained ${s.levels_gained ?? '–'} · mean actions ${s.mean_actions ?? '–'}` +
      (turns != null ? ` · mean turns ${Math.round(turns * 10) / 10}` : '') +
      (s.errors ? ` · ${plural(s.errors, 'error')}` : '') +
      (done < j.samples ? ` · ${j.samples - done} still to finish` : '')));
  } else line.textContent = j.status === 'queued' ? 'Waiting for a free slot on the Sparks.' : 'No sample has finished yet.';
  card.append(line);

  const table = h('table', 'mx-table mx-results');
  const tr = h('tr');
  for (const c of ['#', 'Result', 'Levels', 'Actions', 'Turns', 'Modes that ran', 'Time']) tr.append(h('th', null, c));
  const thead = h('thead'); thead.append(tr); table.append(thead);
  const body = h('tbody');
  for (const row of rows) {
    const r = row.result, p = row.progress || {};
    const t = h('tr');
    t.append(h('td', null, String(row.sample + 1)));
    const fr = r && r.first_request;
    const check = !fr ? '' : fr.equal ? ' · first request = saved' : fr.context_equal_except_last_message ? ' · context = saved' : ' · first request differs';
    if (r) t.append(h('td', `mx-out ${r.outcome}`, (OUTCOME[r.outcome] || r.outcome) + (r.error ? `: ${r.error.slice(0, 120)}` : '') + check));
    else if (row.state === 'running') t.append(h('td', 'mx-live', `running · turn ${p.turn ?? 0}${p.mode ? ' · ' + p.mode : ''} · level ${p.level ?? '–'}`));
    else t.append(h('td', 'muted', row.state || '–'));
    t.append(h('td', null, r ? String(r.levels_cleared) : '–'));
    t.append(h('td', null, r ? String(r.actions_used) : (row.state === 'running' ? String(p.actions ?? 0) : '–')));
    t.append(h('td', null, r ? String(r.turns) : (row.state === 'running' ? String(p.turn ?? 0) : '–')));
    t.append(h('td', 'mx-modescol', r ? (r.modes_run || []).join(', ') : '–'));
    t.append(h('td', null, r ? `${Math.round((r.seconds || 0) / 60)} min` : '–'));
    body.append(t);
  }
  table.append(body);
  if (rows.length) { const wrap = h('div', 'mx-tablewrap'); wrap.append(table); card.append(wrap); }

  if (j.status === 'queued' || j.status === 'running') {
    const cancel = h('button', 'mx-tool mx-danger', 'Cancel this job');
    cancel.onclick = async () => {
      if (!runnerKey()) { askKey(() => {}); return; }
      if (!confirm('Cancel the samples of this job that have not finished?')) return;
      try { await call(`jobs/${j.id}/cancel`, { method: 'POST', body: {}, auth: true }); await refreshResults(document.getElementById('results'), ctx); }
      catch (e) { alert(`Cancel failed: ${e.message}`); }
    };
    card.append(cancel);
  }
  return card;
}
