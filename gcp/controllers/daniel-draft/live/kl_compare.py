"""Quality cost of a KV setting on Daniel's target (3-Oct-2026, daniel-draft bench): compare two runs' kl_probe.json.

Both servers scored the same 20 recorded responses teacher-forced (same token ids). Per run: mean logprob of the recorded
tokens (higher = the model finds its own past outputs likelier). Between runs: mean |delta logprob| per token, the share
of tokens whose |delta| > 0.5, and top-1 agreement (do the two servers predict the same next token). Also by prompt length.
  python kl_compare.py REF_RUN TEST_RUN
"""
import json
import subprocess
import sys

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"


def load(run):
    out = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/kl_probe.json"], capture_output=True).stdout
    d = json.loads(out)
    return d["kv"], {i["id"]: i for i in d["items"] if "error" not in i}


def main():
    (kv_a, a), (kv_b, b) = load(sys.argv[1]), load(sys.argv[2])
    ids = [i for i in a if i in b and a[i]["tokens"] == b[i]["tokens"]]
    rows = []
    for i in ids:
        la, lb, ta, tb = a[i]["logprobs"], b[i]["logprobs"], a[i]["top1"], b[i]["top1"]
        n = min(len(la), len(lb))
        pairs = [(x, y) for x, y in zip(la[:n], lb[:n]) if x is not None and y is not None]
        d = [abs(x - y) for x, y in pairs]
        agree = sum(1 for x, y in zip(ta[:n], tb[:n]) if x == y) / max(n, 1)
        rows.append((a[i]["prompt_len"], len(pairs), sum(x for x, _ in pairs) / len(pairs), sum(y for _, y in pairs) / len(pairs),
                     sum(d) / len(d), sum(1 for x in d if x > 0.5) / len(d), agree))
    tot = sum(r[1] for r in rows)
    w = lambda k: sum(r[k] * r[1] for r in rows) / tot  # noqa: E731  token-weighted
    print(f"{kv_a} vs {kv_b}: {len(rows)} requests, {tot} response tokens (common items with identical token ids)")
    print(f"  mean logprob of recorded tokens: {kv_a} {w(2):.4f} | {kv_b} {w(3):.4f}")
    print(f"  mean |delta logprob| {w(4):.4f} | tokens with |delta| > 0.5: {w(5):.2%} | top-1 agreement {w(6):.2%}")
    for lo, hi in ((0, 40000), (40000, 80000), (80000, 10 ** 9)):
        sub = [r for r in rows if lo <= r[0] < hi]
        if sub:
            t = sum(r[1] for r in sub)
            print(f"  prompts {lo // 1000}-{min(hi, 999999) // 1000}k: {len(sub)} req, |delta| {sum(r[4] * r[1] for r in sub) / t:.4f}, "
                  f"top-1 agree {sum(r[6] * r[1] for r in sub) / t:.2%}, logprob {sum(r[2] * r[1] for r in sub) / t:.4f} vs "
                  f"{sum(r[3] * r[1] for r in sub) / t:.4f}")


if __name__ == "__main__":
    main()
