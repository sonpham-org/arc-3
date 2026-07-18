"""Generate docs/data/runs-index.json: per-run stats, per-game scores, harness facts.

Stats come from each run's benchmark.json. The harness block is curated here --
server/weights/env facts live outside the run artifacts (they belong to the VM
that ran it), and this table is their single source of truth. The `baseline`
entry names the run every other run's knobs are diffed against on the site.
"""

import glob
import json
import os
import re


def extract_prompts(run_dir: str) -> dict:
    """First [SYSTEM PROMPT] and first [USER PROMPT] block from any transcript."""
    for t in sorted(glob.glob(os.path.join(run_dir, "transcripts", "*_p0.txt"))):
        text = open(t, errors="replace").read(200_000)
        blocks = re.split(r"^\[([A-Z ]+)\]$", text, flags=re.M)
        # blocks: [pre, LABEL, content, LABEL, content, ...]
        out = {}
        for label, content in zip(blocks[1::2], blocks[2::2]):
            if label == "SYSTEM PROMPT" and "system" not in out:
                out["system"] = content.strip()
            if label == "USER PROMPT" and "user_example" not in out:
                out["user_example"] = content.strip()
            if len(out) == 2:
                return out
        if out:
            return out
    return {}

BASELINE = "20260712_170321_tufa-exact-rung0"

# Priors hand-authored into the duck-harness prompt (prompts.py addenda + the
# per-turn user prompt in tool_agent._build_user_prompt). Shown on the harness
# page so the assumptions the agent is steered by are visible, not buried in
# source. `type`: design = engineered behaviour, measured = also backed by data
# from the run boards, measurable = assertion a data pass could confirm,
# convention = an interface fact. `evidence` cites data where we have it.
BIASES = [
    {"id": "segmentation-first", "title": "Segmentation-first perception",
     "detail": "Reason over objects from current_frame.segmentation, not raw pixels; never print full boards; use .ascii only for a small specific region.",
     "source": "STRUCTURED_RUNTIME_STATE_ADDENDUM + PYTHON_ADDENDUM", "type": "design"},
    {"id": "background-neutral", "title": "Backgrounds are neutral / dark",
     "detail": "Backgrounds are often white or gray/black-ish large regions — verify by area and stability rather than assuming.",
     "source": "VISUAL_GAME_ADDENDUM", "type": "measured",
     "evidence": "21/25 games in the v12 run have a neutral/dark dominant colour (black in 12)."},
    {"id": "object-shape", "title": "Entities are small blocks",
     "detail": "Game objects usually render as 2x2, 2x3, 3x3, or longer patterned shapes; sometimes 1x1 tokens.",
     "source": "VISUAL_GAME_ADDENDUM", "type": "measurable"},
    {"id": "hud-timer-bar", "title": "Edge strips are HUD/timers, not pieces",
     "detail": "A segmented strip flush to an edge that is the only thing changing is a timer/steps bar — do not click through it segment by segment.",
     "source": "VISUAL_GAME_ADDENDUM", "type": "design"},
    {"id": "no-avatar", "title": "Do not assume a player avatar",
     "detail": "Many games are logic/layout puzzles with no controllable sprite; the state may be a region, cursor, selector, or the whole board.",
     "source": "VISUAL_GAME_ADDENDUM", "type": "design"},
    {"id": "efficiency", "title": "Minimise actions (score is quadratic)",
     "detail": "Optimise for the fewest reliable actions; batch proven sequences; write BFS/search instead of trial and error.",
     "source": "GAME_OVERVIEW + PYTHON_ADDENDUM; score = min(115, (baseline/actions)^2 x 100)", "type": "design"},
    {"id": "anti-absolute-coord", "title": "The goal is not an absolute coordinate",
     "detail": "Do not frame the objective as reaching a specific row/col; use coordinates only to target actions or describe local evidence.",
     "source": "VISUAL_GAME_ADDENDUM", "type": "design"},
    {"id": "re-ground", "title": "Re-ground after score / scene changes",
     "detail": "After any score increase or abrupt change, re-read the newest frame — it may already be the next level. WIN means the whole game is solved.",
     "source": "VISUAL_GAME_ADDENDUM", "type": "design"},
    {"id": "probe-discipline", "title": "Stop probing once effects are known",
     "detail": "Once the state variables and action effects are understood, stop probing and search the inferred state space.",
     "source": "PYTHON_ADDENDUM", "type": "design"},
    {"id": "mouse-convention", "title": "MOUSE is (row, col)",
     "detail": "For MOUSE actions, row is vertical and col is horizontal; pass integer row/col (legacy x/y is rejected).",
     "source": "VISUAL_GAME_ADDENDUM + tool sandbox", "type": "convention"},
]

HARNESS = {
    "20260717_235600_v12-a7-action7-anim": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + ACTION7 fix + compact animation metadata",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px), last-frame + compact animation metadata (no images)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "two fixes ported from the 1.47 dark-agi notebook, on the plain baseline: (1) ACTION7 round-trip -- it was model-visible but silently no-op'd, and the agent used it 234x across 6 games here; (2) always-visible compact animation metadata (animation_changed / animation_only_changed / bbox / counts) in last_action_result, cheaper than full-frame images and the agent reasons about it. seed 1: ex-ft09 1.489 (all-25 1.72).",
    },
    "20260718_005200_v12-a7-action7-anim-b": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + ACTION7 fix + compact animation metadata",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px), last-frame + compact animation metadata (no images)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "seed 2 of the a7 fixes (identical config), run for variance. ex-ft09 0.987 (all-25 1.52). The two seeds (1.489 vs 0.987) show ex-ft09 is far noisier than assumed -- a7 mean ~1.24, within noise of baseline; a single run is not trustworthy.",
    },
    "20260718_114800_v12-ffa7": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + frame-full + ACTION7 fix + compact animation metadata",
        "memory": "scientist note (optional prose)",
        "render": "full-frame animation images + compact animation metadata",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "frame-full (ARC3_FRAME_MODE=full images) combined with the two a7 fixes (ACTION7 round-trip + always-visible compact animation metadata). all-25 1.97 -- but ft09=28.57 carried it; ex-ft09 only 0.864, below frame-full's 1.44. ACTION7 engaged (227 uses). seed 1 of 2.",
    },
    "20260718_114800_v12-ffa7b": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + frame-full + ACTION7 fix + compact animation metadata",
        "memory": "scientist note (optional prose)",
        "render": "full-frame animation images + compact animation metadata",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "seed 2 of frame-full+a7 (identical config). all-25 1.38, ex-ft09 1.437 (ft09=0.00). The two ffa7 seeds (ex-ft09 0.864 vs 1.437, 0.57 spread) fall within seed noise of frame-full / a7 / baseline -- combining ff+a7 did not clearly help; harnesses can't be ranked at 1-2 seeds.",
    },
    "20260716_132600_v12-predict-check": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + full-frame + predict-then-check",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px), full-frame animation",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "predict-then-check on the full-frame base: a predict(...) sandbox call lets the agent commit a testable claim before acting, scored against the actual next frame (surprise = counterexample) with a running prediction_stats gauge -- 1.51, top of the post-2.127 batch",
    },
    "20260715_225100_v12-ff3-framemode": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + frame-mode (ARC3_FRAME_MODE=full)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px), full-frame animation",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "clean 1-variable retest: baseline v12 bundle + source-based full-frame only, nothing else. 1.38 -- isolates full-frame's effect against the 2.127 graft baseline",
    },
    "20260716_014700_v12-base2": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "second baseline rerun of the plain v12 graft stack (variance re-measure): 1.14 vs the 2.127 original -- run-to-run spread on identical config is large",
    },
    "20260716_154900_v12-predict-check-forced": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + full-frame + prescriptive predict-check",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px), full-frame animation",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "prescriptive predict-then-check (ARC3_PREDICT_FORCE=1): same as v12-predict-check but the prompt REQUIRES a predict(...) before every act. Forcing it cost 0.37 (1.14 vs 1.51)",
    },
    "20260715_233600_v12-ff4b": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + click dead-signature",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "winner-inspired toggle on the baseline bundle: CLICK_DEADSIG suppresses MOUSE clicks on object classes (colour+shape) that never change the frame, per level. 0.82",
    },
    "20260715_233600_v12-ff4a": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + multi-frame images",
        "memory": "scientist note (optional prose)",
        "render": "multi-frame 4x (last 4 boards, STEP-labeled)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "winner-inspired toggle on the baseline bundle: MULTIMODAL_FRAMES=4 attaches the last 4 boards as a chronological STEP-labeled image sequence instead of one current frame. 0.56",
    },
    "20260715_193300_v12-ff2": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts) + full-frame (isolated code object)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px), full-frame animation",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "isolated source-based full-frame (ARC3_FRAME_MODE) on the graft base, pulled from a dedicated code object so it never touches the shared tufa0 tarball. 0.53",
    },
    "20260712_170321_tufa-exact-rung0": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
    },
    "20260712_130533_g4-v1-fullstack-32k": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "modified (ledger + fixes)",
        "memory": "two-tier ledger (required arg)",
        "render": "outline 8x + bevel (512px)",
        "yield_s": 900, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": "32768 (clips generation)", "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 132,
    },
    "20260712_130556_g4-v2-ledger-64k": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "modified (ledger + fixes)",
        "memory": "two-tier ledger (required arg)",
        "render": "outline 8x + bevel (512px)",
        "yield_s": 900, "thinking": "on (uncapped)",
        "agent_ctx": 65536, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 132,
    },
    "20260711_200118_a424-control-25game": {
        "hardware": "GB10 DGX Spark",
        "agent_code": "modified (tier-A fixes)",
        "memory": "scientist note + required world_model",
        "render": "plain 4x (256px)",
        "yield_s": 900, "thinking": "off",
        "agent_ctx": 32768, "server": "vLLM 0.24.0",
        "server_max_len": 32768, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 132,
    },
    "20260711_231159_a424-think3x-uncapped": {
        "hardware": "GB10 DGX Spark",
        "agent_code": "modified (tier-A fixes)",
        "memory": "scientist note + required world_model",
        "render": "outline 8x + bevel (512px)",
        "yield_s": 3600, "thinking": "on (uncapped -- pathological on GB10)",
        "agent_ctx": 32768, "server": "vLLM 0.24.0",
        "server_max_len": 32768, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 25, "budget_min": 396,
    },
    "20260711_185043_a424-study-ft09": {
        "hardware": "GB10 DGX Spark",
        "agent_code": "modified (tier-A fixes)",
        "memory": "scientist note + required world_model",
        "render": "plain 4x (256px)",
        "yield_s": 900, "thinking": "off",
        "agent_ctx": 32768, "server": "vLLM 0.24.0",
        "server_max_len": 32768, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 1, "budget_min": 90,
        "note": "single-game deep study, interrupted",
    },
    "20260713_010244_rung1-spec-vrfai-v025": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "rung 1: vrfai quant hits a pathological kernel path on vLLM 0.25; spec decode amplifies it",
    },
    "20260713_033303_rung1b-nospec-vrfai-v025": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "rung 1b: isolates spec decode -- still 3.4x slower than vLLM 0.19 on this quant",
    },
    "20260714_150500_v12-corrected-grafts": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts: shortcircuit + efficiency + retry_guard)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "faithful v12 rerun (Kaggle 1.28 recipe) with engine pinned to competition wheels (arc_agi 0.9.8/arcengine 0.9.3) and teardown parity",
    },
    "20260714_151100_v12-fullframe-peraction": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 + per-action full-frame animation (last_animation)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.19.0 (Tufa wheelhouse)",
        "server_max_len": 65536, "spec_decode": "off",
        "weights": "vrfai FP8 (35.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "v12-corrected plus last_animation: one entry per INDIVIDUAL action of the latest action(...) call, each with every engine frame that single action produced (16-entry cap)",
    },
    "20260715_104400_v12-glm46v": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0 (glm45 parsers)",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "GLM-4.6V AWQ 4-bit (57 GB)", "concurrency": 28, "budget_min": 132,
        "note": "the perception bet (106B-A12B vision MoE, WebVoyager 81): 0.000 -- SOTA visual grounding did not convert to a single level. Several vLLM boot attempts before serving (AWQ MoE)",
    },
    "20260715_113500_v12-gemma4-31b": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (forced via enable_thinking)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "Gemma-4-31B-IT QAT w4a16 (16 GB)", "concurrency": 28, "budget_min": 132,
        "note": "the one dense rival with a real math-reasoning claim (AIME 89.2): 0.156 -- benchmark math does not transfer to interactive grid play",
    },
    "20260715_104800_v12-thinkingcap-27b": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "ThinkingCap-Qwen3.6-27B-FP8 (30.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "brevity-RL fine-tune (-46% thinking tokens): saved thinking did NOT convert to actions -- 1,710 actions vs baseline's 3,073, 6 levels vs 16. Shallower reasoning cost exploration depth",
    },
    "20260714_152900_v12-qwen36-35b-a3b": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "thtennant v12 (taaf_grafts)",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "Qwen3.6-35B-A3B-FP8 (37.5 GB)", "concurrency": 28, "budget_min": 132,
        "note": "model swap experiment: 35B-A3B MoE (3B active) in the v12 harness -- 3,230 actions, zero levels on all 25 games; the 27B dense remains the harness's brain",
    },
    "20260713_042338_rung1c-spec-official-v025": {
        "hardware": "RTX PRO 6000 (GCP spot)",
        "agent_code": "Tufa upstream, pristine",
        "memory": "scientist note (optional prose)",
        "render": "plain 4x (256px)",
        "yield_s": 60, "thinking": "on (uncapped)",
        "agent_ctx": 32768, "server": "vLLM 0.25.0",
        "server_max_len": 65536, "spec_decode": "ngram",
        "weights": "official Qwen FP8 (30.9 GB)", "concurrency": 28, "budget_min": 132,
        "note": "rung 1c: modern serving validated -- statistically tied with tufa-exact",
    },
}

runs = []
for bench_path in sorted(glob.glob("logs/*/benchmark.json")):
    run = os.path.basename(os.path.dirname(bench_path))
    try:
        bench = json.load(open(bench_path))
    except Exception:
        continue
    # Single-game robustness ("signal") runs -- one game x N passes -- belong on the
    # separate Signal-runs tab (see export_signal_runs.py), not the 25-game scoreboard.
    if (bench.get("n_passes") or 1) > 1:
        continue
    games = bench.get("game_runs", [])
    n = len(games) or 1
    per_game = [
        {
            "id": g.get("game_id", "?"),
            "score": round(g.get("final_score") or 0, 3),
            "levels": g.get("levels_completed") or 0,
            "levels_total": g.get("number_of_levels") or 0,
            "actions": sum(g.get("actions_per_level") or []),
        }
        for g in games
    ]
    runs.append({
        "run": run,
        "games": len(games),
        "avg_score": round(sum(g["score"] for g in per_game) / n, 3),
        "levels": sum(g["levels"] for g in per_game),
        "actions": sum(g["actions"] for g in per_game),
        "tokens": sum(
            sum(h.get("generated_tokens") or 0 for h in (g.get("history") or []))
            + (g.get("final_generated_tokens") or 0)
            for g in games
        ),
        "per_game": sorted(per_game, key=lambda g: g["id"]),
        "harness": HARNESS.get(run, {}),
        "prompts": extract_prompts(os.path.dirname(bench_path)),
    })

runs.sort(key=lambda r: -r["avg_score"])
payload = {"baseline": BASELINE, "biases": BIASES, "runs": runs}
os.makedirs("docs/data", exist_ok=True)
json.dump(payload, open("docs/data/runs-index.json", "w"), indent=1)
print(f"wrote {len(runs)} runs; baseline={BASELINE}")
