/*
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: The Mode explorer's board picture (docs/mode-explorer.html, Queue view, next to the queue and Play). Son's ask,
  #arc-3 6-Oct 10:47 ET: "in the screen where you set up mode, at least show the screen at that time as well".
  For the selected game, level and wording it draws the board at the start Play would use, as a real ARC grid in the
  site's palette, and says what the picture is:
    exact     the chosen exact checkpoint's board (the runner replays its saved actions and checks the saved hash)
    reset     level 1: the game's first frame
    rebuilt   the stuck-level snapshot's board (replayed the same way)
    opening   no start there: the level's opening frame from the game file, and Play is not available
    replay    No context (added 6-Oct): the level start a No-context job plays from, replayed by the runner (an exact
              checkpoint's actions, else the original game's winning line) and checked against the expected board
  The board comes from the Spark runner through the site's relay (/api/v1/spark-runner/start-board, answered by
  tools/spark_runner/boards.py). When the runner cannot be reached, it falls back to the level's opening frame from
  the site's static copy (static/data/level-frames/<game>.json, written by boards.py --openings) and says so. Answers
  are kept per game, level, wording and start, so switching back is instant; a stale answer (the user moved on while
  it loaded) is dropped.
SRP/DRY check: Pass - drawing only; which start Play uses comes from spark-runner.js levelStart (passed in as ls) and
  the runner's own answer. Palette is the canonical ARC-3 one (games-play.js COLORS, constants.py COLOR_MAP).
*/

const API = new URL('../../api/v1/spark-runner/', import.meta.url);
const FRAMES = new URL('../data/level-frames/', import.meta.url);
// Canonical ARC-3 board palette (values 0-15), identical to games-play.js and the static game thumbnails.
const COLORS = [
  '#FFFFFF', '#CCCCCC', '#999999', '#666666', '#333333', '#000000', '#E53AA3', '#FF7BCC',
  '#F93C31', '#1E93FF', '#88D8F1', '#FFDC00', '#FF851B', '#921231', '#4FCC30', '#A356D6',
];
const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

const runnerBoards = new Map();   // `${game}:${level}:${variant}:${startKey}` -> Promise<answer>
const staticFrames = new Map();   // game -> Promise<{levels, frames}>
let shown = null;                 // the key the panel is drawing; a late answer for another key is dropped

function startKey(ls) {
  if (!ls || !ls.ok) return ls && ls.unknown ? 'unknown' : 'none';
  if (ls.kind === 'replay') return `replay-${ls.source}${ls.chosen ? '-' + ls.chosen.id : ''}`;
  return ls.kind === 'exact' ? `exact-${ls.chosen && ls.chosen.id}` : ls.kind;
}

async function fromRunner(game, level, variant, context) {
  const r = await fetch(new URL(`start-board?game=${encodeURIComponent(game)}&level=${level}&variant=${variant}&context=${context}`, API),
    { headers: { Accept: 'application/json' }, cache: 'no-store' });
  const type = r.headers.get('Content-Type') || '';
  if (r.redirected || !type.includes('json')) throw new Error(r.status === 401 || r.redirected ? 'sign in to the site again' : `HTTP ${r.status}`);
  const d = await r.json();
  if (!r.ok || !Array.isArray(d.grid)) throw new Error(d.message || d.detail || `HTTP ${r.status}`);
  return d;
}

async function fromStatic(game, level) {
  if (!staticFrames.has(game)) {
    staticFrames.set(game, fetch(new URL(`${game}.json`, FRAMES), { cache: 'no-cache' }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    }));
  }
  let d;
  try { d = await staticFrames.get(game); } catch (e) { staticFrames.delete(game); throw e; }
  const rows = d.frames[level - 1];
  if (!rows) throw new Error(`no opening frame for level ${level}`);
  return rows.map(row => Array.from(row, c => parseInt(c, 16)));
}

function draw(canvas, grid) {
  const rows = grid.length, cols = grid[0].length;
  // Drawn at a fixed number of device pixels per cell and scaled by CSS, so it stays crisp at any panel width.
  const cell = Math.max(4, Math.ceil(512 / Math.max(rows, cols)));
  canvas.width = cols * cell; canvas.height = rows * cell;
  const ctx = canvas.getContext('2d');
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      ctx.fillStyle = COLORS[grid[r][c]] || '#000000';
      ctx.fillRect(c * cell, r * cell, cell, cell);
    }
  }
  canvas.setAttribute('aria-label', `Game board, ${cols} by ${rows} cells`);
}

function caption(ls, level, answer, fallback) {
  if (fallback) {
    return `The opening frame of level ${level} from the game file. The Spark runner cannot be reached right now (${fallback}), ` +
      (ls && ls.ok ? "so this is not drawn from Play's own start; at a level start the two are almost always the same board."
        : ls && ls.unknown ? 'so whether Play can start here is not known.' : 'and Play has no start at this level yet.');
  }
  switch (answer.kind) {
    case 'replay':
      if (answer.replay_source === 'reset') return 'The board a No-context Play starts from: the first frame of the game.';
      return `The board a No-context Play starts from: replayed through ${answer.actions_to_reach} actions ` +
        (answer.replay_source === 'checkpoint' ? "of a saved start" : 'of the recorded winning line') +
        (answer.matches_saved_board === false ? ' (warning: it does not match the expected board).' : ' and checked against the expected board. The model sees this board with a clean conversation.');
    case 'exact':
      return `The board Play starts from: the exact saved start, reached in ${answer.actions_to_reach} actions from the first frame` +
        (answer.matches_saved_board === false ? ' (warning: the replayed board does not match the one saved with it).' : ', replayed and checked against the board saved with it.');
    case 'reset':
      return 'The board Play starts from: the first frame of the game.';
    case 'rebuilt':
      return `The board Play starts from: the stuck-level snapshot, replayed through ${answer.actions_to_reach} actions` +
        (answer.matches_saved_board === false ? ' (warning: it does not match the board saved with it).' : ' and checked against the board saved with it.');
    default:
      return `Play is not available at level ${level} yet, so this is the level's opening frame from the game file.`;
  }
}

// box: the panel element. ctx: {game (stuck-levels row), level, variant, context ('carried' | 'none'), ls (levelStart
// for that level and context)}.
export function renderStartBoard(box, ctx) {
  const { game: g, level, variant, ls } = ctx;
  const context = ctx.context === 'none' ? 'none' : 'carried';
  const key = `${g.game}:${level}:${variant}:${context}:${startKey(ls)}`;
  if (shown === key && box.querySelector('canvas')) return;
  shown = key;
  box.textContent = '';
  const head = h('div', 'mx-bdhead');
  head.append(h('span', 'mx-bdtitle', `Level ${level} at the start`), h('span', 'mx-bdkind', ls && ls.ok ? (ls.kind === 'exact' ? 'exact start' : ls.kind === 'reset' ? 'fresh game' : ls.kind === 'rebuilt' ? 'snapshot' : ls.kind === 'replay' ? 'no context, replayed' : '') : ls && ls.unknown ? 'start not known' : 'no start yet'));
  const frame = h('div', 'mx-bdframe' + (ls && !ls.ok && !ls.unknown ? ' off' : ''));
  const canvas = h('canvas', 'mx-bdcanvas');
  canvas.setAttribute('role', 'img');
  frame.append(canvas, h('span', 'mx-bdwait', 'drawing the board…'));
  const note = h('p', 'mx-bdnote', '');
  box.append(head, frame, note);

  if (!runnerBoards.has(key)) {
    const p = fromRunner(g.game, level, variant, context);
    runnerBoards.set(key, p);
    p.catch(() => runnerBoards.delete(key));   // try the runner again next time
  }
  runnerBoards.get(key).then(answer => {
    if (shown !== key) return;
    draw(canvas, answer.grid);
    frame.classList.add('ready');
    note.textContent = caption(ls, level, answer, null);
  }).catch(async (err) => {
    if (shown !== key) return;
    try {
      const grid = await fromStatic(g.game, level);
      if (shown !== key) return;
      draw(canvas, grid);
      frame.classList.add('ready');
      note.textContent = caption(ls, level, null, err.message);
    } catch (e2) {
      if (shown !== key) return;
      frame.classList.add('failed');
      note.textContent = `Could not draw the board: the runner said "${err.message}" and the site's copy of the opening frames failed (${e2.message}).`;
    }
  });
}
