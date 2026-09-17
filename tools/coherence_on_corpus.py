#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (sub-agent for Bubba)
Date: 17-September-2026
PURPOSE: Coherence analysis of ARC-3 agent reasoning, computed ONLY over the distilled
reasoning corpus (datasets/vendor-coherence/reasoning/corpus.jsonl) produced by tools/distill_reasoning.py.
Boss directive 17-Sep-2026: action-echo steps are not reasoning and must not count in any
statistic, so this file never touches replays/*.jsonl directly.

"Coherence" here is defined as STEP-TO-STEP CONTINUITY OF PUBLISHED REASONING within a
single run, reported as four separable signals:
  (1) presence   - does the run publish reasoning text at all (per-run, not per-step)
  (2) density    - share of that run's steps carrying reasoning text
  (3) continuity - mean Jaccard overlap of content tokens between CONSECUTIVE reasoning
                   steps; high = the agent is carrying state forward, low = each step is
                   written from scratch
  (4) retention  - reasoning density in the final fifth of a run vs the first fifth;
                   <1.0 means the agent stops narrating as the run gets long
Also splits by src_field, because `out` (agent-published prose) and `summary` (provider
reasoning-summary leakage) are different phenomena and must not be pooled.

Dedupe: the `openai-gpt-5-6` vendor dir is the exact union of its luna/sol/terra variant
dirs (verified by basename comm, 374 == 374, zero either-side difference), so umbrella
records are dropped to avoid double-counting.
SRP/DRY check: Pass - distill_reasoning.py filters; analyze_coherence.py aggregates the
RAW replays on usage/rtok signals; this file is the reasoning-text-only counterpart.
"""
import json, os, re, sys, statistics, collections

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "datasets", "vendor-coherence")
CORPUS = os.path.join(ROOT, "reasoning", "corpus.jsonl")
INDEX = os.path.join(ROOT, "reasoning", "index.json")
OUT = os.path.join(ROOT, "reasoning", "coherence-corpus.json")

UMBRELLA = "openai-gpt-5-6"   # exact union of -luna/-sol/-terra
WORD = re.compile(r"[a-z]{3,}")
STOP = set("the and for with that this from are was but not you have has had its her his "
           "one two now then than there here when what which into out over under also can "
           "will would could should may might been being does did doing about after before "
           "more most some such only just very like".split())


def toks(t):
    return {w for w in WORD.findall(t.lower()) if w not in STOP}


def jaccard(a, b):
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def main():
    if not os.path.exists(CORPUS):
        sys.exit(f"missing {CORPUS} - run tools/distill_reasoning.py first")

    runs = collections.OrderedDict()          # (vendor,guid,game) -> list of records
    for line in open(CORPUS):
        r = json.loads(line)
        if r["vendor"] == UMBRELLA:
            continue
        runs.setdefault((r["vendor"], r["guid"], r["game"]), []).append(r)

    # total step counts per run come from index.json (corpus only holds kept steps)
    total_steps = {}
    for r in json.load(open(INDEX)):
        if r["vendor"] == UMBRELLA:
            continue
        total_steps[(r["vendor"], r["guid"], r["game"])] = r["steps"]

    rows = []
    for key, recs in runs.items():
        vendor, guid, game = key
        recs.sort(key=lambda x: (x["step"] is None, x["step"]))
        n_total = total_steps.get(key) or (recs[-1]["step"] or 0) + 1
        tok = [toks(r["text"]) for r in recs]
        # continuity: only between steps that are ADJACENT in the run, not merely
        # adjacent in the filtered list - a 200-step gap is not "carried forward".
        cont = []
        for i in range(1, len(recs)):
            a, b = recs[i - 1], recs[i]
            if a["step"] is None or b["step"] is None or b["step"] - a["step"] != 1:
                continue
            j = jaccard(tok[i - 1], tok[i])
            if j is not None:
                cont.append(j)
        fifth = max(1, n_total // 5)
        early = sum(1 for r in recs if (r["step"] or 0) < fifth)
        late = sum(1 for r in recs if (r["step"] or 0) >= n_total - fifth)
        by_src = collections.Counter(r["src_field"] for r in recs)
        rows.append({
            "vendor": vendor, "guid": guid, "game": game,
            "steps": n_total, "reasoning_steps": len(recs),
            "density": len(recs) / n_total if n_total else 0.0,
            "out_steps": by_src.get("out", 0),
            "summary_steps": by_src.get("summary", 0),
            "chars_per_step": statistics.mean(len(r["text"]) for r in recs),
            "continuity": statistics.mean(cont) if cont else None,
            "continuity_n": len(cont),
            "early_density": early / fifth,
            "late_density": late / fifth,
            "retention": (late / early) if early else None,
            "last_state": recs[-1].get("state"),
            "levels_completed": max((r.get("levels_completed") or 0) for r in recs),
        })

    # runs with ZERO reasoning steps never appear in the corpus - fold them back in
    for key, n in total_steps.items():
        if key in runs:
            continue
        rows.append({"vendor": key[0], "guid": key[1], "game": key[2], "steps": n,
                     "reasoning_steps": 0, "density": 0.0, "out_steps": 0,
                     "summary_steps": 0, "chars_per_step": 0, "continuity": None,
                     "continuity_n": 0, "early_density": 0.0, "late_density": 0.0,
                     "retention": None, "last_state": None, "levels_completed": None})

    json.dump(rows, open(OUT, "w"), indent=1)

    def med(xs):
        xs = [x for x in xs if x is not None]
        return statistics.median(xs) if xs else float("nan")

    by = collections.defaultdict(list)
    for r in rows:
        by[r["vendor"]].append(r)

    print("COHERENCE OF PUBLISHED REASONING - corpus.jsonl only, echo steps already dropped")
    print(f"(umbrella vendor '{UMBRELLA}' excluded as the exact union of -luna/-sol/-terra)\n")
    print(f"{'vendor':<26}{'runs':>5}{'w/out':>6}{'w/txt':>6}{'dens50':>8}{'cont50':>8}"
          f"{'ret50':>7}{'retN':>6}{'chr50':>7}{'steps':>9}{'rsteps':>8}")
    print("-" * 90)
    for v, rs in sorted(by.items()):
        wt = [r for r in rs if r["reasoning_steps"]]
        wo = [r for r in rs if r["out_steps"]]
        print(f"{v:<26}{len(rs):>5}{len(wo):>6}{len(wt):>6}"
              f"{med(r['density'] for r in wt):>8.2f}"
              f"{med(r['continuity'] for r in wt):>8.2f}"
              f"{med(r['retention'] for r in wt):>7.2f}"
              f"{sum(1 for r in wt if r['retention'] is not None):>6}"
              f"{med(r['chars_per_step'] for r in wt):>7.0f}"
              f"{sum(r['steps'] for r in rs):>9}{sum(r['reasoning_steps'] for r in rs):>8}")
    print("\ndens50/cont50/ret50/chr50 = MEDIAN over runs that published any text."
          "\nretN = how many of those runs have a defined retention: it is late/early and"
          "\nundefined when a run publishes nothing in its first fifth, so runs that start"
          "\nsilent are excluded from ret50 while narrate-then-quit runs score 0.0."
          "\nPer-run medians, not step-pooled rates: a vendor with a few enormous runs"
          "\ncannot dominate the number.")

    print("\nPER-RUN PRESENCE (the correct framing - presence first, density second):")
    print(f"{'vendor':<26}{'runs':>5}{'0 text':>8}{'<5%':>6}{'5-90%':>7}{'>=90%':>7}")
    print("-" * 60)
    for v, rs in sorted(by.items()):
        z = sum(1 for r in rs if r["reasoning_steps"] == 0)
        lo = sum(1 for r in rs if 0 < r["density"] < 0.05)
        mid = sum(1 for r in rs if 0.05 <= r["density"] < 0.90)
        hi = sum(1 for r in rs if r["density"] >= 0.90)
        print(f"{v:<26}{len(rs):>5}{z:>8}{lo:>6}{mid:>7}{hi:>7}")

    print("\nSOURCE OF THE TEXT (out = agent-published prose, summary = provider"
          "\nreasoning-summary leakage; these are NOT the same phenomenon):")
    print(f"{'vendor':<26}{'runs w/out':>11}{'runs summary-only':>19}{'out steps':>11}{'summary steps':>15}")
    print("-" * 84)
    for v, rs in sorted(by.items()):
        wo = sum(1 for r in rs if r["out_steps"])
        so = sum(1 for r in rs if r["summary_steps"] and not r["out_steps"])
        print(f"{v:<26}{wo:>11}{so:>19}"
              f"{sum(r['out_steps'] for r in rs):>11}{sum(r['summary_steps'] for r in rs):>15}")

    print("\nASTRA BIMODALITY - per-run density histogram (openai-gpt-6-astra):")
    a = by["openai-gpt-6-astra"]
    h = collections.Counter(min(9, int(10 * r["density"])) for r in a)
    for k in range(10):
        bar = "#" * int(h[k] / 3)
        print(f"  {k*10:3d}-{k*10+10:3d}%  {h[k]:>4}  {bar}")
    lo = [r for r in a if r["density"] < 0.10]
    hi = [r for r in a if r["density"] >= 0.90]
    print(f"  low mode  n={len(lo)}  runs publishing any `out` prose: "
          f"{sum(1 for r in lo if r['out_steps'])}")
    print(f"  high mode n={len(hi)}  runs publishing any `out` prose: "
          f"{sum(1 for r in hi if r['out_steps'])}")
    print(f"  in between n={len(a)-len(lo)-len(hi)}")
    print(f"\nrows written: {OUT}")


if __name__ == "__main__":
    main()
