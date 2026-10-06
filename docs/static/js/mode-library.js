/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: Shared, versioned modes for the Mode explorer (docs/mode-explorer.html). Son's ask, #arc-3 6-Oct 08:42 ET:
  "Mark needs a way to edit and add new modes, is it there? And when will the mode be recorded?"
  - loadLibrary: the current version of every mode from the site's database (/api/v1/modes, railway/modes_store.py),
    the same for everyone signed in. Built-in modes are version 1 from modes.json; every save is a new version with
    who and when, old versions are kept and can be restored, delete hides a mode (history kept).
  - openEditor: the editor behind the pencil on each mode chip (and "+ New mode", which starts from Stock). Reworked
    6-Oct after the Boss, #arc-3 16:39 ET: "It's not clear what part I'm able to edit, and there are parts I absolutely
    do not want to accidentally edit ... I still don't understand if this is the system prompt, the user prompt, or
    what, and where it's getting inserted", and the editor was a narrow panel in the top-left corner with small text.
    Now a centred window (two columns on a desktop, a full-screen sheet on a phone) with:
      * "Where this goes": the system prompt (the same for every mode, never changed by one; "Show system prompt"
        opens it read-only from static/data/system-prompts.json) -> the turn message, sent as the user message at the
        start of each turn the mode runs.
      * The turn message split into blocks (splitTurn): the harness's own lines, read-only and greyed under a lock
        ("Added by the harness every turn"), and the mode's own instruction, the only editable box. A mode's stored text
        is still the whole turn message, as the runner needs it; splitTurn takes it apart with the same line diff
        against Stock that the runner applies, and joinTurn puts it back, giving the stored text byte for byte when
        nothing was edited. Saving can only change the instruction. Where a mode replaces a Stock line (Son's wording
        replaces the "Focus on what changed ..." line) that line shows struck through. A mode with no instruction yet
        (a new mode, or one with Stock's text) gets an empty box where modes.json's insert_rule puts one.
      * The stock tool-call reminders in the turn message are marked "also in the system prompt" (modes.json
        meta.tool_reminders). "Lean turn message", per mode and off by default, has the runner leave them out of that
        mode's turn message (tools/spark_runner/modes.py apply_lean); it is saved in the mode version and sent with
        each Play slot, so each job records it. Built-in Stock (lean) is Stock with it on.
      * Name, colour, the purpose line (shown on the card, never sent to the model), settings, why, note; Save as a new
        version, the version history with Restore, and Delete (hides). It warns when an edit would be refused by the
        runner (an instruction line with a {placeholder} or a [when] marker).
  - migrateLocal: custom modes from the old browser-only store are offered for upload once, then uploaded as shared
    modes; queues that used them are pointed at the uploaded ids. The browser copy is kept.
  - loadRuns: what each Play recorded (the exact mode versions and text sent), for the results list.
SRP/DRY check: Pass - drawing helpers, the settings grid, the line renderer and the line diff are passed in from
  mode-explorer.js so they exist once; storage rules live in railway/modes_store.py; the runner's literal-line rule
  mirrors tools/spark_runner/modes.py (is_literal) so the warning matches what Play would refuse, and the lean lines
  are the runner's LEAN_LINES in modes.json's template form.
*/

const API = new URL('../../api/v1/modes/', import.meta.url);
const PLACEHOLDER = /\{[^{}\s]+\}/;
const CONDITION = /^\[when [^\]]*\]\s*/;
const VARIANTS = { son: "Son's wording", daniel: "Franzen's wording" };
let deps = null;     // { h, settingsGrid, diffLines, lineNode, settingsSummary, FALLBACK_SETTINGS, stockText(variant, base), toolReminders() }

export const lib = { ok: false, me: null, modes: [], error: null };

export function initLibrary(d) { deps = d; }

async function call(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' };
  if (body) headers['Content-Type'] = 'application/json';
  const r = await fetch(new URL(path, API), { method, headers, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' });
  const type = r.headers.get('Content-Type') || '';
  if (r.redirected || !type.includes('json')) throw Object.assign(new Error(r.status === 401 || r.redirected ? 'sign in to the site again' : `HTTP ${r.status}`), { status: r.status });
  const data = await r.json();
  if (!r.ok) throw Object.assign(new Error(data.message || data.error || `HTTP ${r.status}`), { status: r.status, data });
  return data;
}

// A stored mode as the page draws it. A mode with one wording (an uploaded browser mode) answers both switches with
// that wording, and base_variant says which Stock it is diffed against, as custom modes always were.
function asPageMode(r) {
  const keys = Object.keys(r.variants || {});
  const only = keys.length === 1 ? keys[0] : null;
  const variants = {};
  for (const k of Object.keys(VARIANTS)) {
    const v = r.variants[k] || r.variants[only];
    variants[k] = { purpose: v.purpose || '', trigger: v.trigger || '', budget: v.budget || '', prompt: v.prompt };
  }
  return { ...r, variants, base_variant: only, shared: true, custom: !r.builtin };
}

// A version the server just saved becomes the current one on this page.
export function applySaved(row) {
  const m = asPageMode(row);
  const k = lib.modes.findIndex(x => x.id === m.id);
  if (k >= 0) { m.versions = row.version; m.first_at = lib.modes[k].first_at; lib.modes[k] = m; }
  else { m.versions = row.version; lib.modes.push(m); }
  return m;
}

export async function loadLibrary() {
  try {
    const data = await call('');
    lib.modes = data.modes.map(asPageMode);
    lib.me = data.me; lib.ok = lib.modes.length > 0; lib.error = lib.ok ? null : 'no modes stored yet';
  } catch (e) { lib.ok = false; lib.error = e.message; }
  return lib.ok;
}

export async function loadRuns(game) {
  try { return (await call(`runs?game=${encodeURIComponent(game)}`)).runs || {}; } catch { return {}; }
}

export function versionTag(m) { return m && m.version ? `v${m.version}` : ''; }

export function whoWhen(by, at) {
  const d = new Date(at);
  const who = by === 'modes.json (built in)' ? 'built in' : String(by || '').split('@')[0];
  return `${who}${isNaN(d) ? '' : ', ' + d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`;
}

// The version a queue slot sends with Play, so the job record names the exact wording.
export function versionOf(m, variant) {
  if (!m || !m.shared) return null;
  return { mode_id: m.id, version: m.version, variant: m.base_variant || variant, created_by: m.created_by, created_at: m.created_at };
}

// Lines the Spark runner would refuse (tools/spark_runner/modes.py build_delta): removing a templated Stock line, or
// adding a line with a placeholder or a [when] marker.
function runnerProblems(stock, text) {
  const out = [];
  for (const [kind, l, r] of deps.diffLines(stock.split('\n'), text.split('\n'))) {
    if ((kind === 'del' || kind === 'chg') && (PLACEHOLDER.test(l) || CONDITION.test(l))) out.push(`removes the templated Stock line "${l.slice(0, 60)}"`);
    if ((kind === 'add' || kind === 'chg') && (PLACEHOLDER.test(r) || CONDITION.test(r))) out.push(`adds "${r.slice(0, 60)}", which has a {placeholder} or [when] marker`);
  }
  return out;
}

// ---------------------------------------------------------------- turn message: harness lines and the mode's own lines

// The Stock line a new instruction goes next to (modes.json meta.insert_rule).
const FOCUS = 'Focus on what changed most recently in `history`';

// One wording's stored text as blocks, against that wording's Stock text, with the same line diff the runner applies:
// { kind: 'harness', lines } for Stock lines the mode keeps, { kind: 'mode', removed, added } for each place it differs.
// joinTurn gives the stored text back exactly: it is the diff's right-hand lines, in order.
export function splitTurn(stock, text, diffLines) {
  const blocks = [];
  let cur = null;
  for (const [kind, l, r] of diffLines(stock.split('\n'), text.split('\n'))) {
    if (kind === 'same') {
      if (!cur || cur.kind !== 'harness') blocks.push(cur = { kind: 'harness', lines: [] });
      cur.lines.push(l);
      continue;
    }
    if (!cur || cur.kind !== 'mode') blocks.push(cur = { kind: 'mode', removed: [], added: [] });
    if (l !== null) cur.removed.push(l);
    if (r !== null) cur.added.push(r);
  }
  return blocks;
}

// A wording with no instruction of its own gets an empty one where the built-in modes put theirs: in place of the
// focus line in Son's wording, right after it in Franzen's. While it stays empty the focus line stays (fresh).
export function withInstruction(blocks, variant) {
  if (blocks.some(b => b.kind === 'mode')) return blocks;
  const out = [];
  let placed = false;
  for (const b of blocks) {
    const k = placed ? -1 : b.lines.findIndex(x => x.startsWith(FOCUS));
    if (k < 0) { out.push(b); continue; }
    placed = true;
    const cut = variant === 'son' ? k : k + 1;
    if (cut) out.push({ kind: 'harness', lines: b.lines.slice(0, cut) });
    out.push({ kind: 'mode', removed: variant === 'son' ? [b.lines[k]] : [], added: [], fresh: true });
    if (b.lines.length > k + 1) out.push({ kind: 'harness', lines: b.lines.slice(k + 1) });
  }
  if (!placed) out.push({ kind: 'mode', removed: [], added: [], fresh: true });
  return out;
}

export function joinTurn(blocks) {
  return blocks.flatMap(b => (b.kind === 'harness' ? b.lines : b.fresh && !b.added.length ? b.removed : b.added)).join('\n');
}

const LOCK = '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M4 7V5a4 4 0 1 1 8 0v2h.5A1.5 1.5 0 0 1 14 8.5v5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5v-5A1.5 1.5 0 0 1 3.5 7H4Zm1.5 0h5V5a2.5 2.5 0 0 0-5 0v2Z"/></svg>';
const SURFACE = { turn: 'an ordinary turn in the middle of a level', game_over: 'the turn right after a game over',
  level_start: 'the first turn after a level is cleared' };

let SYSTEM = null;   // static/data/system-prompts.json, loaded the first time someone opens it
async function systemPrompts() {
  if (!SYSTEM) SYSTEM = fetch(new URL('../data/system-prompts.json', import.meta.url), { cache: 'no-cache' })
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .catch(e => { SYSTEM = null; throw e; });
  return SYSTEM;
}

function lockHead(text) {
  const d = deps.h('div', 'mx-tm-lock');
  d.innerHTML = LOCK;
  d.append(' ', text);
  return d;
}

// ---------------------------------------------------------------- editor

// id null = new mode, starting from the current Stock mode. onSaved(mode) after any change that made a version.
export function openEditor(id, { variant, stockMode, onSaved }) {
  const { h, settingsGrid, FALLBACK_SETTINGS } = deps;
  const existing = id ? lib.modes.find(m => m.id === id) : null;
  const src = existing || stockMode;
  const isStock = !!existing && existing.id === 'stock';
  // edit the stored wordings, not the page's filled-in copies
  // a new mode starts with the wording on screen only; the other can be added with its own tab
  const stored = existing ? (existing.base_variant ? { [existing.base_variant]: existing.variants[existing.base_variant] } : existing.variants)
    : { [variant]: stockMode.variants[variant] };
  const draft = {
    name: existing ? existing.name : '', color: existing ? existing.color : '#0e7490', base: existing ? existing.base : 'turn',
    variants: JSON.parse(JSON.stringify(stored)), settings: { ...FALLBACK_SETTINGS, ...(src.settings || {}) },
    settings_why: existing ? existing.settings_why || '' : '', lean: existing ? existing.lean === true : false,
  };
  if (!existing) for (const v of Object.values(draft.variants)) { v.purpose = ''; v.trigger = 'Your choice.'; v.budget = ''; }
  const stockOf = (k) => deps.stockText(k, draft.base);
  // the turn message of each wording as blocks; Stock itself has no instruction of its own to edit
  const blocksOf = (k, text) => { const b = splitTurn(stockOf(k), text, deps.diffLines); return isStock ? b : withInstruction(b, k); };
  const turns = {};
  for (const k of Object.keys(draft.variants)) turns[k] = blocksOf(k, draft.variants[k].prompt);
  const reminders = new Set(deps.toolReminders());
  let tab = draft.variants[variant] ? variant : Object.keys(draft.variants)[0];

  const dlg = document.getElementById('modedlg'); dlg.textContent = ''; dlg.className = 'mx-dialog mx-eddlg';
  const form = h('form', 'mx-form mx-edform'); form.method = 'dialog';
  const lab = (t, el, cls) => { const l = h('label', 'mx-field' + (cls ? ' ' + cls : '')); l.append(h('span', 'mx-flabel', t), el); return l; };

  // ---- title bar
  const top = h('div', 'mx-edtop');
  const title = h('div', 'mx-edtitle');
  title.append(h('h2', null, existing ? `Edit ${existing.name}` : 'New mode'));
  if (existing) title.append(h('span', 'mx-rl2', `${versionTag(existing)} · ${whoWhen(existing.created_by, existing.created_at)}`));
  title.append(h('span', 'mx-rl2', existing ? 'Shared with everyone signed in. Saving makes a new version; older versions stay in the history.'
    : 'Starts as Stock. Shared with everyone signed in once saved.'));
  const x = h('button', 'mx-edclose', '×'); x.type = 'button'; x.title = 'Close without saving'; x.setAttribute('aria-label', 'Close without saving');
  x.onclick = () => dlg.close();
  top.append(title, x);

  const body = h('div', 'mx-edbody');
  const text = h('div', 'mx-edtext');     // left: the text
  const where = h('div', 'mx-edwhere');   // right, top: where this goes
  const side = h('div', 'mx-edside');     // right: name, settings, history
  body.append(text, where, side);

  // ---- where this goes
  const sysBtn = h('button', 'mx-tool', 'Show system prompt'); sysBtn.type = 'button';
  sysBtn.title = 'Read the system prompt the runner sends today (read-only)';
  const wsys = h('div', 'mx-wbox mx-wsys');
  wsys.append(lockHead('System prompt'), h('p', null, 'Sent as the system message with every request. The same for every mode: a mode never changes it.'), sysBtn);
  const wturn = h('div', 'mx-wbox mx-wturn');
  wturn.style.setProperty('--mc', draft.color);
  const wsurf = h('p');
  const wl = h('ul', 'mx-wlegend');
  const li1 = h('li', 'lock'); li1.innerHTML = LOCK; li1.append(' Harness lines: added every turn, locked');
  const li2 = h('li', 'mine', isStock ? 'Stock has no instruction of its own; only its settings and lean switch change here' : "This mode's instruction: the only part you edit");
  wl.append(li1, li2);
  wturn.append(h('div', 'mx-wtitle', 'Turn message'), wsurf, wl);
  where.append(h('h3', 'mx-edh', 'Where this goes'), wsys, h('div', 'mx-warrow', '↓ then, each turn this mode runs'), wturn);
  const drawSurface = () => { wsurf.textContent = `Sent as the user message at the start of each turn this mode runs. Built on the harness's message for ${SURFACE[draft.base] || draft.base}.`; };
  drawSurface();

  // ---- left: wording tabs, purpose, system prompt panel, the turn message
  const tabs = h('div', 'mx-segs mx-edtabs');
  const purpose = h('input'); purpose.placeholder = 'What this turn is for, in one line'; purpose.maxLength = 500;
  const sysPanel = h('div', 'mx-syspanel'); sysPanel.hidden = true;
  const turnBox = h('div', 'mx-turn');
  const warn = h('p', 'mx-ed-warn'); warn.hidden = true;
  const redrawWarn = () => {
    const probs = Object.keys(draft.variants).flatMap(k => runnerProblems(stockOf(k), draft.variants[k].prompt).map(p => `${VARIANTS[k]}: ${p}`));
    warn.hidden = !probs.length;
    warn.textContent = probs.length ? `Play would refuse this: ${probs.slice(0, 3).join('; ')}. Instruction lines must be plain text.` : '';
  };
  const sync = (k) => { draft.variants[k].prompt = joinTurn(turns[k]); };

  const fit = (ta) => { ta.style.height = 'auto'; ta.style.height = `${Math.max(ta.scrollHeight + 2, 96)}px`; };
  const harnessBlock = (lines) => {
    const box = h('div', 'mx-tm-harness');
    box.append(lockHead('Added by the harness every turn – not editable here'));
    for (const l of lines) {
      const row = deps.lineNode(l); row.classList.add('mx-tm-line');
      if (reminders.has(l)) {
        row.classList.add('mx-tm-dup');
        if (draft.lean) row.classList.add('mx-tm-out');
        row.append(' ', h('span', 'mx-tm-tag', draft.lean ? 'left out: lean turn message' : 'also in the system prompt'));
        row.title = draft.lean ? 'Lean turn message is on: the runner leaves this line out of this mode\'s turn message. The system prompt still says it.'
          : 'The system prompt already says this. "Lean turn message" leaves it out of this mode\'s turn message.';
      }
      box.append(row);
    }
    return box;
  };
  const drawTurn = () => {
    turnBox.textContent = '';
    const blocks = turns[tab];
    const own = blocks.filter(b => b.kind === 'mode');
    let n = 0;
    for (const b of blocks) {
      if (b.kind === 'harness') { turnBox.append(harnessBlock(b.lines)); continue; }
      n++;
      const sec = h('div', 'mx-tm-mode');
      sec.style.setProperty('--mc', draft.color);
      const ta = h('textarea', 'mx-tm-input'); ta.spellcheck = true;
      ta.value = b.added.join('\n');
      ta.placeholder = 'Write this mode\'s instruction here: what the model should do differently this turn.';
      const label = h('label', 'mx-tm-modeh', `✎ This mode's instruction${own.length > 1 ? ` (part ${n} of ${own.length})` : ''} – the only text you can edit`);
      ta.id = `mx-tm-${n}`; label.htmlFor = ta.id;
      sec.append(label);
      for (const r of b.removed) {
        const row = deps.lineNode(r); row.classList.add('mx-tm-line', 'mx-tm-replaced');
        row.append(' ', h('span', 'mx-tm-tag', b.fresh && !b.added.length ? 'stock line, replaced once you write an instruction' : 'stock line this instruction replaces'));
        sec.append(row);
      }
      sec.append(ta);
      ta.oninput = () => {
        const wasEmpty = !b.added.length;
        b.added = ta.value === '' ? [] : ta.value.replace(/\r/g, '').split('\n');
        sync(tab); fit(ta);
        clearTimeout(ta.t); ta.t = setTimeout(redrawWarn, 150);
        if (b.fresh && b.removed.length && wasEmpty !== !b.added.length) {   // the replaced-line note follows the box
          const tag = sec.querySelector('.mx-tm-replaced .mx-tm-tag');
          if (tag) tag.textContent = b.added.length ? 'stock line this instruction replaces' : 'stock line, replaced once you write an instruction';
        }
      };
      turnBox.append(sec);
      requestAnimationFrame(() => fit(ta));
    }
  };
  const drawTabs = () => {
    tabs.textContent = '';
    for (const k of Object.keys(VARIANTS)) {
      if (!draft.variants[k]) continue;
      const b = h('button', 'mx-seg' + (k === tab ? ' on' : ''), VARIANTS[k]); b.type = 'button';
      b.onclick = () => { tab = k; fill(); };
      tabs.append(b);
    }
    for (const k of Object.keys(VARIANTS)) {
      if (draft.variants[k] || isStock) continue;
      const b = h('button', 'mx-seg', `+ ${VARIANTS[k]}`); b.type = 'button';
      b.title = `Add a ${VARIANTS[k]} version: that wording's Stock message with this instruction in it`;
      b.onclick = () => {
        // the new wording starts with this wording's instruction in its usual place
        const mine = turns[tab].filter(x => x.kind === 'mode').flatMap(x => x.added);
        turns[k] = withInstruction(splitTurn(stockOf(k), stockOf(k), deps.diffLines), k);
        const slot = turns[k].find(x => x.kind === 'mode'); slot.added = mine.slice();
        draft.variants[k] = { purpose: draft.variants[tab].purpose, trigger: '', budget: '', prompt: '' };
        sync(k); tab = k; fill();
      };
      tabs.append(b);
    }
  };
  const showSystem = async (open) => {
    sysPanel.hidden = !open;
    sysBtn.textContent = open ? 'Hide system prompt' : 'Show system prompt';
    if (!open) return;
    sysPanel.textContent = '';
    sysPanel.append(lockHead(`System prompt, ${VARIANTS[tab]} – read-only, the same for every mode`));
    const pre = h('pre', 'mx-syspre', 'loading…');
    sysPanel.append(pre);
    try {
      const d = await systemPrompts();
      pre.textContent = d[tab] || '(not available for this wording)';
      sysPanel.append(h('p', 'mx-rl2', d.meta && d.meta.source ? `How the runner builds it today; a harness change would change it. ${d.meta.tool_reminders_in_system_prompt || ''}` : ''));
    } catch (e) { pre.textContent = `Could not load the system prompt (${e.message}).`; }
  };
  sysBtn.onclick = () => showSystem(sysPanel.hidden);
  const fill = () => {
    drawTabs(); purpose.value = draft.variants[tab].purpose || ''; drawTurn(); redrawWarn();
    if (!sysPanel.hidden) showSystem(true);
  };
  purpose.oninput = () => { draft.variants[tab].purpose = purpose.value; };

  const turnHead = h('div', 'mx-turnhead');
  const jump = h('button', 'mx-linkbtn', 'Jump to the instruction'); jump.type = 'button';
  jump.title = 'Scroll to the box you can edit';
  jump.onclick = () => { const sec = turnBox.querySelector('.mx-tm-mode'); if (sec) { sec.scrollIntoView({ block: 'center', behavior: 'smooth' }); const ta = sec.querySelector('textarea'); if (ta) ta.focus({ preventScroll: true }); } };
  jump.hidden = isStock;
  const th = h('div', 'mx-turntitle'); th.append(h('h3', 'mx-edh', 'Turn message'), jump);
  turnHead.append(th,
    h('p', 'mx-rl2', 'What the model receives as the user message at the start of each turn this mode runs, top to bottom. {Braced} words are filled in by the harness each turn; lines marked "when" appear only sometimes.'));
  text.append(tabs, lab('Purpose (shown on the mode card; not sent to the model)', purpose, 'wide'), sysPanel, turnHead, turnBox, warn);

  // ---- right: name, colour, lean, settings, note, history
  const row = h('div', 'mx-formrow');
  const name = h('input'); name.required = true; name.maxLength = 32; name.value = draft.name; name.placeholder = 'e.g. Map the board';
  const color = h('input'); color.type = 'color'; color.value = draft.color;
  color.oninput = () => { draft.color = color.value; wturn.style.setProperty('--mc', draft.color); for (const s of turnBox.querySelectorAll('.mx-tm-mode')) s.style.setProperty('--mc', draft.color); };
  row.append(lab('Name', name, 'grow'), lab('Colour', color));
  const leanBox = h('label', 'mx-lean');
  const lean = h('input'); lean.type = 'checkbox'; lean.checked = draft.lean;
  leanBox.append(lean, h('span', null, 'Lean turn message'));
  const leanWhy = h('p', 'mx-rl2', 'Leaves the stock tool-call lines out of this mode\'s turn message; the system prompt already says them. Off keeps the message exactly as the harness writes it.');
  lean.onchange = () => { draft.lean = lean.checked; drawTurn(); };
  const det = h('details', 'mx-ed-settings');
  const sum = h('summary', null, 'Settings'); det.append(sum);
  const sumText = () => { sum.textContent = `Settings · ${deps.settingsSummary(draft.settings)}`; };
  det.append(settingsGrid(() => draft.settings, (k, v) => { draft.settings[k] = v; sumText(); }));
  const why = h('textarea'); why.rows = 2; why.value = draft.settings_why; why.placeholder = 'Why these settings (optional)';
  det.append(lab('Why these settings', why, 'wide'));
  sumText();
  const note = h('input'); note.maxLength = 200; note.placeholder = existing ? 'What changed (optional, shows in the history)' : 'Optional note';
  const hist = h('div', 'mx-ed-hist'); hist.hidden = true;
  side.append(h('h3', 'mx-edh', 'Mode'), row, leanBox, leanWhy, det, lab('Note for the history (not sent to the model)', note, 'wide'), hist);

  // ---- footer: save, cancel, history, delete
  const status = h('p', 'mx-sum mx-ed-status');
  const btns = h('div', 'mx-formbtns');
  const save = h('button', 'mx-play', existing ? 'Save new version' : 'Create mode'); save.type = 'submit';
  save.title = 'Saves the name, colour, instruction, lean switch and settings as a new version; the harness lines and the system prompt are never changed';
  const cancel = h('button', 'mx-tool', 'Cancel'); cancel.type = 'button'; cancel.onclick = () => dlg.close();
  btns.append(save, cancel);
  if (existing) {
    const hb = h('button', 'mx-tool', `History (${existing.versions || 1})`); hb.type = 'button';
    hb.onclick = () => { hist.hidden = !hist.hidden; if (!hist.hidden) { drawHistory(hist, existing, dlg, onSaved, status); hist.scrollIntoView({ block: 'nearest' }); } };
    btns.append(hb);
    if (existing.id !== 'stock') {
      const del = h('button', 'mx-tool mx-danger', 'Delete'); del.type = 'button';
      del.title = 'Hides the mode for everyone; its history is kept and it can be brought back';
      del.onclick = async () => {
        if (!confirm(`Delete ${existing.name} for everyone? It is hidden, not erased: its versions are kept and it can be brought back from "+ New mode".`)) return;
        try { const r = await call(`${existing.id}/hide`, { method: 'POST', body: { from_version: existing.version } }); dlg.close(); onSaved(r.mode); }
        catch (e) { status.textContent = `Not deleted: ${e.message}`; }
      };
      btns.append(del);
    }
  } else {
    const gone = lib.modes.filter(m => m.hidden);
    if (gone.length) {
      const p = h('p', 'mx-sum'); p.append('Deleted modes: ');
      gone.forEach((m, i) => {
        const b = h('button', 'mx-linkbtn', m.name); b.type = 'button'; b.title = 'Bring this mode back';
        b.onclick = async () => {
          try { const r = await call(`${m.id}/unhide`, { method: 'POST', body: { from_version: m.version } }); dlg.close(); onSaved(r.mode); }
          catch (e) { status.textContent = `Not brought back: ${e.message}`; }
        };
        p.append(b, i < gone.length - 1 ? ', ' : '');
      });
      side.append(p);
    }
  }
  const foot = h('div', 'mx-edfoot');
  foot.append(btns, status);

  form.onsubmit = async (e) => {
    e.preventDefault();
    const nm = name.value.trim();
    if (!nm) { name.focus(); return; }
    const taken = lib.modes.find(m => !m.hidden && m.id !== (existing && existing.id) && m.name.toLowerCase() === nm.toLowerCase());
    if (taken) { name.setCustomValidity(`A mode called ${nm} already exists.`); name.reportValidity(); name.oninput = () => name.setCustomValidity(''); return; }
    if (!isStock) {
      const blank = Object.keys(draft.variants).filter(k => !turns[k].some(b => b.kind === 'mode' && b.added.some(l => l.trim())));
      if (blank.length && !confirm(`${blank.map(k => VARIANTS[k]).join(' and ')} has no instruction of its own, so that turn message is the same as Stock${draft.lean ? ' (lean)' : ''}. Save anyway?`)) {
        tab = blank[0]; fill(); const ta = turnBox.querySelector('textarea'); if (ta) ta.focus(); return;
      }
    }
    if (!warn.hidden && !confirm(`${warn.textContent}\n\nSave anyway?`)) return;
    const mode = { ...draft, name: nm, color: color.value, settings_why: why.value.trim(), rl2: existing && existing.rl2 };
    save.disabled = true; status.textContent = 'Saving…';
    try {
      const r = await call('save', { method: 'POST', body: { id: existing ? existing.id : null, from_version: existing ? existing.version : null, mode, note: note.value.trim() } });
      dlg.close(); onSaved(r.mode);
    } catch (err) {
      status.textContent = err.status === 409 ? `Not saved: ${err.message}. Your text is still here; copy it, close and reopen the editor.` : `Not saved: ${err.message}`;
      save.disabled = false;
    }
  };
  form.append(top, body, foot);
  dlg.append(form);
  fill();
  dlg.showModal();
  dlg.scrollTop = 0; body.scrollTop = 0;
  if (!existing) name.focus();
  else { const ta = turnBox.querySelector('textarea'); if (ta) ta.focus({ preventScroll: true }); }
}

async function drawHistory(box, m, dlg, onSaved, status) {
  const { h } = deps;
  box.textContent = 'loading…';
  let data;
  try { data = await call(`${m.id}/versions`); } catch (e) { box.textContent = `Could not load the history: ${e.message}`; return; }
  box.textContent = '';
  for (const v of data.versions) {
    const row = h('div', 'mx-ed-hrow');
    const head = h('div', 'mx-ed-hhead');
    head.append(h('b', null, `v${v.version}`), h('span', null, ` ${whoWhen(v.created_by, v.created_at)}${v.hidden ? ' · deleted' : ''}${v.note ? ' · ' + v.note : ''}`));
    const show = h('button', 'mx-linkbtn', 'text'); show.type = 'button';
    const pre = h('pre', 'mx-ed-htext'); pre.hidden = true;
    pre.textContent = Object.entries(v.variants).map(([k, x]) => `── ${VARIANTS[k]} ──\n${x.prompt}`).join('\n\n') + `\n\n── Settings ── ${deps.settingsSummary({ ...deps.FALLBACK_SETTINGS, ...v.settings })}${v.lean ? ' · lean turn message' : ''}`;
    show.onclick = () => { pre.hidden = !pre.hidden; };
    head.append(' ', show);
    if (v.version !== m.version) {
      const rb = h('button', 'mx-linkbtn', 'restore'); rb.type = 'button';
      rb.title = `Make version ${v.version} the current one again (as a new version; nothing is lost)`;
      rb.onclick = async () => {
        if (!confirm(`Restore version ${v.version} of ${m.name}? It becomes a new version ${m.version + 1}; the current one stays in the history.`)) return;
        try { const r = await call(`${m.id}/restore`, { method: 'POST', body: { version: v.version, from_version: m.version } }); dlg.close(); onSaved(r.mode); }
        catch (e) { status.textContent = `Not restored: ${e.message}`; }
      };
      head.append(' · ', rb);
    } else head.append(h('span', 'mx-rl2', ' current'));
    row.append(head, pre);
    box.append(row);
  }
}

// ---------------------------------------------------------------- browser modes -> shared

// Uploads the old browser-only custom modes as shared modes. Returns a map old id -> new id for the queues.
export async function uploadLocal(customModes) {
  const ids = {};
  const failed = [];
  for (const c of customModes) {
    let name = String(c.name || 'Mode').trim().slice(0, 32);
    const clash = (n) => lib.modes.some(m => !m.hidden && m.name.toLowerCase() === n.toLowerCase());
    for (let k = 2; clash(name) && k < 50; k++) name = `${String(c.name).trim().slice(0, 28)} (${k})`;
    const variant = c.base_variant === 'daniel' ? 'daniel' : 'son';
    const mode = { name, color: /^#[0-9a-f]{6}$/i.test(c.color || '') ? c.color : '#0e7490', base: 'turn',
      variants: { [variant]: { purpose: c.purpose || '', trigger: 'Your choice.', budget: '', prompt: c.prompt } },
      settings: c.settings || {}, settings_why: c.settings_why || '' };
    try {
      const r = await call('save', { method: 'POST', body: { id: null, mode, note: 'uploaded from a browser' } });
      ids[c.id] = r.mode.id;
      lib.modes.push(asPageMode(r.mode));
    } catch (e) { failed.push(`${c.name} (${e.message})`); }
  }
  return { ids, failed };
}
