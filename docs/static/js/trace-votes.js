// Thumbs up / thumbs down on what the model wrote, with the reviewer's reason.
//
// The decision panel calls attach() for each section of model output (THINKING, ASSISTANT,
// a TOOL CALL) and load() once the turn is drawn. A mark is a training label, so it is saved
// with the section's exact text and that text's SHA-256 (railway/trace_feedback.py): if the
// run is re-exported and the words at this position change, the old mark stays with the old
// words and is not shown here. One reviewer has one mark per section; pressing the lit thumb
// again clears it.
//
// Where there is no API (a local export, the a424 inspector) the first read fails and the
// thumbs switch themselves off rather than pretending to save.

const ENDPOINT = new URL("../../api/v1/traces/feedback", import.meta.url);
const PROMPT = { up: "Why was this right?", down: "Why was this wrong?" };
const GLYPH = { up: "\u{1F44D}", down: "\u{1F44E}" };

// The same rule as canonical_text() on the server: no NULs. (TextEncoder already turns a
// lone surrogate into U+FFFD, which is what the server does too.)
const canonical = (text) => String(text || "").replaceAll("\u0000", "");

async function sha256Hex(text) {
  if (!globalThis.crypto?.subtle) return null; // not a secure context: fall back to position
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(text)));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function request(method, { query, body } = {}) {
  const url = new URL(ENDPOINT);
  for (const [key, value] of Object.entries(query || {})) url.searchParams.set(key, value);
  const response = await fetch(url, {
    method,
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const type = response.headers.get("Content-Type") || "";
  if (response.redirected || response.status === 401 || !type.includes("json")) {
    throw new Error(response.status === 401 || response.redirected ? "sign in again to vote" : "votes are not available here");
  }
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
  return payload;
}

/**
 * identity: { run, gameIndex, gameId, stepIndex, turn } -- which turn of which game this is.
 * Returns { attach(details, { sectionIndex, label, content }), load() }.
 */
export function createVotes(identity) {
  const entries = [];

  function attach(details, { sectionIndex, label, content }) {
    if (!String(content || "").trim()) return;
    const summary = details.querySelector("summary");
    if (!summary) return;

    const entry = { details, sectionIndex, label, content, mine: null, reason: "", others: [], busy: false };
    entry.sha = sha256Hex(content).catch(() => null);

    const bar = document.createElement("span");
    bar.className = "vote";
    entry.tally = document.createElement("span");
    entry.tally.className = "vote-tally";
    bar.appendChild(entry.tally);
    entry.buttons = {};
    for (const vote of ["up", "down"]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `vote-btn vote-${vote}`;
      button.textContent = GLYPH[vote];
      button.title = vote === "up" ? "This reasoning was right" : "This reasoning was wrong";
      button.setAttribute("aria-label", button.title);
      button.setAttribute("aria-pressed", "false");
      // A click inside <summary> would also fold the section; this one is only a vote.
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        choose(entry, vote);
      });
      entry.buttons[vote] = button;
      bar.appendChild(button);
    }
    summary.insertBefore(bar, summary.querySelector(".size"));

    const note = document.createElement("div");
    note.className = "vote-note";
    note.hidden = true;
    entry.textarea = document.createElement("textarea");
    entry.textarea.rows = 2;
    entry.textarea.maxLength = 4000;
    entry.save = document.createElement("button");
    entry.save.type = "button";
    entry.save.className = "vote-save";
    entry.save.textContent = "Save note";
    entry.status = document.createElement("span");
    entry.status.className = "vote-status";
    const row = document.createElement("div");
    row.className = "vote-note-row";
    row.append(entry.save, entry.status);
    entry.othersBox = document.createElement("div");
    entry.othersBox.className = "vote-others";
    note.append(entry.textarea, row, entry.othersBox);
    entry.note = note;
    summary.insertAdjacentElement("afterend", note);

    entry.save.addEventListener("click", () => entry.mine && send(entry, entry.mine));
    entry.textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && entry.mine) {
        event.preventDefault();
        send(entry, entry.mine);
      }
    });
    // Leaving the box saves it: a reason typed and then scrolled past must not be lost.
    entry.textarea.addEventListener("blur", () => {
      if (entry.mine && !entry.busy && entry.textarea.value.trim() !== entry.reason) send(entry, entry.mine);
    });
    entry.textarea.addEventListener("input", () => {
      entry.status.textContent = entry.textarea.value.trim() === entry.reason ? "" : "not saved yet";
    });

    entries.push(entry);
    paint(entry);
  }

  function paint(entry) {
    for (const vote of ["up", "down"]) {
      const on = entry.mine === vote;
      entry.buttons[vote].classList.toggle("on", on);
      entry.buttons[vote].setAttribute("aria-pressed", String(on));
    }
    const ups = entry.others.filter((v) => v.vote === "up").length;
    const downs = entry.others.length - ups;
    entry.tally.textContent = [ups ? `+${ups}` : "", downs ? `−${downs}` : ""].filter(Boolean).join(" ");
    entry.tally.title = entry.others.length ? "Marks from other reviewers" : "";

    entry.textarea.hidden = entry.save.hidden = !entry.mine;
    if (entry.mine) entry.textarea.placeholder = PROMPT[entry.mine];
    entry.othersBox.replaceChildren(
      ...entry.others.map((v) => {
        const line = document.createElement("div");
        line.className = `vote-other vote-${v.vote}`;
        line.textContent = `${GLYPH[v.vote]} ${v.reviewer}${v.reason ? ` — ${v.reason}` : ""}`;
        return line;
      }),
    );
    entry.note.hidden = !entry.mine && !entry.others.length && !entry.status.textContent;
    entry.details.classList.toggle("voted-up", entry.mine === "up");
    entry.details.classList.toggle("voted-down", entry.mine === "down");
  }

  function choose(entry, vote) {
    if (entry.busy) return;
    const next = entry.mine === vote ? null : vote; // the lit thumb again = take it back
    send(entry, next, { focus: next !== null });
  }

  async function send(entry, vote, { focus = false } = {}) {
    if (entry.busy) return;
    entry.busy = true;
    const before = { mine: entry.mine, reason: entry.reason };
    const reason = vote ? entry.textarea.value.trim() : "";
    entry.mine = vote;
    entry.status.textContent = "saving…";
    paint(entry);
    if (focus) {
      entry.details.open = true;
      entry.textarea.focus();
    }
    try {
      await request("POST", {
        body: {
          run: identity.run,
          gameIndex: identity.gameIndex,
          gameId: identity.gameId ?? null,
          stepIndex: identity.stepIndex,
          turn: Number.isInteger(identity.turn) ? identity.turn : null,
          sectionIndex: entry.sectionIndex,
          sectionLabel: entry.label,
          content: canonical(entry.content),
          vote,
          reason: reason || null,
        },
      });
      entry.reason = reason;
      if (!vote) entry.textarea.value = "";
      entry.status.textContent = vote ? (reason ? "saved" : "saved — add why, then Save note") : "";
    } catch (error) {
      entry.mine = before.mine;
      entry.reason = before.reason;
      entry.status.textContent = `not saved: ${error.message}`;
    } finally {
      entry.busy = false;
      paint(entry);
    }
  }

  async function load() {
    if (!entries.length) return;
    let payload;
    try {
      payload = await request("GET", {
        query: { run: identity.run, game: identity.gameIndex, step: identity.stepIndex },
      });
    } catch (error) {
      for (const entry of entries) {
        for (const button of Object.values(entry.buttons)) {
          button.disabled = true;
          button.title = `Votes are off: ${error.message}`;
        }
      }
      return;
    }
    for (const entry of entries) {
      const sha = await entry.sha;
      const here = (payload.votes || []).filter(
        (v) => v.sectionIndex === entry.sectionIndex && (!sha || v.contentSha256 === sha),
      );
      const mine = here.find((v) => v.mine);
      // A vote cast while the list was loading wins over what the list says.
      if (!entry.busy && entry.mine === null && mine) {
        entry.mine = mine.vote;
        entry.reason = mine.reason || "";
        entry.textarea.value = entry.reason;
      }
      entry.others = here.filter((v) => !v.mine);
      paint(entry);
    }
  }

  return { attach, load };
}
