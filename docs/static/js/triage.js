// The default trace review is a bounded queue of unresolved questions. Pair reviews remain
// available through explicit URLs and invite links; their script never runs in triage mode.
import { draw, el } from "./review-ui.js?v=20261004-input";

const SESSION_LIMIT = 5;
const $ = id => document.getElementById(id);

export function reviewMode(search, hash) {
  const params = new URLSearchParams(search);
  return params.get("view") === "pairs" || params.has("split") || /(?:^#|&)k=([A-Za-z0-9_-]{20,100})(?:&|$)/.test(hash)
    ? "pairs" : "triage";
}

export function safeSourceURL(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export async function triageRequest(path, body, fetcher = fetch) {
  const response = await fetcher(`/api/v1/review/triage/${path}`, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin", cache: "no-store", redirect: "manual",
    headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (response.type === "opaqueredirect" || response.status === 0 || response.status === 401)
    throw Object.assign(new Error("Sign in with your team account to review these questions."), { status: 401 });
  if (response.status === 403)
    throw Object.assign(new Error("This queue is available to the team. Invited reviewers can use Browse trace pairs."), { status: 403 });
  if (!response.ok) {
    throw Object.assign(new Error(response.status === 409
      ? "This question has changed or was already resolved. Reload the queue before reviewing it."
      : "The review service could not complete the request. Please try again."), { status: response.status });
  }
  if (!(response.headers.get("content-type") || "").includes("json"))
    throw new Error("The review service returned an unexpected response. Please sign in or try again.");
  return response.json();
}

export function nextItem(items, seen, route) {
  // Preserve the server's ranking; never replenish a skipped item during this session.
  return items.find(item => item && typeof item.id === "string" && !seen.has(item.id)
    && (!item.status || item.status === "open") && (item.route || item.assessment?.route) === route) || null;
}

function citation(title, cite, records) {
  const entry = records.find(record => record.id === cite?.ref);
  const quote = typeof cite?.quote === "string" && entry?.text?.includes(cite.quote) ? cite.quote : null;
  return el("section", { class: "tq-citation" }, el("h3", {}, title),
    quote ? el("blockquote", {}, quote) : el("p", { class: "muted" }, "No verified excerpt available. Request more evidence before confirming."),
    entry ? el("p", { class: "tq-cite-label" }, `${entry.kind || "Evidence"} · ${entry.id}`) : null);
}

function sourceDetails(item) {
  const packet = item.packet || {};
  const metadata = [
    ["Game build", item.build], ["Trace", item.path_id], ["Trace fingerprint", item.trace_sha256],
    ["Notes fingerprint", item.reference_sha256], ["Screener", item.judge?.model],
    ["Review prompt", item.judge?.prompt_version], ["Question", item.id],
  ];
  const details = el("details", { class: "tq-details" }, el("summary", {}, "Full evidence and source details"),
    el("p", {}, packet.context_complete ? "The focal turn was captured. This is a bounded window, not the whole run." : "The supplied context may be incomplete."),
    ...(packet.omissions || []).map(text => el("p", { class: "muted" }, text)),
    ...[...(packet.evidence || []), ...(packet.reference || [])].map(record =>
      el("section", {}, el("h4", {}, `${record.kind || "Evidence"} · ${record.id}`), el("pre", {}, record.text))),
    el("dl", { class: "tq-metadata" }, ...metadata.filter(([, value]) => value).flatMap(([label, value]) =>
      [el("dt", {}, label), el("dd", {}, value)])));
  return details;
}

function previousReview(item) {
  if (!Array.isArray(item.decisions) || !item.decisions.length) return null;
  const labels = { confirmed: "Issue confirmed", reasonable: "Reasonable experiment", insufficient: "More evidence requested", dismissed: "Concern dismissed" };
  return el("section", { class: "tq-review-context" }, el("h3", {}, "Previous review"),
    ...item.decisions.map(decision => el("div", {},
      el("strong", {}, labels[decision.verdict] || "Review recorded"),
      el("p", {}, decision.note || "No additional note."))));
}

function validBoard(rows) {
  return Array.isArray(rows) && rows.length > 0 && rows.length <= 64
    && Array.from(rows).every(row => typeof row === "string" && /^[0-9a-f]{1,64}$/i.test(row) && row.length === rows[0].length);
}

function focalBoards(item) {
  const packet = item.packet || {};
  if (!validBoard(packet.before) && !validBoard(packet.after)) return null;
  const frames = [["Before", packet.before], ["After", packet.after]].map(([label, rows]) => ({
    label, rows, canvas: validBoard(rows) ? el("canvas", { width: 192, height: 192, role: "img",
      "aria-label": `${item.game} level ${item.level}, ${label.toLowerCase()} turn ${item.step}` }) : null,
  }));
  const details = el("details", { class: "tq-details" }, el("summary", {}, "Board before and after this turn"),
    el("div", { class: "tq-board-pair" }, ...frames.map(frame => el("figure", {},
      el("figcaption", {}, `${frame.label} turn ${item.step}`),
      frame.canvas || el("p", { class: "muted" }, "Frame unavailable.")))));
  details.addEventListener("toggle", () => {
    if (details.open) frames.forEach(frame => { if (frame.canvas) draw(frame.canvas, frame.rows); });
  });
  return details;
}

export async function startTriage(request = triageRequest) {
  const route = new URLSearchParams(location.search).get("route") === "assistant" ? "assistant" : "human";
  const state = { items: [], seen: new Set(), finished: 0, reviewed: 0, current: null, busy: false, started: 0, counts: {} };
  $("tq-human").setAttribute("aria-current", route === "human" ? "page" : "false");
  $("tq-assistant").setAttribute("aria-current", route === "assistant" ? "page" : "false");
  try { $("tq-invite").hidden = !localStorage.getItem("arc3-review-key"); } catch { /* Private mode. */ }
  if (route === "assistant") {
    document.querySelector("#triage h1").textContent = "Investigations for assistants";
    document.querySelector(".tq-header p:last-child").textContent = "These concerns can be checked against existing evidence. They do not need a human rating first.";
  }

  function message(text, error = false) {
    const node = $("tq-message");
    node.replaceChildren(text ? el("p", { class: error ? "tq-error" : "tq-notice" }, text) : "");
    node.setAttribute("role", error ? "alert" : "status");
  }
  function overview() {
    const { human = 0, assistant = 0, resolved = 0 } = state.counts;
    $("tq-counts").textContent = `${human} human questions · ${assistant} assistant investigations · ${resolved} resolved`;
    $("tq-session").textContent = route === "human"
      ? `${state.reviewed} reviewed · ${Math.max(0, SESSION_LIMIT - state.finished)} left in this session. Stop whenever you like.`
      : "Assistant queue · no human review required to begin an investigation.";
  }
  function setBusy(busy) {
    state.busy = busy;
    $("tq-content").setAttribute("aria-busy", String(busy));
    $("tq-content").querySelectorAll("button, textarea").forEach(node => { node.disabled = busy; });
  }
  function empty(title, text, more = false) {
    $("tq-content").replaceChildren(el("section", { class: "tq-empty" }, el("h2", {}, title), el("p", {}, text),
      more ? el("button", { type: "button", onclick: () => {
        state.finished = 0; state.reviewed = 0; message(""); load();
      } }, "Review up to five more") : null));
  }
  async function save(verdict) {
    if (state.busy || !state.current) return;
    const current = state.current;
    const note = $("tq-note").value.trim();
    setBusy(true); message("Saving your decision…");
    try {
      await request("decision", { id: current.id, verdict, ...(note ? { note } : {}), seconds: Math.min(86400, Math.max(0, Math.round((Date.now() - state.started) / 1000))) });
      state.seen.add(current.id); state.finished++; state.reviewed++;
      if (verdict === "insufficient") {
        if (route === "human") {
          state.counts.human = Math.max(0, (state.counts.human || 0) - 1);
          state.counts.assistant = (state.counts.assistant || 0) + 1;
        }
      } else {
        state.counts[route] = Math.max(0, (state.counts[route] || 0) - 1);
        state.counts.resolved = (state.counts.resolved || 0) + 1;
      }
      message(verdict === "insufficient" ? "Sent to the assistant queue for more evidence." : "Decision saved. Thank you.");
      render();
    } catch (error) {
      if (error.status === 409) {
        state.seen.add(current.id); state.finished++;
        message("Another reviewer already handled this question. Moving to the next one."); render();
      } else message(error.message, true);
    } finally { setBusy(false); }
  }
  function render() {
    overview();
    if (route === "human" && state.finished >= SESSION_LIMIT) {
      state.current = null;
      empty("That is enough for this session.", "Your decisions are saved. There is no need to clear the whole queue.",
        !!nextItem(state.items, state.seen, route) || (state.counts[route] || 0) > 0);
      return;
    }
    const item = nextItem(state.items, state.seen, route);
    state.current = item;
    if (!item) {
      empty(state.seen.size ? "No more questions in this batch." : "No questions waiting here.", route === "human"
        ? "Nothing in the current queue needs your judgment. New screened questions will appear here when available."
        : "No assistant investigations are waiting in this batch.");
      $("tq-content").append(el("button", { type: "button", onclick: load }, "Refresh queue"));
      return;
    }
    state.started = Date.now();
    const a = item.assessment || {}, packet = item.packet || {}, evidence = packet.evidence || [], reference = packet.reference || [];
    const impact = ["high", "medium", "low"].includes(a.impact) ? `${a.impact[0].toUpperCase()}${a.impact.slice(1)} impact` : "Prioritized for review";
    const recurrence = Math.max(1, Number(item.occurrences) || 1);
    const card = el("article", { class: "tq-card", "aria-labelledby": "tq-question" },
      el("div", { class: "tq-card-top" }, el("strong", { class: "tq-game" }, `${item.game} · level ${item.level} · turn ${item.step}`),
        el("span", { class: "tq-chip" }, impact), el("span", { class: "muted" }, `${recurrence} occurrence${recurrence === 1 ? "" : "s"} grouped`)),
      el("p", { class: "tq-eyebrow" }, route === "human" ? "Why this needs your judgment" : "What to investigate"),
      el("h2", { id: "tq-question", tabindex: "-1" }, (route === "human" ? a.human_question : a.next_action) || a.summary || "Review the evidence"),
      el("p", { class: "tq-summary" }, a.summary),
      el("p", { class: "tq-caution" }, "A screener flagged this concern; it is not yet an established error."),
      previousReview(item),
      el("div", { class: "tq-evidence" }, citation("What the solver said", a.claim, evidence), citation("What the evidence says", a.support, evidence)),
      a.reference ? citation("Applicable human notes", a.reference, reference) :
        el("p", { class: "muted" }, "No applicable human-note excerpt was cited for this question."),
      focalBoards(item),
      el("div", { class: "tq-explanation" },
        el("h3", {}, "A reasonable alternative"), el("p", {}, a.alternative || "No alternative explanation was supplied; check the full context."),
        el("p", { class: "muted" }, a.solver_knew === "yes" ? "The screener reports that this evidence was available to the solver."
          : a.solver_knew === "no" ? "The solver had not been given this evidence. A discovery attempt is not automatically a mistake."
            : "It is unclear whether the solver had this evidence at the time."),
        el("h3", {}, "What happens next"), el("p", {}, a.next_action || "Investigate the concern before proposing any training change.")),
      sourceDetails(item));
    const notesURL = safeSourceURL(packet.notes_url);
    if (notesURL) card.append(el("a", { href: notesURL, target: "_blank", rel: "noopener noreferrer", class: "tq-source-link" }, "Open original human notes ↗"));
    if (validBoard(packet.start)) {
      const label = packet.board_label || "Level starting board";
      const canvas = el("canvas", { width: 192, height: 192, role: "img", "aria-label": `${label} for ${item.game}, level ${item.level}` });
      const board = el("details", { class: "tq-details" }, el("summary", {}, label), canvas);
      board.addEventListener("toggle", () => { if (board.open) draw(canvas, packet.start); });
      card.append(board);
    }
    const form = el("section", { class: "tq-decision", "aria-label": "Your decision" },
      el("label", { for: "tq-note" }, "Correction or context (optional)"),
      el("textarea", { id: "tq-note", rows: "2", maxlength: "4000", placeholder: "One sentence is enough." }),
      el("div", { class: "tq-actions" },
        ...[["confirmed", "Confirm issue"], ["reasonable", "Reasonable experiment"], ["insufficient", "Need evidence"], ["dismissed", "Dismiss"]]
          .map(([verdict, label]) => el("button", { type: "button", onclick: () => save(verdict) }, label)),
        el("button", { type: "button", class: "tq-skip", onclick: () => {
          if (state.busy) return;
          state.seen.add(item.id); state.finished++; message("Skipped for this session. No decision was recorded."); render();
        } }, "Skip for now")));
    card.append(form);
    $("tq-content").replaceChildren(card);
    $("tq-question").focus({ preventScroll: true });
  }
  async function load() {
    if (state.busy) return;
    setBusy(true); message("Loading review questions…");
    try {
      const exclude = [...state.seen].slice(-100).join(",");
      const data = await request(`queue?route=${route}&limit=20${exclude ? `&exclude=${encodeURIComponent(exclude)}` : ""}`);
      if (!Array.isArray(data.items) || !data.counts || typeof data.counts !== "object")
        throw new Error("The review service returned an incomplete queue. Please try again.");
      state.items = data.items; state.counts = data.counts; message(""); render();
    } catch (error) {
      message(error.message, true);
      $("tq-content").replaceChildren(el("section", { class: "tq-empty" },
        el("h2", {}, error.status === 401 || error.status === 403 ? "Team sign-in required" : "Could not load questions"),
        error.status === 401 ? el("a", { href: "./internal.html" }, "Open team sign-in") : null,
        el("button", { type: "button", onclick: load }, "Try again")));
    } finally { setBusy(false); }
  }
  await load();
}

if (typeof document !== "undefined") {
  if (reviewMode(location.search, location.hash) === "pairs") {
    $("triage").hidden = true;
    $("legacy-review").hidden = false;
    document.body.className = "rv-page";
    import("./review.js?v=20261005").catch(() => {
      $("banner").hidden = false;
      $("banner").textContent = "Could not load trace pairs. Please refresh this page.";
    });
  } else {
    startTriage();
  }
}
