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
  let current = null; // { version, versionId }
  let reviewed = 0;
  const skipped = new Set();
  const seen = []; // this session's order, so "previous game" can step back
  let busy = false;
  let telemetryTimer = null;

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
  $("fbPrev").addEventListener("click", async () => {
    // Back to the game before this one, without going home. The queue keeps its order.
    if (busy || seen.length < 2) return;
    busy = true;
    try {
      seen.pop();
      const previous = seen[seen.length - 1];
      skipped.delete(previous.versionId);
      await load(previous, null, { remember: false });
    } finally {
      busy = false;
      $("fbPrev").disabled = seen.length < 2;
    }
  });
  $("fbExit").addEventListener("click", () => exit());

  function resetForm() {
    $("fbComment").value = "";
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
      `levels ${t.levelsCompleted}/${t.levelsTotal ?? "?"} · ${t.actions} actions · ${t.resets} resets · ${minutes}:${seconds} · ${outcomeFromState(t).replace("_", " ")}`;
  }

  async function load(version, remaining, { remember = true } = {}) {
    resetForm();
    current = { version, versionId: version.versionId };
    if (remember && (!seen.length || seen[seen.length - 1].versionId !== version.versionId)) seen.push(version);
    const blindLabel = version.gameId;
    $("fbGameLabel").textContent = blindLabel;
    $("fbQueueLabel").textContent =
      remaining != null ? ` · ${remaining} game${remaining === 1 ? "" : "s"} in this pool need${remaining === 1 ? "s" : ""} a review` : "";
    $("fbDone").hidden = true;
    form.hidden = false;
    $("fbPrev").disabled = seen.length < 2;
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
    const payload = {
      game_id: current.version.gameId,
      version_id: current.versionId,
      comment: $("fbComment").value.trim() || null,
      outcome: outcomeFromState(t),
      levels_completed: t.levelsCompleted,
      levels_total: t.levelsTotal ?? null,
      actions: t.actions,
      resets: t.resets,
      undos: t.undos,
      seconds: t.seconds,
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
    if (!payload.comment) {
      showError("Write a comment first, or press Skip.");
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
