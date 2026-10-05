"""Table from pre_bench_dense.json (bench_dense.py): per shape and M, cuBLAS / Daniel low-M / best skinny us and GB/s,
plus per-step totals at the target verify width (calls x us)."""
import json
import subprocess
import sys

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
run = sys.argv[1]
name = sys.argv[2] if len(sys.argv) > 2 else "pre_bench_dense.json"
raw = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/{name}"], capture_output=True).stdout.decode()
rows = [json.loads(l) for l in raw.splitlines() if l.startswith("{")]
for r in rows:
    if r.get("kind") in ("env", "bandwidth_GBps", "error", "skip", "fatal"):
        print(json.dumps(r)[:600])
for r in rows:
    if r.get("kind") == "hc_mix":
        print(json.dumps(r))
print(f"\n{'shape':24s} {'M':>3s} {'MB':>7s} {'cuBLAS':>8s} {'lowm':>8s} {'skinny':>8s} {'GB/s cb':>8s} {'GB/s sk':>8s} "
      f"{'x calls':>7s} {'step ms cb->sk':>15s} {'bitEq':>6s} {'det':>4s} tactic")
tot = {}
for r in rows:
    if r.get("kind") != "gemm":
        continue
    cb, lw, sk = r.get("cublas_us"), r.get("lowm_us"), r.get("best_skinny_us")
    cur = cb if r["M"] > 32 else (lw or cb)
    best = min(v for v in (cb, lw, sk) if v)
    t = tot.setdefault(r["M"], [0.0, 0.0])
    t[0] += cur * r["calls"] / 1e3; t[1] += best * r["calls"] / 1e3
    print(f"{r['shape']:24s} {r['M']:3d} {r['weight_MB']:7.1f} {cb or 0:8.1f} {lw or 0:8.1f} {sk or 0:8.1f} "
          f"{r.get('cublas_GBps') or 0:8d} {r.get('skinny_GBps') or 0:8d} {r['calls']:7d} "
          f"{cur * r['calls'] / 1e3:6.3f}->{best * r['calls'] / 1e3:6.3f} {str(r.get('skinny_vs_cublas_bitwise_equal')):>6s} "
          f"{str(r.get('skinny_deterministic'))[:4]:>4s} {json.dumps(r.get('best_tactic'))}")
for m, (a, b) in sorted(tot.items()):
    print(f"M={m}: dense GEMMs per target step (calls as listed) today {a:.2f} ms -> best {b:.2f} ms")
