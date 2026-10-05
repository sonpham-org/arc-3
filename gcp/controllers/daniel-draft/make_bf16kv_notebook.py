"""Variant of a built Daniel-notebook with the DRAFT's KV cache in bf16 (2-Oct-2026, daniel-draft).

His launcher cell passes the target's KV dtype (CFG["KVDTYPE"] = fp8_e4m3) to --speculative-draft-kv-cache-dtype too.
Our PyTorch copy of his drafter reproduces his served proposals 90.8% with exact K/V and 96.8% with K/V rounded through
fp8 e4m3: the fp8 draft cache costs 1-2.5 points of draft accuracy. This edits only that one argument to bfloat16
(about 1 KB more per KV slot, ~1 GB at his pool size); the target's KV stays fp8.

  python make_bf16kv_notebook.py --nb <built dir>/notebook.ipynb --out <dir>   (writes <dir>/notebook.ipynb, uploads it
  to gs://.../daniel-base/notebooks/<sha12>/notebook.ipynb and prints that path)
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
BUCKET = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/notebooks"
OLD = '"--speculative-draft-kv-cache-dtype", CFG["KVDTYPE"],'
NEW = '"--speculative-draft-kv-cache-dtype", "bfloat16",  # daniel-draft: bf16 draft KV (fp8 costs draft accuracy)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nb", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    nb = json.loads(a.nb.read_text(encoding="utf-8"))
    hits = []
    for i, c in enumerate(nb["cells"]):
        s = "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        if OLD in s:
            hits.append(i)
            assert s.count(OLD) == 1, (i, s.count(OLD))
            c["source"] = s.replace(OLD, NEW)
    assert len(hits) == 1, hits
    a.out.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(nb, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    (a.out / "notebook.ipynb").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = f"{BUCKET}/{sha[:12]}/notebook.ipynb"
    (a.out / "BUILD.json").write_text(json.dumps({"from": str(a.nb.resolve()), "edit": [OLD, NEW], "cell": hits[0],
                                                  "notebook_sha256": sha, "gcs_object": obj}, indent=1))
    subprocess.run(GCLOUD + ["storage", "cp", "-q", str(a.out / "notebook.ipynb"), obj], check=True)
    print(obj)


if __name__ == "__main__":
    main()
