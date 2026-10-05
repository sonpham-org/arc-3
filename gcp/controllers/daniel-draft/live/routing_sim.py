"""Batch-aware expert routing study on Daniel's model (3-Oct-2026, daniel-draft; Son: "10 parallel lanes load many
experts - does batch-aware routing still help?").

Input: make_bench_notebook.py --routing dumps (working/routing/req<i>.json: per output token, the 10 routed experts of
each of the 48 MoE layers, from the real server at T0.7, 10 requests in flight). A decode step is modelled as 4
consecutive tokens from each of the 10 lanes (verify width 4; the rejected draft tokens are proxied by the real next
tokens). Per step and layer it counts the distinct experts the GPU must read, then replays routing rules:
  keep-k0  every token keeps its first k0 picks; a pick beyond k0 survives only if some token's first k0 already
           loads that expert (Lynx/OEA-style "piggyback or drop"); reports the distinct experts and the picks dropped
  budget-B keep the B most-demanded experts of the step; picks outside are dropped
Pick order = the order the server returned (assumed best-first, as the fused top-k kernel emits it).
Expert bytes per (layer, expert) at W4A16 g128: 3 x 2560 x 640 x 0.5 B + scales ~= 2.5 MB.
  python routing_sim.py RUN [--lanes 10] [--width 4]
"""
import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
CACHE = Path(r"D:\codex-work\daniel-draft\live\_routing")
L, K, E = 48, 10, 512
MB_PER_EXPERT = (3 * 2560 * 640 * 0.5 + 3 * 2560 * 640 / 128 * 2) / 1e6


def load(run):
    dst = CACHE / run
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(G + ["storage", "rsync", "-r", f"{B}/{run}/working/routing", str(dst)], capture_output=True, timeout=900)
    lanes = []
    for f in sorted(dst.glob("req*.json")):
        d = json.loads(f.read_text())
        raw = d.get("routed_experts")
        if not raw:
            print(f"{f.name}: no routing ({list(d.get('meta', {}))[:8]})"); continue
        buf = base64.b64decode(raw)
        n_out = len(d.get("output_ids") or [])
        for dt in (np.int32, np.int16, np.int64, np.uint8):
            a = np.frombuffer(buf, dtype=dt)
            if a.size % (L * K) == 0 and (not n_out or abs(a.size // (L * K) - n_out) <= 2):
                break
        else:
            print(f"{f.name}: cannot infer layout: {len(buf)} bytes, {n_out} output tokens"); continue
        r = a.reshape(-1, L, K).astype(np.int64)
        if r.max() >= E or r.min() < 0:
            print(f"{f.name}: ids out of range ({r.min()}..{r.max()}), dtype {dt.__name__}"); continue
        lanes.append(r)
        print(f"{f.name}: {r.shape[0]} tokens x {L} layers x {K} (dtype {np.dtype(dt).name}), prompt {d.get('prompt_len')}")
    return lanes


def steps(lanes, n_lanes, width):
    """Steps of `width` tokens per lane; shorter lanes wrap around (requests end at different lengths) so every step
    keeps n_lanes lanes, up to the longest lane."""
    use = lanes[:n_lanes]
    n = max(len(x) for x in use) // width
    for s in range(n):
        rows = []
        for x in use:
            idx = (np.arange(s * width, (s + 1) * width)) % (len(x) - len(x) % width or len(x))
            rows.append(x[idx])
        yield np.stack(rows)  # [lanes, width, L, K]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--lanes", type=int, default=10)
    ap.add_argument("--width", type=int, default=4)
    a = ap.parse_args()
    lanes = load(a.run)
    if len(lanes) < a.lanes:
        print(f"only {len(lanes)} lanes with routing"); a.lanes = len(lanes)
    if not lanes:
        return 1
    T = a.lanes * a.width
    rnd = E * (1 - (1 - K / E) ** T)
    # baseline + rules
    rules = [("baseline", None)] + [(f"keep-{k0}", k0) for k0 in (8, 6, 5, 4)] + [(f"budget-{b}", -b) for b in (200, 160, 128)]
    acc = {name: [0.0, 0.0, 0] for name, _ in rules}  # distinct experts sum, dropped picks sum, count
    single = 0.0
    nsteps = 0
    for st in steps(lanes, a.lanes, a.width):
        nsteps += 1
        picks = st.reshape(T, L, K).transpose(1, 0, 2)  # [L, T, K]
        for li in range(L):
            p = picks[li]
            ids, cnt = np.unique(p, return_counts=True)
            single += (cnt == 1).sum()
            for name, k0 in rules:
                if k0 is None:
                    acc[name][0] += len(ids); acc[name][2] += 1
                elif k0 > 0:
                    core = np.unique(p[:, :k0])
                    extra = p[:, k0:]
                    dropped = (~np.isin(extra, core)).sum()
                    acc[name][0] += len(core); acc[name][1] += dropped; acc[name][2] += 1
                else:
                    bud = -k0
                    keep = ids[np.argsort(-cnt, kind="stable")[:bud]]
                    dropped = (~np.isin(p, keep)).sum()
                    acc[name][0] += min(bud, len(ids)); acc[name][1] += dropped; acc[name][2] += 1
    n = acc["baseline"][2]
    base = acc["baseline"][0] / n
    print(f"\n{nsteps} steps x {L} layers; {a.lanes} lanes x width {a.width} = {T} tokens per step")
    print(f"distinct experts per layer per step: {base:.0f} of {E} (random routing would load {rnd:.0f}); "
          f"used by one token only: {single / n:.0f}")
    print(f"expert bytes per step: {base * L * MB_PER_EXPERT / 1000:.1f} GB (all experts {E * L * MB_PER_EXPERT / 1000:.1f} GB)")
    print(f"{'rule':12s} {'experts':>8s} {'bytes':>7s} {'picks dropped':>14s}")
    for name, _ in rules:
        d, dr, c = acc[name]
        print(f"{name:12s} {d / c:8.0f} {d / c / base:7.0%} {dr / (c * T * K):14.1%}")


if __name__ == "__main__":
    sys.exit(main())
