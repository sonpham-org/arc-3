"""Real routing sample for the MoE microbench: [S, 48, 52, 10] int16 (13 lanes x 4 consecutive tokens, lane-major).
Lanes 0-9 = the 10 real requests of daniel-bench-route10-1003; lanes 10-12 = the 3 longest requests at a +256 offset."""
import base64, json
from pathlib import Path
import numpy as np
L, K = 48, 10
src = Path(r"D:\codex-work\daniel-draft\live\_routing\daniel-bench-route10-1003")
lanes = []
for f in sorted(src.glob("req*.json")):
    d = json.loads(f.read_text()); a = np.frombuffer(base64.b64decode(d["routed_experts"]), dtype=np.int32)
    lanes.append(a.reshape(-1, L, K))
order = sorted(range(len(lanes)), key=lambda i: -len(lanes[i]))
S, W = 12, 4
out = np.zeros((S, L, 13 * W, K), np.int16)
for s in range(S):
    rows = []
    for li in range(13):
        x = lanes[li] if li < 10 else lanes[order[li - 10]]
        off = (s * 37 + (256 if li >= 10 else 0)) % (len(x) - W)
        rows.append(x[off:off + W])
    st = np.concatenate(rows, 0)  # [52, L, K]
    out[s] = st.transpose(1, 0, 2)
d40 = np.mean([len(np.unique(out[s, l, :40])) for s in range(S) for l in range(L)])
d52 = np.mean([len(np.unique(out[s, l])) for s in range(S) for l in range(L)])
print("distinct experts per layer: T=40", round(d40, 1), "T=52", round(d52, 1))
p = Path(r"D:\codex-work\daniel-draft\kernels\bench\routing_sample.npy"); np.save(p, out); print(p, out.shape, p.stat().st_size)
