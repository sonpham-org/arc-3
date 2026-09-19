// "Feedback games": play one game after another and review each, blind.
//
// The server picks what to play next -- the current version of a game line that most needs a
// review (railway/games_store.py next_version): for a signed-in team member, the versions with
// the fewest team reviews and none of their own; for the public, the least-reviewed overall.
// Nothing about the game is shown before or during play (no title for blind families, no change
// notes, no earlier reviews), so the review is a first impression. Signed-in reviews are filed
// as team reviews and always rank ahead of public ones.

const SEEN_KEY = "arc3-feedback-seen";
const POOL_KEY = "arc3-feedback-pool";
const NICK_KEY = "arc3-feedback-nickname";

const $ = (id) => document.getElementById(id);

function readSeen() {
  try {
    const seen = JSON.parse(localStorage.getItem(SEEN_KEY) || "[]");
    return Array.isArray(seen) ? seen.filter((id) => typeof id === "string") : [];
  } catch (e) {
    return [];
  }
}

function rememberSeen(versionId) {
  if (!versionId) return;
  try {
    const seen = readSeen().filter((id) => id !== versionId);
    seen.push(versionId);
    localStorage.setItem(SEEN_KEY, JSON.stringify(seen.slice(-300)));
  } catch (e) {
    /* storage off: the server-side queue still works, it just may repeat a game */
  }
}

export function createFeedback({ player, api, getMe, onExit }) {
  const form = $("fbForm");
  const ratings = {};
  const flags = new Set();
  let verdict = null;
  let current = null; // { version, versionId }
  let reviewed = 0;
  const skipped = new Set();
  let busy = false;
  let telemetryTimer = null;

  // ── Form wiring ──
  for (const group of form.querySelectorAll("[data-rating]")) {
    const key = group.dataset.rating;
    for (const button of group.querySelectorAll("button[data-value]")) {
      button.addEventListener("click", () => {
        const value = Number(button.dataset.value);
        ratings[key] = ratings[key] === value ? null : value;
        for (const b of group.querySelectorAll("button[data-value]")) {
          b.classList.toggle("active", Number(b.dataset.value) === ratings[key]);
        }
      });
    }
  }
  for (const button of form.querySelectorAll("[data-flag]")) {
    button.addEventListener("click", () => {
      const flag = button.dataset.flag;
      if (flags.has(flag)) flags.delete(flag);
      else flags.add(flag);
      button.classList.toggle("active", flags.has(flag));
      button.setAttribute("aria-pressed", flags.has(flag) ? "true" : "false");
    });
  }
  for (const button of form.querySelectorAll("[data-verdict]")) {
    button.addEventListener("click", () => {
      verdict = verdict === button.dataset.verdict ? null : button.dataset.verdict;
      for (const b of form.querySelectorAll("[data-verdict]")) b.classList.toggle("active", b.dataset.verdict === verdict);
    });
  }
  try {
    $("fbNick").value = localStorage.getItem(NICK_KEY) || "";
    const pool = localStorage.getItem(POOL_KEY);
    if (pool && [...$("fbPool").options].some((o) => o.value === pool)) $("fbPool").value = pool;
  } catch (e) {
    /* defaults are fine */
  }
  $("fbPool").addEventListener("change", () => {
    try {
      localStorage.setItem(POOL_KEY, $("fbPool").value);
    } catch (e) {
      /* not remembered, still applied */
    }
    next();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submit();
  });
  $("fbSkip").addEventListener("click", () => {
    if (current) skipped.add(current.versionId);
    next();
  });
  $("fbExit").addEventListener("click", () => exit());

  function resetForm() {
    for (const key of Object.keys(ratings)) ratings[key] = null;
    flags.clear();
    verdict = null;
    for (const b of form.querySelectorAll("button.active")) b.classList.remove("active");
    for (const b of form.querySelectorAll("[data-flag]")) b.setAttribute("aria-pressed", "false");
    for (const area of form.querySelectorAll("textarea")) area.value = "";
    $("fbOutcome").value = "auto";
    $("fbWebsite").value = "";
    showError(null);
  }

  function showError(message) {
    $("fbError").hidden = !message;
    $("fbError").textContent = message || "";
  }

  function identityLine() {
    const me = getMe();
    const who = $("fbWho");
    who.replaceChildren();
    if (me) {
      who.textContent = `Reviewing as team · ${me.email}`;
      $("fbNickWrap").hidden = true;
    } else {
      who.append("Reviewing as public · ");
      const link = document.createElement("a");
      link.href = api.signInUrl();
      link.textContent = "team sign-in";
      who.appendChild(link);
      $("fbNickWrap").hidden = false;
    }
  }

  function outcomeFromState(t) {
    if (t.state === "WIN") return "won";
    if (t.state === "GAME_OVER") return "lost";
    return "in_progress";
  }

  function paintTelemetry() {
    if (!current) return;
    const t = player.telemetry();
    const minutes = Math.floor(t.seconds / 60);
    const seconds = String(t.seconds % 60).padStart(2, "0");
    $("fbTelemetry").textContent =
      `levels ${t.levelsCompleted}/${t.levelsTotal ?? "?"} · ${t.actions} actions · ${t.resets} resets · ${minutes}:${seconds}` +
      ($("fbOutcome").value === "auto" ? ` · ${outcomeFromState(t).replace("_", " ")}` : "");
  }

  async function load(version, remaining) {
    resetForm();
    current = { version, versionId: version.versionId };
    const blindLabel = version.gameId;
    $("fbGameLabel").textContent = blindLabel;
    $("fbQueueLabel").textContent =
      remaining != null ? ` · ${remaining} game${remaining === 1 ? "" : "s"} in this pool need${remaining === 1 ? "s" : ""} a review` : "";
    $("fbDone").hidden = true;
    form.hidden = false;
    const loaded = await player.load(version, { blind: true });
    if (!loaded) return;
    // File the review under the bytes that actually ran (see games-api.js fetchSource).
    if (loaded.sha256) current.versionId = `${version.gameId}@${loaded.sha256.slice(0, 12)}`;
    paintTelemetry();
  }

  async function next() {
    if (busy) return;
    busy = true;
    showError(null);
    try {
      const me = getMe();
      const exclude = [...new Set([...(me ? [] : readSeen()), ...skipped])].slice(-400);
      const params = { pool: $("fbPool").value, exclude: exclude.join(",") };
      if (!me) params.visitor = api.visitorId();
      const result = await api.nextVersion(!!me, params);
      if (!result.version) {
        current = null;
        player.stop();
        form.hidden = true;
        $("fbDone").hidden = false;
        return;
      }
      await load(result.version, result.remaining);
    } catch (err) {
      showError(`Could not get the next game (${err.message}). The feedback queue needs the site's API.`);
    } finally {
      busy = false;
    }
  }

  function collect() {
    const t = player.telemetry();
    const outcome = $("fbOutcome").value === "auto" ? outcomeFromState(t) : $("fbOutcome").value;
    const text = (id) => $(id).value.trim() || null;
    const payload = {
      game_id: current.version.gameId,
      version_id: current.versionId,
      outcome,
      levels_completed: t.levelsCompleted,
      levels_total: t.levelsTotal ?? null,
      actions: t.actions,
      resets: t.resets,
      undos: t.undos,
      seconds: t.seconds,
      fun: ratings.fun ?? null,
      clarity: ratings.clarity ?? null,
      difficulty: ratings.difficulty ?? null,
      novelty: ratings.novelty ?? null,
      flags: [...flags],
      goal_guess: text("fbGoal"),
      liked: text("fbLiked"),
      disliked: text("fbDisliked"),
      suggestion: text("fbSuggestion"),
      bugs: text("fbBugs"),
      verdict,
      website: $("fbWebsite").value,
      client: {
        viewport: `${window.innerWidth}x${window.innerHeight}`,
        tileMode: t.tileMode,
        filter: t.filter,
        mobile: matchMedia("(pointer: coarse)").matches,
      },
    };
    if (!getMe()) {
      payload.visitor_id = api.visitorId();
      payload.nickname = $("fbNick").value.trim() || null;
    }
    return payload;
  }

  async function submit() {
    if (!current || busy) return;
    const payload = collect();
    const saidSomething =
      ["fun", "clarity", "difficulty", "novelty"].some((k) => payload[k] != null) ||
      payload.flags.length ||
      ["goal_guess", "liked", "disliked", "suggestion", "bugs"].some((k) => payload[k]) ||
      payload.verdict;
    if (!saidSomething) {
      showError("Rate it, tick a flag, or write something first — or press Skip.");
      return;
    }
    busy = true;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      await api.submitFeedback(!!getMe(), payload);
      reviewed += 1;
      $("fbCount").textContent = `${reviewed} reviewed this session`;
      rememberSeen(current.version.versionId);
      rememberSeen(current.versionId);
      try {
        localStorage.setItem(NICK_KEY, $("fbNick").value.trim());
      } catch (e) {
        /* fine */
      }
      busy = false;
      await next();
    } catch (err) {
      showError(err.status === 429 ? "That's a lot of reviews very fast — give it a few minutes." : `Could not send (${err.message}).`);
    } finally {
      busy = false;
      button.disabled = false;
    }
  }

  async function enter({ version } = {}) {
    identityLine();
    player.mountStage($("fbStageSlot"));
    $("fbCount").textContent = `${reviewed} reviewed this session`;
    clearInterval(telemetryTimer);
    telemetryTimer = setInterval(paintTelemetry, 1000);
    if (version) {
      busy = true;
      try {
        await load(version, null);
      } finally {
        busy = false;
      }
    } else {
      await next();
    }
  }

  function exit() {
    clearInterval(telemetryTimer);
    player.stop();
    player.unmountStage();
    current = null;
    onExit();
  }

  return { enter, exit, refreshIdentity: identityLine, isActive: () => !$("feedbackView").hidden };
}
