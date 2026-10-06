#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Render the exact requests a Spark runner job would post to the model, with no model: sample.main() runs
  the real job (the harness, the start, the prompt profile, the mode slots) while requests.post is answered by a
  scripted stand-in. Every request body is kept. Two uses:
    preview  the first request of a job (the page's "Preview request" button, server.py /api/preview-request):
             the script is empty, so the first request is captured and the sample stops before anything is sent.
    tour     the prompt dedup check (docs/plans/2026-10-06-prompt-dedup.md): a script that walks the turn kinds a
             real game meets, so the check covers more than a first turn:
               1  inspect-only snippet reporting 3000 generated tokens -> the turn yields (token budget)
               2  resumed turn: the first action of the level's recorded winning line
               3  next turn: a reply with no tool call -> the harness's retry nudge
               4  nudge: the rest of the level's winning line -> the level is cleared
               5  level start: one action repeated in a long batch, to run out a step budget -> game over
               6  the turn after the game over is captured, then the sample stops
             What each request turned out to be is recorded (yield resume, nudge, level start, game over), since a
             start that is not at the level's start, or a game without a step budget, will not reach every kind.
  The spec is a normal job spec (server.py builds it; build_spec here builds the same for the command line), so a
  render goes through exactly the code a job runs. Checkpoint capture is off; nothing is written outside <out>.
  Usage: render_requests.py <spec.json> <out dir> [preview|tour]   prints a JSON summary; bodies in <out>/requests/
         render_requests.py --spec <game> <level> <variant> <context> <profile> <out dir> [preview|tour] [slots.json]
         render_requests.py --check-all <out dir> <slots.json> [profile ...]   the dedup check: every case in CASES
             toured in its own process, every captured request run through dupcheck; <out>/dedup-checks.json
         render_requests.py --page-data <work dir> <out.json>   the Mode explorer's static/data/prompt-profiles.json:
             each profile's system prompt per wording and tool schema, and dedup example turn messages from one tour
SRP/DRY check: Pass - no prompt or play logic here; sample.main plays, prompt_profiles shapes text, dupcheck checks.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sample  # noqa: E402


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict):
        self._payload = payload
        self.text = json.dumps(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def reply(code: str | None, tokens: int, text: str = "") -> dict:
    msg = {"role": "assistant", "content": text}
    if code is not None:
        msg["tool_calls"] = [{"id": f"call_{abs(hash(code)) % 10**8}", "type": "function",
                              "function": {"name": "python", "arguments": json.dumps({"code": code})}}]
    return {"choices": [{"message": msg, "finish_reason": "tool_calls" if code else "stop"}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": tokens, "total_tokens": 1000 + tokens}}


def model_actions(actions: list[dict]) -> list:
    """Engine actions ({name, data}) as the model writes them for action(actions)."""
    from inference.agent.action_names import to_model_action
    out = []
    for a in actions:
        if a.get("automatic") or a["name"] == "RESET":
            continue
        name = to_model_action(a["name"]) or a["name"]
        if a["name"] == "ACTION6":
            out.append({"action": "MOUSE", "row": int(a["data"]["y"]), "col": int(a["data"]["x"])})
        else:
            out.append(name)
    return out


def tour_script(game: str, level: int):
    """Replies for the tour, given the level's winning line (replays.solution_levels)."""
    import replays
    sol = (replays.solution_levels(game) or [])
    line = sol[level - 1] if 0 < level <= len(sol) else []
    nxt = sol[level] if level < len(sol) else line
    state = {"n": 0}

    def next_reply(body: dict) -> dict | None:
        n = state["n"]
        state["n"] += 1
        acts = model_actions(line)
        filler = (model_actions(nxt)[:1] or acts[:1] or ["UP"]) * 400
        if n == 0:
            return reply("print(len(current_frame.segmentation['nodes']))", 3000)
        if n == 1:
            return reply(f"action({acts[:1]!r})", 50)
        if n == 2:
            return reply(None, 50, "Thinking about the board.")
        if n == 3:
            return reply(f"action({acts[1:]!r})", 50)
        if n == 4:
            return reply(f"action({filler!r})", 50)
        return None
    return next_reply


def kinds_of(body: dict) -> list[str]:
    """What a captured request's last message is (by the harness's own wording, either profile)."""
    msgs = body.get("messages") or []
    last = msgs[-1] if msgs else {}
    c = last.get("content")
    text = c if isinstance(c, str) else " ".join(p.get("text", "") for p in c or [] if isinstance(p, dict))
    k = []
    if last.get("role") == "tool":
        k.append("tool_result")
    if "Nothing has been executed since the turn opener" in text or "You yielded control" in text:
        k.append("yield_resume")
    if "You have not acted yet" in text or "did not call a tool" in text:
        k.append("retry_nudge")
    if "GAME OVER" in text:
        k.append("game_over")
    if "cleared the previous level" in text or "completed the previous level" in text:
        k.append("level_start")
    if "Instructions for this turn" in text:
        k.append("mode_block")
    return k or ["turn"]


def render(spec: dict, out: Path, script: str = "preview") -> dict:
    if out.exists():
        shutil.rmtree(out)
    (out / "requests").mkdir(parents=True)
    spec = {**spec, "capture": False}
    (out / "spec.json").write_text(json.dumps(spec, indent=1))
    bodies: list[dict] = []
    nexts = {"fn": None}

    def post(url, *a, **kw):
        if not str(url).endswith("/chat/completions"):
            raise RuntimeError(f"unexpected request to {url}")
        body = kw.get("json")
        bodies.append(json.loads(json.dumps(body)))
        with gzip.open(out / "requests" / f"{len(bodies):02d}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(body, fh)
        if script == "tour" and nexts["fn"] is None:
            nexts["fn"] = tour_script(spec["game"], int(spec["stuck_level"]))
        r = nexts["fn"](body) if nexts["fn"] else None
        if r is None:
            raise sample.DryStop()
        return FakeResponse(r)
    import requests
    requests.post = post
    try:
        sample.main(out, 0)
    except sample.DryStop:
        pass
    res_path = out / "samples" / "0" / "error.txt"
    error = res_path.read_text()[-600:] if res_path.exists() else None
    summary = {"game": spec["game"], "level": spec["stuck_level"], "variant": spec["variant"],
               "context": spec.get("context", "carried"), "profile": spec.get("prompt_profile") or "dedup",
               "start": spec["start"]["kind"], "requests": len(bodies),
               "kinds": [kinds_of(b) for b in bodies], "error": error}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def build_spec(game: str, level: int, variant: str, context: str, profile: str, slots: list[dict] | None = None) -> dict:
    """The spec server.play would write for this game and level (start resolved by server.resolve_start)."""
    import server
    start, start_kind, game_id, _ = server.resolve_start(game, level, variant, context)
    stock = {"key": "stock", "mode": "stock", "name": "Stock", "base": "turn", "instructions": "",
             "settings": dict(sample.checkpoints.STOCK_SETTINGS)}
    scheme = [{**s, "key": f"{i}:{s['mode']}"} for i, s in enumerate(slots or [])]
    return {"kind": "play", "game": game, "game_id": game_id, "stuck_level": level, "variant": variant,
            "scheme": scheme, "stock": stock, "start": start, "context": context, "prompt_profile": profile,
            "caps": {"max_actions": 1000, "max_turns": 12, "max_minutes": 40, "levels_to_play": 9},
            "model": {"base_url": "http://127.0.0.1:9/v1", "model_id": "render"}}


# The dedup check's cases: carried starts of every kind (exact checkpoint, rebuilt snapshot with its conversation
# rebuilt from the site's transcripts, fresh game) and No-context starts, both wordings, several games and levels.
CASES = [
    ("bp35", 2, "son", "carried"), ("cd82", 3, "son", "carried"), ("ft09", 3, "son", "carried"),
    ("lf52", 3, "son", "carried"), ("ls20", 4, "son", "carried"), ("ka59", 3, "daniel", "carried"),
    ("sk48", 1, "son", "carried"), ("lf52", 3, "son", "none"), ("lf52", 3, "daniel", "none"),
    ("ls20", 2, "son", "none"), ("ft09", 1, "daniel", "none"), ("cd82", 4, "son", "none"), ("wa30", 2, "son", "none"),
]


def check_all(out: Path, slots_file: Path, profiles: list[str]) -> dict:
    import subprocess
    import dupcheck
    rows = []
    for prof in profiles:
        for g, lv, var, ctx in CASES:
            d = out / f"{g}-{lv}-{var}-{ctx}-{prof}"
            r = subprocess.run([sys.executable, __file__, "--spec", g, str(lv), var, ctx, prof, str(d), "tour",
                                str(slots_file)], capture_output=True, text=True, timeout=900)
            try:
                summ = json.loads(r.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError):
                summ = {"error": (r.stderr or r.stdout)[-400:]}
            checks = []
            for f in sorted((d / "requests").glob("*.json.gz")) if (d / "requests").is_dir() else []:
                rep = dupcheck.check(dupcheck.load(f))
                checks.append({"request": f.name, "messages": rep["messages"], "ok": rep["ok"],
                               "fail_counts": rep["fail_counts"],
                               "failures": {k: rep[k][:6] for k in rep["fail_counts"] if rep[k]}})
            row = {"case": d.name, "profile": prof, "summary": summ, "requests_checked": len(checks),
                   "ok": bool(checks) and all(c["ok"] for c in checks), "checks": checks}
            rows.append(row)
            print(d.name, summ.get("start"), summ.get("kinds"), "ok" if row["ok"] else
                  {k: sum(c["fail_counts"][k] for c in checks) for k in (checks[0]["fail_counts"] if checks else {})},
                  summ.get("error") or "", flush=True)
    result = {"cases": rows, "profiles": profiles}
    (out / "dedup-checks.json").write_text(json.dumps(result, indent=1))
    return result


def message_text(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    return "\n".join(p.get("text", "") if p.get("type") == "text" else "[image]" for p in c or [] if isinstance(p, dict))


def page_data(work: Path, out_file: Path) -> dict:
    """System prompts, tool schemas and example turn messages for the page, from real renders (no hand-typed text)."""
    import subprocess
    import prompt_profiles
    from datetime import datetime, timezone
    game, level = "lf52", 3
    data = {"meta": {"author": "Claude Opus 5.5 (Bubba)", "date": "06-October-2026",
                     "purpose": "What the Spark runner sends, per prompt profile, for the Mode explorer: the system "
                                "prompt of each wording, the tool schema, and (dedup) example turn messages. Rendered "
                                "by the runner's own harness with no model (tools/spark_runner/render_requests.py "
                                "--page-data); rebuild it when the harness, its flags or prompt_profiles.py change.",
                     "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "example": {"game": game, "level": level, "context": "none",
                                 "note": "Turn examples come from one scripted walk through Leapfrog (lf52) level 3 "
                                         "with no context: the values are real for that walk; every turn the harness "
                                         "fills in its own."},
                     "default_profile": prompt_profiles.DEFAULT_PROFILE,
                     "mode_header": prompt_profiles.MODE_HEADER},
            "profiles": {}}
    for prof in prompt_profiles.PROFILES:
        entry = {"system": {}, "tools": None, "turn_examples": {}}
        for var in ("son", "daniel"):
            d = work / f"{prof}-{var}"
            subprocess.run([sys.executable, __file__, "--spec", game, str(level), var, "none", prof, str(d),
                            "tour" if var == "son" else "preview"], check=True, capture_output=True, timeout=600)
            bodies = [json.load(gzip.open(f, "rt")) for f in sorted((d / "requests").glob("*.json.gz"))]
            entry["system"][var] = bodies[0]["messages"][0]["content"]
            entry["tools"] = bodies[0]["tools"]
            if var == "son":
                for b in bodies:
                    kinds = kinds_of(b)
                    key = ("game_over" if "game_over" in kinds else "level_start" if "level_start" in kinds else
                           "yield_resume" if "yield_resume" in kinds else "retry_nudge" if "retry_nudge" in kinds else
                           "tool_result" if "tool_result" in kinds else "turn")
                    if key == "turn" and len(b["messages"]) == 2:
                        key = "first_turn"
                    if key != "tool_result" and key not in entry["turn_examples"]:
                        # display copy: a 400-action trace line is cut for the page (the request had it whole)
                        entry["turn_examples"][key] = "\n".join(
                            ln if len(ln) <= 700 else f"{ln[:600]} … [{len(ln) - 600} more characters in the real message]"
                            for ln in message_text(b["messages"][-1]).split("\n"))
        data["profiles"][prof] = entry
    out_file.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return {k: list(v["turn_examples"]) for k, v in data["profiles"].items()}


if __name__ == "__main__":
    if sys.argv[1] == "--page-data":
        print(json.dumps(page_data(Path(sys.argv[2]), Path(sys.argv[3]))))
        sys.exit(0)
    if sys.argv[1] == "--check-all":
        res = check_all(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:] or ["dedup"])
        sys.exit(0 if all(r["ok"] for r in res["cases"] if r["profile"] == "dedup") else 1)
    if sys.argv[1] == "--spec":
        g, lv, var, ctx, prof, o = sys.argv[2:8]
        mode = sys.argv[8] if len(sys.argv) > 8 else "tour"
        slots = json.loads(Path(sys.argv[9]).read_text()) if len(sys.argv) > 9 else None
        sp = build_spec(g, int(lv), var, ctx, prof, slots)
        print(json.dumps(render(sp, Path(o), mode)))
    else:
        print(json.dumps(render(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]),
                                sys.argv[3] if len(sys.argv) > 3 else "preview")))
