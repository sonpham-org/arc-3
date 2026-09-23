#!/usr/bin/env python3
"""
Author: Claude Opus 5 (Bubba subagent, label no-score-pressure-wide)
Date: 21-September-2026
PURPOSE: Compare the stripped and control arms of the no-score-pressure wide experiment
game-by-game. Produces the behavioural read the arm was run for -- does the model act sooner,
does it experiment, does it stop chasing or avoiding on-screen bars -- from the harness's own
artifacts only.

Per-game outcome (levels, score, actions, turns, tool validity, reasoning length) is NOT
recomputed here: it is delegated to arc3-round4/eval/collect_results.py, which already defines
those metrics and fixed their denominators. This script adds only what that one does not have:

  turns_to_first_action -- analysis_step of the first turn the harness recorded as actually
                           executing an environment step. "Does it act sooner."
  probe_turns           -- turns that called the tool but executed no action. "Does it
                           deliberate or does it try things."
  bar_talk              -- [THINKING] blocks mentioning a timer / progress bar / HUD / counter,
                           and separately those mentioning action efficiency or conserving
                           moves. "Does it stop chasing or avoiding bars."

Counting rule for bar_talk: one hit per turn maximum, so a single verbose turn cannot swamp
the count, and it is reported as a share of answered turns so arms with different turn counts
stay comparable.

SRP/DRY check: Pass -- reuses collect_results.collect for every metric it already owns and
defines no scoring of its own. Reads only run-dir artifacts the harness wrote.
"""
from __future__ import annotations
import importlib.util, json, os, re, sys

GAMES = ["ar25-0c556536","bp35-0a0ad940","cd82-fb555c5d","cn04-2fe56bfb","dc22-fdcac232",
         "ft09-0d8bbf25","g50t-5849a774","ka59-38d34dbb","lf52-271a04aa","lp85-305b61c3",
         "ls20-9607627b","m0r0-492f87ba","r11l-495a7899","re86-8af5384d","s5i5-18d95033",
         "sb26-7fbdac44","sc25-635fd71a","sk48-d8078629","sp80-589a99af","su15-1944f8ab",
         "tn36-ef4dde99","tr87-cd924810","tu93-0768757b","vc33-5430563c","wa30-ee6fef47"]

COLLECT = os.environ.get("ARC3_COLLECT_RESULTS",
                         "/home/son/arc3-round4/eval/collect_results.py")

BAR_RE  = re.compile(r"timer|progress bar|remaining[- ]step|HUD|counter|gauge|edge bar|status bar", re.I)
EFF_RE  = re.compile(r"efficien|as few (in-game )?actions|conserve|waste(d)? (an )?action|action budget|minimi[sz]e .{0,20}action", re.I)
TURN_RE = re.compile(r"^--- analysis_step=(\d+) \| action=(\d+) \|", re.M)
# A real call to the environment: `action(`, not `last_action_result`, `valid_actions`,
# `_action`, or the word inside prose.
CALL_RE = re.compile(r"(?<![\w.])action\s*\(")


def _load_collect():
    spec = importlib.util.spec_from_file_location("collect_results", COLLECT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.collect


def _tool_code(block):
    """Pull each tool call's `code` argument out of the transcript's raw_tool_calls dump.

    The dump is pretty-printed JSON following a `raw_tool_calls:` line. It is emitted for
    natively parsed and markup-recovered calls alike, which is what makes it the stable
    source. Returns [] if the block has none or the JSON will not parse -- callers fall back.
    """
    m = re.search(r"^raw_tool_calls:\n(\[.*?\n\])\n", block, re.S | re.M)
    if not m:
        return []
    try:
        calls = json.loads(m.group(1))
    except Exception:
        return []
    out = []
    for c in calls:
        args = (c.get("function") or {}).get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                out.append(args); continue
        if isinstance(args, dict) and isinstance(args.get("code"), str):
            out.append(args["code"])
    return out


def behaviour(run_dir, game):
    """Read one game's transcript for the behavioural signals collect_results does not carry."""
    tr = os.path.join(run_dir, "transcripts", f"{game}_p0.txt")
    if not os.path.exists(tr):
        return {"missing": True}
    raw = open(tr, errors="replace").read()
    marks = [(m.start(), int(m.group(1))) for m in TURN_RE.finditer(raw)]
    blocks = []
    for i, (pos, step) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(raw)
        blocks.append((step, raw[pos:end]))

    first_action_turn, probe_turns, bar, eff, answered = None, 0, 0, 0, 0
    for step, b in blocks:
        if "tool_call_count:" not in b:
            continue                      # turn still in flight or errored; not answered
        answered += 1
        # Look only inside the code the model actually emitted. Searching the whole block
        # would match the system prompt's own `action(...)` documentation and the tool
        # result text, which is how a first cut of this script scored every turn as acting.
        #
        # Read it from the harness's own `raw_tool_calls` dump first. That block is written
        # whether the call was parsed natively by vLLM or recovered from markup by the
        # harness fallback, so this survives a tool-call-parser change. The
        # `<parameter=code>` form is only a fallback for the markup path, where the XML is
        # echoed into the transcript; under native parsing it may not be echoed at all, and
        # relying on it alone would silently report zero actions.
        code = " ".join(_tool_code(b)) or "\n".join(
            re.findall(r"<parameter=code>\n(.*?)</parameter>", b, re.S))
        acted = bool(CALL_RE.search(code))
        if acted and first_action_turn is None:
            first_action_turn = step
        if not acted:
            probe_turns += 1
        think = "\n".join(re.findall(r"\[THINKING\]\n(.*?)(?=\n\[|\Z)", b, re.S))
        if BAR_RE.search(think):
            bar += 1                      # one hit per turn, not per mention
        if EFF_RE.search(think):
            eff += 1
    return {"turns_to_first_action": first_action_turn, "probe_turns": probe_turns,
            "answered_turns": answered, "bar_talk_turns": bar, "efficiency_talk_turns": eff}


def arm(run_dir):
    res = _load_collect()(run_dir, GAMES)
    for g in GAMES:
        res["games"][g].update(behaviour(run_dir, g))
    return res


def cell(v, fmt="{}", dash="-"):
    return dash if v is None else fmt.format(v)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: analyze_nosp_arms.py <stripped_run_dir> <control_run_dir> [out.json]")
    arms = {"stripped": arm(sys.argv[1]), "control": arm(sys.argv[2])}
    if len(sys.argv) > 3:
        json.dump(arms, open(sys.argv[3], "w"), indent=2)

    print(f"{'game':6s} | {'STRIPPED lv/act/turn/1st/bar':30s} | {'CONTROL lv/act/turn/1st/bar':30s}")
    print("-" * 74)
    for g in GAMES:
        row = []
        for a in ("stripped", "control"):
            r = arms[a]["games"][g]
            if r.get("missing"):
                row.append("MISSING".ljust(30)); continue
            row.append(f"{r.get('levels_completed')}/{r.get('total_levels')} "
                       f"a={r.get('actions')} t={r.get('turns')} "
                       f"1st={cell(r.get('turns_to_first_action'))} "
                       f"bar={r.get('bar_talk_turns')} eff={r.get('efficiency_talk_turns')}".ljust(30))
        print(f"{g[:4]:6s} | {row[0]} | {row[1]}")

    print("-" * 74)
    for a in ("stripped", "control"):
        gs = [r for r in arms[a]["games"].values() if not r.get("missing")]
        lv = sum(r.get("levels_completed") or 0 for r in gs)
        cleared = sum(1 for r in gs if (r.get("levels_completed") or 0) > 0)
        acts = sum(r.get("actions") or 0 for r in gs)
        ans = sum(r.get("answered_turns") or 0 for r in gs)
        bar = sum(r.get("bar_talk_turns") or 0 for r in gs)
        eff = sum(r.get("efficiency_talk_turns") or 0 for r in gs)
        firsts = [r["turns_to_first_action"] for r in gs if r.get("turns_to_first_action")]
        never = sum(1 for r in gs if not r.get("turns_to_first_action"))
        print(f"{a:9s} games={len(gs)} cleared>=1={cleared} levels={lv} actions={acts} "
              f"answered_turns={ans} never_acted={never} "
              f"median_first_action_turn={sorted(firsts)[len(firsts)//2] if firsts else '-'} "
              f"bar_talk={bar} ({100*bar/ans if ans else 0:.0f}% of turns) "
              f"eff_talk={eff} ({100*eff/ans if ans else 0:.0f}%)")
