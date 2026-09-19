// The ideas board, on top of the Games page: every game idea we have (GPT's ledger, the
// Anthropic briefs, the Flash mechanic lineages) and whether it has been explored yet. An idea
// is explored once a game has been built from it; the team moves the rest by hand.
//
// Team-only, because an idea names its mechanic; the API refuses it to anyone signed out.
// Everything user-written goes in with textContent.

const COLUMNS = [
  { status: "unexplored", label: "Not explored yet" },
  { status: "exploring", label: "Exploring" },
  { status: "explored", label: "Explored" },
  { status: "dropped", label: "Dropped" },
];
const SOURCE_LABELS = {
  "gpt-ideas-v2": "GPT ideas",
  "anthropic-ideas-v1": "Anthropic ideas",
  "flash-lineages-v1": "Flash lineages",
  "flash-long-tail-v1": "Flash long tail",
};
const PAGE = 20;
const OPEN_KEY = "arc3-ideas-open";

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
};

export function createIdeasBoard({ api, onOpenGame }) {
  const root = document.getElementById("ideasBoard");
  const columns = new Map(); // status -> { list, more, count, offset, total }
  const filter = { q: "", source: "" };
  let token = 0;

  function sourceLabel(source) {
    return SOURCE_LABELS[source] || source;
  }

  function card(idea) {
    const node = el("article", "ib-card");
    node.dataset.idea = idea.ideaId;
    node.appendChild(el("div", "ib-title", idea.title));
    const meta = el("div", "ib-meta");
    meta.append(
      el("span", "ib-src", sourceLabel(idea.source)),
      idea.axis ? el("span", "ib-axis", idea.axis) : "",
      el("span", "ib-id", idea.ideaId),
    );
    node.appendChild(meta);
    node.appendChild(el("p", "ib-pitch", idea.pitch));
    if (idea.games && idea.games.length) {
      const games = el("div", "ib-games");
      games.append("Built as ");
      for (const gameId of idea.games) {
        const link = el("a", "ib-game", gameId);
        link.href = `#g=${encodeURIComponent(gameId)}`;
        link.addEventListener("click", (event) => {
          event.preventDefault();
          onOpenGame(gameId);
        });
        games.appendChild(link);
      }
      node.appendChild(games);
    }
    if (idea.note) node.appendChild(el("p", "ib-note", idea.note));
    const move = el("select", "ib-move");
    move.setAttribute("aria-label", `Move ${idea.title}`);
    for (const column of COLUMNS) {
      const option = el("option", null, column.label);
      option.value = column.status;
      option.selected = column.status === idea.status;
      move.appendChild(option);
    }
    move.addEventListener("change", async () => {
      const to = move.value;
      move.disabled = true;
      try {
        await api.updateIdea(idea.ideaId, { status: to });
        const from = columns.get(idea.status);
        const target = columns.get(to);
        from.total -= 1;
        target.total += 1;
        idea.status = to;
        node.remove();
        target.list.prepend(node);
        paintCounts();
      } catch (err) {
        move.value = idea.status;
        move.title = `Could not move it (${err.message})`;
      } finally {
        move.disabled = false;
      }
    });
    node.appendChild(move);
    return node;
  }

  function paintCounts() {
    let total = 0;
    for (const column of COLUMNS) {
      const state = columns.get(column.status);
      state.count.textContent = state.total;
      state.more.hidden = state.list.childElementCount >= state.total;
      total += state.total;
    }
    const explored = columns.get("explored").total;
    const waiting = columns.get("unexplored").total;
    document.getElementById("ibSummary").textContent =
      `${total} idea${total === 1 ? "" : "s"} · ${explored} explored · ${waiting} not explored yet`;
  }

  async function loadColumn(status, append) {
    const state = columns.get(status);
    const mine = token;
    const result = await api.listIdeas({
      status,
      q: filter.q,
      source: filter.source,
      offset: append ? state.list.childElementCount : 0,
      limit: PAGE,
    });
    if (mine !== token) return null;
    if (!append) state.list.replaceChildren();
    for (const idea of result.ideas) state.list.appendChild(card(idea));
    return result;
  }

  async function reload() {
    token += 1;
    const mine = token;
    const results = await Promise.all(COLUMNS.map((column) => loadColumn(column.status, false)));
    if (mine !== token || !results[0]) return;
    for (const column of COLUMNS) columns.get(column.status).total = results[0].counts[column.status] || 0;
    const select = document.getElementById("ibSource");
    if (select.options.length <= 1) {
      for (const [source, n] of Object.entries(results[0].sources)) {
        const option = el("option", null, `${sourceLabel(source)} (${n})`);
        option.value = source;
        select.appendChild(option);
      }
    }
    paintCounts();
  }

  function build() {
    const board = document.getElementById("ibColumns");
    board.replaceChildren();
    for (const column of COLUMNS) {
      const col = el("section", `ib-col ib-${column.status}`);
      const head = el("header", "ib-col-head");
      const count = el("span", "ib-count", "…");
      head.append(el("span", null, column.label), count);
      const list = el("div", "ib-list");
      const more = el("button", "sm ib-more", "Show more");
      more.type = "button";
      more.hidden = true;
      more.addEventListener("click", async () => {
        more.disabled = true;
        try {
          await loadColumn(column.status, true);
          paintCounts();
        } finally {
          more.disabled = false;
        }
      });
      col.append(head, list, more);
      board.appendChild(col);
      columns.set(column.status, { list, more, count, total: 0 });
    }
  }

  function setOpen(open) {
    document.getElementById("ibColumns").hidden = !open;
    document.getElementById("ibFilters").hidden = !open;
    document.getElementById("ibToggle").textContent = open ? "Hide board" : "Show board";
    try {
      localStorage.setItem(OPEN_KEY, open ? "1" : "0");
    } catch (e) {
      /* not remembered */
    }
  }

  async function show() {
    root.hidden = false;
    build();
    let open = true;
    try {
      open = localStorage.getItem(OPEN_KEY) !== "0";
    } catch (e) {
      /* default open */
    }
    setOpen(open);
    document.getElementById("ibToggle").addEventListener("click", () =>
      setOpen(document.getElementById("ibColumns").hidden));
    let debounce = null;
    document.getElementById("ibSearch").addEventListener("input", (event) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        filter.q = event.target.value.trim();
        reload();
      }, 250);
    });
    document.getElementById("ibSource").addEventListener("change", (event) => {
      filter.source = event.target.value;
      reload();
    });
    try {
      await reload();
    } catch (err) {
      document.getElementById("ibSummary").textContent = `The ideas board could not load (${err.message}).`;
    }
  }

  return { show };
}
