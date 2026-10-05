"""Hot-swap the served model between RL rounds without restarting SGLang (4-Oct-2026, Son: "we should do hot-swapping
now ... the main point is to have GPU always occupied"; gcp/controllers/rl/box/README.md).

Runs INSIDE the rollout notebook's container, as a subprocess of the rollout server (rollout_driver.serve_sessions), so
the notebook kernel that forks the game children never imports torch or touches CUDA. Run it with the server's own
venv python (/tmp/sgl-intel/venv/bin/python: torch + safetensors); it needs no sglang import and no CUDA. Daniel's SGLang build (0.5.19
fork) has every piece; the launcher adds --enable-memory-saver --enable-weights-cpu-backup (build_rl_notebook.py
--hotswap):
  sleep   POST /release_memory_occupation: weights (backed up to host RAM), KV cache and CUDA graph memory leave the
          card, so the box's trainer can use it; virtual addresses stay mapped, so the captured CUDA graphs stay valid
  wake    POST /resume_memory_occupation: everything back (the KV cache empty)
  apply   POST /update_weights_from_tensor, load_format None = model.load_weights(named tensors) and nothing else.
          The RL LoRA only changes ~300 plain bf16 projection weights (MERGE_REPORT.json "tensors"); the delta file
          holds their merged values (absolute, not differences), so applying it to ANY earlier round's weights gives
          this round's model. NOT /update_weights_from_disk: that one re-runs every module's
          process_weights_after_loading, which would repack the already-repacked 4-bit experts.
          Tensors go by shared memory (torch file_system strategy: a /dev/shm name in the request, not the bytes).
  check   POST /get_weights_by_name on the first delta tensor: the served values must equal the file's (best effort:
          a fused parameter has another name; then only the update calls' own success counts).
CLI (what serve_sessions runs):
  python hotswap.py apply <delta.safetensors> <server url> [--chunk-gb 2]   -> one JSON line, exit 0 when verified
  python hotswap.py sleep|wake <server url>                                -> one JSON line
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def post(url: str, path: str, body: dict | None = None, timeout: float = 1800.0) -> tuple[int, str]:
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def sleep(url: str) -> dict:
    t = time.time()
    code, text = post(url, "/release_memory_occupation", {})
    return {"op": "sleep", "ok": code == 200, "code": code, "s": round(time.time() - t, 1), "text": text[:300]}


def wake(url: str) -> dict:
    t = time.time()
    code, text = post(url, "/resume_memory_occupation", {})
    return {"op": "wake", "ok": code == 200, "code": code, "s": round(time.time() - t, 1), "text": text[:300]}


def apply(delta: str, url: str, chunk_gb: float = 2.0) -> dict:
    import base64
    import io
    from multiprocessing.reduction import ForkingPickler

    import torch
    import torch.multiprocessing as mp       # registers torch's ForkingPickler reductions
    from safetensors import safe_open
    mp.set_sharing_strategy("file_system")

    def serialize(obj) -> str:              # = sglang MultiprocessingSerializer.serialize(obj, output_str=True)
        buf = io.BytesIO()
        ForkingPickler(buf).dump(obj)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    t = time.time()
    out = {"op": "apply", "delta": delta, "tensors": 0, "bytes": 0, "posts": 0}
    with safe_open(delta, framework="pt", device="cpu") as f:
        names = sorted(f.keys())
        first = names[0]
        batch, size = [], 0

        def send(last: bool) -> None:
            nonlocal batch, size
            if not batch:
                return
            payload = serialize(batch)
            code, text = post(url, "/update_weights_from_tensor",
                              {"serialized_named_tensors": [payload], "load_format": None, "flush_cache": last})
            if code != 200 or '"success":true' not in text.replace(" ", ""):
                raise RuntimeError(f"update_weights_from_tensor: {code} {text[:400]}")
            out["posts"] += 1
            batch, size = [], 0

        for n in names:
            x = f.get_tensor(n).contiguous().share_memory_()
            batch.append((n, x))
            size += x.numel() * x.element_size()
            out["tensors"] += 1
            out["bytes"] += x.numel() * x.element_size()
            if size >= chunk_gb * 2**30:
                send(False)
        send(True)
        want = f.get_tensor(first).flatten()[:8].float().tolist()
    # read-back check, best effort: the served parameter can be a fused one under another name (then no check)
    code, text = post(url, "/get_weights_by_name", {"name": first, "truncate_size": 1})
    got = None
    if code == 200:
        try:
            v = json.loads(text)
            while isinstance(v, list) and v and isinstance(v[0], list):
                v = v[0]
            got = [float(x) for x in v][:8] if isinstance(v, list) else None
        except (ValueError, TypeError):
            got = None
    out["verified"] = None if not got else all(abs(a - b) <= 1e-2 * max(1.0, abs(b)) for a, b in zip(got, want))
    out.update(ok=True, check_name=first, check_code=code, want=want[:4], got=(got or [])[:4],
               s=round(time.time() - t, 1))
    del torch
    return out


def main(argv: list[str]) -> int:
    op = argv[1] if len(argv) > 1 else ""
    try:
        if op == "apply":
            chunk = float(argv[argv.index("--chunk-gb") + 1]) if "--chunk-gb" in argv else 2.0
            res = apply(argv[2], argv[3], chunk)
            ok = res["ok"] and res["verified"] is not False      # None = no read-back possible, posts all succeeded
        elif op in ("sleep", "wake"):
            res = (sleep if op == "sleep" else wake)(argv[2])
            ok = res["ok"]
        else:
            print(__doc__)
            return 2
    except Exception as e:  # noqa: BLE001 - one JSON line either way, for the caller's log
        res, ok = {"op": op, "ok": False, "error": f"{type(e).__name__}: {e}"[:600]}, False
    print(json.dumps(res), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
