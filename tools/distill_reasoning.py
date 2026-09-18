#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: Distill the ARC-3 replay harvest down to ONLY the steps that carry agent
reasoning text. Reads the compact per-run .jsonl files written by tools/harvest_replays.py
(one record per step, most with reasoning_present=false) and emits a reasoning-only
corpus: one JSONL record per reasoning-bearing step, plus a per-run index and a
human-readable text dump. Boss directive 17-Sep-2026: the non-reasoning steps are junk,
keep the text.
SRP/DRY check: Pass - harvest_replays.py fetches/strips; this file only filters and
reshapes what is already on disk. No network, no re-download, safe to re-run.
"""
import json, os, sys, glob, re

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "datasets", "vendor-coherence")
SRC = os.path.join(ROOT, "replays")
OUT = os.path.join(ROOT, "reasoning")

# harvest stores the text under one of these keys depending on source shape
TEXT_KEYS = ("out", "reasoning", "text", "summary")

# Most agents echo the action they chose into the same field ("ACTION6 44 21").
# That is not reasoning - it is the move, already captured in act_id. Boss directive
# 17-Sep-2026: keep the reasoning, drop the junk.
ACTION_ECHO = re.compile(r"^(RESET|ACTION\d+)(\s+-?\d+)*$", re.I)

def strip_echo(txt):
    """Drop pure action-echo lines (usually a trailing one) and blank filler."""
    kept = [ln for ln in txt.splitlines() if ln.strip() and not ACTION_ECHO.match(ln.strip())]
    return "\n".join(kept).strip()

def text_of(rec):
    """Return (text, source_field) picking the richest NON-echo value.

    Records carry both `out` and `summary`; on ~2.3k steps `out` is a bare action echo
    while `summary` holds the real reasoning. Taking the first non-empty key would drop
    those. Take the longest surviving candidate instead, and report which field won.
    """
    best, best_key = "", None
    for k in TEXT_KEYS:
        v = rec.get(k)
        if isinstance(v, list):
            v = "\n".join(x for x in v if isinstance(x, str))
        if not isinstance(v, str) or not v.strip():
            continue
        cleaned = strip_echo(v)
        if len(cleaned) > len(best):
            best, best_key = cleaned, k
    return (best, best_key) if best else (None, None)


def main():
    os.makedirs(OUT, exist_ok=True)
    index = []
    corpus_path = os.path.join(OUT, "corpus.jsonl")
    n_files = n_steps = n_kept = 0
    with open(corpus_path, "w") as corpus:
        for path in sorted(glob.glob(os.path.join(SRC, "*", "*.jsonl"))):
            if path.endswith(".reasoning.jsonl"):
                continue
            vendor = os.path.basename(os.path.dirname(path))
            base = os.path.basename(path)[:-len(".jsonl")]
            guid, _, game = base.partition("__")
            kept, total, chars = [], 0, 0
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    total += 1
                    txt, src = text_of(rec)
                    if txt is None:
                        continue
                    chars += len(txt)
                    kept.append({
                        "vendor": vendor,
                        "guid": guid,
                        "game": game,
                        "step": rec.get("i"),
                        "ts": rec.get("ts"),
                        "act_id": rec.get("act_id"),
                        "state": rec.get("state"),
                        "levels_completed": rec.get("levels_completed"),
                        "fchanged": rec.get("fchanged"),
                        "src_field": src,
                        "text": txt,
                    })
            n_files += 1
            n_steps += total
            n_kept += len(kept)
            if not kept:
                index.append({"vendor": vendor, "guid": guid, "game": game,
                              "steps": total, "reasoning_steps": 0, "chars": 0})
                continue
            vdir = os.path.join(OUT, vendor)
            os.makedirs(vdir, exist_ok=True)
            with open(os.path.join(vdir, base + ".reasoning.jsonl"), "w") as out:
                for rec in kept:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    corpus.write(json.dumps(rec, ensure_ascii=False) + "\n")
            with open(os.path.join(vdir, base + ".reasoning.txt"), "w") as out:
                out.write(f"# {vendor} | {game} | {guid}\n")
                out.write(f"# {len(kept)} of {total} steps carry reasoning text\n\n")
                for rec in kept:
                    out.write(f"----- step {rec['step']}/{total-1}  act={rec['act_id']}  "
                              f"lvl={rec['levels_completed']}  changed={rec['fchanged']}\n")
                    out.write(rec["text"].rstrip() + "\n\n")
            index.append({"vendor": vendor, "guid": guid, "game": game,
                          "steps": total, "reasoning_steps": len(kept), "chars": chars})

    index.sort(key=lambda r: (r["vendor"], -r["reasoning_steps"]))
    with open(os.path.join(OUT, "index.json"), "w") as fh:
        json.dump(index, fh, indent=2)

    by_vendor = {}
    for r in index:
        v = by_vendor.setdefault(r["vendor"], {"runs": 0, "steps": 0, "reasoning_steps": 0,
                                               "chars": 0, "runs_with_text": 0})
        v["runs"] += 1
        v["steps"] += r["steps"]
        v["reasoning_steps"] += r["reasoning_steps"]
        v["chars"] += r["chars"]
        v["runs_with_text"] += 1 if r["reasoning_steps"] else 0

    lines = ["vendor                       runs  w/text   steps  reasoning   pct      MB"]
    for v, s in sorted(by_vendor.items()):
        pct = (100.0 * s["reasoning_steps"] / s["steps"]) if s["steps"] else 0.0
        lines.append(f"{v:28s} {s['runs']:4d} {s['runs_with_text']:7d} {s['steps']:7d} "
                     f"{s['reasoning_steps']:10d} {pct:5.1f}% {s['chars']/1e6:7.1f}")
    summary = "\n".join(lines)
    with open(os.path.join(OUT, "SUMMARY.txt"), "w") as fh:
        fh.write(summary + "\n\n"
                 f"files={n_files} steps={n_steps} reasoning_steps={n_kept} "
                 f"({100.0*n_kept/n_steps if n_steps else 0:.1f}%)\n")
    print(summary)
    print(f"\nfiles={n_files} steps={n_steps} reasoning_steps={n_kept} "
          f"({100.0*n_kept/n_steps if n_steps else 0:.1f}%)")
    print(f"corpus: {corpus_path}")

if __name__ == "__main__":
    main()
