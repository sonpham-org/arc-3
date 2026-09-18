#!/usr/bin/env python3.13
"""
Author: Claude Opus 5 (sub-agent for Bubba)
Date: 17-September-2026
PURPOSE: Aggregate the compact ARC-3 replay corpus produced by harvest_replays.py into
         per-config coherence statistics. Reports THREE distinct and separately-labelled
         signals, because the vendor harness adapters differ structurally:
           (1) summary_rate  - actions whose parsed reasoning.reasoning summary text is
               non-null. This is the headline number the Boss has been reading.
           (2) rtok_rate     - actions where usage.output_tokens_details.reasoning_tokens>0,
               i.e. the model actually spent reasoning tokens regardless of retention.
           (3) prose_rate    - actions whose visible `output` exceeds a bare action token,
               which is where Anthropic-style adapters carry working memory instead.
         Also emits adapter keysets so an unreadable schema is never reported as a zero.
SRP/DRY check: Pass - harvest_replays.py fetches/strips only; this file only aggregates.
"""
import json, os, glob, statistics, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "datasets", "vendor-coherence")
REPLAYS = os.path.join(ROOT, "replays")
BARE_OUTPUT_MAX = 40  # chars; "ACTION6 40 33" is ~13


def analyze_run(path):
    n = summ = rtok = prose = fchg = 0
    outlens, prune_before, prune_after, cached, itok = [], [], [], [], []
    for line in open(path):
        r = json.loads(line)
        if not r.get("reasoning_present"):
            continue
        n += 1
        if r.get("summary"):
            summ += 1
        u = r.get("usage") or {}
        if (u.get("rtok") or 0) > 0:
            rtok += 1
        if u.get("cached") is not None:
            cached.append(u["cached"])
        if u.get("in") is not None:
            itok.append(u["in"])
        o = r.get("out") or ""
        outlens.append(len(o))
        if len(o) > BARE_OUTPUT_MAX:
            prose += 1
        if r.get("fchanged") is True:
            fchg += 1
        h = r.get("hist") or {}
        if h.get("before_prune") is not None:
            prune_before.append(h["before_prune"])
            prune_after.append(h.get("after_prune"))
    return {
        "actions": n, "summary": summ, "rtok": rtok, "prose": prose, "fchanged": fchg,
        "out_len_mean": statistics.mean(outlens) if outlens else 0,
        "in_tok_max": max(itok) if itok else None,
        "cached_max": max(cached) if cached else None,
        "prune_before_max": max(prune_before) if prune_before else None,
        "prune_after_max": max([p for p in prune_after if p is not None]) if prune_after else None,
    }


def main():
    rows = []
    for gdir in sorted(glob.glob(os.path.join(REPLAYS, "*"))):
        group = os.path.basename(gdir)
        for mp in sorted(glob.glob(os.path.join(gdir, "*.meta.json"))):
            meta = json.load(open(mp))
            if not meta.get("_complete"):
                continue
            for run in meta.get("runs", []):
                jp = os.path.join(gdir, f"{meta['guid']}__{run['game_id']}.jsonl")
                if not os.path.exists(jp):
                    continue
                a = analyze_run(jp)
                rows.append({
                    "group": group, "model": meta.get("model"),
                    "config": meta.get("config"), "guid": meta["guid"],
                    "game_id": run["game_id"], "run_state": run.get("run_state"),
                    "score": run.get("run_score"),
                    "levels_completed": run.get("levels_completed"),
                    "resets": run.get("run_resets"),
                    "integrity": run.get("integrity"),
                    "keysets": run.get("stats", {}).get("keysets", {}),
                    "unparseable": run.get("stats", {}).get("unparseable", 0),
                    **a,
                })
    # Dedupe: `openai-gpt-5-6` is the union of its luna/sol/terra variant groups, so the
    # same (guid, game_id) appears under two group dirs. Config (from the session API) is
    # the real discriminator, so drop umbrella-group duplicates.
    seen, uniq = set(), []
    for r in rows:
        k = (r["guid"], r["game_id"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    dropped = len(rows) - len(uniq)
    rows = uniq
    print(f"deduped {dropped} duplicate (guid,game_id) rows from umbrella groups\n")

    out = os.path.join(ROOT, "coherence-rows.json")
    json.dump(rows, open(out, "w"), indent=1)

    # ---- aggregate per config ----
    by = {}
    for r in rows:
        by.setdefault(r["config"] or r["group"], []).append(r)

    def pct(a, b):
        return (100.0 * a / b) if b else float("nan")

    print(f"{'config':<46}{'sess':>5}{'acts':>7}{'summ%':>7}{'rtok%':>7}"
          f"{'prose%':>7}{'fchg%':>7}{'outlen':>7}{'win%*':>6}{'bad':>4}")
    print("-" * 104)
    lines = []
    for c, rs in sorted(by.items(), key=lambda kv: -sum(x["actions"] for x in kv[1])):
        A = sum(x["actions"] for x in rs)
        row = (f"{c[:45]:<46}{len(rs):>5}{A:>7}"
               f"{pct(sum(x['summary'] for x in rs), A):>7.1f}"
               f"{pct(sum(x['rtok'] for x in rs), A):>7.1f}"
               f"{pct(sum(x['prose'] for x in rs), A):>7.1f}"
               f"{pct(sum(x['fchanged'] for x in rs), A):>7.1f}"
               f"{(sum(x['out_len_mean'] * x['actions'] for x in rs) / A if A else 0):>7.0f}"
               f"{pct(sum(1 for x in rs if x['run_state'] == 'WIN'), len(rs)):>6.0f}"
               f"{sum(1 for x in rs if x['integrity'] != 'ok'):>4}")
        print(row)
        lines.append(row)

    print("\n* win% is NOT comparable across harness families: every -provider-adapter config"
          "\n  reads 100% win, which is almost certainly a publication filter on the public"
          "\n  results page, not a harness-quality effect. Unpublished sessions are not visible"
          "\n  from an unauthenticated endpoint, so this stays unresolved.")

    # ---- the reframe: summary retention vs reasoning effort, within one harness family ----
    print("\nSUMMARY RETENTION vs REASONING EFFORT (provider-adapter family only):")
    order = ["none", "low", "medium", "high", "xhigh", "max"]
    fam = [c for c in by if c and c.endswith("-provider-adapter")]
    for eff in order:
        hits = [c for c in fam if f"-{eff}-provider-adapter" in c]
        for c in sorted(hits):
            rs = by[c]
            A = sum(x["actions"] for x in rs)
            print(f"  {eff:<7}{c[:44]:<46} summ={pct(sum(x['summary'] for x in rs), A):5.1f}%"
                  f"  rtok={pct(sum(x['rtok'] for x in rs), A):5.1f}%  n={A}")

    nonad = [r for r in rows if not (r["config"] or "").endswith("-provider-adapter")]
    ns = sum(r["summary"] for r in nonad)
    print(f"\nNON-adapter configs with any non-null reasoning summary: "
          f"{ns} summaries across {sum(r['actions'] for r in nonad)} actions "
          f"({len([r for r in nonad if r['summary']])} of {len(nonad)} runs)")

    print("\nADAPTER KEYSETS (a zero rate with an unfamiliar keyset means UNREAD, not absent):")
    ks = {}
    for r in rows:
        for k, v in (r["keysets"] or {}).items():
            ks.setdefault(k, {}).setdefault(r["config"] or r["group"], 0)
            ks[k][r["config"] or r["group"]] += v
    for k, cfgs in ks.items():
        print(f"  [{k}] -> {len(cfgs)} configs, {sum(cfgs.values())} actions")
    bad = sum(r["unparseable"] for r in rows)
    print(f"\nunparseable reasoning payloads: {bad}")
    print(f"sessions: {len(rows)}   rows written: {out}")


if __name__ == "__main__":
    main()
