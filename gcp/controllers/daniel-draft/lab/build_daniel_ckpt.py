"""Build the trainer's checkpoint dir for Daniel Franzen's MTP drafter (2-Oct-2026, daniel-draft lab).

train_draft.py / verify_draft.py (lobotomy/mtp) read one checkpoint dir through model.safetensors.index.json: the dense
mtp.* tensors (draft_torch.MAP), the fused routed experts (draft_torch.EXPERTS), embed + lm_head (SHARED) and the
TARGET's final mixer (model.language_model.hyper_connection_mixer.*). Built here from Daniel's own files only:
  - dense mtp.*, embed, lm_head: his drafter's mtp-dense.safetensors as-is (symlinked; same tensor names);
  - routed experts: his drafter's compressed-tensors pack-quantized INT4 (g32, symmetric) experts, dequantized
    (q * scale, BF16: the weights his server multiplies with) and fused as gate_up [E, 2I, H] = [gate; up], down [E, H, I];
  - target mixer: his AutoRound target's model-00017 shard (BF16; AutoRound quantized only the decoder layers).
Checks (OUT/build.json; a failed check exits non-zero):
  - every dequantized expert against the AutoRound checkpoint's own BF16 MTP experts (cosine: RTN g32 error only;
    a wrong nibble order or scale layout gives ~0);
  - lm_head: the drafter's copy equals the target's (train_draft scores the target with the draft's lm_head);
  - dense: the drafter's mtp.* against the AutoRound mtp.* (informational: both should be the stock weights).
Also writes OUT/mask.pt (all 512 experts kept) for --mask.

  python build_daniel_ckpt.py --drafter DRAFTER_DIR --target AUTOROUND_DIR --out OUT_DIR
"""
import argparse
import json
import os
import struct
import sys
from pathlib import Path

import torch
from safetensors.torch import save_file

E, I, H, GROUP = 512, 640, 2560, 32
DT = {"BF16": torch.bfloat16, "F16": torch.float16, "F32": torch.float32, "I32": torch.int32, "I64": torch.int64}
EXPERTS = ("mtp.layers.0.mlp.experts.gate_up_proj", "mtp.layers.0.mlp.experts.down_proj")
MIXER = [f"model.language_model.hyper_connection_mixer.{n}.weight" for n in ("hc_norm", "input_mix_weight_down",
                                                                           "input_mix_weight_up")]


class ST:
    """One safetensors file, tensors read on demand (plain seek + read)."""

    def __init__(self, path):
        self.path = Path(path)
        with open(path, "rb") as f:
            (hl,) = struct.unpack("<Q", f.read(8))
            self.head = json.loads(f.read(hl))
        self.head.pop("__metadata__", None)
        self.base = 8 + hl
        self.f = open(path, "rb")

    def get(self, n):
        info = self.head[n]
        a, b = info["data_offsets"]
        self.f.seek(self.base + a)
        buf = bytearray(self.f.read(b - a))
        return torch.frombuffer(buf, dtype=DT[info["dtype"]]).reshape(info["shape"])


SHIFTS = torch.arange(0, 32, 4, dtype=torch.int32)


def dequant(st, n):
    """compressed-tensors pack-quantized int4: 8 values per int32 along the input dim, value k at bits 4k (stored as
    q + 8); weight = q * scale[:, col // GROUP]."""
    pk = st.get(n + ".weight_packed")
    sc = st.get(n + ".weight_scale")
    shape = tuple(st.get(n + ".weight_shape").tolist())
    q = ((pk.unsqueeze(-1) >> SHIFTS) & 0xF).reshape(pk.shape[0], -1) - 8
    assert tuple(q.shape) == shape and sc.shape == (shape[0], shape[1] // GROUP), (n, q.shape, shape, sc.shape)
    return (q.float() * sc.float().repeat_interleave(GROUP, dim=1)).to(torch.bfloat16)


def cos(a, b):
    a, b = a.float().flatten(), b.float().flatten()
    return float(a @ b / (a.norm() * b.norm()).clamp_min(1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafter", type=Path, required=True)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-cos", type=float, default=0.98, help="per-expert floor vs the BF16 MTP experts")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    dwm = json.loads((a.drafter / "model.safetensors.index.json").read_text())["weight_map"]
    twm = json.loads((a.target / "model.safetensors.index.json").read_text())["weight_map"]
    dense_file = "mtp-dense.safetensors"
    dense_names = sorted(n for n, f in dwm.items() if f == dense_file)
    ex_files = sorted({f for f in dwm.values() if f != dense_file})
    assert len(ex_files) == 1, ex_files
    ex = ST(a.drafter / ex_files[0])
    dense = ST(a.drafter / dense_file)
    extra = ST(a.target / twm["mtp.layers.0.mlp.experts.0.gate_proj.weight"])
    tshard = twm["lm_head.weight"]
    assert all(twm[n] == tshard for n in MIXER), [twm[n] for n in MIXER]
    tgt = ST(a.target / tshard)
    report = {"drafter": str(a.drafter), "target": str(a.target), "dense_tensors": len(dense_names)}

    gu = torch.empty(E, 2 * I, H, dtype=torch.bfloat16)
    dn = torch.empty(E, H, I, dtype=torch.bfloat16)
    cmin, csum, worst = 1.0, 0.0, None
    for e in range(E):
        p = f"mtp.layers.0.mlp.experts.{e}."
        for proj, dst in (("gate_proj", gu[e, :I]), ("up_proj", gu[e, I:]), ("down_proj", dn[e])):
            w = dequant(ex, p + proj)
            dst.copy_(w)
            c = cos(w, extra.get(p + proj + ".weight"))
            csum += c
            if c < cmin:
                cmin, worst = c, p + proj
        if e % 64 == 0:
            print(f"experts {e}/{E} min_cos={cmin:.5f}", flush=True)
    report["experts"] = {"min_cos_vs_bf16": round(cmin, 6), "mean_cos_vs_bf16": round(csum / (3 * E), 6),
                         "worst": worst}
    save_file({EXPERTS[0]: gu.contiguous(), EXPERTS[1]: dn.contiguous()}, str(a.out / "experts-bf16.safetensors"),
              metadata={"format": "pt", "source": "dequantized from " + ex_files[0]})
    del gu, dn

    lm_d, lm_t = dense.get("lm_head.weight"), tgt.get("lm_head.weight")
    report["lm_head_equal"] = bool(lm_d.shape == lm_t.shape and torch.equal(lm_d, lm_t))
    report["lm_head_cos"] = round(cos(lm_d, lm_t), 6) if lm_d.shape == lm_t.shape else None
    del lm_d, lm_t
    dense_vs = {}
    for n in dense_names:
        if n.startswith("mtp.") and n in extra.head:
            x, y = dense.get(n), extra.get(n)
            dense_vs[n] = "equal" if torch.equal(x, y) else round(cos(x, y), 6)
    report["dense_vs_autoround_mtp"] = {"equal": sum(v == "equal" for v in dense_vs.values()), "of": len(dense_vs),
                                        "differ": {k: v for k, v in dense_vs.items() if v != "equal"}}

    for name, src in ((dense_file, a.drafter / dense_file), ("target-" + tshard, a.target / tshard)):
        link = a.out / name
        if link.is_symlink() or link.exists():
            link.unlink()
        os.symlink(src.resolve(), link)
    wm = {n: dense_file for n in dense_names}
    wm.update({n: "experts-bf16.safetensors" for n in EXPERTS})
    wm.update({n: "target-" + tshard for n in MIXER})
    (a.out / "model.safetensors.index.json").write_text(json.dumps({"metadata": {}, "weight_map": wm}, indent=1))
    torch.save({"mtp": torch.zeros(E, dtype=torch.bool)}, a.out / "mask.pt")

    ok = cmin >= a.min_cos and report["lm_head_equal"]
    report["ok"] = ok
    (a.out / "build.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report), flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
