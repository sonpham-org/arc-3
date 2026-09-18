"""
Author: Claude Opus 5 (Bubba sub-agent)
Date: 17-September-2026
PURPOSE: Analyse the ARC-3 replay corpus pulled by tools/arc3/pull_replays.py and answer one
question with numbers: are agent reasoning traces coherent, or is the visible text mush?
Walks the decision-step recordings tree (<game_id>/<guid>.ndjson), parses
data.action_input.reasoning (a JSON *string* wrapping
{output, reasoning, usage}), and reports: actions total, how many carry a reasoning field, how
many carry NON-NULL summary text, median/max summary length, reasoning-token usage, and a
per-model / per-runner breakdown joined from the <guid>.meta.json session records. Crucially it
separates "the model reasoned badly" from "the provider only exposed a lossy summary, usually
null" by cross-tabbing null summary text against non-zero usage.reasoning_tokens. Also scores
competence behaviourally: frame-change rate after an action (frames hashed, not held), levels
completed, and actions used vs level_baseline_actions from the session metadata.
Integration points: consumes datasets/decision-steps/v0/recordings/ written by
tools/replay_scrape.py; emits JSON to stdout
and optionally --out for the write-up.
SRP/DRY check: Pass — pull_replays.py only fetches; nothing in the workspace parses recording
JSONL or the nested reasoning envelope.
"""
import argparse, collections, glob, hashlib, json, os, statistics, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "datasets", "decision-steps", "v0", "recordings")


def parse_reasoning(ai):
    """action_input.reasoning is a JSON string -> {output, reasoning, usage}. Returns dict|None."""
    if not isinstance(ai, dict):
        return None
    r = ai.get("reasoning")
    if r is None:
        return None
    if isinstance(r, dict):
        return r
    if isinstance(r, str):
        try:
            v = json.loads(r)
            return v if isinstance(v, dict) else {"reasoning": r}
        except Exception:                          # noqa: BLE001 - plain-text reasoning
            return {"reasoning": r}
    return None


def scan(path, meta):
    """One recording -> per-session stats. Frames are hashed, never accumulated."""
    s = {"actions": 0, "with_reasoning_field": 0, "with_summary_text": 0,
         "summary_lens": [], "reasoning_tokens": [], "null_summary_but_tokens": 0,
         "null_summary_and_no_tokens": 0, "frame_changed": 0, "frame_same": 0,
         "changed_given_summary": 0, "n_given_summary": 0,
         "changed_given_no_summary": 0, "n_given_no_summary": 0,
         "levels_completed": 0, "lines": 0, "bytes": os.path.getsize(path)}
    prev_hash, prev_level = None, None
    with open(path, "rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:                      # noqa: BLE001 - tolerate a truncated tail
                continue
            s["lines"] += 1
            d = obj.get("data") or {}
            frame = d.get("frame")
            h = hashlib.blake2b(json.dumps(frame, sort_keys=True).encode(),
                                digest_size=8).hexdigest() if frame is not None else None
            ai = d.get("action_input")
            has_action = isinstance(ai, dict) and ai.get("id") is not None or bool(ai)
            if has_action:
                s["actions"] += 1
            pr = parse_reasoning(ai)
            has_summary = False
            if pr is not None:
                s["with_reasoning_field"] += 1
                txt = pr.get("reasoning")
                usage = pr.get("usage") or {}
                rt = usage.get("reasoning_tokens")
                if rt is None:   # OpenAI Responses API nests it here
                    rt = (usage.get("output_tokens_details") or {}).get("reasoning_tokens")
                if rt is None:   # Chat Completions shape
                    rt = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
                if isinstance(rt, int):
                    s["reasoning_tokens"].append(rt)
                if isinstance(txt, str) and txt.strip():
                    has_summary = True
                    s["with_summary_text"] += 1
                    s["summary_lens"].append(len(txt))
                else:
                    if isinstance(rt, int) and rt > 0:
                        s["null_summary_but_tokens"] += 1
                    else:
                        s["null_summary_and_no_tokens"] += 1
            if prev_hash is not None and h is not None and has_action:
                changed = h != prev_hash
                s["frame_changed" if changed else "frame_same"] += 1
                if pr is not None:
                    if has_summary:
                        s["n_given_summary"] += 1
                        s["changed_given_summary"] += changed
                    else:
                        s["n_given_no_summary"] += 1
                        s["changed_given_no_summary"] += changed
            if h is not None:
                prev_hash = h
            lv = d.get("levels_completed")
            if isinstance(lv, int):
                s["levels_completed"] = max(s["levels_completed"], lv)
            prev_level = lv
    return s


def classify(meta):
    """(class, label). Three populations, and conflating them wrecks the numbers:
    llm      - a language model drove the actions (model field or a model_* tag)
    scripted - ARC's preview baseline bots (guidedrandom, blindsquirrel, heuristicagent,
               action-model). These emit a `reasoning` string too, but it is telemetry
               ("Type: arrow, Chance: 1.00"), not model reasoning.
    human    - no ai_agent flag
    """
    if not meta.get("ai_agent"):
        return "human", "human"
    tags = meta.get("tags") or []
    if meta.get("model"):
        return "llm", meta["model"]
    for t in tags:
        if t.startswith(("model_", "model:")):
            return "llm", t.split("_", 1)[-1].split(":", 1)[-1]
        if t.startswith(("gpt-", "claude-", "gemini", "o3", "o4")):
            return "llm", t
    known = [t for t in tags if t not in ("agent",) and "-" not in t]
    return "scripted", (known[0] if known else "scripted-unknown")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--out")
    args = ap.parse_args()

    per_model = collections.defaultdict(lambda: collections.defaultdict(int))
    per_model_lens = collections.defaultdict(list)
    per_model_rt = collections.defaultdict(list)
    sessions, baselines = [], []
    agg = collections.Counter()
    all_lens, all_rt = [], []

    # Recordings live one directory per game build: <root>/<game_id>/<guid>.ndjson, with the
    # cached /api/sessions document beside it as <guid>.meta.json. Both extensions are
    # accepted so a corpus pulled before the .ndjson rename still reads.
    paths = sorted(p for ext in ("*.ndjson", "*.jsonl")
                   for p in glob.glob(os.path.join(args.root, "*", ext)))
    metas = {p: json.load(open(p)) for p in
             glob.glob(os.path.join(args.root, "*", "*.meta.json"))}

    for path in paths:
        guid = os.path.basename(path).rsplit(".", 1)[0]
        mp = os.path.join(os.path.dirname(path), f"{guid}.meta.json")
        meta = metas.get(mp, {})
        # A recording is keyed by RUN guid; the session document it belongs to may be filed
        # under the parent session guid instead, so fall back to a scan of every cached doc.
        if not meta:
            for m in metas.values():
                if any(r.get("guid") == guid for e in (m.get("environments") or [])
                       for r in (e.get("runs") or [])):
                    meta = m
                    break
        is_agent = bool(meta.get("ai_agent"))
        cls, model = classify(meta)
        runner = meta.get("runner") or cls
        s = scan(path, meta)
        s.update({"guid": guid, "model": model, "runner": runner, "is_agent": is_agent,
                  "class": cls, "tags": meta.get("tags") or []})
        # actions used vs the human baseline for the levels this run cleared
        for e in meta.get("environments") or []:
            for r in e.get("runs") or []:
                if r.get("guid") != guid:
                    continue
                la, lb = r.get("level_actions") or [], r.get("level_baseline_actions") or []
                cleared = r.get("levels_completed") or 0
                for i, a in enumerate(la):
                    # Only levels the run actually CLEARED are comparable. Uncleared levels
                    # are censored at exactly 5x baseline (the action cap), so including them
                    # manufactures a pile of 5.0 ratios that measure nothing. Negative entries
                    # are "not attempted" sentinels.
                    if i < cleared and i < len(lb) and isinstance(a, int) \
                            and isinstance(lb[i], int) and a > 0 and lb[i] > 0:
                        baselines.append({"model": model, "class": cls, "game": e.get("id"),
                                          "level": i, "actions": a, "baseline": lb[i],
                                          "ratio": a / lb[i], "is_agent": is_agent})
        key = f"{cls}|{model}|{runner}"
        for k in ("actions", "with_reasoning_field", "with_summary_text",
                  "null_summary_but_tokens", "null_summary_and_no_tokens",
                  "frame_changed", "frame_same", "changed_given_summary", "n_given_summary",
                  "changed_given_no_summary", "n_given_no_summary", "bytes"):
            per_model[key][k] += s[k]
            agg[k] += s[k]
        per_model[key]["sessions"] += 1
        per_model_lens[key] += s["summary_lens"]
        per_model_rt[key] += s["reasoning_tokens"]
        if cls == "llm":
            all_lens += s["summary_lens"]
            all_rt += s["reasoning_tokens"]
        s.pop("summary_lens"); s.pop("reasoning_tokens")
        sessions.append(s)

    def stats(v):
        if not v:
            return None
        return {"n": len(v), "median": statistics.median(v), "mean": round(statistics.mean(v), 1),
                "max": max(v), "min": min(v),
                "p90": statistics.quantiles(v, n=10)[8] if len(v) > 9 else max(v)}

    models = {}
    for k, d in sorted(per_model.items()):
        models[k] = {**dict(d),
                     "summary_len": stats(per_model_lens[k]),
                     "reasoning_tokens": stats(per_model_rt[k]),
                     "summary_rate": round(d["with_summary_text"] / d["with_reasoning_field"], 4)
                     if d["with_reasoning_field"] else None,
                     "frame_change_rate": round(d["frame_changed"] /
                                                (d["frame_changed"] + d["frame_same"]), 4)
                     if (d["frame_changed"] + d["frame_same"]) else None}

    ag_b = [b for b in baselines if b["is_agent"]]
    llm_b = [b for b in baselines if b["class"] == "llm"]
    out = {
        "corpus": {"recordings": len(sessions),
                   "agent_recordings": sum(1 for s in sessions if s["is_agent"]),
                   "human_recordings": sum(1 for s in sessions if not s["is_agent"]),
                   "gb": round(agg["bytes"] / 1e9, 2)},
        "totals": dict(agg),
        "llm_summary_len": stats(all_lens),
        "llm_reasoning_tokens": stats(all_rt),
        "per_model": models,
        "classes": {c: sum(1 for x in sessions if x["class"] == c)
                    for c in ("llm", "scripted", "human")},
        "llm_only": {k: sum(x[k] for x in sessions if x["class"] == "llm")
                     for k in ("actions", "with_reasoning_field", "with_summary_text",
                               "null_summary_but_tokens", "null_summary_and_no_tokens")},
        "scripted_only": {k: sum(x[k] for x in sessions if x["class"] == "scripted")
                          for k in ("actions", "with_reasoning_field", "with_summary_text")},
        "baseline_ratio_llm": stats([b["ratio"] for b in llm_b]),
        "baseline_ratio_agent": stats([b["ratio"] for b in ag_b]),
        "baseline_ratio_human": stats([b["ratio"] for b in baselines if not b["is_agent"]]),
        "baseline_beats_human_agent": sum(1 for b in ag_b if b["ratio"] < 1),
        "baseline_n_agent": len(ag_b),
        "baseline_beats_human_llm": sum(1 for b in llm_b if b["ratio"] < 1),
        "baseline_n_llm": len(llm_b),
    }
    txt = json.dumps(out, indent=1, default=str)
    if args.out:
        open(os.path.expanduser(args.out), "w").write(txt)
        json.dump(sessions, open(os.path.expanduser(args.out) + ".sessions.json", "w"), indent=1)
    print(txt)


if __name__ == "__main__":
    main()
