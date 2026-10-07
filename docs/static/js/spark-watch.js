/*
Author: Claude Opus 5.5 (Bubba)
Date: 07-October-2026
PURPOSE: Watch one Spark sample in the site's trace viewer (viewer.html), live while it plays and afterwards (Son, #arc-3
  7-Oct: "Allow me to click on each currently being played game and view it too"). The Mode explorer's job list links
  each sample to viewer.html#run=spark:<job>:<sample>&game=0; api.js sends every "spark:" run here instead of to the
  static run exports. This module pulls the sample's own trace-viewer events through the site relay
  (/api/v1/spark-runner/jobs/<job>/samples/<k>/events?after=n, railway/spark_runner.py, which adds the runner key on
  the server) from the Spark runner (tools/spark_runner/server.py sample_events), only the new ones on each poll, and
  shapes them into the four payloads the viewer already reads: run overview, game shell, frames and per-turn steps.
  main.js, board.js, log.js, scrubber.js and decision.js draw them unchanged.
SRP/DRY check: Pass - data shaping only, no drawing. The frame and transcript-section shaping mirrors the viewer's own
  loader (ARC3-Inference/viewer/data.py: _build_frames, parse_click_cell, _split_labeled_sections, _ARC_COLOR_MAP), kept
  to those few rules so the live view matches stored runs; the relay and key handling stay in spark_runner.py.
*/

const SITE = new URL("../../", import.meta.url);
const PREFIX = "spark:";
const REFRESH_MS = 4000;   // main.js polls every 1.5 s; the Sparks are asked at most this often

// ARC3-Inference/viewer/data.py _ARC_COLOR_MAP and grid_utils.ARC_COLOR_CHARS, as the static exports carry them.
const COLOR_CHARS = "WwgGcBMPRbSYOrNp";
const PALETTE = ["#FFFFFF", "#CCCCCC", "#999999", "#666666", "#333333", "#000000", "#E53AA3", "#FF7BCC",
  "#F93C31", "#1E93FF", "#88D8F1", "#FFDC00", "#FF851B", "#921231", "#4FCC30", "#A356D6"].map((hex) =>
  `rgb(${parseInt(hex.slice(1, 3), 16)}, ${parseInt(hex.slice(3, 5), 16)}, ${parseInt(hex.slice(5, 7), 16)})`);

const FRAME_KEYS = ["type", "title", "action_num", "analysis_step", "action_name", "action_display", "score", "state",
  "level", "reward", "board_changed", "level_completed", "game_over", "run_status"];
const CLICK_RE = /row\s*=\s*(\d+)\s*,\s*col\s*=\s*(\d+)/i;
const SECTION_RE = /^\[(.+?)\]\s*$/gm;
const KNOWN_LABELS = new Set(["ASSISTANT", "ACTION_RESPONSE", "ANALYZER STATUS", "MODEL CONTEXT", "MODEL RESPONSE META",
  "OUTPUT", "PROMPT LOG SNAPSHOT", "SYSTEM PROMPT", "THINKING", "USER PROMPT"]);
const KNOWN_PREFIXES = ["ERROR", "TOOL CALL:", "TOOL RESULT:"];

export const isSparkRun = (run) => typeof run === "string" && run.startsWith(PREFIX);

/** The viewer link for one sample (k counts from 0, as the runner does). */
export const watchHref = (job, k) => `./viewer.html#run=${encodeURIComponent(`${PREFIX}${job}:${k}`)}&game=0`;

function parseRun(run) {
  const m = /^spark:([a-z0-9-]{8,40}):(\d{1,2})$/.exec(run || "");
  if (!m) throw new Error(`not a Spark sample: ${run}`);
  return { job: m[1], k: Number(m[2]) };
}

function splitSections(text) {
  const matches = [...String(text || "").matchAll(SECTION_RE)].filter((m) => {
    const label = m[1].trim();
    return KNOWN_LABELS.has(label) || KNOWN_PREFIXES.some((p) => label.startsWith(p));
  });
  return matches.map((m, i) => {
    const label = m[1].trim();
    const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
    const kind = ["ASSISTANT", "OUTPUT", "THINKING"].includes(label) ? "reasoning"
      : /^(TOOL CALL|TOOL RESULT|ERROR)/.test(label) ? "tool" : "meta";
    return { label, content: text.slice(m.index + m[0].length, end).trim(), kind };
  });
}

const samples = new Map();   // run -> { events, frames, steps, meta, fetched, pending }

function sampleFor(run) {
  if (!samples.has(run)) samples.set(run, { events: [], frames: [], steps: [], meta: null, fetched: 0, pending: null });
  return samples.get(run);
}

function absorb(s, events) {
  for (const ev of events) {
    const eventIndex = s.events.length;
    s.events.push(ev);
    if (ev.type === "initial" || ev.type === "action") {
      const frame = { frameIndex: s.frames.length, eventIndex };
      for (const key of FRAME_KEYS) if (ev[key] !== undefined && ev[key] !== null) frame[key] = ev[key];
      frame.board_ascii = ev.board_ascii || "";
      const click = CLICK_RE.exec(ev.action_display || "");
      if (click) frame.click = { row: Number(click[1]), col: Number(click[2]) };
      s.frames.push(frame);
    } else if (ev.type === "analysis") {
      // A turn can log several analysis events (one per model call); like data.py, the turn keeps its first board
      // and its latest transcript.
      const same = s.steps.find((step) => step.analysisStep === ev.analysis_step);
      if (same) {
        same.localContext = { sections: splitSections(ev.transcript) };
        continue;
      }
      s.steps.push({
        stepIndex: s.steps.length, analysisStep: ev.analysis_step, title: ev.title, sourceEventIndex: eventIndex,
        level: ev.level, score: ev.score, state: ev.state, stepKind: "analysis",
        boardEvent: { board_ascii: ev.board_ascii || "" },
        localContext: { sections: splitSections(ev.transcript) },
      });
    }
  }
}

async function pull(run) {
  const { job, k } = parseRun(run);
  const s = sampleFor(run);
  for (let piece = 0; piece < 50; piece += 1) {
    const url = new URL(`api/v1/spark-runner/jobs/${job}/samples/${k}/events?after=${s.events.length}`, SITE);
    const response = await fetch(url, { cache: "no-store", credentials: "same-origin" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.message || body.detail || (response.status === 401
        ? "sign in to the site to watch Spark samples" : `the Spark runner answered ${response.status}`));
    }
    if (body.after !== s.events.length) break;   // another pull got there first
    absorb(s, body.events || []);
    s.meta = body;
    if (!body.events?.length || body.next >= body.total) break;
  }
  s.fetched = Date.now();
}

async function sync(run) {
  const s = sampleFor(run);
  const ended = s.meta && s.meta.status !== "playing";
  if (s.meta && (ended || Date.now() - s.fetched < REFRESH_MS)) return s;
  if (!s.pending) s.pending = pull(run).finally(() => { s.pending = null; });
  await s.pending;
  return s;
}

function shell(run, s) {
  const { job, k } = parseRun(run);
  const m = s.meta || {};
  return {
    game_id: m.game_id || m.game || job, status: m.status || "playing",
    display_name: `${m.game_id || m.game || ""} · Spark job ${job} · sample ${k + 1}`,
    levels_completed: m.levels_completed, total_levels: m.total_levels,
    eventCount: s.events.length, actionCount: s.frames.length,
    viewer_steps: s.steps, stepCount: s.steps.length, stepsAreLazy: true,
  };
}

export async function sparkOverview(run) {
  const s = await sync(run);
  const { job, k } = parseRun(run);
  const game = { ...shell(run, s), board_ascii: s.frames[s.frames.length - 1]?.board_ascii || "" };
  delete game.viewer_steps;
  return {
    run_name: `Spark job ${job} · sample ${k + 1}`, selected_run: run, available_runs: [run], source: "spark_runner",
    arc_palette: PALETTE, color_chars: COLOR_CHARS, games: [game],
  };
}

export async function sparkGame(run) {
  return shell(run, await sync(run));
}

export async function sparkFrames(run) {
  const s = await sync(run);
  return { gameIndex: 0, frameCount: s.frames.length, frames: s.frames.slice() };
}

export async function sparkStep(run, stepIndex) {
  const s = await sync(run);
  const step = s.steps[stepIndex];
  if (!step) throw new Error(`step ${stepIndex} is not here yet`);
  // The turn's actions arrive after its analysis event, so they are gathered when the step is opened.
  const actions = s.frames.filter((f) => f.analysis_step === step.analysisStep && f.type === "action");
  return {
    stepIndex, stepCount: s.steps.length,
    step: { ...step, actionDisplay: actions.map((f) => f.action_display).filter(Boolean).join(" -> "),
      batchSize: actions.length, detailLoaded: true },
  };
}
