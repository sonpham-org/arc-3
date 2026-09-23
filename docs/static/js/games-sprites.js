// Games page: the per-game sprite editor in the play view's sidebar, beside the tuning panel.
//
// A game's editable art is declared as data, not code: docs/static/games/sprites/<id>.json lists
// the literal glyphs worth repainting, each with the exact source text that locates it. No spec
// file means no Sprites tab -- that is the normal case, and it is silent. Most of the catalog has
// no sprite to edit: the dominant drawing idiom is a solid rectangle painted at a computed offset
// (`f[24:35, x:x+7] = AGENT`), which has no pixel art in it at all.
//
// Painting a cell does not talk to the game object. It rewrites that one literal in the source
// text the player was loaded from and hands the whole patched module back through the same
// applyTunedSource() the tuning panel uses, which re-execs it in the Pyodide worker. Sprite edits
// and knob edits therefore compose through one pipeline rather than two racing ones -- see
// games-play.js, which patches knobs first and sprites second onto the same base source.
//
// Three things keep it honest against a moving catalog. A sprite is anchored on the exact source
// text of its own literal -- not a name (the good ones are nested two dicts deep, at
// SPECIES_ART["ladybird"]["stand"]) and not a line number (the bytes the player runs come from the
// API's head, which moves). The anchor must occur exactly once in the fetched source or the sprite
// is dropped from the panel rather than patched blind, which is the rule readScalar() uses in
// games-tuning.js for the same reason. And a bad paint is a Python exception, not a validation
// error we could have predicted, so the last art that loaded is kept and a failed load is rolled
// back to it before the message is shown.
//
// The brush is restricted to the symbols the sprite already uses, which is a correctness
// requirement and not a simplification. Cell values mean different things per game: some store
// ARC palette indices, some store indices into a two-entry colour tuple (painting a 12 there is
// an IndexError, not a recolour), and sd78 maps characters through its own ART_KEY where "X"
// means "substitute the species colour at build time". A 16-swatch palette would be correct for
// one encoding and broken for the rest.

const SPEC_DIR = "./static/games/sprites/";

// ── Reading and patching ─────────────────────────────────────────────────────
// Mirrored from scripts/measure_game_sprites.py (render/patch). The two must agree exactly: the
// spec's recorded default is produced there, and this has to reproduce it byte for byte to know
// an unedited sprite is unedited -- and to find the anchor again on a second paint.

const isGrid = (rows, cols, value) =>
  Array.isArray(value) && value.length === rows && value.every((r) => Array.isArray(r) && r.length === cols);

// The indent the literal's rows sit at, and the one its closing bracket sits at. Not the same:
// art nested inside a call is written one level in from its own bracket.
const rowIndent = (anchor) => (anchor.split("\n")[1] || "").match(/^[ \t]*/)[0];
const closeIndent = (anchor) => (anchor.split("\n").pop() || "").match(/^[ \t]*/)[0];

// `grid` written back in the anchor's own bracket, quote and layout style. Style is preserved
// rather than normalised because an untouched sprite has to come back identical.
export function renderSprite(sprite, grid) {
  const anchor = sprite.anchor;
  const open = anchor[0];
  const close = open === "[" ? "]" : ")";
  const quote = anchor.includes('"') ? '"' : "'";
  let pieces;
  if (sprite.encoding === "charStencil") {
    pieces = grid.map((row) => `${quote}${row.join("")}${quote}`);
  } else if (sprite.encoding === "intGrid") {
    const inner = open === "[" ? ["[", "]"] : ["(", ")"];
    pieces = grid.map((row) => `${inner[0]}${row.join(", ")}${inner[1]}`);
  } else {
    // offsets: a sparse pixel set, emitted in the order the grid is scanned.
    pieces = grid.map((p) => `(${p[0]}, ${p[1]})`);
  }
  if (anchor.includes("\n")) {
    const body = pieces.map((piece) => `\n${rowIndent(anchor)}${piece},`).join("");
    return `${open}${body}\n${closeIndent(anchor)}${close}`;
  }
  return `${open}${pieces.join(", ")}${close}`;
}

// `source` with this one sprite's literal replaced, or the source untouched if its anchor no
// longer occurs exactly once. Never guesses at a near match.
export function patchSprite(source, sprite, grid) {
  const anchor = sprite.anchor;
  if (!anchor || source.split(anchor).length !== 2) return source;
  return source.replace(anchor, renderSprite(sprite, grid));
}

// Every sprite in `spec` that this exact source text still supports. The source wins: a sprite
// whose anchor has been rewritten by the evolution loop is dropped, not applied against a guess.
export function resolveSprites(spec, source) {
  if (!spec || spec.schema !== 1 || !Array.isArray(spec.sprites)) return [];
  const out = [];
  for (const s of spec.sprites) {
    if (!s || !s.anchor || !s.rows || !s.cols) continue;
    if (source.split(s.anchor).length !== 2) continue; // absent, or ambiguous
    const grid = toGrid(s);
    if (!grid) continue;
    out.push({ ...s, base: grid });
  }
  return out;
}

// A sprite's published art as a rows x cols array of cell symbols, whatever encoding it is
// stored in. `offsets` is the odd one: a sparse pixel set becomes a boolean grid over its own
// bounding box, and comes back out as coordinates again.
export function toGrid(sprite) {
  const { rows, cols, encoding, default: art } = sprite;
  if (encoding === "charStencil") {
    if (!Array.isArray(art) || art.length !== rows) return null;
    return art.map((row) => [...String(row)]);
  }
  if (encoding === "intGrid") {
    return isGrid(rows, cols, art) ? art.map((row) => [...row]) : null;
  }
  if (encoding === "offsets") {
    if (!Array.isArray(art)) return null;
    const grid = Array.from({ length: rows }, () => Array(cols).fill(0));
    for (const [x, y] of art) {
      const gy = y - sprite.originY;
      const gx = x - sprite.originX;
      if (gy >= 0 && gy < rows && gx >= 0 && gx < cols) grid[gy][gx] = 1;
    }
    return grid;
  }
  return null;
}

// The inverse of toGrid: the editor's grid in the shape the source literal wants.
export function fromGrid(sprite, grid) {
  if (sprite.encoding === "charStencil") return grid.map((row) => row);
  if (sprite.encoding === "intGrid") return grid;
  const out = [];
  for (let y = 0; y < grid.length; y += 1) {
    for (let x = 0; x < grid[y].length; x += 1) {
      if (grid[y][x]) out.push([x + sprite.originX, y + sprite.originY]);
    }
  }
  return out;
}

export const sameGrid = (a, b) =>
  a.length === b.length && a.every((row, y) => row.length === b[y].length && row.every((c, x) => c === b[y][x]));

async function fetchSpec(gameId) {
  if (!/^[A-Za-z0-9_-]+$/.test(gameId || "")) return null;
  try {
    // Rewritten in place as a game is re-tuned, so never cached -- same reasoning as manifest.json.
    const response = await fetch(`${SPEC_DIR}${gameId}.json`, { cache: "no-store" });
    if (!response.ok) return null; // 404 is the ordinary answer: this game has no art to edit.
    return await response.json();
  } catch (e) {
    return null;
  }
}

// Pyodide hands the whole traceback back as the message; the sidebar has room for the last line,
// which is the one that names the fault.
function briefly(err) {
  const text = String((err && err.message) || err || "the patched game did not load").trim();
  const last = text.split("\n").map((line) => line.trim()).filter(Boolean).pop() || text;
  return last.length > 140 ? `${last.slice(0, 139)}…` : last;
}

// ── The panel ────────────────────────────────────────────────────────────────

// `apply(values)` is the caller's business: it owns the patch composition, the engine call, the
// load token and the repaint. It resolves when the patched module is running and throws
// otherwise; this module only decides what to paint and what to do when it did not take.
export function createSprites({ root, apply }) {
  let sprites = [];
  let source = "";
  let values = new Map();    // sprite id -> the grid on screen
  let lastGood = new Map();  // the last set that loaded
  let brush = new Map();     // sprite id -> the symbol being painted with
  let cells = new Map();     // sprite id -> array of cell buttons
  let busy = false;
  let pending = false;

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };

  const status = el("p", "tune-msg");
  status.hidden = true;

  function setStatus(text, bad) {
    status.textContent = text || "";
    status.classList.toggle("tune-bad", !!bad);
    status.hidden = !text;
  }

  function hide() {
    root.hidden = true;
    root.replaceChildren();
    sprites = [];
    cells = new Map();
    pending = false;
  }

  const copy = (grid) => grid.map((row) => [...row]);

  // What one cell should look like. A charStencil paints characters and an intGrid paints
  // numbers, so the swatch carries the symbol itself; the colour behind it is the game's, where
  // the spec could name one, and a neutral otherwise.
  function paintCell(sprite, button, symbol) {
    const empty = isEmpty(sprite, symbol);
    button.textContent = empty ? "" : String(symbol);
    button.classList.toggle("sprite-empty", empty);
    button.title = empty ? "empty" : `${symbol}`;
  }

  // "Nothing here" per encoding. Deliberately not "#": that is ink in half the games that use
  // it (g045 draws a hull as "###"), and treating it as empty would blank the sprite on screen.
  const isEmpty = (sprite, symbol) =>
    sprite.encoding === "offsets" ? !symbol : symbol === "." || symbol === " " || symbol === -1;

  function repaint(sprite) {
    const grid = values.get(sprite.id);
    const buttons = cells.get(sprite.id) || [];
    let index = 0;
    for (let y = 0; y < grid.length; y += 1) {
      for (let x = 0; x < grid[y].length; x += 1) {
        paintCell(sprite, buttons[index], grid[y][x]);
        index += 1;
      }
    }
    const card = buttons.length ? buttons[0].closest(".sprite-card") : null;
    if (card) card.classList.toggle("sprite-moved", !sameGrid(grid, sprite.base));
  }

  // The whole panel's current art, as the caller's apply() wants it: sprite -> grid.
  const snapshot = () => sprites.map((s) => ({ sprite: s, grid: values.get(s.id) }));

  // One reload at a time; cells painted mid-flight are coalesced and run straight after.
  async function flush() {
    if (busy) { pending = true; return; }
    busy = true;
    root.classList.add("tune-busy");
    try {
      do {
        pending = false;
        const attempt = new Map([...values].map(([id, grid]) => [id, copy(grid)]));
        try {
          await apply(snapshot());
          lastGood = attempt;
          setStatus("");
        } catch (err) {
          // The worker's game object is whatever the failed exec left behind, so the rollback is
          // a real reload, not just a repaint of the grid.
          values = new Map([...lastGood].map(([id, grid]) => [id, copy(grid)]));
          for (const sprite of sprites) repaint(sprite);
          setStatus(`Put back: ${briefly(err)}`, true);
          try {
            await apply(snapshot());
          } catch (e) {
            setStatus(`Could not be put back — reload the page: ${briefly(err)}`, true);
            pending = false;
          }
        }
      } while (pending);
    } finally {
      busy = false;
      root.classList.remove("tune-busy");
    }
  }

  function build(spec) {
    root.replaceChildren();
    root.append(el("h2", "section", "Sprites"));

    if (!sprites.length) {
      root.append(el("p", "tune-note", spec.note
        || "Nothing in this version's source is a literal glyph the panel can repaint."));
      return;
    }

    root.append(el("p", "tune-note",
      "Click or drag a cell to paint it. The brush is limited to the symbols this sprite already "
      + "uses, because a symbol the game does not know is an error, not a colour."));

    for (const sprite of sprites) {
      const card = el("div", "sprite-card");
      card.append(el("h3", "tune-group-name", sprite.label));

      // The brush strip: this sprite's own alphabet, nothing more.
      const strip = el("div", "sprite-brushes");
      const options = sprite.encoding === "offsets" ? [0, 1] : sprite.alphabet;
      for (const symbol of options) {
        const swatch = el("button", "sprite-brush");
        swatch.type = "button";
        paintCell(sprite, swatch, symbol);
        swatch.addEventListener("click", () => {
          brush.set(sprite.id, symbol);
          for (const other of strip.children) other.classList.toggle("sprite-brush-on", other === swatch);
        });
        strip.append(swatch);
      }
      brush.set(sprite.id, options[options.length - 1]);
      strip.children[options.length - 1].classList.add("sprite-brush-on");
      card.append(strip);

      const grid = values.get(sprite.id);
      const board = el("div", "sprite-grid");
      board.style.gridTemplateColumns = `repeat(${sprite.cols}, 1fr)`;
      const buttons = [];
      for (let y = 0; y < grid.length; y += 1) {
        for (let x = 0; x < grid[y].length; x += 1) {
          const cell = el("button", "sprite-cell");
          cell.type = "button";
          const put = () => {
            const next = brush.get(sprite.id);
            if (values.get(sprite.id)[y][x] === next) return;
            values.get(sprite.id)[y][x] = next;
            repaint(sprite);
            flush();
          };
          cell.addEventListener("mousedown", put);
          // Dragging across the grid paints, which is what makes this feel like a paint tool
          // rather than a form. buttons=1 is the left button still being held.
          cell.addEventListener("mouseenter", (event) => { if (event.buttons === 1) put(); });
          board.append(cell);
          buttons.push(cell);
        }
      }
      cells.set(sprite.id, buttons);
      card.append(board);

      const reset = el("button", "tune-reset", "Reset this sprite");
      reset.type = "button";
      reset.addEventListener("click", () => {
        values.set(sprite.id, copy(sprite.base));
        repaint(sprite);
        flush();
      });
      card.append(reset);
      root.append(card);
      repaint(sprite);
    }

    const resetAll = el("button", "tune-reset", "Reset every sprite");
    resetAll.type = "button";
    resetAll.addEventListener("click", () => {
      for (const sprite of sprites) values.set(sprite.id, copy(sprite.base));
      for (const sprite of sprites) repaint(sprite);
      flush();
    });
    root.append(resetAll, status);
    root.append(el("p", "tune-note",
      "Art bakes in when the module loads, so repainting restarts the current level. Colour can "
      + "carry meaning in these games — recolouring a wall or a goal may change what the game "
      + "treats as solid."));
  }

  return {
    // Show the panel for a freshly loaded version, or hide it. `sourceText` must be the exact
    // bytes the player is running, so the anchor check is against what is on screen.
    async attach(version, sourceText, { blind }) {
      hide();
      // Blind families must not gain a second place to leak a game's shape -- and a picture of
      // the actor is a more direct read of it than a list of constant names.
      if (!version || blind) return;
      const spec = await fetchSpec(version.gameId);
      if (!spec || spec.gameId !== version.gameId) return;
      source = sourceText || "";
      sprites = resolveSprites(spec, source);
      values = new Map(sprites.map((s) => [s.id, copy(s.base)]));
      lastGood = new Map(sprites.map((s) => [s.id, copy(s.base)]));
      setStatus("");
      build(spec);
      root.hidden = false;
      return sprites.length;
    },
    // Has this game any art at all? The tab switcher asks before it offers a Sprites tab.
    has: () => sprites.length > 0,
    // The panel's current art, for the caller's patch composition.
    current: snapshot,
    detach: hide,
  };
}
