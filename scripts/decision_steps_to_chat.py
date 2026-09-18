#!/usr/bin/env python3
"""
Author: Claude Opus 5 (Bubba)
Date: 16-September-2026
PURPOSE: Convert decision-step v0 records (datasets/decision-steps/v0/episodes/*.jsonl) into
chat-template messages for SFT. Input side = memory_in + last_action/last_result + optional
ascii; target side = decision.rationale, decision.memory_out, decision.action,
decision.expected_observation, emitted as one JSON assistant turn so the target is parseable
and scorable rather than free prose. Written for the a108 training-stack smoke test; this is
the data path under test, not a production trainer.
SRP/DRY check: Pass - only converter in scripts/; SCHEMA.md is the field contract and is not
restated here beyond the field paths actually read. NOT COMMITTED, review artifact.

NOTE on field paths (SCHEMA.md says so, the setup brief got it wrong):
  rationale / expected_observation / memory_out / action are nested under `decision`.
  memory_in is top-level and is an INPUT, not a target.
NOTE on v0 content: `ascii` is null in all 11 records, so there is currently no board
observation in-record - only frame_ref pointers. The prompt is structured memory only.
"""
import json, argparse, pathlib


def _fmt_action(a):
    if a is None:
        return "none (first decision of the episode)"
    return json.dumps(a, sort_keys=True)


def build_prompt(rec):
    m = rec["memory_in"]
    parts = [
        f"Game: {rec['game_id']}   Level: {rec['level']}",
        f"Segment boundary: {rec['segment']['boundary_reason']}",
        "",
        f"Goal: {m['goal']}",
        f"Current plan: {m['current_plan']}",
        f"Known mechanics: {json.dumps(m['known_mechanics'], indent=1) if m['known_mechanics'] else '(none yet)'}",
        f"Tested actions: {', '.join(m['tested_actions']) or '(none yet)'}",
        f"Hypotheses: {json.dumps(m['hypotheses'], indent=1) if m['hypotheses'] else '(none yet)'}",
        "",
        f"Last action: {_fmt_action(rec['last_action'])}",
        f"Last result: {_fmt_action(rec['last_result'])}",
    ]
    if rec.get("ascii"):
        parts += ["", "Board:", rec["ascii"]]
    parts += ["", "Decide the next action. Respond with a single JSON object."]
    return "\n".join(parts)


def build_target(rec):
    d = rec["decision"]
    return json.dumps(
        {
            "rationale": d["rationale"],
            "memory_out": d["memory_out"],
            "action": d["action"],
            "expected_observation": d["expected_observation"],
        },
        indent=1,
    )


SYSTEM = (
    "You are playing an ARC-3 interactive reasoning game. You see only your own structured "
    "memory and the result of your last action. Choose the next action. Your rationale must be "
    "falsifiable and your expected_observation must be something the next frame can refute."
)


def convert(rec):
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(rec)},
            {"role": "assistant", "content": build_target(rec)},
        ],
        "tier": rec["tier"],
        "game_id": rec["game_id"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tiers", default="gold",
                    help="comma-separated tiers to keep, or 'all'")
    a = ap.parse_args()

    keep = None if a.tiers == "all" else set(a.tiers.split(","))
    n = 0
    with open(a.out, "w") as out:
        for p in sorted(pathlib.Path(a.episodes_dir).glob("*.jsonl")):
            for line in p.read_text().splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if keep is not None and rec["tier"] not in keep:
                    continue
                out.write(json.dumps(convert(rec)) + "\n")
                n += 1
    print(f"wrote {n} records -> {a.out}")


if __name__ == "__main__":
    main()
