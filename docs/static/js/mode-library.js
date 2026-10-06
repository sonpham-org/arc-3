/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: Shared, versioned modes for the Mode explorer (docs/mode-explorer.html). Son's ask, #arc-3 6-Oct 08:42 ET:
  "Mark needs a way to edit and add new modes, is it there? And when will the mode be recorded?"
  - loadLibrary: the current version of every mode from the site's database (/api/v1/modes, railway/modes_store.py),
    the same for everyone signed in. Built-in modes are version 1 from modes.json; every save is a new version with
    who and when, old versions are kept and can be restored, delete hides a mode (history kept).
  - openEditor: the editor behind the pencil on each mode chip (and "+ New mode", which starts from Stock). Reworked
    twice on 6-Oct: after the Boss at 16:39 ET ("It's not clear what part I'm able to edit ... I still don't understand
    if this is the system prompt, the user prompt, or what"), and again for the prompt profiles (the Boss approved
    Astra's notes at 17:07 ET: no duplicated instructions, a mode is only what changes this turn). A centred window
    (two columns on a desktop, a full-screen sheet on a phone) showing what the model receives in three labelled parts:
      1 System prompt: read-only, the same for every mode (static/data/prompt-profiles.json, rendered by the runner's
        harness for the profile chosen next to Play);
      2 This turn: read-only, the facts the harness fills in at the start of each turn (a real example for the
        mode's surface: an ordinary turn, after a game over, or after a cleared level);
      3 Mode instructions: the only editable text, one text for both wordings, added by the runner as the last part
        of the turn message under "Instructions for this turn (<name> mode):". Stock has none.
    "Preview request" asks the runner for the exact first request Play would send with this text (the game, level,
    wording and context chosen in the Queue view; spark-runner.js previewRequest). Name, colour, purpose (shown on the
    card, never sent), settings, why, note; Save as a new version, the version history with Restore, and Delete (hides).
    A stored mode is {instructions, variants: {son, daniel: {purpose, trigger, budget}}, ...}; versions saved before
    6-Oct stored the whole turn message per wording and are read through instructionsOf (their added lines). The
    lean switch of 16:39 is gone: the dedup prompts leave every standing line out of every turn message.
  - migrateLocal: custom modes from the old browser-only store are offered for upload once, then uploaded as shared
    modes; queues that used them are pointed at the uploaded ids. The browser copy is kept.
  - loadRuns: what each Play recorded (the exact mode versions and text sent), for the results list.
SRP/DRY check: Pass - drawing helpers, the settings grid, instructionsOf and the preview call are passed in from
  mode-explorer.js and spark-runner.js so they exist once; storage rules live in railway/modes_store.py; the prompt
  texts shown are the runner's own renders (prompt-profiles.json), never retyped here.
*/

const API = new URL('../../api/v1/modes/', import.meta.url);
const VARIANTS = { son: "Son's wording", daniel: "Franzen's wording" };
let deps = null;     // { h, settingsGrid, settingsSummary, FALLBACK_SETTINGS, instructionsOf, prompts(), profile(), previewTarget(), previewRequest, renderPreview, surfaces() }

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

// A stored mode as the page draws it. Since 6-Oct a mode is its instructions (one text for both wordings). A version
// from before stored the whole turn message; one with a single wording (an uploaded browser mode) answers both
// switches with it, and base_variant says which Stock its instructions are read against.
function asPageMode(r) {
  const keys = Object.keys(r.variants || {});
  const only = typeof r.instructions !== 'string' && keys.length === 1 ? keys[0] : null;
  const variants = {};
  for (const k of Object.keys(VARIANTS)) {
    const v = (r.variants || {})[k] || (r.variants || {})[only || keys[0]] || {};
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

const LOCK = '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M4 7V5a4 4 0 1 1 8 0v2h.5A1.5 1.5 0 0 1 14 8.5v5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 13.5v-5A1.5 1.5 0 0 1 3.5 7H4Zm1.5 0h5V5a2.5 2.5 0 0 0-5 0v2Z"/></svg>';
const EXAMPLE_FOR = { turn: 'turn', game_over: 'game_over', level_start: 'level_start' };

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
  const purposeOf = (m) => (m && m.variants && (m.variants[variant] || m.variants.son) || {});
  const draft = {
    name: existing ? existing.name : '', color: existing ? existing.color : '#0e7490', base: existing ? existing.base : 'turn',
    instructions: existing ? deps.instructionsOf(existing, variant) : '',
    purpose: existing ? purposeOf(existing).purpose || '' : '', trigger: existing ? purposeOf(existing).trigger || '' : 'Your choice.',
    budget: existing ? purposeOf(existing).budget || '' : '',
    settings: { ...FALLBACK_SETTINGS, ...(src.settings || {}) }, settings_why: existing ? existing.settings_why || '' : '',
  };
  const legacy = existing && typeof existing.instructions !== 'string';
  const P = () => { const d = deps.prompts(); return d && d.profiles[deps.profile() === 'original' ? 'original' : 'dedup']; };

  const dlg = document.getElementById('modedlg'); dlg.textContent = ''; dlg.className = 'mx-dialog mx-eddlg';
  const form = h('form', 'mx-form mx-edform'); form.method = 'dialog';
  const lab = (t, el, cls) => { const l = h('label', 'mx-field' + (cls ? ' ' + cls : '')); l.append(h('span', 'mx-flabel', t), el); return l; };

  // ---- title bar
  const top = h('div', 'mx-edtop');
  const title = h('div', 'mx-edtitle');
  title.append(h('h2', null, existing ? `Edit ${existing.name}` : 'New mode'));
  if (existing) title.append(h('span', 'mx-rl2', `${versionTag(existing)} · ${whoWhen(existing.created_by, existing.created_at)}`));
  title.append(h('span', 'mx-rl2', existing ? 'Shared with everyone signed in. Saving makes a new version; older versions stay in the history.'
    : 'Starts with no instructions, like Stock. Shared with everyone signed in once saved.'));
  const x = h('button', 'mx-edclose', '×'); x.type = 'button'; x.title = 'Close without saving'; x.setAttribute('aria-label', 'Close without saving');
  x.onclick = () => dlg.close();
  top.append(title, x);

  const body = h('div', 'mx-edbody');
  const text = h('div', 'mx-edtext');     // left: the three parts
  const side = h('div', 'mx-edside');     // right: name, settings, history
  body.append(text, side);

  // ---- left: 1 system prompt, 2 this turn, 3 mode instructions, preview
  const part = (n, name, why, cls) => {
    const sec = h('div', `mx-part ${cls}`);
    const hd = h('h3', null);
    hd.append(h('span', 'mx-partn', String(n)), ` ${name} `, h('span', 'mx-partwhy', why));
    sec.append(hd);
    return sec;
  };
  const p = P();
  const sys = part(1, 'System prompt', 'sent with every request · the same for every mode · read-only', 'mx-part-sys');
  const sysDet = h('details');
  sysDet.append(h('summary', null, 'Show the system prompt'), h('pre', 'mx-syspre', p ? p.system[variant] : 'Could not load the system prompt.'));
  sys.append(lockHead('A mode never changes this. Every standing instruction (tools, Python, actions, deaths, how to play) is here, once.'), sysDet);

  const turn = part(2, 'This turn', 'the user message · filled in by the harness · read-only', 'mx-part-turn');
  const turnNote = h('p', 'mx-rl2');
  const turnPre = h('pre', 'mx-syspre mx-turnex');
  const baseSel = h('select');
  for (const [k, label] of Object.entries(deps.surfaces() || {})) { const o = h('option', null, label); o.value = k; baseSel.append(o); }
  baseSel.value = draft.base;
  baseSel.title = 'Which turn this mode is meant for. It only picks the example shown here and the note on the card; the runner fills in the real facts every turn.';
  const drawTurn = () => {
    const meta = deps.prompts() && deps.prompts().meta.example;
    turnPre.textContent = (p && p.turn_examples[EXAMPLE_FOR[draft.base] || 'turn']) || '(no example)';
    turnNote.textContent = `What the harness writes at the start of the turn: what the last sequence did, any event, the step, level and valid actions, retained functions, then the board images. A real example from ${meta ? `${meta.game} level ${meta.level}` : 'a walk through a game'}; the values change every turn.`;
  };
  baseSel.onchange = () => { draft.base = baseSel.value; drawTurn(); };
  turn.append(lockHead('Not editable: the runner fills this in from the game.'), lab('Meant for', baseSel), turnNote, turnPre);
  drawTurn();

  const mine = part(3, 'Mode instructions', 'the end of the same user message · the only part you edit', 'mx-part-mode');
  mine.style.setProperty('--mc', draft.color);
  const header = h('div', 'mx-modehdr');
  const drawHeader = () => { header.textContent = ((deps.prompts() && deps.prompts().meta.mode_header) || 'Instructions for this turn ({name} mode):').replace('{name}', name.value.trim() || 'this'); };
  const ta = h('textarea', 'mx-tm-input'); ta.spellcheck = true; ta.id = 'mx-instr';
  ta.value = draft.instructions;
  ta.placeholder = 'What the model should do differently on the turn this mode runs. Only what changes this turn: the tool manual and the general advice are already in the system prompt.';
  ta.disabled = isStock;
  const fit = () => { ta.style.height = 'auto'; ta.style.height = `${Math.max(ta.scrollHeight + 2, 120)}px`; };
  ta.oninput = () => { draft.instructions = ta.value.replace(/\r/g, ''); fit(); };
  const instrLabel = h('label', 'mx-tm-modeh', isStock ? 'Stock adds no instructions: the turn message is only the facts above. Only its settings change here.' : '✎ Instructions for the turn this mode runs');
  instrLabel.htmlFor = ta.id;
  mine.append(instrLabel, header, ta);
  if (legacy) mine.append(h('p', 'mx-rl2', 'This version was saved before 6-Oct as a whole turn message; the box shows the lines it added to Stock, which is what the runner sends. Saving stores just these instructions.'));

  const pv = h('div', 'mx-part mx-part-preview');
  const pvBtn = h('button', 'mx-play', 'Preview request'); pvBtn.type = 'button';
  const pvOut = h('div', 'mx-preview');
  const t = deps.previewTarget();
  pvBtn.disabled = !t;
  pvBtn.title = t ? `The exact first request Play would send for ${t.nickname} level ${t.level} with these instructions (the game, level, wording and context chosen in the Queue view). Built by the runner's own harness; nothing is played or saved.` : 'Pick a game in the Queue view first';
  if (t) pvBtn.textContent = `Preview request · ${t.nickname} level ${t.level}`;
  pvBtn.onclick = async () => {
    pvOut.textContent = 'Building the request on the runner…';
    try {
      const d = await deps.previewRequest({ ...t, mode: existing ? existing.id : 'new', name: name.value.trim() || 'New', instructions: isStock ? '' : draft.instructions });
      deps.renderPreview(pvOut, d, { header: 'Exactly what Play would send first with this text' });
    } catch (e) { pvOut.textContent = `No preview: ${e.message}`; }
  };
  pv.append(pvBtn, pvOut);
  text.append(sys, turn, mine, pv);

  // ---- right: name, colour, purpose, settings, note, history
  const row = h('div', 'mx-formrow');
  const name = h('input'); name.required = true; name.maxLength = 32; name.value = draft.name; name.placeholder = 'e.g. Map the board';
  name.oninput = drawHeader;
  const color = h('input'); color.type = 'color'; color.value = draft.color;
  color.oninput = () => { draft.color = color.value; mine.style.setProperty('--mc', draft.color); };
  row.append(lab('Name', name, 'grow'), lab('Colour', color));
  const purpose = h('input'); purpose.placeholder = 'What this turn is for, in one line'; purpose.maxLength = 500; purpose.value = draft.purpose;
  const det = h('details', 'mx-ed-settings');
  const sum = h('summary', null, 'Settings'); det.append(sum);
  const sumText = () => { sum.textContent = `Settings · ${deps.settingsSummary(draft.settings)}`; };
  det.append(settingsGrid(() => draft.settings, (k, v) => { draft.settings[k] = v; sumText(); }));
  const why = h('textarea'); why.rows = 2; why.value = draft.settings_why; why.placeholder = 'Why these settings (optional)';
  det.append(lab('Why these settings', why, 'wide'));
  sumText();
  const note = h('input'); note.maxLength = 200; note.placeholder = existing ? 'What changed (optional, shows in the history)' : 'Optional note';
  const hist = h('div', 'mx-ed-hist'); hist.hidden = true;
  side.append(h('h3', 'mx-edh', 'Mode'), row, lab('Purpose (shown on the mode card; not sent to the model)', purpose, 'wide'), det,
    lab('Note for the history (not sent to the model)', note, 'wide'), hist);

  // ---- footer: save, cancel, history, delete
  const status = h('p', 'mx-sum mx-ed-status');
  const btns = h('div', 'mx-formbtns');
  const save = h('button', 'mx-play', existing ? 'Save new version' : 'Create mode'); save.type = 'submit';
  save.title = 'Saves the name, colour, instructions and settings as a new version; the system prompt and the turn facts are never changed';
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
      const p2 = h('p', 'mx-sum'); p2.append('Deleted modes: ');
      gone.forEach((m, i) => {
        const b = h('button', 'mx-linkbtn', m.name); b.type = 'button'; b.title = 'Bring this mode back';
        b.onclick = async () => {
          try { const r = await call(`${m.id}/unhide`, { method: 'POST', body: { from_version: m.version } }); dlg.close(); onSaved(r.mode); }
          catch (e) { status.textContent = `Not brought back: ${e.message}`; }
        };
        p2.append(b, i < gone.length - 1 ? ', ' : '');
      });
      side.append(p2);
    }
  }
  const foot = h('div', 'mx-edfoot');
  foot.append(btns, status);

  form.onsubmit = async (e) => {
    e.preventDefault();
    const nm = name.value.trim();
    if (!nm) { name.focus(); return; }
    const taken = lib.modes.find(m => !m.hidden && m.id !== (existing && existing.id) && m.name.toLowerCase() === nm.toLowerCase());
    if (taken) { name.setCustomValidity(`A mode called ${nm} already exists.`); name.reportValidity(); name.oninput = () => { name.setCustomValidity(''); drawHeader(); }; return; }
    const instructions = isStock ? '' : draft.instructions.trim();
    if (!isStock && !instructions && !confirm('This mode has no instructions, so its turn message is the same as Stock\'s. Save anyway?')) { ta.focus(); return; }
    const v = { purpose: purpose.value.trim(), trigger: draft.trigger, budget: draft.budget };
    const mode = { name: nm, color: color.value, base: draft.base, instructions, variants: { son: v, daniel: { ...v } },
      settings: draft.settings, settings_why: why.value.trim(), rl2: existing && existing.rl2 };
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
  drawHeader();
  dlg.showModal();
  dlg.scrollTop = 0; body.scrollTop = 0;
  requestAnimationFrame(fit);
  if (!existing) name.focus();
  else if (!isStock) ta.focus({ preventScroll: true });
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
    pre.textContent = (typeof v.instructions === 'string'
      ? `── Instructions ──\n${v.instructions || '(none)'}`
      : Object.entries(v.variants).map(([k, x]) => `── ${VARIANTS[k]}, whole turn message (before 6-Oct) ──\n${x.prompt}`).join('\n\n'))
      + `\n\n── Settings ── ${deps.settingsSummary({ ...deps.FALLBACK_SETTINGS, ...v.settings })}${v.lean ? ' · lean turn message' : ''}`;
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
    // since 6-Oct a mode is its instructions; an old browser mode's are the lines its prompt added to Stock
    const instructions = typeof c.instructions === 'string' ? c.instructions
      : deps.instructionsOf({ base: 'turn', base_variant: variant, variants: { [variant]: { prompt: c.prompt || '' } } }, variant);
    const v = { purpose: c.purpose || '', trigger: 'Your choice.', budget: '' };
    const mode = { name, color: /^#[0-9a-f]{6}$/i.test(c.color || '') ? c.color : '#0e7490', base: 'turn', instructions,
      variants: { son: v, daniel: { ...v } },
      settings: c.settings || {}, settings_why: c.settings_why || '' };
    try {
      const r = await call('save', { method: 'POST', body: { id: null, mode, note: 'uploaded from a browser' } });
      ids[c.id] = r.mode.id;
      lib.modes.push(asPageMode(r.mode));
    } catch (e) { failed.push(`${c.name} (${e.message})`); }
  }
  return { ids, failed };
}
