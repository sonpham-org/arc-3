"""Compare greedy_check.json of two bench runs (3-Oct-2026, daniel-draft kernels; add_greedy_cell.py).

Per run: pass1 vs pass2 inside the same server (its own nondeterminism floor). Across runs: pass1 vs pass1.
For each prompt pair: identical-token prefix length (first divergence), and on that common prefix the decode-time
logprob difference (mean / max |delta|). Equal tokens + |delta| at the floor's size = lossless at fp noise.
  python greedy_compare.py CONTROL_RUN TEST_RUN
"""
import json
import subprocess
import sys

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"


def load(run):
    raw = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/greedy_check.json"], capture_output=True).stdout
    return json.loads(raw)


def pair(xs, ys):
    rows = []
    for x, y in zip(xs, ys):
        assert x["id"] == y["id"]
        n = 0
        while n < min(len(x["ids"]), len(y["ids"])) and x["ids"][n] == y["ids"][n]:
            n += 1
        d = [abs(a - b) for a, b in zip(x["lp"][:n], y["lp"][:n]) if a is not None and b is not None]
        rows.append({"prefix": n, "len": min(len(x["ids"]), len(y["ids"])), "mean_dlp": sum(d) / len(d) if d else None,
                     "max_dlp": max(d) if d else None, "exact_lp": sum(1 for v in d if v == 0) / len(d) if d else None})
    full = sum(1 for r in rows if r["prefix"] == r["len"])
    md = [r["mean_dlp"] for r in rows if r["mean_dlp"] is not None]
    mx = [r["max_dlp"] for r in rows if r["max_dlp"] is not None]
    ex = [r["exact_lp"] for r in rows if r["exact_lp"] is not None]
    return {"prompts": len(rows), "identical_outputs": full,
            "mean_common_prefix": round(sum(r["prefix"] for r in rows) / len(rows), 1),
            "mean_abs_dlogprob": round(sum(md) / len(md), 6) if md else None,
            "max_abs_dlogprob": round(max(mx), 5) if mx else None,
            "share_bitwise_equal_logprobs": round(sum(ex) / len(ex), 4) if ex else None,
            "first_divergence": [r["prefix"] for r in rows]}


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    out = {"control_floor (pass1 vs pass2)": pair(a["passes"][0]["items"], a["passes"][1]["items"]),
           "test_floor (pass1 vs pass2)": pair(b["passes"][0]["items"], b["passes"][1]["items"]),
           "control vs test (pass1)": pair(a["passes"][0]["items"], b["passes"][0]["items"]),
           "control vs test (pass2)": pair(a["passes"][1]["items"], b["passes"][1]["items"])}
    for k, v in out.items():
        print(f"{k:32s} {json.dumps(v)}")


if __name__ == "__main__":
    main()
