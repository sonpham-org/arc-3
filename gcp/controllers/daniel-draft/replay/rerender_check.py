"""How faithfully does a later prompt re-render what the model generated? (4-Oct-2026, replay data prep)

  python3 rerender_check.py CAPTURE_DIR OUT.json

On a LIVE capture (req files = each request's prompt ids, decode files = what it generated): for every request that
finished (its generated tokens end in <|im_end|>), find the later request whose prompt carries that response
(the assistant turn whose tokens best match), and compare the re-rendered span (after <|im_start|>assistant\\n<think>\\n
up to and including <|im_end|>) with the generated tokens. A replay trains on the re-rendered spans, so this is the
gap between replayed and served data. numpy only (reads .mtpc without torch).
"""
import difflib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

import numpy as np

IM_START, IM_END, ASSISTANT, NL, THINK = 248045, 248046, 74455, 198, 248068
NP = {"int32": np.int32, "int64": np.int64, "bfloat16": np.uint16, "float32": np.float32}


def header(path):
    with open(path, "rb") as f:
        assert f.read(8) == b"ARC3MTPC"
        (hl,) = struct.unpack("<Q", f.read(8))
        h = json.loads(f.read(hl))
    h["_base"] = 16 + hl
    return h


def tensor(path, h, name):
    dt, shape, off, nb = h["tensors"][name]
    with open(path, "rb") as f:
        f.seek(h["_base"] + off)
        return np.frombuffer(f.read(nb), dtype=NP[dt]).reshape(shape)


def spans(prompt):
    """[(g0, g1)] generated spans of every assistant turn in a prompt (g1 exclusive, includes <|im_end|>); the final
    generation prompt (no <|im_end|> after it) is skipped."""
    out = []
    idx = np.nonzero(prompt == IM_START)[0]
    for i in idx:
        if i + 3 < len(prompt) and prompt[i + 1] == ASSISTANT and prompt[i + 2] == NL and prompt[i + 3] == THINK:
            g0 = i + 4 + (1 if i + 4 < len(prompt) and prompt[i + 4] == NL else 0)
            e = np.nonzero(prompt[g0:] == IM_END)[0]
            if e.size:
                out.append((int(g0), int(g0 + e[0] + 1)))
    return out


def main():
    cap, out_path = Path(sys.argv[1]), sys.argv[2]
    reqs, steps = {}, {}
    for p in sorted(cap.glob("*.mtpc")):
        if "_prefill_" in p.name:
            continue
        h = header(p)
        if h["kind"] == "req":
            reqs[h["rid"]] = (h["seq"], tensor(p, h, "prompt_ids").astype(np.int64))
        elif h["kind"] == "decode":
            meta = tensor(p, h, "meta")
            D = h["draft"]
            for k, rid in enumerate(h["rids"]):
                steps.setdefault(rid, []).append((int(meta[k, 0]), int(meta[k, 1]), meta[k, 2:2 + D].copy(),
                                                  meta[k, 2 + D:].copy()))
    gen = {}
    for rid, (seq, prompt) in reqs.items():
        toks = list(prompt)
        st = sorted(steps.get(rid, []), key=lambda s: s[0])
        for s, acc, pred, drf in st:
            if s != len(toks):
                break
            toks.extend(int(t) for t in drf[:acc])
        if st and st[-1][0] + st[-1][1] == len(toks):
            toks.append(int(st[-1][2][st[-1][1] - 1]))
        g = toks[len(prompt):]
        if g and g[-1] == IM_END:
            gen[rid] = (seq, len(prompt), g)
    order = sorted(reqs.items(), key=lambda kv: kv[1][0])
    sp = {rid: spans(p) for rid, (s, p) in order}
    res = Counter()
    rows = []
    for rid, (seq, plen, g) in sorted(gen.items(), key=lambda kv: kv[1][0]):
        G = np.asarray(g)
        best = None
        for qrid, (qseq, qp) in order:
            if qseq <= seq:
                continue
            for g0, g1 in sp[qrid]:
                S = qp[g0:g1]
                if not len(S):
                    continue
                m = difflib.SequenceMatcher(None, G[:80].tolist(), S[:80].tolist(), autojunk=False).ratio()
                if best is None or m > best[0]:
                    best = (m, qrid, g0, g1)
            if best and best[0] >= 0.8:
                break  # the first later request that carries it (the next turn)
        if best is None or best[0] < 0.5:
            res["no_carrier"] += 1
            rows.append({"rid": rid, "gen": len(G), "carrier": None})
            continue
        m, qrid, g0, g1 = best
        S = reqs[qrid][1][g0:g1]
        sm = difflib.SequenceMatcher(None, G.tolist(), S.tolist(), autojunk=False)
        same = sum(b.size for b in sm.get_matching_blocks())
        d = np.nonzero(S[:min(len(S), len(G))] != G[:min(len(S), len(G))])[0]
        first = int(d[0]) if d.size else (min(len(S), len(G)) if len(S) != len(G) else -1)
        exact = len(S) == len(G) and first == -1
        res["carried"] += 1
        res["exact"] += exact
        res["gen_tokens"] += len(G)
        res["span_tokens"] += len(S)
        res["matched_tokens"] += same
        rows.append({"rid": rid, "gen": len(G), "span": len(S), "same": same, "first_diff": first, "exact": exact,
                     "carrier": qrid, "g0": g0,
                     "diff": [] if exact else [(t, i1, i2, j1, j2, G[i1:i2].tolist()[:8], S[j1:j2].tolist()[:8])
                                               for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"][:6]})
    res["finished_requests"] = len(gen)
    res["requests"] = len(reqs)
    firsts = Counter(min(r["first_diff"], 99) if r.get("first_diff", -1) >= 0 else -1 for r in rows if r.get("carrier"))
    summary = {**res, "exact_share": round(res["exact"] / max(1, res["carried"]), 4),
               "token_match_share": round(res["matched_tokens"] / max(1, res["gen_tokens"]), 5),
               "carried_gen_share": round(res["gen_tokens"] / max(1, sum(len(g) for _, _, g in gen.values())), 4),
               "first_diff_hist": sorted(firsts.items())}
    json.dump({"summary": summary, "rows": rows}, open(out_path, "w"))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
