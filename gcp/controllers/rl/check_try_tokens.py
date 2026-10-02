"""Exact-token check on OUR serving build, from try results (plan §11; §9a did it for Daniel's SGLang 0.5.19).

Every live request of a try, rendered the way the trainer renders it, must have exactly the prompt token count the
server reported for it. The try results carry the server's usage per live request (try_driver.py, 2-Oct) and each
try's lake episode holds its exact requests. Both tool-serialization profiles are tried; the report says which one
is exact on this build.

  python check_try_tokens.py --campaign rl-1002a --hf /opt/m/bf16 [--max-tries 8] [--out report.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lake  # noqa: E402
import render  # noqa: E402

ROOT = "gs://cellens-ai-artifacts/arc3-rl/tries"
PROFILES = ("sglang-0.5.19", "as-sent")


def gcat(uri: str) -> bytes | None:
    p = subprocess.run(["gcloud", "storage", "cat", uri], capture_output=True)
    return p.stdout if p.returncode == 0 else None


def gls(prefix: str) -> list[str]:
    p = subprocess.run(["gcloud", "storage", "ls", prefix], capture_output=True, text=True)
    return [l.strip() for l in p.stdout.splitlines() if l.strip()] if p.returncode == 0 else []


class GcsBlobs:
    def __init__(self, cache: Path):
        self.cache = cache

    def get(self, sha: str) -> bytes:
        p = self.cache / sha
        if not p.exists():
            raw = gcat(f"{lake.LAKE_ROOT}/blobs/{sha[:2]}/{sha}")
            if raw is None:
                raise FileNotFoundError(sha)
            p.write_bytes(raw)
        return p.read_bytes()


def check_try(processor, rec: dict, blobs: GcsBlobs, tmp: Path) -> list[dict]:
    uri = (rec.get("try_doc") or {}).get("payload_uri")
    if not uri or not rec.get("usage"):
        return []
    raw = gcat(uri)
    if raw is None:
        return []
    ep = tmp / "episode.jsonl.gz"
    ep.write_bytes(raw)
    lines = lake.read_episode(ep)
    usage_by_step: dict[int, list[dict]] = defaultdict(list)
    for u in rec["usage"]:
        usage_by_step[int(u.get("step") or 0)].append(u)
    seen: dict[int, int] = defaultdict(int)
    tools = None
    out = []
    for c, msgs, _reply in lake.call_messages(lines, blobs.get):
        tools = c.get("tools") or tools
        step = int(c.get("turn") or 0)
        k = seen[step]
        seen[step] += 1
        us = usage_by_step.get(step, [])
        if k >= len(us) or not (us[k].get("usage") or {}).get("prompt_tokens"):
            continue
        logged = int(us[k]["usage"]["prompt_tokens"])
        row = {"try": rec["try_id"], "step": step, "k": k, "logged": logged}
        for prof in PROFILES:
            r = render.render(processor, {"messages": msgs, "tools": tools,
                                          "chat_template_kwargs": c.get("chat_template_kwargs")},
                              add_generation_prompt=True, profile=prof)
            row[prof] = len(r["input_ids"]) - logged
        out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--hf", required=True)
    ap.add_argument("--max-tries", type=int, default=8)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    from transformers import AutoProcessor
    processor = AutoProcessor.from_pretrained(a.hf)
    tmp = Path(tempfile.mkdtemp())
    (tmp / "blobs").mkdir()
    blobs = GcsBlobs(tmp / "blobs")
    rows = []
    n = 0
    for uri in gls(f"{ROOT}/{a.campaign}/results/"):
        if not uri.endswith(".json") or uri.endswith("._error.json"):
            continue
        rec = json.loads(gcat(uri) or b"{}")
        if not (rec.get("outcome") or {}).get("valid"):
            continue
        got = check_try(processor, rec, blobs, tmp)
        if got:
            rows += got
            n += 1
            print(rec["try_id"], {p: sorted({r[p] for r in got}) for p in PROFILES}, flush=True)
        if n >= a.max_tries:
            break
    summary = {p: {"requests": len(rows), "exact": sum(r[p] == 0 for r in rows),
                   "diffs": sorted({r[p] for r in rows})[:10]} for p in PROFILES}
    print("SUMMARY", json.dumps(summary), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    return 0 if rows and any(s["exact"] == s["requests"] for s in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
