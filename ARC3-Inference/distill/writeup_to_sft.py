#!/usr/bin/env python3
"""
Author: Claude Fable 5.1
Date: 19-September-2026
PURPOSE: Round-4 arm W builder. Takes round 3's SFT corpus (recordings_to_sft.py output,
89 records) and appends the Boss's FULL write-up for each record's game to that record's
system prompt: simpleExplanation, mechanicsExplanation, every mechanicsBreakdown rule
(grouped by introducedOnLevel), and every playerObservation with all its fields. Nothing
else in the record changes, so arm W differs from round 3 by exactly one thing: what the
model conditions on. Supervised tokens are unchanged.

This is the arm docs/plans/2026-09-19-arc3-lora-round4-spec.md §3.1 chose NOT to build
(it excluded rules as "answer key"). The Boss asked for it on 19-Sep: rules of a training
game in that game's own training context leak nothing into the fenced eval games. The
rationale-only arm R (spec §6) is a different, narrower builder; this one is deliberately
the maximal version so the two bracket the question.

Source of truth is the per-game `.ts` in arc-explainer/shared/arc3Games/, parsed by bracket
matching (they are TypeScript, not JSON). Left out of the rendered block on purpose:
`informalName`, `officialTitle` (game names stay opaque -- the record already carries the
code), `source` file:line citations (the agent cannot read them), and image fields.

Fence: `--fence` is REQUIRED with no default. Any record on a fenced game, or any write-up
for a fenced game, is a hard error unless --allow-fence-drop is passed. Round 3's corpus has
zero fenced records, so this should drop nothing.

Usage:
  python distill/writeup_to_sft.py \
    --corpus  /home/son/arc3-round3/data/sft_human_windowed.jsonl \
    --arc3-games ~/GitHub/arc-explainer/shared/arc3Games \
    --fence ar25,re86,sb26,su15,tr87,tu93,vc33 \
    --out /home/son/arc3-round4/data/sft_writeup.jsonl \
    --manifest /home/son/arc3-round4/data/sft_writeup_manifest.json
SRP/DRY check: Pass -- recordings_to_sft.py stays the untouched round-3 artifact; this only
annotates its output. tools/render_rulebooks.py renders the fetched endpoint JSON (527
per-level rules, a different schema) for the oracle arm and is not reused here because the
.ts files are the current source and carry prose the endpoint does not.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_STR = r"(?:'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"|`((?:[^`\\]|\\.)*)`)"


def _unescape(s: str) -> str:
    return s.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def _grp(m: re.Match) -> str:
    return next(g for g in m.groups() if g is not None)


def _top_field(src: str, name: str) -> str:
    m = re.search(rf"\n  {name}:\s*{_STR}", src)
    return _unescape(_grp(m)) if m else ""


def _bracket_block(src: str, name: str) -> str:
    """The `name: [ ... ]` array literal, by bracket matching. Empty string if absent."""
    i = src.find(f"{name}: [")
    if i < 0:
        return ""
    j = i + len(name) + 2
    depth = 0
    in_str = False
    esc = False
    q = ""
    while j < len(src):
        c = src[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == q:
                in_str = False
        elif c in "'\"`":
            in_str = True
            q = c
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return src[i : j + 1]
        j += 1
    raise ValueError(f"unbalanced brackets in {name}")


def _objects(block: str) -> list[str]:
    """Top-level `{ ... }` literals inside an array block."""
    out: list[str] = []
    depth = 0
    in_str = False
    esc = False
    q = ""
    start = -1
    for k, c in enumerate(block):
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == q:
                in_str = False
            continue
        if c in "'\"`":
            in_str = True
            q = c
        elif c == "{":
            if depth == 0:
                start = k
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                out.append(block[start : k + 1])
                start = -1
    return out


def _obj_field(obj: str, name: str) -> str:
    m = re.search(rf"\b{name}:\s*{_STR}", obj)
    if m:
        return _unescape(_grp(m))
    m = re.search(rf"\b{name}:\s*(\d+)", obj)
    return m.group(1) if m else ""


def render_writeup(src: str) -> tuple[str, dict]:
    """The Boss's full write-up as plain prose, plus counts for the manifest."""
    simple = _top_field(src, "simpleExplanation")
    mech = _top_field(src, "mechanicsExplanation")
    rules = _objects(_bracket_block(src, "mechanicsBreakdown"))
    notes = _objects(_bracket_block(src, "playerObservations"))
    if not simple or not mech or not rules:
        raise ValueError("write-up missing simpleExplanation, mechanicsExplanation or mechanicsBreakdown")

    parts: list[str] = []
    parts.append("What a human player who has cleared this game wrote about it.")
    parts.append("In short:\n" + simple)
    parts.append("How the game works:\n" + mech)

    by_level: dict[int, list[str]] = {}
    for r in rules:
        text = _obj_field(r, "text").strip()
        if not text:
            raise ValueError("mechanicsBreakdown entry without text")
        lvl = int(_obj_field(r, "introducedOnLevel") or 1)
        if text[-1] not in ".!?":
            text += "."
        by_level.setdefault(lvl, []).append(text)
    lines = ["Rules, by the level each one first matters on:"]
    for lvl in sorted(by_level):
        lines.append(f"Level {lvl}:")
        lines.extend(f"- {t}" for t in by_level[lvl])
    parts.append("\n".join(lines))

    if notes:
        lines = ["What he noticed while playing:"]
        for n in notes:
            lvl = _obj_field(n, "level")
            bits = []
            saw, did, exp, hap, code = (_obj_field(n, k) for k in ("saw", "did", "expected", "happened", "inCode"))
            if saw:
                bits.append(f"He saw: {saw}")
            if did:
                bits.append(f"He did: {did}")
            if exp:
                bits.append(f"He expected: {exp}")
            if hap:
                bits.append(f"What happened: {hap}")
            if code:
                bits.append(f"In the game's code: {code}")
            prefix = f"(level {lvl}) " if lvl else ""
            lines.append(f"- {prefix}" + " ".join(bits))
        parts.append("\n".join(lines))

    parts.append("End of the human write-up.")
    text = "\n\n".join(parts)
    return text, {"rules": len(rules), "notes": len(notes), "chars": len(text)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--corpus", required=True, type=Path)
    p.add_argument("--arc3-games", required=True, type=Path)
    p.add_argument("--fence", required=True, help="Comma-separated bare game codes. Required, no default.")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--allow-fence-drop", action="store_true")
    p.add_argument("--stdout-game", help="print one game's rendered block and exit")
    a = p.parse_args()

    fence = frozenset(c.strip().lower() for c in a.fence.split(",") if c.strip())
    if not fence:
        sys.exit("--fence is empty")

    if a.stdout_game:
        text, counts = render_writeup((a.arc3_games / f"{a.stdout_game}.ts").read_text(encoding="utf-8"))
        print(text)
        print(json.dumps(counts), file=sys.stderr)
        return 0

    rendered: dict[str, str] = {}
    per_game: dict[str, dict] = {}
    n_in = n_out = fenced_records = 0
    with a.corpus.open(encoding="utf-8") as fin, a.out.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            n_in += 1
            rec = json.loads(line)
            code = str(rec["game_id"]).split("-", 1)[0].lower()
            if code in fence:
                fenced_records += 1
                continue
            if code not in rendered:
                path = a.arc3_games / f"{code}.ts"
                if not path.exists():
                    sys.exit(f"no write-up for {code}: {path}")
                text, counts = render_writeup(path.read_text(encoding="utf-8"))
                rendered[code] = text
                per_game[code] = {**counts, "records": 0}
            msgs = rec["messages"]
            if msgs[0].get("role") != "system" or not isinstance(msgs[0].get("content"), str):
                sys.exit(f"record {rec['id']} has no string system prompt at messages[0]")
            msgs[0]["content"] = msgs[0]["content"].rstrip("\n") + "\n\n" + rendered[code]
            rec["writeup"] = {
                "source": f"arc-explainer/shared/arc3Games/{code}.ts",
                "chars": per_game[code]["chars"],
                "rules": per_game[code]["rules"],
                "notes": per_game[code]["notes"],
            }
            per_game[code]["records"] += 1
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_out += 1

    manifest = {
        "corpus": str(a.corpus),
        "out": str(a.out),
        "fence": sorted(fence),
        "records_in": n_in,
        "records_out": n_out,
        "fenced_records_dropped": fenced_records,
        "games": per_game,
        "writeup_chars_total": sum(g["chars"] * g["records"] for g in per_game.values()),
    }
    a.manifest.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "games"}, indent=1))
    for code, g in sorted(per_game.items()):
        print(f"  {code}: {g['records']} records, {g['rules']} rules, {g['notes']} notes, {g['chars']} chars")
    if fenced_records and not a.allow_fence_drop:
        sys.exit(f"FENCE HIT: {fenced_records} records on fenced games were dropped; pass --allow-fence-drop to accept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
