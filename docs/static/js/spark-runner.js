/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: The Mode explorer's Play row and results list (docs/mode-explorer.html, Queue view). Talks only to the
  site's own relay, /api/v1/spark-runner/* (railway/spark_runner.py), which forwards over the ARC tailnet to the
  Spark runner on Jethro (tools/spark_runner/server.py) and keeps every job it sees in the site's database.
  - renderPlayRow: the Play button with two small inline fields (samples, turn cap) next to it, and one line saying what Play will do or why it is off (runner unreachable, no starting point, replay
    not verified, held-out game). Play sends the queue (each item's mode instructions and settings), the Stock tail,
    the wording, the prompt profile, samples and caps; the action and minute caps keep their
    defaults. Signing in to the site is all Play and Cancel need: the relay adds the runner's key on the server
    (the Boss, 6-Oct 11:01 ET: "It needs a runner key?!?"), so the page never asks for it or keeps it. A key left in
    this browser by the earlier key prompt is deleted on load.
  - renderResults: everything that ran for the open game's selected level, newest first, for anyone signed in: the
    live job (queued / running, per-sample turn, mode, actions, level) and every past job from the runner or, when
    the Sparks are off, from the site's storage — the queue that was run, samples cleared vs not, levels gained,
    actions, turns, next to the stock tally for that level. While anything is live it refreshes every few seconds.
  Prompt profiles (6-Oct, the Boss approved Astra's notes at 17:07 ET): each slot sends its mode's turn-only
  instructions (ctx.instructionsOf) and the mode version it came from, and the request names the prompt profile
  ("dedup", the default for every mode including Stock: every standing instruction once in the system prompt, the turn
  message only this turn's facts plus the mode's instructions; "original" only to compare with runs from before).
  The site stores the exact instructions and versions with the job, and every job card shows them and its profile.
  The Stock comparison says which prompts it was measured with: the full-run stock tally and every job before 6-Oct
  used the original prompts, so it is not a like-for-like baseline for dedup jobs until fresh Stock runs exist; the
  No-context Stock pool only counts jobs of the same profile.
  - previewRequest / renderPreview: the exact first request Play would send for a game, level, wording, context and
    mode, rendered by the runner's own harness with no model (runner /api/preview-request), drawn as its messages in
    order with the mode's instructions marked, plus the runner's duplicate check of that request. Used by the Prompts
    view and the mode editor.
  - Starting level (added 6-Oct, Son: "show all the levels as 1, 2, 3, 4, 5, 6 buttons"): every call takes the level the
    page has selected (ctx.level), not only the stuck level. levelStart says whether Play can start there and from what:
    an exact checkpoint for that game, level and wording; a fresh game for level 1 (the runner starts any public game
    from RESET); the stuck-level snapshot (conversation rebuilt); otherwise not, with the reason. sparkTally counts, per
    level, how many Spark samples (Play and idle-time harvest) played it and how many cleared it, from the same jobs
    answer the results list already loads, and hands it to the page through ctx.onJobs for the level buttons.
  - Exact starts (added 6-Oct, Son): every job says whether it started from an EXACT level-start checkpoint (the
    request body, harness state and actions saved when some run cleared the level before) or from the snapshot
    whose conversation was rebuilt from stored transcripts; exact samples also say whether their first request
    matched the saved one. The Play note says which start Play will use (the chosen checkpoint: fewest actions from
    RESET, then fewest tokens) and the results header lists this game's levels that have exact starts. The runner
    line shows harvest (idle-time Stock runs that collect exact starts).
  - Context (added 6-Oct, Son: "Right now future levels require previous context. Add a 'non-context' mode too."): a
    toggle next to Play, "Carry context" (everything above) or "No context". No context starts the chosen level at that
    level's start board, reached by a verified replay on the runner (an exact checkpoint's actions, else the original
    game's winning line; level 1 a fresh game), with a new game's first turn: no earlier turns, no notes, no kept
    functions. Every level of the trainable public games can start that way (the runner's replay-starts answer).
    Results are split by context: each kind gets its own section and its own Stock comparison (carried: the stock
    tally from full runs; no context: the Stock-only No-context Spark jobs at that level), and the Spark tally on the
    level buttons counts only jobs of the selected kind. Jobs from before the option carried context.
  - Hover tips (added 6-Oct, the Boss: "Are there tooltips or instructions on the page?"): Play (or why it is off),
    samples and turn cap, the runner line, each job's status or place in line, its queue, Cancel, and every column.
  - Guided tour (added 6-Oct, Son: "Have like a 'Help' icon, and do a demo"): playRequest hands the tour the request
    Play would send, to show it without sending; Play does nothing while ctx.demo() says the tour is running.
SRP/DRY check: Pass - mode text and settings come from mode-explorer.js (shared modes + the queue); the tally from
  stuck-levels.json; this file only sends, polls and draws. No results are invented: empty states say nothing ran.
*/

const API = new URL('../../api/v1/spark-runner/', import.meta.url);
const POLL_MS = 5000;
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

let stuckPoints = null;      // from /stuck-points, null until loaded, false if the runner cannot be reached
let health = null;
let pollTimer = null;
let exactStarts = null;     // /exact-starts rows (every game, not only those with a snapshot); null until loaded
let resultsKey = null;       // the game, level and context the results box is showing; a poll for another one is dropped
let replayStarts = null;     // /replay-starts: per trainable game, levels a No-context job can start from; null until loaded, false if unreachable
// Play options survive the page's redraws (every queue edit redraws the Play row).
const opts = { samples: 10, max_turns: 20, max_actions: 250, max_minutes: 120 };

// The key prompt that used to be here kept the runner key in localStorage; nothing reads it now, so drop it.
try { localStorage.removeItem('arc3-spark-runner-key'); } catch { /* private mode */ }

async function call(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' };
  if (body) headers['Content-Type'] = 'application/json';
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
  // the relay answers this one from its stored index when the Sparks are off, so the level buttons still show exact starts
  try { exactStarts = (await call('exact-starts')).levels || []; } catch { exactStarts = []; }
  try { replayStarts = (await call('replay-starts')).games || {}; } catch { replayStarts = false; }
}

// Jobs from before the context option carried context.
export function contextOf(j) { return (j && j.context) === 'none' ? 'none' : 'carried'; }
const CONTEXT_NAME = { carried: 'Carry context', none: 'No context' };

function pointOf(game) { return Array.isArray(stuckPoints) ? stuckPoints.find(p => p.game === game) || null : null; }
function exactRow(game, level, variant) {
  return (exactStarts || []).find(x => x.game === game && x.level === level && x.variant === variant && x.chosen) || null;
}

// Where Play would start this game at this level with this wording, or why it cannot:
// {ok, kind: 'exact' | 'reset' | 'rebuilt', chosen, count, why}. Mirrors the runner's play(): exact checkpoint first,
// then a fresh game for level 1, then the stuck-level snapshot if it passed its replay check.
// With context 'none': {ok, kind: 'replay', source: 'reset' | 'checkpoint' | 'winning_line'} when the runner has a
// verified replay to that level's start, else why not.
export function levelStart(g, level, variant, context = 'carried') {
  if (context === 'none') return replayStart(g, level, variant);
  const ex = exactRow(g.game, level, variant);
  if (ex) return { ok: true, kind: 'exact', chosen: ex.chosen, count: ex.count };
  if (level === 1) return { ok: true, kind: 'reset' };
  const point = pointOf(g.game);
  if (point && point.stuck_level === level && point.replay_verified) return { ok: true, kind: point.actions ? 'rebuilt' : 'reset' };
  if (exactStarts === null || stuckPoints === null) return { ok: false, unknown: true, why: 'Checking the Spark runner…' };
  if (stuckPoints === false) return { ok: false, unknown: true, why: 'The Spark runner cannot be reached right now, so whether this level can start is not known.' };
  if (point && point.stuck_level === level) return { ok: false, why: `The starting point for level ${level} has not passed its replay check, so it cannot be played.` };
  const other = exactRow(g.game, level, variant === 'son' ? 'daniel' : 'son');
  return { ok: false, why: other
    ? `Level ${level} has a saved start only for ${variant === 'son' ? "Franzen's" : "Son's"} wording; switch the version to play it.`
    : `No saved start for level ${level} yet. One is saved when a Spark run that began fresh or from an exact start clears level ${level - 1} (runs from a rebuilt start do not count); idle Spark time collects them.` };
}

function replayStart(g, level, variant) {
  if (level === 1) return { ok: true, kind: 'replay', source: 'reset' };
  if (replayStarts === null) return { ok: false, unknown: true, why: 'Checking the Spark runner…' };
  if (replayStarts === false) return { ok: false, unknown: true, why: 'The Spark runner cannot be reached right now, so whether this level can start without context is not known.' };
  const row = replayStarts[g.game];
  if (row && (row.playable_levels || []).includes(level)) {
    const ex = exactRow(g.game, level, variant) || exactRow(g.game, level, variant === 'son' ? 'daniel' : 'son');
    return ex ? { ok: true, kind: 'replay', source: 'checkpoint', chosen: ex.chosen } : { ok: true, kind: 'replay', source: 'winning_line' };
  }
  return { ok: false, why: row ? `Level ${level} has no verified replay to its start, so it cannot start without context.`
    : `${g.nickname} has no winning line on the runner, so only level 1 can start without context.` };
}

// Per level: Spark samples that played it and that cleared it. A sample that started at level L and cleared c levels
// cleared L..L+c-1; when it stopped on a cap before its last level it played level L+c without clearing it. Samples
// that ended in an error or were stopped count only the levels they did clear.
const CAPS = new Set(['action_cap', 'turn_cap', 'time_cap']);
// Only jobs of the given context count (harvest runs carry context), so the two kinds never mix on the level buttons.
export function sparkTally(jobs, context = 'carried') {
  const t = {};
  const add = (lv, cleared) => { const x = t[lv] || (t[lv] = { played: 0, cleared: 0 }); x.played++; if (cleared) x.cleared++; };
  for (const j of jobs || []) {
    if (contextOf(j) !== context) continue;
    const start = j.stuck_level || 1;
    const toPlay = j.kind === 'harvest' ? 99 : ((j.caps || {}).levels_to_play || 1);
    for (const row of j.sample_rows || []) {
      const r = row.result;
      if (!r) continue;
      const c = r.levels_cleared || 0;
      for (let k = 0; k < c; k++) add(start + k, true);
      if (CAPS.has(r.outcome) && c < toPlay) add(start + c, false);
    }
  }
  return t;
}

function pct(a, b) { return b ? `${Math.round((100 * a) / b)}%` : '–'; }
function plural(n, word) { return `${n} ${word}${n === 1 ? '' : 's'}`; }

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
  // Each slot is its mode's turn-only instructions (empty for Stock). `version` names the stored mode version the
  // text came from; the site keeps it with the job (modes_store.py).
  const slotFor = (mode, settings) => ({ mode: mode.id, name: mode.name, base: mode.base || 'turn',
    instructions: ctx.instructionsOf(mode, v), settings: clampSettings(settings), version: ctx.versionOf(mode, v) });
  const scheme = ctx.scheme.slots.map((slot) => {
    const m = ctx.findMode(slot.mode);
    if (!m) throw new Error(`the queue uses a mode that no longer exists (${slot.mode})`);
    return slotFor(m, ctx.slotSettings(slot));
  });
  const stock = ctx.findMode('stock');
  return {
    game: ctx.game.game, stuck_level: ctx.level, variant: v, scheme, context: ctx.context === 'none' ? 'none' : 'carried',
    prompt_profile: profileOf(ctx),
    stock: slotFor(stock, ctx.defaults(stock)), samples: opts.samples, max_turns: opts.max_turns,
    max_actions: opts.max_actions, max_minutes: opts.max_minutes, label: null,
  };
}

export const PROFILE_NAME = { dedup: 'Dedup prompts', original: 'Original prompts' };
export function profileOf(ctx) { return ctx.profile === 'original' ? 'original' : 'dedup'; }
// Jobs from before prompt profiles (6-Oct) ran the original prompts; the runner says so in each job view.
function jobProfile(j) { return j.prompt_profile === 'dedup' ? 'dedup' : 'original'; }

// The exact request Play would send now, for the guided tour's "what Play would send" (mode-tour.js); never sent there.
export function playRequest(ctx) { return buildRequest(ctx); }

// Why Play is off for this game and level, or '' when it can run.
function blocked(g, level, variant, context) {
  if (stuckPoints === false) return health && health.message ? `${health.message} Nothing can start; past results still show below.`
    : 'The Spark runner cannot be reached from the site right now, so nothing can start. Past results still show below.';
  if (stuckPoints === null) return 'Checking the Spark runner…';
  const ls = levelStart(g, level, variant, context);
  return ls.ok ? '' : ls.why;
}

function ordinal(n) {
  const t = n % 100, e = n % 10;
  return n + (t >= 11 && t <= 13 ? 'th' : e === 1 ? 'st' : e === 2 ? 'nd' : e === 3 ? 'rd' : 'th');
}

function runnerLine() {
  if (!health) return '';
  if (health.ok === false) return '';
  const m = health.model || {};
  const pq = health.play_queue || [];
  const busy = pq.length
    ? ` · playing ${pq[0].game}${pq[0].by ? ' for ' + pq[0].by : ''}${pq.length > 1 ? `, ${plural(pq.length - 1, 'job')} waiting in line` : ''}`
    : health.samples_running || health.samples_queued ? ` · ${health.samples_running} running, ${health.samples_queued} waiting` : ' · idle';
  const hv = health.harvest;
  const harvest = !hv ? '' : !hv.enabled ? ' · harvest off'
    : (hv.running || []).length ? ` · harvesting exact starts (${hv.running.map(r => r.game).join(', ')})` : '';
  return (m.reachable && m.serves_expected_model ? 'Sparks ready' : 'Runner up, model server not answering') + busy + harvest;
}

export function renderPlayRow(box, ctx) {
  box.textContent = '';
  const g = ctx.game, q = ctx.scheme;
  const lv = ctx.level;
  const cx = ctx.context === 'none' ? 'none' : 'carried';
  const why = blocked(g, lv, ctx.variant, cx);
  const ls = levelStart(g, lv, ctx.variant, cx);
  // Carry context / No context, right next to Play; switching redraws the level buttons, board and results
  const seg = h('div', 'mx-segs mx-ctxseg');
  seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Context');
  for (const [k, label] of Object.entries(CONTEXT_NAME)) {
    const b = h('button', 'mx-seg' + (k === cx ? ' on' : ''), label);
    b.setAttribute('aria-pressed', k === cx ? 'true' : 'false');
    b.title = k === 'carried' ? 'The model keeps what an earlier run of this game learned before this level: its conversation, notes and kept functions (exact start or snapshot).'
      : "The game board is at this level's start, but the model starts a clean conversation, as on a new game's first turn: no earlier turns, no notes, no kept functions.";
    b.onclick = () => { if (k !== cx && ctx.onContext) ctx.onContext(k); };
    seg.append(b);
  }
  const play = h('button', 'mx-play', 'Play');
  play.disabled = !!why;
  play.title = why ? `Play is off: ${why}` : 'Send this queue to the Sparks. One job runs at a time; if others are ahead, yours waits and its place in line is shown below.';
  const num = (label, key, min, max, title) => {
    const l = h('label', 'mx-inl'); l.title = title;
    const i = h('input'); i.title = title; i.setAttribute('aria-label', `${label}: ${title}`); i.type = 'number'; i.min = min; i.max = max; i.step = 1; i.value = opts[key]; i.inputMode = 'numeric';
    i.onchange = () => { const n = Math.round(+i.value); if (Number.isFinite(n) && n >= min && n <= max) opts[key] = n; else i.value = opts[key]; };
    l.append(i, h('span', null, label));
    return l;
  };
  const samples = num('samples', 'samples', 1, 20, 'How many times to play the level from the same starting point');
  const turns = num('turns max', 'max_turns', 1, 60, 'Model turns per sample before it stops (the queue counts toward this)');
  const prof = h('select', 'mx-profsel');
  prof.setAttribute('aria-label', 'Prompts');
  prof.title = 'Which prompts the runner sends. Dedup (the default, every mode including Stock): each standing instruction once, in the system prompt; the turn message has only this turn\'s facts and the mode\'s instructions. Original: the prompts as they were before 6-Oct, only to compare with old runs.';
  for (const [k, label] of Object.entries(PROFILE_NAME)) { const o = h('option', null, k === 'original' ? `${label} (old runs)` : label); o.value = k; prof.append(o); }
  prof.value = profileOf(ctx);
  prof.onchange = () => { if (ctx.onProfile) ctx.onProfile(prof.value); };
  const status = h('span', 'mx-runstatus', runnerLine());
  status.title = 'The Spark runner right now: whether the model answers, whose job is playing and how many wait in line.';
  const row = h('div', 'mx-playline');
  row.append(seg, play, samples, turns, prof, status);
  box.append(row);
  const version = ctx.variant === 'son' ? "Son's" : "Franzen's";
  const pname = profileOf(ctx) === 'dedup' ? 'dedup prompts' : 'the original prompts';
  const note = h('p', 'mx-playnote', why || (q.slots.length
    ? `Plays the queue, one mode per turn from the start of level ${lv}, then Stock until the level is cleared or a cap is hit. Uses ${version} wording and ${pname}.`
    : `Empty queue: Play runs Stock only from level ${lv}, a baseline from the same starting point, with ${pname}.`) +
    (why ? '' : ls.kind === 'replay' ? ` No context: the board is replayed to the start of level ${lv}` +
        (ls.source === 'reset' ? ' (the first frame)' : ls.source === 'checkpoint' ? ' from a saved start\'s actions' : ' along the recorded winning line') +
        ' and checked; the model gets only the system prompt and a first-turn prompt for that board.'
      : ls.kind === 'exact' ? ` Exact start: the conversation, board pictures and tool state saved when a run reached this level in ${ls.chosen.actions_to_reach} actions.`
      : ls.kind === 'reset' ? ' Start: a fresh game from its first frame, as a real run begins.'
      : ' Start: the snapshot, with the conversation rebuilt from stored transcripts (no exact start for this level yet).'));
  box.append(note);
  play.onclick = async () => {
    // the guided tour never sends anything (the page is inert then too; this is the second lock)
    if (ctx.demo && ctx.demo()) return;
    // (exact or rebuilt is decided by the runner when the job is queued; the job card shows which)
    let req;
    try { req = buildRequest(ctx); } catch (e) { note.textContent = `Not sent: ${e.message}`; return; }
    play.disabled = true; note.textContent = 'Sending to the runner…';
    try {
      const r = await call('play', { method: 'POST', body: req });
      // One Play job at a time gets every lane on the Sparks; the rest wait whole, first come first served.
      note.textContent = r.place_in_line > 1
        ? `Queued on the Sparks: ${plural(r.queued_samples, 'sample')}, ${ordinal(r.place_in_line)} in line. It starts when the ${r.place_in_line === 2 ? 'job' : 'jobs'} ahead of it finish. Watch it below.`
        : `Queued on the Sparks: ${plural(r.queued_samples, 'sample')}, starting now with the whole cluster. Watch it below.`;
      const res = document.getElementById('results');
      if (res) await refreshResults(res, ctx);
    } catch (e) {
      note.textContent = e.status === 401 && /runner key/.test(e.message)
        ? 'Not started: the Spark runner turned the site away. That is a site setup problem, not yours; tell Bubba.'
        : `Not started: ${e.message}`;
    } finally { play.disabled = !!blocked(g, lv, ctx.variant, cx); }
  };
}

// ---------------------------------------------------------------- results

function resTitle(ctx) { return `Results · ${ctx.game.nickname}, level ${ctx.level}`; }

export function renderResults(box, ctx) {
  const key = `${ctx.game.game}:${ctx.level}:${ctx.context}`;
  if (resultsKey !== key) {
    box.textContent = '';
    box.append(h('h2', 'mx-resh', resTitle(ctx)), h('p', 'mx-sum', 'loading…'));
  }
  resultsKey = key;
  refreshResults(box, ctx);
}

async function refreshResults(box, ctx) {
  clearTimeout(pollTimer);
  const game = ctx.game.game, key = `${game}:${ctx.level}:${ctx.context}`;
  let data;
  const runs = ctx.loadRuns ? ctx.loadRuns(game) : Promise.resolve({});
  // Play and harvest jobs together: Play jobs are listed below, both feed the level buttons' Spark tally.
  try { data = await call(`jobs?game=${encodeURIComponent(game)}&kind=all&limit=200`); data.records = await runs; }
  catch (e) {
    if (resultsKey !== key) return;
    box.textContent = '';
    box.append(h('h2', 'mx-resh', resTitle(ctx)), h('p', 'mx-sum', `Could not load results: ${e.message}`));
    return;
  }
  if (resultsKey !== key || !box.isConnected) return;
  const jobs = data.jobs || [];
  data.jobs = jobs.filter(j => (j.kind || 'play') === 'play');
  if (ctx.onJobs) ctx.onJobs(game, sparkTally(jobs, ctx.context === 'none' ? 'none' : 'carried'), jobs.filter(j => j.kind === 'harvest').length);
  drawResults(box, ctx, data);
  const live = data.jobs.some(j => j.status === 'queued' || j.status === 'running');
  if (live) pollTimer = setTimeout(() => { if (resultsKey === key) refreshResults(box, ctx); }, POLL_MS);
}

function stockTally(g, level) {
  const p = (g.per_level || []).find(x => x.level === level);
  return p ? { cleared: p.cleared, n: p.n } : null;
}

// Stock-only No-context Spark jobs at this level, pooled, optionally leaving one job out (its own card): the No-context
// Stock comparison. The full-run stock tally carries context from the start of the game, so it is never used here.
function noContextStock(jobs, level, skipId, profile) {
  let cleared = 0, n = 0;
  for (const j of jobs) {
    if (contextOf(j) !== 'none' || j.stuck_level !== level || j.id === skipId || (j.scheme_summary || []).length) continue;
    if (jobProfile(j) !== profile) continue;   // Stock under other prompts is a different baseline
    for (const row of j.sample_rows || []) {
      const r = row.result;
      if (!r || r.outcome === 'error') continue;
      n++; if (r.outcome === 'cleared' || r.outcome === 'won') cleared++;
    }
  }
  return n ? { cleared, n } : null;
}

// The Stock comparison for one context, as {line (header sentence), pct (for a job card) }.
// profile: the prompts the comparison is for (the job's own, or the one selected for Play in the header line).
function stockFor(ctx, jobs, context, skipId, profile = profileOf(ctx)) {
  const g = ctx.game, lv = ctx.level;
  const pn = profile === 'dedup' ? 'dedup prompts' : 'original prompts';
  if (context === 'none') {
    const st = noContextStock(jobs, lv, skipId, profile);
    return st ? { st, line: `Stock without context for this level, ${pn}: cleared in ${st.cleared} of ${st.n} Stock-only No-context samples (${pct(st.cleared, st.n)}).` }
      : { st: null, line: `No Stock comparison without context with ${pn} yet: nobody has played this level Stock-only in No-context mode with them. Play an empty queue with No context to get one. The full-run stock tally is not used here, because those runs carried context.` };
  }
  const st = stockTally(g, lv);
  const caveat = profile === 'dedup' ? ' Measured with the original prompts, before 6-Oct: not a like-for-like baseline for dedup jobs until fresh Stock runs with the dedup prompts exist.' : '';
  return { st, original: profile === 'dedup', line: st ? `Stock tally for this level: cleared in ${st.cleared} of ${st.n} full runs (${pct(st.cleared, st.n)}); those runs carried context from the start of the game, like the jobs here.${caveat}`
    : 'No stock tally for this level.' };
}

function drawResults(box, ctx, data) {
  const g = ctx.game, lv = ctx.level;
  const cur = ctx.context === 'none' ? 'none' : 'carried';
  box.textContent = '';
  box.append(h('h2', 'mx-resh', resTitle(ctx)));
  if (data.from_storage) box.append(h('p', 'mx-sum mx-warnline', `${data.message} Showing what the site stored earlier.`));
  const exact = (exactStarts || []).filter(x => x.game === g.game && x.variant === ctx.variant && x.chosen).sort((a, b) => a.level - b.level);
  box.append(h('p', 'mx-sum', exact.length
    ? `Exact starts for ${g.nickname}: ${exact.map(x => `level ${x.level} (${x.chosen.actions_to_reach} actions from reset${x.count > 1 ? `, best of ${x.count}` : ''})`).join(', ')}.`
    : `No exact starts for ${g.nickname} yet; idle Spark time collects them.`));
  const all = (data.jobs || []).slice().sort((a, b) => String(b.created).localeCompare(String(a.created)));
  const here = all.filter(j => j.stuck_level === lv);
  // One section per context, the selected one first; the other only when it has jobs here. Never mixed.
  for (const context of [cur, cur === 'none' ? 'carried' : 'none']) {
    const jobs = here.filter(j => contextOf(j) === context);
    if (context !== cur && !jobs.length) continue;
    const sec = h('section', 'mx-ctxsec');
    sec.append(h('h3', 'mx-ctxh', `${CONTEXT_NAME[context]}${context === cur ? '' : ' (the other kind; switch next to Play to start one)'}`));
    sec.append(h('p', 'mx-sum', stockFor(ctx, all, context).line));
    if (!jobs.length) sec.append(h('p', 'mx-qempty mx-noruns', `Nothing has run on ${g.nickname} level ${lv} ${context === 'none' ? 'without context' : 'with context carried'} yet. Build a queue and press Play.`));
    for (const j of jobs) sec.append(jobCard(j, ctx, (data.records || {})[j.id], stockFor(ctx, all, context, j.id, jobProfile(j))));
    box.append(sec);
  }
  const other = all.length - here.length;
  if (other) box.append(h('p', 'mx-sum', `${plural(other, 'other job')} for ${g.nickname} started from a different level and ${other === 1 ? 'is' : 'are'} not shown; pick that level above to see ${other === 1 ? 'it' : 'them'}.`));
}

const STATUS_TIP = { queued: 'Queued: sent to the Sparks and about to start.', running: 'Running on the Sparks now; this list refreshes by itself.',
  done: 'Finished: every sample has a result.', cancelled: 'Cancelled: samples that had not finished were stopped.', failed: 'The job failed; see the rows for the error.',
  preempted: 'Stopped early to make room on the Sparks; finished samples are kept.', interrupted: 'Cut short when the runner restarted; finished samples are kept.' };
const COLUMNS = [
  ['#', 'Sample number. Each sample plays the level once from the same start.'],
  ['Result', 'How the sample ended: cleared the level, hit a cap (actions, turns or time), was stopped, or hit an error.'],
  ['Levels', 'Levels this sample cleared.'],
  ['Actions', 'Game actions the sample used.'],
  ['Turns', 'Model turns the sample took (the queue plus the Stock turns after it).'],
  ['Modes that ran', 'The modes actually used, turn by turn.'],
  ['Time', 'How long the sample took, in minutes.'],
];
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
// that version and when, its settings and its instructions (jobs from before 6-Oct: the whole turn message it sent).
// Jobs from before recording started say so.
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
      ` · ${st.tool_calls != null ? st.tool_calls + ' tool calls' : 'any tool calls'} · ${st.actions != null ? '≤' + st.actions + ' actions' : 'any actions'}` +
      (s.lean ? ' · lean turn message (stock tool-call lines left out)' : '')));
    const instr = typeof s.instructions === 'string';
    const pre = h('pre', 'mx-wtext', instr ? (s.instructions || '(no instructions: Stock)') : s.prompt || '');
    if (!instr && s.prompt) box.append(h('div', 'mx-wset', 'Sent before 6-Oct as a whole turn message (original prompts):'));
    box.append(pre);
    det.append(box);
  }
  return det;
}

function jobCard(j, ctx, rec, st) {
  const card = h('div', 'card mx-job');
  const top = h('div', 'mx-jobtop');
  const when = new Date(j.created);
  const startKind = j.start_kind || (j.conversation_exact ? 'exact' : 'rebuilt');
  const sk = h('span', `chip mx-js ${startKind === 'rebuilt' ? 'queued' : 'done'}`, startKind === 'replay' ? 'no context'
    : startKind === 'rebuilt' ? 'conversation rebuilt' : startKind === 'reset' ? 'from reset' : 'exact start');
  sk.title = startKind === 'replay' ? `No context: the board was replayed to this level's start (${j.replay_source === 'checkpoint' ? "a saved start's actions" : j.replay_source === 'winning_line' ? 'the recorded winning line' : 'the first frame'}) and the model began a clean conversation`
    : startKind === 'rebuilt' ? 'Started from the snapshot: the game state is exact, the conversation was rebuilt from stored transcripts'
    : startKind === 'reset' ? 'Started from the first frame of the game' : `Started from an exact checkpoint${j.start_checkpoint ? ' (' + j.start_checkpoint + ')' : ''}: the saved request, harness state and actions`;
  const waiting = j.place_in_line > 1;
  const stChip = h('span', `chip mx-js ${j.status}`, waiting ? `${ordinal(j.place_in_line)} in line` : j.status);
  stChip.title = waiting ? `Place in line: ${plural(j.jobs_ahead, 'job')} ahead. The Sparks play one job at a time, first come first served.`
    : STATUS_TIP[j.status] || `Job status: ${j.status}`;
  const qt = queueTags(j, ctx, rec);
  qt.title = 'The queue this job ran, one mode per turn, with the version of each mode; Stock played the turns after it.';
  const pc = h('span', `chip mx-js ${jobProfile(j) === 'dedup' ? 'done' : 'queued'}`, jobProfile(j) === 'dedup' ? 'dedup prompts' : 'original prompts');
  pc.title = jobProfile(j) === 'dedup' ? 'Ran with the dedup prompts: each standing instruction once in the system prompt; the turn message only this turn\'s facts and the mode\'s instructions.'
    + (j.prompt_profile_assigned ? ` Queued before prompt profiles existed; given the default ${j.prompt_profile_assigned}.` : '')
    : 'Ran with the original prompts (the harness as it was before 6-Oct, standing instructions repeated in every turn message).';
  top.append(stChip, sk, pc, qt);
  card.append(top);
  const caps = j.caps || {};
  const meta = [isNaN(when) ? j.created : when.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }),
    j.variant === 'daniel' ? "Franzen's wording" : "Son's wording", plural(j.samples, 'sample')];
  if (caps.max_turns) meta.push(`up to ${caps.max_turns} turns`);
  if (j.by) meta.push(j.by);
  card.append(h('p', 'mx-jobmeta', meta.join(' · ')));
  const cmp = st && st.st;
  if (j.label) card.append(h('p', 'mx-sum', j.label));
  card.append(wordingBlock(rec, ctx));

  const rows = j.sample_rows || [];
  const results = rows.map(r => r.result).filter(Boolean);
  const s = j.summary || {};
  const done = s.finished_samples ?? results.length;
  const line = h('p', 'mx-jobsum');
  if (done) {
    const cleared = s.cleared ?? results.filter(r => r.outcome === 'cleared' || r.outcome === 'won').length;
    const turns = results.length ? results.reduce((a, r) => a + (r.turns || 0), 0) / results.length : null;
    const b = h('b', null, `Cleared in ${cleared} of ${done} (${pct(cleared, done)})`);
    line.append(b, document.createTextNode(
      (cmp ? ` vs stock ${contextOf(j) === 'none' ? 'without context' : 'with context'} ${pct(cmp.cleared, cmp.n)}${st.original ? ' (measured with the original prompts)' : ''}` : '') +
      ` · levels gained ${s.levels_gained ?? '–'} · mean actions ${s.mean_actions ?? '–'}` +
      (turns != null ? ` · mean turns ${Math.round(turns * 10) / 10}` : '') +
      (s.errors ? ` · ${plural(s.errors, 'error')}` : '') +
      (done < j.samples ? ` · ${j.samples - done} still to finish` : '')));
  } else line.textContent = waiting ? `Waiting in line: ${plural(j.jobs_ahead, 'job')} ahead. The Sparks play one person's job at a time, first come first served.`
    : j.status === 'queued' ? 'Starting on the Sparks.' : 'No sample has finished yet.';
  card.append(line);

  const table = h('table', 'mx-table mx-results');
  const tr = h('tr');
  for (const [c, tip] of COLUMNS) { const th = h('th', null, c); th.title = tip; tr.append(th); }
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
    cancel.title = 'Stop the samples of this job that have not finished. Finished samples and their results are kept.';
    cancel.onclick = async () => {
      if (!confirm('Cancel the samples of this job that have not finished?')) return;
      try { await call(`jobs/${j.id}/cancel`, { method: 'POST', body: {} }); await refreshResults(document.getElementById('results'), ctx); }
      catch (e) { alert(`Cancel failed: ${e.message}`); }
    };
    card.append(cancel);
  }
  return card;
}

// ---------------------------------------------------------------- request preview

// The exact first request Play would send for this game, level, wording, context, prompt profile and mode, rendered
// by the runner's own harness with no model (tools/spark_runner/render_requests.py via the runner's
// /api/preview-request), with the runner's duplicate check of it. Nothing is played or saved.
export async function previewRequest(p) {
  return call('preview-request', { method: 'POST', body: {
    game: p.game, level: p.level, variant: p.variant === 'daniel' ? 'daniel' : 'son',
    context: p.context === 'none' ? 'none' : 'carried', prompt_profile: p.profile === 'original' ? 'original' : 'dedup',
    mode: p.mode || 'stock', name: p.name || null, instructions: p.instructions || '' } });
}

const ROLE_NAME = { system: 'System prompt', user: 'User message', assistant: 'Model reply (earlier turn)', tool: 'Tool result (earlier turn)' };

// Draws a preview: a summary line, the duplicate check, the tool schema, then every message in order. A carried start
// sends the earlier conversation too; those messages are folded away, the system prompt and this turn's message open.
export function renderPreview(box, data, { header } = {}) {
  box.textContent = '';
  const req = data.request || {};
  const msgs = req.messages || [];
  const startName = { replay: 'no context (board replayed to the level start)', exact: 'exact saved start, its conversation carried',
    rebuilt: 'snapshot, conversation rebuilt from transcripts', reset: 'fresh game' }[data.start_kind] || data.start_kind;
  box.append(h('p', 'mx-sum', `${header || 'Exactly what Play would send first'}: ${data.game} level ${data.level}, ${data.variant === 'daniel' ? "Franzen's" : "Son's"} wording, ${startName}, ${PROFILE_NAME[data.prompt_profile] || data.prompt_profile}. ${msgs.length} messages; images are the board pictures, not shown here.`));
  const dc = data.duplicate_check || {};
  const bad = Object.entries(dc.fail_counts || {}).filter(([, n]) => n);
  const chk = h('p', `mx-sum ${dc.ok ? 'mx-okline' : 'mx-warnline'}`, dc.ok
    ? 'Duplicate check of this whole request (system prompt, tool definition, every message): no instruction is said twice.'
    : `Duplicate check of this whole request found repeats: ${bad.map(([k, n]) => `${n} ${k.replace(/_/g, ' ')}`).join(', ')}.`);
  chk.title = 'The runner checks the assembled request sentence by sentence and by meaning (tools/spark_runner/dupcheck.py). Per-turn facts that recur in earlier turns (step, level, valid actions) are allowed.';
  box.append(chk);
  const tools = h('details', 'mx-pvmsg mx-pvtool');
  const fn = ((req.tools || [])[0] || {}).function || {};
  tools.append(h('summary', null, `Tool definition · ${fn.name || 'python'}`), h('pre', 'mx-wtext', JSON.stringify(req.tools || [], null, 1)));
  box.append(tools);
  const last = msgs.length - 1;
  msgs.forEach((m, i) => {
    const open = i === 0 || i === last;
    const det = h('details', `mx-pvmsg mx-pv-${m.role}${i === last ? ' mx-pvlast' : ''}`);
    det.open = open && i === last;
    const label = i === last ? 'User message · this turn (what the mode adds is marked)' : ROLE_NAME[m.role] || m.role;
    det.append(h('summary', null, `${i + 1}. ${label}`));
    const body = h('div', 'mx-pvbody');
    for (const part of m.parts || []) {
      if (part.kind === 'image') { body.append(h('div', 'mx-pvimg', '[board image]')); continue; }
      const text = part.text || '';
      const k = i === last ? text.indexOf('Instructions for this turn (') : -1;
      if (k < 0) { body.append(h('pre', 'mx-wtext', text)); continue; }
      const end = text.indexOf('\n\n', k);
      if (k > 0) body.append(h('pre', 'mx-wtext', text.slice(0, k)));
      const mine = h('pre', 'mx-wtext mx-pvmode', end < 0 ? text.slice(k) : text.slice(k, end));
      mine.title = 'The mode\'s instructions: the only part a mode sets';
      body.append(mine);
      if (end >= 0) body.append(h('pre', 'mx-wtext', text.slice(end)));
    }
    for (const t of m.tool_calls || []) body.append(h('pre', 'mx-wtext muted', `tool call: ${t}`));
    det.append(body);
    box.append(det);
  });
}
