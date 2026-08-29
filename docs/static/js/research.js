(function () {
  "use strict";

  const DATA_URL = "./static/research/alternative-games.json";

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderCorpora(corpora) {
    const root = document.getElementById("corpusBars");
    const max = Math.max(...corpora.map((item) => item.count));
    corpora.forEach((item) => {
      const row = el("div", "corpus-row");
      row.dataset.kind = item.kind;
      const label = el("div", "label", item.label);
      const track = el("div", "track");
      const bar = el("div", "bar");
      bar.style.width = `${(item.count / max) * 100}%`;
      track.appendChild(bar);
      const value = el("div", "value", String(item.count));
      row.append(label, track, value);
      root.appendChild(row);
    });
  }

  function renderLedger(ledger) {
    const root = document.getElementById("ledgerAxes");
    const max = Math.max(...ledger.axes.map((item) => item.count));
    ledger.axes.forEach((item) => {
      const row = el("div", "axis-row");
      const label = el("span", "axis-label", item.axis);
      const track = el("span", "axis-track");
      const fill = el("span", "axis-fill");
      fill.style.width = `${(item.count / max) * 100}%`;
      track.appendChild(fill);
      row.append(label, track, el("span", "axis-value", String(item.count)));
      root.appendChild(row);
    });
  }

  function renderGaps(gaps) {
    const root = document.getElementById("gapGrid");
    const detail = document.getElementById("gapDetail");
    let selected = null;

    function select(index) {
      selected = index;
      [...root.children].forEach((button, i) => {
        button.classList.toggle("active", i === index);
        button.setAttribute("aria-pressed", i === index ? "true" : "false");
      });
      const gap = gaps[index];
      detail.replaceChildren();
      detail.appendChild(el("strong", "", gap.label));
      detail.appendChild(el("p", "", gap.question));
      detail.appendChild(el("small", "", `Evidence contract: ${gap.evidence}`));
    }

    gaps.forEach((gap, index) => {
      const button = el("button", "", gap.label);
      button.type = "button";
      button.setAttribute("aria-pressed", "false");
      button.prepend(el("span", "gap-num", String(index + 1).padStart(2, "0")));
      button.addEventListener("click", () => select(index));
      root.appendChild(button);
    });
    if (selected === null) select(0);
  }

  function renderProgression(levels) {
    const root = document.getElementById("q001Progression");
    const max = Math.max(...levels.map((level) => level.optimal_actions));
    levels.forEach((level) => {
      const step = el("div", "progress-step");
      const bar = el("div", "progress-bar");
      bar.style.height = `${30 + (level.optimal_actions / max) * 120}px`;
      bar.appendChild(el("span", "actions", String(level.optimal_actions)));
      const label = el("div", "progress-label");
      label.appendChild(el("strong", "", `L${level.level} · ${level.role}`));
      label.appendChild(el("span", "", level.demand));
      step.append(bar, label);
      root.appendChild(step);
    });
  }

  function quietFieldDemo() {
    const svg = document.getElementById("quietFieldDemo");
    const status = document.getElementById("quietFieldStatus");
    const ns = "http://www.w3.org/2000/svg";
    const state = { eye: 1, veil: true, shy: 0, bold: 0, pulses: 0 };
    const shyPath = [6, 7, 8];
    const boldPath = [2, 3, 4, 5];
    const shyTarget = 2;
    const boldTarget = 1;
    const yEye = 85;
    const yShy = 180;
    const yBold = 275;

    function sx(x) { return 52 + x * 64; }

    function add(name, attrs, text) {
      const node = document.createElementNS(ns, name);
      Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
      if (text !== undefined) node.textContent = text;
      svg.appendChild(node);
      return node;
    }

    function visible(objectX) {
      const oppositeSides = (state.eye < 4 && objectX > 4) || (state.eye > 4 && objectX < 4);
      return !(state.veil && oppositeSides);
    }

    function drawTrack(path, y) {
      add("path", {
        d: `M ${sx(path[0])} ${y} L ${sx(path[path.length - 1])} ${y}`,
        stroke: "#4a5568", "stroke-width": 4, "stroke-dasharray": "3 10", fill: "none"
      });
    }

    function render() {
      svg.replaceChildren();
      add("rect", { x: 0, y: 0, width: 640, height: 360, fill: "#05070b" });
      for (let x = 0; x < 9; x += 1) {
        for (let y = 40; y <= 320; y += 40) {
          add("circle", { cx: sx(x), cy: y, r: 1.5, fill: "#313947" });
        }
      }
      drawTrack(shyPath, yShy);
      drawTrack(boldPath, yBold);

      const veilColor = state.veil ? "#8ad8f1" : "#42556b";
      add("rect", { x: sx(4) - 7, y: 28, width: 14, height: 292, fill: veilColor });
      add("line", {
        x1: state.veil ? sx(4) : sx(4) - 33,
        y1: state.veil ? 28 : 174,
        x2: state.veil ? sx(4) : sx(4) + 33,
        y2: state.veil ? 320 : 174,
        stroke: "#fff", "stroke-width": 2, opacity: .72
      });

      const eyeX = sx(state.eye);
      add("path", { d: `M ${eyeX} ${yEye - 18} L ${eyeX + 24} ${yEye} L ${eyeX} ${yEye + 18} L ${eyeX - 24} ${yEye} Z`, fill: "#fff" });
      add("circle", { cx: eyeX, cy: yEye, r: 8, fill: "#1e93ff" });

      const shyX = sx(shyPath[state.shy]);
      const boldX = sx(boldPath[state.bold]);
      if (visible(shyPath[state.shy])) {
        add("line", { x1: eyeX, y1: yEye + 10, x2: shyX, y2: yShy - 13, stroke: "#1e93ff", "stroke-width": 2, "stroke-dasharray": "3 8", opacity: .8 });
      }
      if (visible(boldPath[state.bold])) {
        add("line", { x1: eyeX, y1: yEye + 10, x2: boldX, y2: yBold - 13, stroke: "#1e93ff", "stroke-width": 2, "stroke-dasharray": "3 8", opacity: .8 });
      }

      add("rect", { x: sx(shyPath[shyTarget]) - 13, y: yShy - 13, width: 26, height: 26, fill: "none", stroke: "#4fcc30", "stroke-width": 4 });
      add("rect", { x: sx(boldPath[boldTarget]) - 13, y: yBold - 13, width: 26, height: 26, fill: "none", stroke: "#4fcc30", "stroke-width": 4 });
      add("path", { d: `M ${shyX + 12} ${yShy - 14} A 19 19 0 1 0 ${shyX + 12} ${yShy + 14} A 13 13 0 1 1 ${shyX + 12} ${yShy - 14}`, fill: "#e53aa3" });
      add("path", { d: `M ${boldX} ${yBold - 20} L ${boldX + 7} ${yBold - 7} L ${boldX + 20} ${yBold} L ${boldX + 7} ${yBold + 7} L ${boldX} ${yBold + 20} L ${boldX - 7} ${yBold + 7} L ${boldX - 20} ${yBold} L ${boldX - 7} ${yBold - 7} Z`, fill: "#ffdc00" });

      const shySeen = visible(shyPath[state.shy]);
      const boldSeen = visible(boldPath[state.bold]);
      const complete = state.shy === shyTarget && state.bold === boldTarget;
      status.textContent = complete
        ? `Synchronized after ${state.pulses} pulse${state.pulses === 1 ? "" : "s"}.`
        : `Shy ${shySeen ? "seen → frozen" : "hidden → will move"}; bold ${boldSeen ? "seen → will move" : "hidden → frozen"}.`;
    }

    function action(name) {
      if (name === "left") state.eye = Math.max(0, state.eye - 1);
      if (name === "right") state.eye = Math.min(8, state.eye + 1);
      if (name === "veil") state.veil = !state.veil;
      if (name === "pulse") {
        const shyMoves = !visible(shyPath[state.shy]);
        const boldMoves = visible(boldPath[state.bold]);
        if (shyMoves) state.shy = (state.shy + 1) % shyPath.length;
        if (boldMoves) state.bold = (state.bold + 1) % boldPath.length;
        state.pulses += 1;
      }
      if (name === "reset") Object.assign(state, { eye: 1, veil: true, shy: 0, bold: 0, pulses: 0 });
      render();
    }

    document.querySelectorAll("[data-demo-action]").forEach((button) => {
      button.addEventListener("click", () => action(button.dataset.demoAction));
    });
    render();
  }

  async function main() {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`Research data failed: ${response.status}`);
    const data = await response.json();
    renderCorpora(data.corpora);
    renderLedger(data.external_ledger);
    renderGaps(data.gap_hypotheses);
    renderProgression(data.q001_progression);
    quietFieldDemo();
  }

  main().catch((error) => {
    console.error(error);
    const target = document.querySelector("main");
    const message = el("p", "research-error", "The research figures could not be loaded.");
    message.setAttribute("role", "alert");
    target.prepend(message);
  });
})();
