/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: Shared, versioned modes for the Mode explorer (docs/mode-explorer.html). Son's ask, #arc-3 6-Oct 08:42 ET:
  "Mark needs a way to edit and add new modes, is it there? And when will the mode be recorded?"
  - loadLibrary: the current version of every mode from the site's database (/api/v1/modes, railway/modes_store.py),
    the same for everyone signed in. Built-in modes are version 1 from modes.json; every save is a new version with
    who and when, old versions are kept and can be restored, delete hides a mode (history kept).
  - openEditor: the small editor behind the Edit button on each mode chip (and "+ New mode", which starts from Stock):
    name and colour, the prompt text in Son's and Franzen's wording where the mode has both, a live line diff against
    the harness's Stock prompt (the text the Spark runner diffs against), the settings (temperature, thinking,
    effort, thinking budget, tool calls, action budget), an optional note, Save as a new version, the version
    history with Restore, and Delete. It warns when an edit would be refused by the runner (removing a templated
    Stock line, or adding a line with a {placeholder} or a [when] marker).
  - migrateLocal: custom modes from the old browser-only store are offered for upload once, then uploaded as shared
    modes; queues that used them are pointed at the uploaded ids. The browser copy is kept.
  - loadRuns: what each Play recorded (the exact mode versions and text sent), for the results list.
SRP/DRY check: Pass - drawing helpers, the settings grid and the line diff are passed in from mode-explorer.js so they
  exist once; storage rules live in railway/modes_store.py; the runner's literal-line rule mirrors
  tools/spark_runner/modes.py (is_literal) so the warning matches what Play would refuse.
*/

const API = new URL('../../api/v1/modes/', import.meta.url);
const PLACEHOLDER = /\{[^{}\s]+\}/;
const CONDITION = /^\[when [^\]]*\]\s*/;
const VARIANTS = { son: "Son's wording", daniel: "Franzen's wording" };
let deps = null;     // { h, settingsGrid, diffLines, FALLBACK_SETTINGS, stockText(variant, base), flash }

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

// Compact unified diff: changed lines only, with one line of context around each run.
function diffView(box, stock, text) {
  const { h } = deps;
  box.textContent = '';
  const rows = deps.diffLines(stock.split('\n'), text.split('\n'));
  const keep = rows.map((r, i) => r[0] !== 'same' || (rows[i - 1] && rows[i - 1][0] !== 'same') || (rows[i + 1] && rows[i + 1][0] !== 'same'));
  if (!rows.some(r => r[0] !== 'same')) { box.append(h('div', 'mx-ed-same', 'Same text as Stock.')); return; }
  let gap = false;
  rows.forEach(([kind, l, r], i) => {
    if (!keep[i]) { if (!gap) box.append(h('div', 'mx-ed-gap', '⋯')); gap = true; return; }
    gap = false;
    if (kind === 'same') box.append(h('div', 'mx-ed-ctx', '  ' + l));
    if (kind === 'del' || kind === 'chg') box.append(h('div', 'mx-ed-del', '− ' + l));
    if (kind === 'add' || kind === 'chg') box.append(h('div', 'mx-ed-add', '+ ' + r));
  });
}

// ---------------------------------------------------------------- editor

// id null = new mode, starting from the current Stock mode. onSaved(mode) after any change that made a version.
export function openEditor(id, { variant, stockMode, onSaved }) {
  const { h, settingsGrid, FALLBACK_SETTINGS } = deps;
  const existing = id ? lib.modes.find(m => m.id === id) : null;
  const src = existing || stockMode;
  // edit the stored wordings, not the page's filled-in copies
  // a new mode starts with the wording on screen only; the other can be added with its own tab
  const stored = existing ? (existing.base_variant ? { [existing.base_variant]: existing.variants[existing.base_variant] } : existing.variants)
    : { [variant]: stockMode.variants[variant] };
  const draft = {
    name: existing ? existing.name : '', color: existing ? existing.color : '#0e7490', base: existing ? existing.base : 'turn',
    variants: JSON.parse(JSON.stringify(stored)), settings: { ...FALLBACK_SETTINGS, ...(src.settings || {}) },
    settings_why: existing ? existing.settings_why || '' : '',
  };
  if (!existing) for (const v of Object.values(draft.variants)) { v.purpose = ''; v.trigger = 'Your choice.'; v.budget = ''; }
  let tab = draft.variants[variant] ? variant : Object.keys(draft.variants)[0];

  const dlg = document.getElementById('modedlg'); dlg.textContent = '';
  const form = h('form', 'mx-form mx-edform'); form.method = 'dialog';
  const title = h('div', 'mx-edtitle');
  title.append(h('h2', null, existing ? `Edit ${existing.name}` : 'New mode'));
  if (existing) title.append(h('span', 'mx-rl2', `${versionTag(existing)} · ${whoWhen(existing.created_by, existing.created_at)}`));
  form.append(title);
  form.append(h('p', 'mx-sum', existing
    ? 'Shared with everyone signed in. Saving makes a new version; older versions stay in the history and can be restored.'
    : 'Starts as Stock. Add your focus lines where you want them. Shared with everyone signed in once saved.'));

  const lab = (t, el, cls) => { const l = h('label', 'mx-field' + (cls ? ' ' + cls : '')); l.append(h('span', 'mx-flabel', t), el); return l; };
  const row = h('div', 'mx-formrow');
  const name = h('input'); name.required = true; name.maxLength = 32; name.value = draft.name; name.placeholder = 'e.g. Map the board';
  const color = h('input'); color.type = 'color'; color.value = draft.color;
  row.append(lab('Name', name, 'grow'), lab('Colour', color));
  form.append(row);

  // wording tabs: one per variant the mode has
  const tabs = h('div', 'mx-segs mx-edtabs');
  const purpose = h('input'); purpose.placeholder = 'What this turn is for, in one line'; purpose.maxLength = 500;
  const prompt = h('textarea', 'mx-prompt'); prompt.rows = 10; prompt.spellcheck = false;
  const diffBox = h('div', 'mx-ed-diff');
  const diffHead = h('div', 'mx-flabel');
  const warn = h('p', 'mx-ed-warn'); warn.hidden = true;
  const stockOf = (k) => deps.stockText(k, draft.base);
  const redraw = () => {
    const text = draft.variants[tab].prompt;
    diffHead.textContent = `Difference from the harness's Stock prompt (${VARIANTS[tab].replace(' wording', '')})`;
    diffView(diffBox, stockOf(tab), text);
    const probs = Object.keys(draft.variants).flatMap(k => runnerProblems(stockOf(k), draft.variants[k].prompt).map(p => `${VARIANTS[k]}: ${p}`));
    warn.hidden = !probs.length;
    warn.textContent = probs.length ? `Play would refuse this: ${probs.slice(0, 3).join('; ')}. The runner only adds plain lines and removes plain lines.` : '';
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
      if (draft.variants[k]) continue;
      const b = h('button', 'mx-seg', `+ ${VARIANTS[k]}`); b.type = 'button';
      b.title = `Add a ${VARIANTS[k]} version, starting from that Stock prompt`;
      b.onclick = () => { draft.variants[k] = { purpose: draft.variants[tab].purpose, trigger: '', budget: '', prompt: stockOf(k) }; tab = k; fill(); };
      tabs.append(b);
    }
  };
  const fill = () => { drawTabs(); purpose.value = draft.variants[tab].purpose || ''; prompt.value = draft.variants[tab].prompt; redraw(); };
  let t = 0;
  prompt.oninput = () => { draft.variants[tab].prompt = prompt.value; clearTimeout(t); t = setTimeout(redraw, 150); };
  purpose.oninput = () => { draft.variants[tab].purpose = purpose.value; };
  form.append(tabs, lab('Purpose', purpose, 'wide'), lab('Prompt (sent as the turn message)', prompt, 'wide'));
  const dwrap = h('div', 'mx-field wide'); dwrap.append(diffHead, diffBox); form.append(dwrap, warn);

  const det = h('details', 'mx-ed-settings');
  const sum = h('summary', null, 'Settings'); det.append(sum);
  const sumText = () => { sum.textContent = `Settings · ${deps.settingsSummary(draft.settings)}`; };
  det.append(settingsGrid(() => draft.settings, (k, v) => { draft.settings[k] = v; sumText(); }));
  const why = h('textarea'); why.rows = 2; why.value = draft.settings_why; why.placeholder = 'Why these settings (optional)';
  det.append(lab('Why these settings', why, 'wide'));
  sumText();
  form.append(det);
  const note = h('input'); note.maxLength = 200; note.placeholder = existing ? 'What changed (optional, shows in the history)' : 'Optional note';
  form.append(lab('Note', note, 'wide'));
  const status = h('p', 'mx-sum mx-ed-status');

  const btns = h('div', 'mx-formbtns');
  const save = h('button', 'mx-play', existing ? 'Save new version' : 'Create mode'); save.type = 'submit';
  const cancel = h('button', 'mx-tool', 'Cancel'); cancel.type = 'button'; cancel.onclick = () => dlg.close();
  btns.append(save, cancel);
  const hist = h('div', 'mx-ed-hist'); hist.hidden = true;
  if (existing) {
    const hb = h('button', 'mx-tool', `History (${existing.versions || 1})`); hb.type = 'button';
    hb.onclick = () => { hist.hidden = !hist.hidden; if (!hist.hidden) drawHistory(hist, existing, dlg, onSaved, status); };
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
      form.append(p);
    }
  }
  form.append(btns, status, hist);

  form.onsubmit = async (e) => {
    e.preventDefault();
    const nm = name.value.trim();
    if (!nm) { name.focus(); return; }
    for (const [k, v] of Object.entries(draft.variants)) if (!v.prompt.trim()) { tab = k; fill(); prompt.focus(); return; }
    const taken = lib.modes.find(m => !m.hidden && m.id !== (existing && existing.id) && m.name.toLowerCase() === nm.toLowerCase());
    if (taken) { name.setCustomValidity(`A mode called ${nm} already exists.`); name.reportValidity(); name.oninput = () => name.setCustomValidity(''); return; }
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
  dlg.append(form);
  fill();
  dlg.showModal();
  if (!existing) name.focus();
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
    pre.textContent = Object.entries(v.variants).map(([k, x]) => `── ${VARIANTS[k]} ──\n${x.prompt}`).join('\n\n') + `\n\n── Settings ── ${deps.settingsSummary({ ...deps.FALLBACK_SETTINGS, ...v.settings })}`;
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
