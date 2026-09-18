"""Per-game reasoning-style + efficiency table for one ARC-3 run directory.

Author: Claude Opus 5 (Bubba sub-agent)
Date: 17-September-2026
PURPOSE: Extract, from a single ARC-3 run directory, the per-game reasoning-style metrics
(reasoning block length, self-talk rate, assistant content and tool-argument size) alongside
the efficiency and outcome metrics (environment actions, generated tokens, tokens/action,
levels cleared, official score) and write them to <run>/style_table.json. This is the
measurement layer for the compact-reasoning A/B; multipass_compare.py aggregates its output
across runs. Depends only on run artifacts, optionally on a local tokenizer.
SRP/DRY check: Pass -- action and level counts are read exactly as aggregate.py reads them,
so both arms are measured by the same code path rather than a reimplementation.

Data sources, all run artifacts:
  <run>/<game>_p0_requests.jsonl   -- per-response `reasoning` text and server `usage`
  <run>/artifacts/<game>_p0_events.jsonl -- action/level/score event stream
  <run>/benchmark.json             -- actions_per_level, state
  <run>/evaluation.json            -- official per-game score

Action and level counts are taken exactly as aggregate.py (the script that
produced the published baseline table) takes them, so the two runs are measured
by the same code path.
"""
import collections, glob, json, os, re, sys

RUN = sys.argv[1]
TOKENIZER_DIR = sys.argv[2] if len(sys.argv) > 2 else None

SELF_TALK = re.compile(r"\b(wait|hmm+|actually)\b", re.I)

_tok = None
if TOKENIZER_DIR:
    try:
        from transformers import AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(TOKENIZER_DIR, trust_remote_code=True)
    except Exception as exc:  # tokenizer is a nicety, not a requirement
        print(f"# tokenizer unavailable ({exc}); reasoning tokens will be null", file=sys.stderr)


def ntok(text):
    if _tok is None or not text:
        return None
    return len(_tok.encode(text, add_special_tokens=False))


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, errors="replace"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def median(xs):
    xs = sorted(xs)
    if not xs:
        return 0.0
    m = len(xs) // 2
    return float(xs[m]) if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


bench = {}
bpath = os.path.join(RUN, "benchmark.json")
if os.path.exists(bpath):
    for g in json.load(open(bpath)).get("game_runs", []):
        bench[g["game_id"]] = g

# official scores: evaluation.json, falling back to score.json
official = {}
official_levels = {}
epath = os.path.join(RUN, "evaluation.json")
if os.path.exists(epath):
    for v in json.load(open(epath)).get("games", []):
        if isinstance(v, dict) and v.get("game_id"):
            official[v["game_id"]] = v.get("score")
            official_levels[v["game_id"]] = v.get("levels_completed")
# benchmark.json is the fallback, and the only source before evaluation.json is written
for gid, g in bench.items():
    official.setdefault(gid, g.get("final_score"))
    official_levels.setdefault(gid, g.get("levels_completed"))

rows = []
for ev_path in sorted(glob.glob(os.path.join(RUN, "artifacts", "*_p0_events.jsonl"))):
    gid = os.path.basename(ev_path).replace("_p0_events.jsonl", "")
    events = read_jsonl(ev_path)
    reqs = read_jsonl(os.path.join(RUN, gid + "_p0_requests.jsonl"))
    responses = [r for r in reqs if r.get("event") == "response"]

    gen = sum((r.get("usage") or {}).get("completion_tokens") or 0 for r in responses)
    prompt_tok = sum((r.get("usage") or {}).get("prompt_tokens") or 0 for r in responses)

    blocks = []
    content_chars = []
    toolarg_chars = []
    for r in responses:
        rm = r.get("response_message") or {}
        txt = rm.get("reasoning") or ""
        if txt.strip():
            blocks.append(txt)
        # Verbosity can RELOCATE rather than vanish: the instruction tells the model to
        # push analysis into the python call, so track assistant content and tool-call
        # argument size alongside reasoning. A drop in reasoning chars that is offset by
        # a rise in these is not a win.
        content_chars.append(len(rm.get("content") or ""))
        args = 0
        for tc in (rm.get("tool_calls") or []):
            fn = (tc or {}).get("function") or {}
            args += len(fn.get("arguments") or "")
        toolarg_chars.append(args)

    chars = [len(b) for b in blocks]
    toks = [t for t in (ntok(b) for b in blocks) if t is not None]
    selftalk = sum(1 for b in blocks if SELF_TALK.search(b))

    last = events[-1] if events else {}
    max_action = max([e.get("action_num") or 0 for e in events], default=0)
    b = bench.get(gid, {})
    apl = b.get("actions_per_level") or []
    actions = sum(apl) if apl else max_action
    _lv = official_levels.get(gid)
    levels = int(_lv) if isinstance(_lv, (int, float)) else 0

    rows.append({
        "game": gid,
        "state": b.get("state") or last.get("state") or "?",
        "levels_completed": levels,
        "actions": actions,
        "official_score": official.get(gid),
        "generated_tokens": gen,
        "prompt_tokens": prompt_tok,
        "llm_responses": len(responses),
        "reasoning_blocks": len(blocks),
        "reasoning_chars_mean": round(sum(chars) / len(chars), 1) if chars else 0.0,
        "reasoning_chars_median": round(median(chars), 1),
        "reasoning_tokens_mean": round(sum(toks) / len(toks), 1) if toks else None,
        "reasoning_tokens_median": round(median(toks), 1) if toks else None,
        "selftalk_frac": round(selftalk / len(blocks), 4) if blocks else None,
        "tokens_per_action": round(gen / actions, 1) if actions else None,
        "content_chars_mean": round(sum(content_chars) / len(content_chars), 1) if content_chars else None,
        "toolarg_chars_mean": round(sum(toolarg_chars) / len(toolarg_chars), 1) if toolarg_chars else None,
        "output_chars_mean": round(
            (sum(len(b) for b in blocks) + sum(content_chars) + sum(toolarg_chars)) / len(responses), 1
        ) if responses else None,
    })

rows.sort(key=lambda r: r["game"])

allchars = [c for r, g in [(r, None) for r in rows] for c in []]  # placeholder, real pooling below
pool_chars, pool_toks, pool_blocks, pool_self = [], [], 0, 0
for ev_path in sorted(glob.glob(os.path.join(RUN, "artifacts", "*_p0_events.jsonl"))):
    gid = os.path.basename(ev_path).replace("_p0_events.jsonl", "")
    for r in read_jsonl(os.path.join(RUN, gid + "_p0_requests.jsonl")):
        if r.get("event") != "response":
            continue
        txt = (r.get("response_message") or {}).get("reasoning") or ""
        if not txt.strip():
            continue
        pool_blocks += 1
        pool_chars.append(len(txt))
        t = ntok(txt)
        if t is not None:
            pool_toks.append(t)
        if SELF_TALK.search(txt):
            pool_self += 1

pool_content = sum((r["content_chars_mean"] or 0) * r["llm_responses"] for r in rows)
pool_toolarg = sum((r["toolarg_chars_mean"] or 0) * r["llm_responses"] for r in rows)
pool_responses = sum(r["llm_responses"] for r in rows)

tot_actions = sum(r["actions"] for r in rows)
tot_gen = sum(r["generated_tokens"] for r in rows)
scores = [r["official_score"] for r in rows if isinstance(r["official_score"], (int, float))]

summary = {
    "run": RUN,
    "games": len(rows),
    "score_sum": round(sum(scores), 2) if scores else None,
    "scoring_games": sum(1 for s in scores if s > 0),
    "levels_cleared": sum(r["levels_completed"] for r in rows),
    "total_actions": tot_actions,
    "total_generated_tokens": tot_gen,
    "tokens_per_action_overall": round(tot_gen / tot_actions, 1) if tot_actions else None,
    "reasoning_blocks": pool_blocks,
    "reasoning_chars_mean": round(sum(pool_chars) / len(pool_chars), 1) if pool_chars else None,
    "reasoning_chars_median": round(median(pool_chars), 1),
    "reasoning_tokens_mean": round(sum(pool_toks) / len(pool_toks), 1) if pool_toks else None,
    "reasoning_tokens_median": round(median(pool_toks), 1) if pool_toks else None,
    "selftalk_frac_pooled": round(pool_self / pool_blocks, 4) if pool_blocks else None,
    "llm_responses": pool_responses,
    "content_chars_mean": round(pool_content / pool_responses, 1) if pool_responses else None,
    "toolarg_chars_mean": round(pool_toolarg / pool_responses, 1) if pool_responses else None,
    "output_chars_mean": round(
        (sum(pool_chars) + pool_content + pool_toolarg) / pool_responses, 1
    ) if pool_responses else None,
}

out = {"summary": summary, "per_game": rows}
print(json.dumps(out, indent=2))
dest = os.path.join(RUN, "style_table.json")
json.dump(out, open(dest, "w"), indent=2)
print("\n# wrote " + dest, file=sys.stderr)
