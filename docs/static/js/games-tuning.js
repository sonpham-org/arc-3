// Games page: the per-game tuning panel in the play view's sidebar.
//
// A game's tunable constants are declared as data, not code: docs/static/games/params/<id>.json
// lists the module-level scalars worth turning, with a range and a plain-English note each. No
// spec file means no panel -- that is the normal case, and it is silent.
//
// Turning a knob does not talk to the game object. It rewrites the constant's line in the source
// text the player was loaded from and hands the whole patched module back to gameLoad(), which
// re-execs it in the Pyodide worker. Derived constants (hg51's `MAST = 3 * NOTCH + 2`) recompute
// for free that way, which is the whole reason this works on source text rather than on state.
//
// Two things keep it honest against a moving catalog. The evolution loop rewrites these games,
// so a spec written for v2 will meet v4: every knob is matched against the source that was
// actually fetched, and one that no longer resolves to a single scalar assignment is dropped
// from the panel rather than applied blind. And a bad value is a Python exception, not a
// validation error we could have predicted -- so the last set of values that loaded is kept, and
// a failed load is rolled back to it before the message is shown.

const SPEC_DIR = "./static/games/params/";

// A spec may only name a module-level SHOUTING_CASE constant: the name goes into a RegExp.
const NAME_OK = /^[A-Z][A-Z0-9_]*$/;

// One line-anchored scalar int assignment, with an optional trailing comment and nothing else.
// The tail is pinned deliberately: `CELL = 8 if hard else 6` must not match and quietly lose its
// conditional. Tuple unpacks (`CELL, GRID, CAP = 8, 8, 3`) never match -- a comma follows the
// name, not an equals -- which is why they are excluded from the specs in the first place.
const assignment = (name) => new RegExp(`^(${name}[ \\t]*=[ \\t]*)(-?\\d+)([ \\t]*(?:#[^\\n]*)?)$`, "gm");

// The value NAME is assigned in `source`, or null unless there is exactly one such line. More
// than one match means the file shadows or re-assigns it and we cannot say which one drives the
// drawing, so the knob is dropped.
export function readScalar(source, name) {
  if (!NAME_OK.test(name)) return null;
  const found = [...source.matchAll(assignment(name))];
  return found.length === 1 ? Number(found[0][2]) : null;
}

// `source` with each named constant set to its new value, keeping the assignment's own spacing
// and trailing comment. Names that do not resolve are skipped, not guessed at.
export function patchSource(source, values) {
  let out = source;
  for (const [name, value] of Object.entries(values)) {
    if (readScalar(out, name) === null) continue;
    out = out.replace(assignment(name), (_m, head, _old, tail) => `${head}${value}${tail}`);
  }
  return out;
}

// The knobs in `spec` that this exact source text still supports, each carrying the value the
// source actually assigns (not the value the spec was written against -- the source wins).
export function resolveKnobs(spec, source) {
  if (!spec || spec.schema !== 1 || !Array.isArray(spec.params)) return [];
  const knobs = [];
  for (const p of spec.params) {
    if (!p || p.type !== "int" || !NAME_OK.test(p.name || "")) continue;
    const value = readScalar(source, p.name);
    if (value === null) continue;
    const step = Math.max(1, Math.round(p.step || 1));
    knobs.push({
      name: p.name,
      label: p.label || p.name,
      group: p.group || "Tuning",
      note: p.note || "",
      step,
      // The published value is always reachable, whatever range the spec claims.
      min: Math.min(Number.isFinite(p.min) ? p.min : value, value),
      max: Math.max(Number.isFinite(p.max) ? p.max : value, value),
      base: value,
    });
  }
  return knobs;
}

async function fetchSpec(gameId) {
  if (!/^[A-Za-z0-9_-]+$/.test(gameId || "")) return null;
  try {
    // Rewritten in place as a game is re-tuned, so never cached -- same reasoning as manifest.json.
    const response = await fetch(`${SPEC_DIR}${gameId}.json`, { cache: "no-store" });
    if (!response.ok) return null; // 404 is the ordinary answer: this game has no spec.
    return await response.json();
  } catch (e) {
    return null;
  }
}

// Pyodide hands the whole traceback back as the message. The sidebar has room for the line that
// actually names the fault, which is the last one.
function briefly(err) {
  const text = String((err && err.message) || err || "the patched game did not load").trim();
  const last = text.split("\n").map((line) => line.trim()).filter(Boolean).pop() || text;
  return last.length > 140 ? `${last.slice(0, 139)}…` : last;
}

// `apply(patchedSource, values)` is the caller's business: it owns the engine call, the load
// token and the repaint. It resolves when the patched module is running and throws otherwise;
// this module only decides what to patch and what to do when it did not take.
export function createTuning({ root, apply, debounceMs = 200 }) {
  let knobs = [];
  let source = "";
  let values = {};   // the set on screen
  let lastGood = {}; // the last set that loaded
  let inputs = new Map();
  let busy = false;
  let pending = null;
  let timer = null;

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
    knobs = [];
    inputs = new Map();
    clearTimeout(timer);
    pending = null;
  }

  function paintValue(name) {
    const row = inputs.get(name);
    if (!row) return;
    row.readout.textContent = String(values[name]);
    row.slider.value = String(values[name]);
    row.row.classList.toggle("tune-moved", values[name] !== row.knob.base);
  }

  // One reload at a time; a knob turned mid-flight is coalesced and run straight after.
  async function flush() {
    if (busy) { pending = true; return; }
    busy = true;
    root.classList.add("tune-busy");
    try {
      do {
        pending = false;
        const attempt = { ...values };
        try {
          await apply(patchSource(source, attempt), attempt);
          lastGood = attempt;
          setStatus("");
        } catch (err) {
          // The worker's game object is whatever the failed exec left behind, so the rollback is
          // a real reload, not just a repaint of the sliders.
          values = { ...lastGood };
          for (const knob of knobs) paintValue(knob.name);
          setStatus(`Put back: ${briefly(err)}`, true);
          try {
            await apply(patchSource(source, lastGood), lastGood);
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

  function queue() {
    clearTimeout(timer);
    timer = setTimeout(flush, debounceMs);
  }

  function build(spec) {
    root.replaceChildren();
    root.append(el("h2", "section", "Tuning"));

    if (!knobs.length) {
      root.append(el("p", "tune-note", spec.note
        || "Nothing in this version's source is a single scalar constant the panel can turn."));
      return;
    }

    const groups = new Map();
    for (const knob of knobs) {
      if (!groups.has(knob.group)) groups.set(knob.group, []);
      groups.get(knob.group).push(knob);
    }

    for (const [name, members] of groups) {
      const box = el("div", "tune-group");
      box.append(el("h3", "tune-group-name", name));
      for (const knob of members) {
        const row = el("div", "tune-row");
        const head = el("label", "tune-head");
        head.append(el("span", "tune-label", knob.label));
        const readout = el("span", "tune-value");
        head.append(readout);
        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = String(knob.min);
        slider.max = String(knob.max);
        slider.step = String(knob.step);
        slider.value = String(knob.base);
        slider.title = knob.note ? `${knob.name} — ${knob.note}` : knob.name;
        head.htmlFor = slider.id = `tune-${knob.name}`;
        // Dragging only moves the number; the worker is asked once the drag settles.
        slider.addEventListener("input", () => {
          values[knob.name] = Number(slider.value);
          paintValue(knob.name);
          queue();
        });
        slider.addEventListener("change", () => {
          values[knob.name] = Number(slider.value);
          paintValue(knob.name);
          clearTimeout(timer);
          flush();
        });
        row.append(head, slider);
        box.append(row);
        inputs.set(knob.name, { knob, row, slider, readout });
      }
      root.append(box);
    }

    const reset = el("button", "tune-reset", "Reset to defaults");
    reset.type = "button";
    reset.addEventListener("click", () => {
      values = Object.fromEntries(knobs.map((k) => [k.name, k.base]));
      for (const knob of knobs) paintValue(knob.name);
      clearTimeout(timer);
      flush();
    });
    root.append(reset, status);
    root.append(el("p", "tune-note", "Constants bake in when the module loads, so changing a value restarts the current level."));

    for (const knob of knobs) paintValue(knob.name);
  }

  return {
    // Show the panel for a freshly loaded version, or hide it. `sourceText` must be the exact
    // bytes the player is running, so the drift check is against what is on screen.
    async attach(version, sourceText, { blind }) {
      hide();
      // Blind families must not gain a second place to leak a game's shape.
      if (!version || blind) return;
      const spec = await fetchSpec(version.gameId);
      if (!spec || spec.gameId !== version.gameId) return;
      source = sourceText || "";
      knobs = resolveKnobs(spec, source);
      values = Object.fromEntries(knobs.map((k) => [k.name, k.base]));
      lastGood = { ...values };
      setStatus("");
      build(spec);
      root.hidden = false;
    },
    detach: hide,
  };
}
