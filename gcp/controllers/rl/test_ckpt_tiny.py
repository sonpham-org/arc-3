"""Resume test for lora_train.py --ckpt-every on a tiny random model (trainer VM, about a minute per part).

A Spot stop mid-round must cost only the records since the last checkpoint, and the resumed run must train exactly
what the unbroken run would have.
  --part one   one copy: a run stopped after step 1 and rerun into the same --out ends with the unbroken run's
               adapter (same records, same order, optimizer restored); its log has each record once (a row written
               after the checkpoint is dropped, then trained again) plus a resume row; an earlier log with no
               checkpoint is kept under a dated name; a finished run leaves no checkpoint behind.
  --part two   two copies (--dp 2): they start identical (copy 0's LoRA init is broadcast) and give the one-copy
               adapter (same global batch); a two-copy checkpoint resumes as one copy.
Exit 0 = pass. Run: python test_ckpt_tiny.py --hf /opt/m/bf16 --part one
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_trainer_tiny as tt  # noqa: E402

FAILS = []
N_RECS = 6           # accum 2: three optimizer steps


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def write_records(path: Path) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for k in range(N_RECS):
            r = tt.conversation()
            r["messages"][1]["content"][0]["text"] = f"Frame {k + 1}: what do you do?" + " Look again." * k
            r["messages"][2]["reasoning_content"] = f"Try {k}: I should test UP alone first."
            r["meta"] = {"game": f"tiny{k}"}
            fh.write(json.dumps(r) + "\n")


def tiny_checkpoint(hf: str, root: Path) -> Path:
    from transformers import AutoModelForImageTextToText
    torch.manual_seed(0)
    model = AutoModelForImageTextToText.from_config(tt.tiny_config(hf)).to(torch.bfloat16)
    ck = root / "ck"
    model.save_pretrained(ck, safe_serialization=True, max_shard_size="20MB")
    if not (ck / "model.safetensors.index.json").exists():      # single shard: write an index like the real one
        from safetensors import safe_open
        with safe_open(str(ck / "model.safetensors"), framework="pt") as sf:
            keys = list(sf.keys())
        (ck / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {k: "model.safetensors" for k in keys}}))
    return ck


def train(env: dict, out: Path, *extra: str, gpus: int = 1) -> int:
    cmd = [sys.executable, str(HERE / "lora_train.py"), "train", "--model", env["ck"], "--hf", env["hf"],
           "--records", env["recs"], "--out", str(out), "--gpus", str(gpus), "--gpu-gib", "20", "--fast", "0",
           "--offload", "0", "--rank", "4", "--alpha", "8", "--lr", "1e-3", "--warmup", "1", "--accum", "2",
           "--max-tokens", "100000", "--ckpt-every", "1", *extra]
    p = subprocess.run(cmd, capture_output=True, text=True)
    tail = "\n".join((p.stdout + p.stderr).splitlines()[-25:])
    print(f"--- {out.name} {' '.join(extra)} -> exit {p.returncode}\n{tail}", flush=True)
    return p.returncode


def rows(out: Path) -> list[dict]:
    log = out / "train_log.jsonl"
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []


def adapter(out: Path) -> dict:
    from safetensors.torch import load_file
    return load_file(str(out / "adapter_model.safetensors"))


def same_adapter(a: dict, b: dict) -> tuple[bool, str]:
    """Whole-adapter relative differences, lora_A and lora_B apart. A different start (an adapter not loaded, another
    random init) moves lora_A by ~140% (2-Oct: a two-copy run from another init: 1.42); a correct run moves it by
    well under 1%. lora_B starts at zero and Adam's first steps are about lr * sign(gradient), so kernel noise can
    flip a few near-zero entries: it gets a looser bound. Single tensors are not compared for the same reason."""
    if a.keys() != b.keys():
        return False, f"different tensors ({len(a)} vs {len(b)})"
    diff = {}
    for kind in ("lora_A", "lora_B"):
        ks = [k for k in a if kind in k]
        num = sum(float((a[k].float() - b[k].float()).pow(2).sum()) for k in ks) ** 0.5
        den = sum(float(a[k].float().pow(2).sum()) for k in ks) ** 0.5
        diff[kind] = num / max(den, 1e-12)
    trained = sum(float(a[k].float().abs().max()) > 0 for k in a if "lora_B" in k)
    ok = diff["lora_A"] <= 1e-2 and diff["lora_B"] <= 0.1 and trained > 0
    return ok, f"lora_A differs {diff['lora_A']:.2%}, lora_B {diff['lora_B']:.2%}; {trained} lora_B tensors trained"


def part_one(env: dict, root: Path) -> None:
    a, b = root / "a", root / "b"
    check("one copy, unbroken: exit 0", train(env, a) == 0)
    check("one copy, unbroken: adapter saved, no checkpoint left",
          (a / "ADAPTER.json").exists() and not (a / "ckpt.json").exists() and not list(a.glob("ckpt-*")))
    ra = [r for r in rows(a) if "loss" in r]
    check("one copy, unbroken: one row per record", len(ra) == N_RECS, str(len(ra)))

    b.mkdir()
    (b / "train_log.jsonl").write_text('{"loss": 9.9, "game": "earlier-attempt"}\n')
    check("stopped run: exit 0", train(env, b, "--stop-after", "1") == 0)
    st = json.loads((b / "ckpt.json").read_text()) if (b / "ckpt.json").exists() else {}
    check("stopped run: checkpoint after step 1 (2 records)", st.get("step") == 1 and st.get("done") == 2, str(st))
    check("stopped run: no final adapter", not (b / "ADAPTER.json").exists())
    kept = list(b.glob("train_log.2*.jsonl"))
    check("stopped run: the earlier log was kept under a dated name",
          len(kept) == 1 and "earlier-attempt" in kept[0].read_text(), str([k.name for k in kept]))
    check("stopped run: its log has the 2 records", [r.get("game") for r in rows(b)] == [r["game"] for r in ra[:2]],
          str([r.get("game") for r in rows(b)]))
    with (b / "train_log.jsonl").open("a") as fh:            # a record that finished after the checkpoint
        fh.write('{"loss": 7.7, "game": "after-checkpoint"}\n')
    check("resumed run: exit 0", train(env, b) == 0)
    rb = rows(b)
    games = [r["game"] for r in rb if "loss" in r]
    resume = [r for r in rb if "resume" in r]
    check("resumed run: each record once, in the unbroken order", games == [r["game"] for r in ra], str(games))
    check("resumed run: one resume row; the row after the checkpoint dropped",
          len(resume) == 1 and resume[0].get("rows_dropped") == 1 and "after-checkpoint" not in json.dumps(rb),
          json.dumps(resume))
    ok, detail = same_adapter(adapter(a), adapter(b))
    check("resumed run: the unbroken run's adapter", ok, detail)
    check("resumed run: same losses as the unbroken run after the checkpoint",
          all(abs(x["loss"] - y["loss"]) <= 1e-3 * max(1.0, abs(x["loss"]))
              for x, y in zip(ra[2:], [r for r in rb if "loss" in r][2:])))
    check("resumed run: no checkpoint left", not (b / "ckpt.json").exists() and not list(b.glob("ckpt-*")))


def part_two(env: dict, root: Path) -> None:
    if torch.cuda.device_count() < 2:
        check("two copies need two GPUs", False, str(torch.cuda.device_count()))
        return
    a, c, d = root / "a", root / "c", root / "d"
    if not (a / "adapter_model.safetensors").exists():
        check("one copy, unbroken (reference): exit 0", train(env, a) == 0)
    check("two copies, unbroken: exit 0 (the copies agreed after steps 1 and 2)", train(env, c, "--dp", "2", gpus=2) == 0)
    rc = [r for r in rows(c) if "loss" in r]
    check("two copies: one row per record, both copies trained",
          len(rc) == N_RECS and {r["rank"] for r in rc} == {0, 1}, str([(r["game"], r["rank"]) for r in rc]))
    if (c / "adapter_model.safetensors").exists():
        ok, detail = same_adapter(adapter(a), adapter(c))
        check("two copies: the one-copy adapter (same global batch)", ok, detail)
    check("two copies, stopped after step 1: exit 0", train(env, d, "--dp", "2", "--stop-after", "1", gpus=2) == 0)
    st = json.loads((d / "ckpt.json").read_text()) if (d / "ckpt.json").exists() else {}
    check("two copies, stopped: checkpoint at 2 records", st.get("done") == 2 and st.get("world") == 2, str(st))
    check("one copy resumes the two-copy checkpoint: exit 0", train(env, d) == 0)
    if (d / "adapter_model.safetensors").exists():
        ok, detail = same_adapter(adapter(a), adapter(d))
        check("one copy resumes the two-copy checkpoint: the one-copy adapter", ok, detail)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hf", required=True)
    ap.add_argument("--part", choices=["one", "two", "both"], default="one")
    args = ap.parse_args()
    root = Path(tempfile.mkdtemp(prefix="ckpt-tiny-"))
    write_records(root / "recs.jsonl.gz")
    env = {"hf": args.hf, "ck": str(tiny_checkpoint(args.hf, root)), "recs": str(root / "recs.jsonl.gz")}
    if args.part in ("one", "both"):
        part_one(env, root)
    if args.part in ("two", "both"):
        part_two(env, root)
    print(f"{'ALL PASS' if not FAILS else 'FAILED: ' + '; '.join(FAILS)} ({root})", flush=True)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
