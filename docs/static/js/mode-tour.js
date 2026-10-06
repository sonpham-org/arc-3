/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: The Mode explorer's guided tour (docs/mode-explorer.html), started by the "?" Help button in the pinned dock
  (Son, #arc-3 6-Oct 13:10 ET: "You can even do a demo too. Have like a 'Help' icon, and do a demo."). A spotlight dims
  the page and cuts holes around one control (or a few) at a time, with a small caption card: step counter, Back /
  Next / Skip, arrow keys, Esc. Steps: game list, level buttons, context switch, board, mode bar, the pencil that
  opens the mode editor (added 6-Oct with the editor rework: where the text goes, locked harness lines, the one
  editable instruction, lean turn message), queue, samples and turn cap, Play, results, and the Help button itself.
  Demo: while the tour runs, the page (through the host object mode-explorer.js passes in) picks a sample game and
  level, flies Probe, Hypothesize and Execute from the mode bar into the queue, opens one turn's settings for a moment,
  and the Play step can show what Play would send without sending it. The host keeps all of that in memory only (no
  localStorage writes, no URL changes) and puts the person's own view, game, level, context and queues back when the
  tour ends, however it ends. The real page is made inert and a full-screen shade swallows every click, so nothing
  under the spotlight can be pressed: no Play, no Cancel, no mode edits.
  On a phone the card sits along the bottom of the screen and each step scrolls its control into view under the
  pinned bars. With prefers-reduced-motion the modes are placed without the flying animation and scrolling jumps.
SRP/DRY check: Pass — this file only draws the tour and runs its steps; every change to the page goes through the
  host's own functions in mode-explorer.js (pickGame, pickLevel, addItem, the settings toggle), and the Play preview
  is spark-runner.js's own request builder, so the demo shows exactly what Play would send.
*/

const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const PAD = 6;
const reduced = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const phone = () => window.innerWidth <= 600;
const pause = (ms) => new Promise(r => setTimeout(r, reduced() ? Math.min(ms, 150) : ms));
const px = (name) => parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)) || 0;

let T = null;   // the running tour, or null

// Each step: title, text (a string or a function of the host), the elements to light up, and what the demo does on
// arriving (enter) and leaving (leave). enter must be safe to run again (Back, then Next).
function steps(host) {
  const $ = (sel) => document.querySelector(sel);
  return [
    { title: 'A quick tour, with a demo',
      text: 'This tour points at each part of the page and shows it working on a sample game. It only pretends: nothing is sent to the Sparks and nothing is saved. When it ends, your own game, level and queue come back exactly as they were. Arrow keys or the buttons move along; Esc leaves.',
      targets: () => [] },
    { title: 'Pick a game',
      text: () => `The games the Sparks can play, hardest first. The small badge is the level where stock runs usually get stuck. The demo picked ${host.demo().nickname}.`,
      targets: () => [$('#gamebar')],
      enter: () => host.demoGame() },
    { title: 'Pick a level',
      text: () => `Play starts from the level you pick. The green fill shows how often stock runs clear it, and the thin bar along the bottom how often Spark runs did. A dot marks an exact saved start, a ring a fresh or rebuilt start; a greyed level cannot start yet (hover it, or tap it on a phone, for why). The demo picked level ${host.demo().level}.`,
      targets: () => [$('.mx-levelbox')],
      enter: () => { host.demoGame(); host.demoLevel(); } },
    { title: 'Carry context or No context',
      text: 'Carry context starts the level with what an earlier run of the game learned before it. No context puts the board at the same level start but gives the model a clean first turn, as in a new game.',
      targets: () => [$('.mx-ctxseg')] },
    { title: 'The board at the start',
      text: 'The board the model sees on its first turn, for the chosen game, level and context. The line under it says where the picture comes from.',
      targets: () => [$('#startboard')] },
    { title: 'Modes',
      text: 'Each mode is one turn\'s instructions. Drag a mode into the queue, or tap it on a phone. The pencil next to a mode edits it for everyone, and every save keeps a new version; New mode adds one. Watch: Probe, Hypothesize and Execute go into the queue.',
      targets: () => [$('#modes'), $('#queue')],
      enter: (live) => host.fillQueue(live, true) },
    { title: 'Editing a mode',
      text: 'The pencil opens the mode editor in a large window. It shows where the text goes: the system prompt is the same for every mode and a mode never changes it; a mode only edits the turn message, sent as the user message at the start of each turn it runs. Grey lines with a lock come from the harness and cannot be edited there; the highlighted box, the mode\'s own instruction, is the only text you change. The tool-call lines the system prompt already says are marked, and "Lean turn message" leaves them out: Stock (lean) is Stock with that on, to test it against plain Stock.',
      targets: () => [$('#modes .mx-chipedit') || $('#modes')],
      enter: (live) => host.fillQueue(live, false) },
    { title: 'The queue',
      text: 'One mode runs per turn, in this order; drag an item to move it. The gear opens that turn\'s own settings (open here for the first turn), the x takes it out, and Stock plays every turn after the queue.',
      targets: () => [$('#queue'), $('#slotset')],
      enter: (live) => { host.fillQueue(live, false); host.settings(0); },
      leave: () => host.settings(-1) },
    { title: 'Samples and turn cap',
      text: 'Samples is how many times the level is played from the same start. Turns max is the most model turns each sample gets, the queue included.',
      targets: () => [...document.querySelectorAll('#playrow .mx-inl')],
      enter: (live) => host.fillQueue(live, false) },
    { title: 'Play',
      text: 'Play sends the queue to the Sparks. They run one job at a time, so yours may wait in line; its place shows in the results. The tour never presses it; the button below only shows what it would send.',
      targets: () => [$('#playrow .mx-play'), $('#playrow .mx-playnote')],
      enter: (live) => host.fillQueue(live, false),
      extra: () => previewButton(host) },
    { title: 'Results',
      text: 'Everything that ran for this game and level shows here: a live job with each sample\'s turn and mode as it plays, then past runs, newest first, next to stock. Every run records the exact version and wording of each mode it used.',
      targets: () => [$('#results')],
      enter: (live) => host.fillQueue(live, false) },
    { title: 'That\'s it',
      text: 'Press ? any time to take this tour again; the how-to panel at the top has the short version. Finish puts your own game, level and queue back.',
      targets: () => [$('#tourhelp')] },
  ];
}

// "What Play would send": the request Play would build right now, as plain lines, shown in the card only.
function previewButton(host) {
  const wrap = h('div', 'mx-tour-extra');
  const b = h('button', 'mx-tool', 'Show what Play would send');
  b.type = 'button';
  b.onclick = () => {
    const lines = host.playPreview();
    const list = h('ul', 'mx-tour-send');
    for (const l of lines) list.append(h('li', null, l));
    wrap.replaceChildren(h('p', 'mx-tour-sendh', 'Play would send this (not sent):'), list);
    place();
  };
  wrap.append(b);
  return wrap;
}

// ---------------------------------------------------------------- shade, holes and card

function build() {
  const root = h('div', 'mx-tour');
  // the dim layer; each lit area is cut out of it with an even-odd clip path (see frame)
  const shade = h('div', 'mx-tour-shade');
  shade.setAttribute('aria-hidden', 'true');
  const rings = h('div', 'mx-tour-rings'); rings.setAttribute('aria-hidden', 'true');
  const card = h('div', 'mx-tour-card');
  card.setAttribute('role', 'dialog'); card.setAttribute('aria-modal', 'true'); card.setAttribute('aria-labelledby', 'mx-tour-title');
  // a transparent layer over everything, holes included, takes every click and touch: nothing lit can be pressed
  const block = h('div', 'mx-tour-block');
  block.addEventListener('pointerdown', (e) => e.preventDefault());
  root.append(shade, block, rings, card);
  return { root, shade, rings, card };
}

function visibleRect(el) {
  if (!el || !el.isConnected) return null;
  const r = el.getBoundingClientRect();
  if (!r.width && !r.height) return null;
  const x0 = Math.max(r.left - PAD, 0), y0 = Math.max(r.top - PAD, 0);
  const x1 = Math.min(r.right + PAD, innerWidth), y1 = Math.min(r.bottom + PAD, innerHeight);
  return x1 > x0 && y1 > y0 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
}

// Redrawn every frame while the tour is open: holes follow scrolling, sticky bars and the page redrawing itself.
function frame() {
  if (!T) return;
  const rects = T.targets().map(visibleRect).filter(Boolean);
  const key = rects.map(r => `${r.x|0},${r.y|0},${r.w|0},${r.h|0}`).join(';') + `|${innerWidth}x${innerHeight}`;
  if (key !== T.key) {
    T.key = key;
    const W = innerWidth, H = innerHeight;
    const path = [`M0 0H${W}V${H}H0Z`].concat(rects.map(r => `M${r.x} ${r.y}h${r.w}v${r.h}h${-r.w}Z`)).join('');
    T.ui.shade.style.clipPath = `path(evenodd, "${path}")`;
    T.ui.rings.replaceChildren();
    for (const r of rects) {
      const ring = h('div', 'mx-tour-ring');
      Object.assign(ring.style, { left: `${r.x}px`, top: `${r.y}px`, width: `${r.w}px`, height: `${r.h}px` });
      T.ui.rings.append(ring);
    }
    T.rects = rects;
    place();
  }
  T.raf = requestAnimationFrame(frame);
}

// The card goes under the lit area if it fits, else above it, else beside it; on a phone, or when nothing fits,
// along the bottom of the screen (centred when nothing is lit).
function place() {
  if (!T) return;
  const card = T.ui.card, rects = T.rects || [];
  card.classList.remove('bottom', 'centre');
  card.style.left = card.style.top = '';
  if (!rects.length) { card.classList.add(phone() ? 'bottom' : 'centre'); return; }
  if (phone()) { card.classList.add('bottom'); return; }
  const u = rects.reduce((a, r) => ({ x0: Math.min(a.x0, r.x), y0: Math.min(a.y0, r.y), x1: Math.max(a.x1, r.x + r.w), y1: Math.max(a.y1, r.y + r.h) }),
    { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity });
  const cw = card.offsetWidth, ch = card.offsetHeight, gap = 12, m = 12;
  const left = Math.min(Math.max(u.x0, m), innerWidth - cw - m);
  let pos = null;
  if (u.y1 + gap + ch <= innerHeight - m) pos = { left, top: u.y1 + gap };
  else if (u.y0 - gap - ch >= m) pos = { left, top: u.y0 - gap - ch };
  else if (u.x1 + gap + cw <= innerWidth - m) pos = { left: u.x1 + gap, top: Math.min(Math.max(u.y0, m), innerHeight - ch - m) };
  else if (u.x0 - gap - cw >= m) pos = { left: u.x0 - gap - cw, top: Math.min(Math.max(u.y0, m), innerHeight - ch - m) };
  if (!pos) { card.classList.add('bottom'); return; }
  card.style.left = `${pos.left}px`; card.style.top = `${pos.top}px`;
}

// Scroll the step's first element outside the dock to just under the pinned site tabs and dock (the dock is always in
// sight), so on the Modes step the queue the modes fly into is in view too.
function reveal(els) {
  const el = els.find(e => !e.closest('#dock'));
  if (!el) return;
  const top = el.getBoundingClientRect().top + scrollY - (px('--navh') + px('--dockh') + 14);
  if (Math.abs(top - scrollY) < 4) return;
  scrollTo({ top: Math.max(top, 0), behavior: reduced() ? 'auto' : 'smooth' });
}

function drawCard(step, i, n) {
  const card = T.ui.card; card.replaceChildren();
  const head = h('div', 'mx-tour-head');
  head.append(h('span', 'mx-tour-count', `${i + 1} of ${n}`));
  const skip = h('button', 'mx-tour-skip', i === n - 1 ? '' : 'Skip tour');
  skip.type = 'button'; skip.onclick = () => endTour();
  if (i < n - 1) head.append(skip);
  card.append(head);
  const title = h('h2', 'mx-tour-title', step.title); title.id = 'mx-tour-title';
  const body = h('p', 'mx-tour-text', typeof step.text === 'function' ? step.text() : step.text);
  body.setAttribute('aria-live', 'polite');
  card.append(title, body);
  if (step.extra) card.append(step.extra());
  const btns = h('div', 'mx-tour-btns');
  const back = h('button', 'mx-tool', 'Back'); back.type = 'button'; back.disabled = i === 0; back.onclick = () => go(i - 1);
  const next = h('button', 'mx-play', i === n - 1 ? 'Finish' : 'Next'); next.type = 'button';
  next.onclick = () => (i === n - 1 ? endTour() : go(i + 1));
  btns.append(back, next);
  card.append(btns);
  next.focus({ preventScroll: true });
}

async function go(i) {
  if (!T || i < 0 || i >= T.steps.length) return;
  const prev = T.steps[T.i];
  if (prev && prev.leave && T.i !== i) prev.leave();
  T.i = i;
  const token = ++T.token;
  const step = T.steps[i];
  const live = () => T && T.token === token;   // false once the person moved on or left
  T.targets = () => step.targets().filter(Boolean);
  T.key = null;
  if (step.enter) {
    const p = step.enter(live);
    // the page redraws synchronously; the flying modes run on while the card is already up
    drawCard(step, i, T.steps.length);
    reveal(T.targets());
    await p;
    if (!live()) return;
    T.key = null;
  } else {
    drawCard(step, i, T.steps.length);
    reveal(T.targets());
  }
}

function onKey(e) {
  if (!T) return;
  if (e.key === 'Escape') { e.preventDefault(); endTour(); return; }
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); if (T.i < T.steps.length - 1) go(T.i + 1); return; }
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); go(T.i - 1); return; }
  if (e.key === 'Tab') {   // focus stays in the card
    const f = [...T.ui.card.querySelectorAll('button:not(:disabled)')];
    if (!f.length) return;
    const k = f.indexOf(document.activeElement);
    e.preventDefault();
    f[(k + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus();
  }
}

// ---------------------------------------------------------------- start and end

export function startTour(host) {
  if (T) return;
  if (!host.ready()) { host.notReady(); return; }
  const ui = build();
  const back = document.activeElement;
  host.begin();
  T = { host, ui, i: -1, token: 0, steps: steps(host), targets: () => [], key: null, rects: [], raf: 0, back };
  for (const el of document.querySelectorAll('body > nav, body > main')) el.inert = true;
  document.body.append(ui.root);
  document.body.classList.add('mx-touring');
  addEventListener('keydown', onKey, true);
  addEventListener('resize', place);
  T.raf = requestAnimationFrame(frame);
  go(0);
}

export function endTour() {
  if (!T) return;
  const t = T;
  T = null;
  cancelAnimationFrame(t.raf);
  removeEventListener('keydown', onKey, true);
  removeEventListener('resize', place);
  const step = t.steps[t.i];
  if (step && step.leave) step.leave();
  t.ui.root.remove();
  for (const g of document.querySelectorAll('.mx-tour-ghost')) g.remove();
  for (const el of document.querySelectorAll('body > nav, body > main')) el.inert = false;
  document.body.classList.remove('mx-touring');
  t.host.end();
  if (t.back && t.back.isConnected) t.back.focus({ preventScroll: true });
}

export function touring() { return !!T; }

// A copy of a mode chip flies from the bar to the end of the queue (skipped with reduced motion); the caller then adds
// the item for real. Resolves when it lands, or at once when the tour has moved on.
export async function flyChip(chip, live) {
  const q = document.getElementById('queue');
  if (!chip || !q || reduced()) return;
  const tail = q.querySelector('.mx-qtail') || q;
  const from = chip.getBoundingClientRect(), to = tail.getBoundingClientRect();
  const ghost = chip.cloneNode(true);
  ghost.classList.add('mx-tour-ghost');
  ghost.removeAttribute('id');
  Object.assign(ghost.style, { left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px` });
  document.body.append(ghost);
  const dx = to.left - from.left, dy = to.top - from.top;
  const anim = ghost.animate([
    { transform: 'translate(0, 0) scale(1)' },
    { transform: `translate(${dx * 0.5}px, ${dy * 0.5 - 30}px) scale(1.06)`, offset: 0.5 },
    { transform: `translate(${dx}px, ${dy}px) scale(1)` },
  ], { duration: 750, easing: 'ease-in-out', fill: 'forwards' });
  const stop = setInterval(() => { if (!live()) anim.finish(); }, 50);
  try { await anim.finished; } catch { /* cancelled */ }
  clearInterval(stop);
  ghost.remove();
}

export { pause };
