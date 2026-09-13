import { fetchGame, fetchGameFrames, fetchGameStep, fetchRunOverview } from "./api.js";
import { initBoard, setPalette, showBoard } from "./board.js?v=20260815-frames";
import {
  canonicalGameRef,
  framePositionForRoute,
  parseViewerHash,
  resolveGameIndex,
  viewerHash,
} from "./viewer-route.js?v=20260911-turn-links";

const API = document.body.dataset.debuggerApi.replace(/\/$/, "");
const state = { route: null, overview: null, game: null, frames: [], frame: null, modelFrame: null, step: null, resumeContext: null, contextPreview: null, session: null };
let capabilities = null;
let pollTimer = null;
let previewTimer = null;
let previewSerial = 0;

const RECONSTRUCTED_PYTHON_TOOL = {
  type: "function",
  function: {
    name: "python",
    description: "Run one ephemeral Python snippet against the preloaded ARC game state and optionally return the revised carried world model.",
    parameters: {
      type: "object",
      properties: {
        code: { type: "string", description: "Python code to run against current_frame, history, transitions, and action(actions)." },
        world_model: { type: "string", description: "The revised knowledge ledger to carry into later turns." },
      },
      required: ["code", "world_model"],
    },
  },
};

const $ = (selector) => document.querySelector(selector);
const el = {
  crumb: $("#debug-crumb"),
  status: $("#cluster-status"),
  sourceBadge: $("#context-source"),
  board: $("#debug-board"),
  boardMeta: $("#debug-board-meta"),
  system: $("#system-prompt"),
  user: $("#user-prompt"),
  memory: $("#memory"),
  context: $("#context-so-far"),
  contextStats: $("#context-stats"),
  contextNote: $("#context-preview-note"),
  flags: $("#flag-list"),
  audit: $("#source-audit"),
  maxTokens: $("#max-tokens"),
  temperature: $("#temperature"),
  topP: $("#top-p"),
  topK: $("#top-k"),
  resume: $("#resume"),
  response: $("#response"),
  responseMeta: $("#response-meta"),
  followup: $("#followup"),
  followupSend: $("#followup-send"),
  viewerLink: $("#viewer-link"),
  copy: $("#copy-debug-link"),
};

initBoard(el.board);

function lastSection(sections, label) {
  return [...(sections || [])].reverse().find((section) => section.label === label)?.content || "";
}

function extractMemory(userPrompt, sections) {
  const prompt = String(userPrompt);
  const knowledgeLedger = prompt.match(/Knowledge ledger carried from earlier turns:\s*([\s\S]*?)\s*End of carried knowledge ledger\./i);
  if (knowledgeLedger) return knowledgeLedger[1].trim();
  const legacyWorldModel = prompt.match(/Working world model carried from earlier turns:\s*([\s\S]*?)\s*end of world model\./i);
  if (legacyWorldModel) return legacyWorldModel[1].trim();
  const tool = [...(sections || [])].reverse().find((section) => section.label === "TOOL CALL: python");
  if (!tool) return "";
  const worldModel = String(tool.content || "").match(/<parameter=world_model>\s*([\s\S]*?)\s*<\/parameter>/i);
  return worldModel ? worldModel[1].trim() : "";
}

function patchTextContent(message, text) {
  if (typeof message.content === "string") return { ...message, content: text };
  if (Array.isArray(message.content)) {
    const content = message.content.map((part) => ({ ...part }));
    const index = content.findIndex((part) => part.type === "text");
    if (index >= 0) content[index].text = text;
    else content.unshift({ type: "text", text });
    return { ...message, content };
  }
  return { ...message, content: text };
}

function messageText(message) {
  if (!message) return "";
  if (typeof message.content === "string") return message.content;
  if (!Array.isArray(message.content)) return "";
  return message.content
    .filter((part) => part?.type === "text")
    .map((part) => String(part.text || ""))
    .join("\n");
}

function editedExactMessages(resumeContext) {
  const messages = structuredClone(resumeContext.messages || []);
  const systemIndex = messages.findIndex((message) => message.role === "system");
  if (systemIndex >= 0) messages[systemIndex] = patchTextContent(messages[systemIndex], el.system.value);
  const userIndex = messages.findLastIndex((message) => message.role === "user");
  if (userIndex >= 0) {
    let prompt = el.user.value;
    const ledger = /Knowledge ledger carried from earlier turns:[\s\S]*?End of carried knowledge ledger\./i;
    const legacy = /Working world model carried from earlier turns:[\s\S]*?end of world model\./i;
    if (el.memory.value.trim()) {
      const rendered = `Knowledge ledger carried from earlier turns:\n${el.memory.value.trim()}\nEnd of carried knowledge ledger.`;
      if (ledger.test(prompt)) prompt = prompt.replace(ledger, rendered);
      else if (legacy.test(prompt)) prompt = prompt.replace(legacy, rendered);
      else prompt = `${rendered}\n${prompt}`;
    } else {
      prompt = prompt.replace(ledger, "").replace(legacy, "").trim();
    }
    messages[userIndex] = patchTextContent(messages[userIndex], prompt);
  }
  return messages;
}

function renderAudit(resumeContext, systemPrompt, userPrompt) {
  const rows = [
    ["Exact request snapshot", resumeContext?.source === "exact_request", "Structured roles and tool-call ids are available."],
    ["Carried knowledge ledger", Boolean(el.memory.value.trim()), "Detected in the selected turn's effective prompt."],
    ["State graph", /STATE GRAPH|state_graph/.test(systemPrompt), "Mainline currently records this only when the source harness exposed it."],
    ["Full animation context", /last_animation|frame_stats/.test(`${systemPrompt}\n${userPrompt}`), "The selected prompt advertises intermediate animation frames."],
    ["Common-theme sidecar", /Common themes and predicates learned from other games/.test(userPrompt), "Cross-game priors were present in this turn."],
  ];
  el.audit.innerHTML = rows.map(([label, on, note]) => `
    <div class="audit-row"><span class="audit-light ${on ? "on" : "off"}"></span>
      <div><b>${label}</b><small>${on ? "detected" : "not detected"} · ${note}</small></div></div>`).join("");
}

function renderFlags(resumeContext) {
  const inferred = resumeContext?.defaultFlags || {};
  el.flags.innerHTML = capabilities.flags.map((spec) => {
    const checked = Object.hasOwn(inferred, spec.id) ? inferred[spec.id] : spec.default;
    return `<label class="flag-row">
      <input type="checkbox" data-flag="${spec.id}" ${checked ? "checked" : ""}>
      <span><b>${spec.label}</b><small>${spec.effect}</small></span>
    </label>`;
  }).join("");
}

function selectedFlags() {
  return Object.fromEntries([...el.flags.querySelectorAll("[data-flag]")].map((input) => [input.dataset.flag, input.checked]));
}

function contextForRequest() {
  const resumeContext = state.resumeContext;
  const context = {
    systemPrompt: el.system.value,
    userPrompt: el.user.value,
    memory: el.memory.value,
    source: resumeContext?.source || "reconstructed",
    boardImage: el.board.toDataURL("image/png"),
    tools: resumeContext?.tools || [],
    toolChoice: resumeContext?.toolChoice || "auto",
  };
  if (resumeContext?.messages?.length) context.messages = editedExactMessages(resumeContext);
  return context;
}

function formatStoredContext(resumeContext, sections) {
  const messages = resumeContext?.messages || [];
  if (messages.length) {
    const blocks = messages.map((message, index) => {
      const role = String(message.role || "unknown").toUpperCase();
      const toolCallId = message.tool_call_id ? ` · tool_call_id=${message.tool_call_id}` : "";
      const parts = [`[MESSAGE ${index + 1}/${messages.length} · ${role}${toolCallId}]`];
      const reasoning = messageText({ content: message.reasoning || message.reasoning_content });
      if (reasoning) parts.push("[REASONING]", reasoning);
      const content = messageText(message);
      if (content) parts.push(content);
      if (Array.isArray(message.content) && message.content.some((part) => ["image_url", "input_image"].includes(part?.type))) {
        parts.push("[CURRENT GRID IMAGE ATTACHED]");
      }
      if (message.tool_calls?.length) parts.push("[TOOL CALLS]", JSON.stringify(message.tool_calls, null, 2));
      return parts.join("\n");
    });
    if (resumeContext.tools?.length) blocks.push(`[AVAILABLE TOOLS]\n${JSON.stringify(resumeContext.tools, null, 2)}`);
    return blocks.join("\n\n");
  }
  return (sections || []).map((section) => `[${section.label || "SECTION"}]\n${section.content || ""}`).join("\n\n");
}

function formatTokenCount(value) {
  const number = Number(value || 0);
  return number >= 1000 ? `${(number / 1000).toFixed(1)}K` : String(number);
}

function sessionRequestBody() {
  return {
    origin: {
      run: state.route.run,
      game: state.game.game_id,
      turn: state.frame.analysis_step,
      frame: state.frame.frameIndex,
      url: location.href,
    },
    context: contextForRequest(),
    flags: selectedFlags(),
    settings: {
      maxTokens: Number(el.maxTokens.value),
      temperature: Number(el.temperature.value),
      topP: Number(el.topP.value),
      topK: Number(el.topK.value),
    },
  };
}

async function previewPlayContext() {
  if (!capabilities || !state.step) return;
  const serial = ++previewSerial;
  el.resume.disabled = true;
  el.contextStats.textContent = "COUNTING TOKENS…";
  el.contextNote.className = "provenance-note";
  try {
    const preview = await api("/v1/preview", {
      method: "POST",
      body: JSON.stringify(sessionRequestBody()),
    });
    if (serial !== previewSerial) return;
    state.contextPreview = preview;
    el.context.value = preview.contextText || "The final request contains no displayable text.";
    el.contextStats.textContent = `${preview.messageCount} messages · ${formatTokenCount(preview.promptTokens)} input · ${formatTokenCount(preview.availableOutputTokens)} free`;
    if (preview.fits) {
      const provenance = preview.source === "exact_request"
        ? "Exact saved message stack, after applying the current fork flags."
        : "Reconstructed source: this older run did not retain its exact historical message stack.";
      el.contextNote.textContent = `${provenance} The live Qwen tokenizer confirms that this request fits its ${formatTokenCount(preview.maxModelLen)}-token window.`;
      el.contextNote.className = `provenance-note ${preview.source === "exact_request" ? "" : "warn"}`.trim();
      el.resume.disabled = false;
    } else {
      el.contextNote.textContent = `This input leaves ${preview.availableOutputTokens} tokens, but ${preview.requestedOutputTokens} output tokens are requested. Reduce Max output tokens before Play.`;
      el.contextNote.className = "provenance-note error";
    }
  } catch (error) {
    if (serial !== previewSerial) return;
    el.contextStats.textContent = "TOKEN CHECK FAILED";
    el.contextNote.textContent = `The final request could not be validated: ${error.message}`;
    el.contextNote.className = "provenance-note error";
  }
}

function scheduleContextPreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(previewPlayContext, 350);
}

function modelStateFrame(frames, selected) {
  const turn = selected?.analysis_step;
  let position = frames.indexOf(selected);
  if (position < 0) return selected;
  if (turn !== undefined && turn !== null) {
    while (position > 0 && frames[position - 1]?.analysis_step === turn) position -= 1;
  }
  return position > 0 ? frames[position - 1] : selected;
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    cache: "no-store",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
  return payload;
}

async function connectCluster() {
  try {
    capabilities = await api("/v1/capabilities");
    el.status.className = "cluster-status ready";
    el.status.textContent = `● ${capabilities.model} · ${capabilities.clusterNodes.join(" + ")}`;
  } catch (error) {
    el.status.className = "cluster-status error";
    el.status.textContent = `Spark gateway unavailable · ${error.message}. Railway's ARC tailnet relay is offline.`;
    throw error;
  }
}

async function loadTurn() {
  state.route = parseViewerHash();
  if (!state.route.run || state.route.game === null) throw new Error("Open a game turn from Viewer first.");
  state.overview = await fetchRunOverview(state.route.run);
  const gameIndex = resolveGameIndex(state.overview.games, state.route.game, state.route.instance);
  if (gameIndex < 0) throw new Error(`Game ${state.route.game} is not in ${state.route.run}.`);
  [state.game, { frames: state.frames }] = await Promise.all([
    fetchGame(state.route.run, gameIndex),
    fetchGameFrames(state.route.run, gameIndex),
  ]);
  let position = framePositionForRoute(state.frames, state.route);
  if (position === null) position = Math.max(0, state.frames.length - 1);
  state.frame = state.frames[position];
  state.modelFrame = modelStateFrame(state.frames, state.frame);
  const turn = state.route.turn ?? state.frame?.analysis_step;
  const summary = [...(state.game.viewer_steps || [])].reverse().find((candidate) => candidate.analysisStep === turn);
  if (!summary) throw new Error("This frame has no resumable model turn.");
  state.step = (await fetchGameStep(state.route.run, gameIndex, summary.stepIndex)).step;

  setPalette(state.overview.arc_palette, state.overview.color_chars);
  showBoard(state.modelFrame.board_ascii);
  const ref = canonicalGameRef(state.overview.games, gameIndex);
  const hash = viewerHash({ run: state.route.run, ...ref, turn, frame: state.frame.frameIndex });
  history.replaceState(null, "", `${location.pathname}${location.search}${hash}`);
  el.viewerLink.href = `./viewer.html${hash}`;
  el.crumb.textContent = `${state.route.run} · ${state.game.game_id} · T${turn} · frame ${state.frame.frameIndex}`;
  el.boardMeta.textContent = `State seen by Qwen before T${turn} · score ${state.modelFrame.score ?? 0} · ${state.modelFrame.state || ""}`;

  const context = state.step.context || state.step.localContext || {};
  const sections = (context.sections || []).filter((section) => section.inContext !== false);
  const exactMessages = state.step.resumeContext?.messages || [];
  const exactSystem = exactMessages.find((message) => message.role === "system");
  const exactUser = [...exactMessages].reverse().find((message) => message.role === "user");
  const systemPrompt = messageText(exactSystem) || lastSection(sections, "SYSTEM PROMPT");
  const userPrompt = messageText(exactUser) || lastSection(sections, "USER PROMPT");
  el.system.value = systemPrompt;
  el.system.placeholder = systemPrompt ? "" : "Not stored in this legacy export. Exact request-log exports preserve it.";
  el.user.value = userPrompt;
  el.memory.value = extractMemory(userPrompt, sections);
  const hasPythonTool = /Only tool:\s*`python`|python tool/i.test(`${systemPrompt}\n${userPrompt}`);
  state.resumeContext = state.step.resumeContext || {
    source: "reconstructed",
    messages: [],
    tools: hasPythonTool ? [RECONSTRUCTED_PYTHON_TOOL] : [],
    toolChoice: "auto",
    defaultFlags: {
      thinking: true,
      memory: Boolean(el.memory.value.trim()),
      tools: hasPythonTool,
      current_grid: true,
      transition_guidance: /distinguish gameplay change from HUD-only change/i.test(userPrompt),
      strategy_guidance: /compact inspection\/search code/i.test(userPrompt),
      mouse_guidance: /include integer row and col arguments/i.test(userPrompt),
    },
  };
  const exact = state.resumeContext.source === "exact_request";
  el.sourceBadge.textContent = exact ? "EXACT REQUEST" : "RECONSTRUCTED";
  el.sourceBadge.className = `context-source ${exact ? "exact" : "reconstructed"}`;
  const storedContext = formatStoredContext(state.resumeContext, sections);
  el.context.value = storedContext || "No stored text was available for this turn.";
  el.contextStats.textContent = `${state.resumeContext.messages?.length || sections.length} stored records`;
  el.contextNote.textContent = exact
    ? "Preparing the exact outbound request after applying the current fork flags…"
    : "Preparing the best available reconstructed request; this run did not retain the complete historical message stack.";
  el.contextNote.className = `provenance-note ${exact ? "" : "warn"}`.trim();
  renderAudit(state.resumeContext, systemPrompt, userPrompt);
}

function renderResponse(session) {
  state.session = session;
  el.resume.disabled = ["queued", "running"].includes(session.status);
  el.followupSend.disabled = session.status !== "complete";
  if (["queued", "running"].includes(session.status)) {
    el.response.className = "response pending";
    el.response.textContent = session.status === "queued" ? "Queued on the Spark cluster…" : "Qwen is continuing this turn…";
    el.responseMeta.textContent = `session ${session.id}`;
    return;
  }
  if (session.status === "error") {
    el.response.className = "response failed";
    el.response.textContent = session.error || "The resumed turn failed.";
    return;
  }
  const response = session.response || {};
  const blocks = [];
  if (response.reasoning) blocks.push(`THINKING\n${response.reasoning}`);
  if (response.content) blocks.push(`ASSISTANT\n${response.content}`);
  if (response.toolCalls?.length) blocks.push(`TOOL CALLS\n${JSON.stringify(response.toolCalls, null, 2)}`);
  el.response.className = "response";
  el.response.textContent = blocks.join("\n\n") || "Qwen returned an empty response.";
  const usage = response.usage || {};
  el.responseMeta.textContent = [
    `${response.elapsedSeconds ?? "?"}s`,
    usage.prompt_tokens !== undefined ? `${usage.prompt_tokens} input tok` : "",
    usage.completion_tokens !== undefined ? `${usage.completion_tokens} output tok` : "",
    response.finishReason || "",
  ].filter(Boolean).join(" · ");
}

async function pollSession(id) {
  clearTimeout(pollTimer);
  try {
    const session = await api(`/v1/sessions/${encodeURIComponent(id)}`);
    renderResponse(session);
    if (["queued", "running"].includes(session.status)) {
      pollTimer = setTimeout(() => pollSession(id), 1200);
    }
  } catch (error) {
    el.response.className = "response failed";
    el.response.textContent = error.message;
  }
}

el.resume.addEventListener("click", async () => {
  el.resume.disabled = true;
  try {
    const session = await api("/v1/sessions", {
      method: "POST",
      body: JSON.stringify(sessionRequestBody()),
    });
    renderResponse(session);
    pollSession(session.id);
  } catch (error) {
    el.resume.disabled = false;
    el.response.className = "response failed";
    el.response.textContent = error.message;
  }
});

for (const input of [el.system, el.user, el.memory, el.maxTokens, el.temperature, el.topP, el.topK]) {
  input.addEventListener("input", scheduleContextPreview);
}
el.flags.addEventListener("change", scheduleContextPreview);

el.followupSend.addEventListener("click", async () => {
  if (!state.session || !el.followup.value.trim()) return;
  try {
    const session = await api(`/v1/sessions/${encodeURIComponent(state.session.id)}/messages`, {
      method: "POST",
      body: JSON.stringify({ message: el.followup.value }),
    });
    el.followup.value = "";
    renderResponse(session);
    pollSession(session.id);
  } catch (error) {
    el.response.className = "response failed";
    el.response.textContent = error.message;
  }
});

el.copy.addEventListener("click", async () => {
  await navigator.clipboard.writeText(location.href);
  const previous = el.copy.textContent;
  el.copy.textContent = "Copied";
  setTimeout(() => { el.copy.textContent = previous; }, 1200);
});

async function initialize() {
  el.resume.disabled = true;
  const [turnResult, clusterResult] = await Promise.allSettled([loadTurn(), connectCluster()]);
  if (turnResult.status === "rejected") {
    el.response.className = "response failed";
    el.response.textContent = turnResult.reason.message;
    return;
  }
  if (clusterResult.status === "rejected") {
    el.flags.innerHTML = '<p class="provenance-note">The Railway tailnet relay must be online to load the authoritative editable flag registry.</p>';
    el.response.className = "response failed";
    el.response.textContent = `Turn context loaded, but the Spark gateway is unavailable: ${clusterResult.reason.message}`;
    return;
  }
  renderFlags(state.resumeContext);
  await previewPlayContext();
}

initialize();
