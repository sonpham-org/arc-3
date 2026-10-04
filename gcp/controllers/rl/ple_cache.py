"""Per-record n-gram (PLE) embeddings, computed once, so training processes never hold the n-gram table.

Author: Claude Opus 5.5 (4-Oct-2026, Son: "optimize the recipe to the teeth"). One model copy per GPU needs four
copies' worth of host RAM, and each copy materializes the n-gram table (~95 GiB in the HF checkpoint's 20M-row-
base config; the trainer's /opt/m/bf16 holds a 10M x 160 table, ~3.2 GB, where this is optional) although nothing
about it trains: its output depends only on the record's token ids (hashed n-grams -> rows of a frozen embedding).
So:
  precompute   ONE CPU process builds the PLE layer's n-gram embedding exactly as the model builds it (the decoder
               layer's own Qwen4ExpTextNGramEmbedding, its 128 shards concatenated on dim 0 as transformers'
               WeightConverter does), runs it on every record's rendered ids, writes <cache>/<record id>.L<layer>.pt
               (BF16 [1, S, ple_embed_dim], ~590 MB at 115k tokens), and exits.
  install      in each training process, BEFORE from_pretrained: the n-gram embedding is built with a 1-row
               placeholder table, and its forward returns the cached tensor of the current record (set_record).
  model_dir    the checkpoint dir seen by from_pretrained without the 128 shard keys (symlinks + a filtered index),
               so nothing reads or allocates the table.
check_against(model, ...) compares the cache with the live module on a loaded model (exact equality expected).

  python ple_cache.py precompute --model /opt/m/bf16 --hf /opt/m/bf16 --records '<glob>' --out /opt/m/work/ple/<job>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import torch
from torch import nn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TABLE_PART = ".ple.ple_embedding.ngram_embedding."          # every key of the n-gram table (row shards or one tensor)
SHARD_KEY = TABLE_PART + "shard_"                            # the HF checkpoint: 128 row shards (~95 GiB)
TABLE_KEY = TABLE_PART + "weight"                            # a checkpoint saved as one tensor


def is_table_key(k: str) -> bool:
    return TABLE_PART in k


def _shard_no(k: str) -> int:
    m = re.search(r"(\d+)(?:\.weight)?$", k.split(TABLE_PART, 1)[1])
    return int(m.group(1)) if m else -1
_STATE: dict = {"cache": None, "record": None, "installed": False, "orig_init": None, "orig_fwd": None}


def _m():
    from transformers.models.qwen4_exp import modeling_qwen4_exp as m
    return m


def ple_layers(model_dir: str | Path) -> list[int]:
    wm = json.loads((Path(model_dir) / "model.safetensors.index.json").read_text())["weight_map"]
    return sorted({int(k.split(".")[3]) for k in wm if is_table_key(k)})


# ------------------------------------------------------------------------------------------------ precompute
def build_table_module(model_dir: str | Path, layer: int):
    """The decoder layer's own n-gram embedding module (indices, multipliers) with its full table on the CPU."""
    from accelerate import init_empty_weights
    from safetensors import safe_open
    from transformers import AutoConfig
    m = _m()
    cfg = AutoConfig.from_pretrained(str(model_dir))
    tc = cfg.get_text_config() if hasattr(cfg, "get_text_config") else cfg.text_config
    with init_empty_weights():                        # params on meta; buffers (multipliers, offsets) are real
        dec = m.Qwen4ExpTextDecoderLayer(tc, layer_idx=layer)
    mod = dec.ple.ple_embedding
    wm = json.loads((Path(model_dir) / "model.safetensors.index.json").read_text())["weight_map"]
    pre = f"model.language_model.layers.{layer}{TABLE_PART}"
    shards = sorted((_shard_no(k), k) for k in wm if k.startswith(pre))       # row shards in order (or one tensor)
    rows, dim = mod.ngram_embedding.weight.shape
    table = torch.empty(rows, dim, dtype=torch.bfloat16)
    at = 0
    for _, key in shards:
        with safe_open(str(Path(model_dir) / wm[key]), framework="pt") as sf:
            t = sf.get_tensor(key)
        table[at:at + t.shape[0]].copy_(t)
        at += t.shape[0]
    if at != rows:
        raise RuntimeError(f"layer {layer}: shards give {at} rows, the module wants {rows}")
    mod.ngram_embedding = nn.Embedding.from_pretrained(table, freeze=True)
    # the checkpoint also stores the multipliers the model would rebuild: they must agree
    mk = f"model.language_model.layers.{layer}.ple.ple_embedding.layer_multipliers"
    if mk in wm:
        with safe_open(str(Path(model_dir) / wm[mk]), framework="pt") as sf:
            stored = sf.get_tensor(mk)
        if not torch.equal(stored.to(mod.layer_multipliers.dtype), mod.layer_multipliers):
            raise RuntimeError(f"layer {layer}: rebuilt layer_multipliers differ from the checkpoint's")
    return mod.eval()


@torch.no_grad()
def precompute(model_dir: str, hf: str, records: list[dict], out: str | Path) -> dict:
    import lora_train
    import render
    from transformers import AutoProcessor
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    processor = AutoProcessor.from_pretrained(hf)
    t0 = time.time()
    mods = {layer: build_table_module(model_dir, layer) for layer in ple_layers(model_dir)}
    built = time.time() - t0
    n = 0
    for rec in records:
        ids = torch.tensor([render.render(processor, rec, add_generation_prompt=False)["input_ids"]], dtype=torch.long)
        key = lora_train.id_of(rec)
        for layer, mod in mods.items():
            p = out / f"{key}.L{layer}.pt"
            if p.exists():
                continue
            emb = mod(ids, None).to(torch.bfloat16).contiguous()
            torch.save({"emb": emb, "tokens": ids.shape[1]}, p)
        n += 1
    rep = {"records": n, "layers": sorted(mods), "build_s": round(built, 1), "total_s": round(time.time() - t0, 1),
           "out": str(out)}
    (out / "PLE_CACHE.json").write_text(json.dumps(rep, indent=1))
    return rep


# ------------------------------------------------------------------------------------------------ training side
def _link(dst: Path, src: Path) -> None:
    """Symlink (Linux VMs); a hard link or a copy where symlinks need privileges (Windows tests)."""
    try:
        dst.symlink_to(src.resolve())
    except OSError:
        try:
            os.link(src, dst)
        except OSError:
            import shutil
            shutil.copy2(src, dst)


def model_view(model_dir: str | Path, out: str | Path, drop_table: bool = True, drop_experts: bool = False) -> Path:
    """A checkpoint dir without the n-gram table and/or the BF16 routed experts, so from_pretrained never reads them.
    transformers 5.18 reads EVERY tensor of each file it opens (4-Oct: a symlinked view with a filtered index still
    pulled in the table shards and the BF16 experts that share files with needed weights: ~100 GB of table per copy,
    and four copies loading at once were OOM-killed). So: files whose tensors are all kept are symlinked, files that
    mix kept and dropped tensors are rewritten with the kept ones only, files with nothing kept are left out. Built
    once (by the --dp parent); ~9 GB of dense weights when both are dropped."""
    from safetensors import safe_open
    from safetensors.torch import save_file
    src, out = Path(model_dir), Path(out)
    if (out / "model.safetensors.index.json").exists():      # built already
        return out
    tmp = out.with_name(out.name + ".partial")
    tmp.mkdir(parents=True, exist_ok=True)
    idx = json.loads((src / "model.safetensors.index.json").read_text())
    wm = idx["weight_map"]

    def keep(k: str) -> bool:
        if drop_table and is_table_key(k):
            return False
        if drop_experts and ".mlp.experts." in k:
            return False
        return True
    by_file: dict[str, list[str]] = {}
    for k, f in wm.items():
        by_file.setdefault(f, []).append(k)
    new_wm, written, linked = {}, 0, 0
    for f, keys in sorted(by_file.items()):
        kept = [k for k in keys if keep(k)]
        if not kept:
            continue
        if len(kept) == len(keys):
            link = tmp / f
            if not link.exists():
                _link(link, src / f)
            new_wm.update({k: f for k in kept})
            linked += 1
            continue
        name = f"view-{f}"
        with safe_open(str(src / f), framework="pt") as sf:
            tensors = {k: sf.get_tensor(k).contiguous() for k in kept}
        save_file(tensors, str(tmp / name), metadata={"format": "pt"})
        new_wm.update({k: name for k in kept})
        written += 1
    for f in src.iterdir():                                   # config, tokenizer, chat template, processor files
        if f.suffix != ".safetensors" and f.name != "model.safetensors.index.json" and not f.name.startswith("."):
            link = tmp / f.name
            if not link.exists():
                _link(link, f)
    idx["weight_map"] = new_wm
    (tmp / "model.safetensors.index.json").write_text(json.dumps(idx))
    (tmp / "VIEW.json").write_text(json.dumps({"source": str(src), "drop_table": drop_table,
                                               "drop_experts": drop_experts, "files_linked": linked,
                                               "files_rewritten": written, "keys": len(new_wm)}, indent=1))
    tmp.rename(out)                                           # atomic: a half-built view is never used
    return out


def default_view_dir(model_dir: str | Path, drop_table: bool, drop_experts: bool) -> Path:
    """The box-wide view next to the model (built once, reused by every job)."""
    p = Path(model_dir)
    tag = "-".join(t for t, on in (("notable", drop_table), ("noexperts", drop_experts)) if on)
    return p.with_name(f"{p.name}-view-{tag}")


def model_dir_without_table(model_dir: str | Path, out: str | Path) -> Path:
    return model_view(model_dir, out, drop_table=True, drop_experts=False)


def install(cache_dir: str | Path) -> None:
    """Placeholder table + cached forward for every Qwen4ExpTextNGramEmbedding built from now on."""
    m = _m()
    _STATE["cache"] = Path(cache_dir)
    if _STATE["installed"]:
        return
    cls = m.Qwen4ExpTextNGramEmbedding
    _STATE["orig_init"], _STATE["orig_fwd"] = cls.__init__, cls.forward
    orig_init = cls.__init__

    def __init__(self, config, embedding_dim, layer_idx, ple_layer_index=0):
        orig_init(self, config, embedding_dim, layer_idx, ple_layer_index)
        self.ngram_embedding = nn.Embedding(1, self.ngram_embedding.embedding_dim)     # 1 row: never looked up

    def forward(self, input_ids, past_key_values=None):
        if past_key_values is not None:
            raise RuntimeError("ple_cache: training only (no generation cache)")
        if _STATE["record"] is None:
            raise RuntimeError("ple_cache: set_record(<record id>) before the forward")
        p = _STATE["cache"] / f"{_STATE['record']}.L{self.layer_idx}.pt"
        d = torch.load(p, map_location="cpu")
        if d["tokens"] != input_ids.shape[1]:
            raise RuntimeError(f"ple_cache: {p.name} has {d['tokens']} tokens, the batch {input_ids.shape[1]}")
        return d["emb"].to(input_ids.device, non_blocking=True)

    cls.__init__, cls.forward = __init__, forward
    _STATE["installed"] = True


def set_record(key: str | None) -> None:
    _STATE["record"] = key


@torch.no_grad()
def check_against(model, processor, rec: dict, cache_dir: str | Path) -> dict:
    """On a model loaded the usual way (live table): the cached embedding == the live module's output."""
    import lora_train
    import render
    m = _m()
    ids = torch.tensor([render.render(processor, rec, add_generation_prompt=False)["input_ids"]], dtype=torch.long)
    key = lora_train.id_of(rec)
    out = {}
    for name, mod in model.named_modules():
        if isinstance(mod, m.Qwen4ExpTextNGramEmbedding):
            live = mod(ids, None).float().cpu()
            cached = torch.load(Path(cache_dir) / f"{key}.L{mod.layer_idx}.pt", map_location="cpu")["emb"].float()
            out[name] = {"equal": bool(torch.equal(live, cached)), "max_abs": float((live - cached).abs().max())}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["precompute"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--hf", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import lora_train
    print(json.dumps(precompute(a.model, a.hf, lora_train.load_records(a.records), a.out)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
