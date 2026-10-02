"""The served NVFP4 routed experts inside the HF trainer (plan §3: train through what the rollout server computes).

The RadixArk checkpoint we serve (modelopt NVFP4, 2-Oct: gs://cellens-ai-artifacts/arc3-duck/models/
qwen3.8-flash-next-nvfp4-radixark/7b71922...) stores each routed expert as gate/up/down projections of
  weight          uint8 [out, in/2]      two fp4 (e2m1) codes per byte, element 2i in the low nibble
  weight_scale    float8_e4m3fn [out, in/16]   one scale per 16-element block
  weight_scale_2  float32 scalar         the projection's global scale
  input_scale     float32 scalar         the activation global scale (the server also quantizes activations)
Everything else (attention, linear attention, shared expert, router, hyper-connections) is BF16 and byte-identical
to the official checkpoint, so the trainer loads those from the BF16 model and only the experts from here.

Memory: packed experts are ~1.4 GB per layer instead of 4.5 GB in BF16 (~37 GB less per GPU on 4 GPUs), which is
what lets ~100k-token records train. Each forward (and each checkpoint replay) unpacks one layer's 512 experts to
BF16 (~5 GB, freed after the layer) and runs the model's own grouped_mm expert code on them.

Activations: weights match the server exactly; activations stay BF16 here (W4A16). The server's NVFP4 activation
rounding is not reproduced yet (ARC3_NVFP4_ACT is reserved for that); the trainer-vs-server log-prob check measures
the gap.

Use: install_placeholder() BEFORE from_pretrained (the expert keys of the BF16 checkpoint are then skipped and never
take memory), then load_packed(model, nvfp4_dir) after it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import torch
from torch import nn
from torch.utils.checkpoint import checkpoint

FP4_VALUES = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, -0.0, -0.5, -1.0, -1.5, -2.0, -3.0, -4.0, -6.0]
CHUNK = int(os.environ.get("ARC3_NVFP4_CHUNK", "32"))          # experts unpacked per step (bounds the fp32 scratch)
TOKEN_CHUNK = int(os.environ.get("ARC3_MOE_TOKEN_CHUNK", "16384"))   # tokens per expert pass (bounds activations)
_STATE = {"orig": None}


def _m():
    from transformers.models.qwen4_exp import modeling_qwen4_exp as m
    return m


_LUT2: dict = {}


def _byte_lut(device, low_first: bool) -> torch.Tensor:
    """[256, 2] float32: the two fp4 values of every packed byte (one gather per byte, no stack)."""
    key = (str(device), low_first)
    if key not in _LUT2:
        v = torch.tensor(FP4_VALUES, dtype=torch.float32)
        b = torch.arange(256)
        lo, hi = v[b & 0x0F], v[b >> 4]
        _LUT2[key] = (torch.stack((lo, hi) if low_first else (hi, lo), dim=-1)).to(device)
    return _LUT2[key]


def dequant(q: torch.Tensor, s: torch.Tensor, s2_rows: torch.Tensor, out_dtype=torch.bfloat16,
            chunk: int = 0, low_first: bool = True) -> torch.Tensor:
    """q uint8 [E, R, C/2], s float8 [E, R, C/16], s2_rows float32 [E, R] -> [E, R, C] in out_dtype."""
    e, r, half = q.shape
    c = half * 2
    lut2 = _byte_lut(q.device, low_first)
    out = torch.empty(e, r, c, dtype=out_dtype, device=q.device)
    chunk = chunk or CHUNK
    for a in range(0, e, chunk):
        b = min(e, a + chunk)
        vals = lut2[q[a:b].long()].view(b - a, r, c // 16, 16)                   # [n, R, C/16, 16]
        sc = s[a:b].float() * s2_rows[a:b, :, None]
        torch.mul(vals, sc[..., None], out=vals)
        out[a:b] = vals.view(b - a, r, c)
    return out


GPTQ_GROUP = int(os.environ.get("ARC3_GPTQ_GROUP", "128"))
# auto_gptq "v1" packing stores each zero point minus 1 (a symmetric int4 zero of 8 is stored as 7): test_nvfp4.py
# --format gptq checks which convention Daniel's checkpoint uses against the BF16 experts.
GPTQ_ZERO_OFFSET = int(os.environ.get("ARC3_GPTQ_ZERO_OFFSET", "1"))


def dequant_gptq(qw: torch.Tensor, qz: torch.Tensor, s: torch.Tensor, out: torch.Tensor | None = None,
                 group: int = 0, zero_offset: int | None = None, chunk: int = 0) -> torch.Tensor:
    """GPTQ int4 (AutoRound "auto_round:auto_gptq"): qw int32 [E, in/8, out] (input row 8k+j in bits 4j..4j+3),
    qz int32 [E, G, out/8] (output column 8c+j in bits 4j), s [E, G, out] -> [E, out, in] (nn.Linear layout).
    W[o, i] = (q[i, o] - (z[g(i), o] + zero_offset)) * s[g(i), o], g(i) = i // group."""
    e, in8, n_out = qw.shape
    n_in = in8 * 8
    group = group or GPTQ_GROUP
    zo = GPTQ_ZERO_OFFSET if zero_offset is None else zero_offset
    n_g = n_in // group
    if out is None:
        out = torch.empty(e, n_out, n_in, dtype=torch.bfloat16, device=qw.device)
    shifts = torch.arange(0, 32, 4, device=qw.device, dtype=torch.int32)
    chunk = chunk or CHUNK
    for a in range(0, e, chunk):
        b = min(e, a + chunk)
        q = ((qw[a:b].unsqueeze(2) >> shifts.view(1, 1, 8, 1)) & 0xF).reshape(b - a, n_g, group, n_out)
        z = ((qz[a:b].unsqueeze(-1) >> shifts.view(1, 1, 1, 8)) & 0xF).reshape(b - a, n_g, n_out) + zo
        w = (q.float() - z.unsqueeze(2).float()) * s[a:b].float().unsqueeze(2)
        out[a:b] = w.reshape(b - a, n_in, n_out).transpose(1, 2)
    return out


def checkpoint_format(weight_map: dict) -> str:
    """'gptq' (Daniel's Intel W4A16) or 'nvfp4' (RadixArk, Combo A), from the expert tensor names."""
    probe = "model.language_model.layers.0.mlp.experts.0.gate_proj."
    if probe + "qweight" in weight_map:
        return "gptq"
    if probe + "weight_scale" in weight_map:
        return "nvfp4"
    raise ValueError("no packed routed experts found (neither GPTQ qweight nor NVFP4 weight_scale)")


class _Shim:
    """What transformers' grouped_mm_experts_forward reads from an experts module."""

    def __init__(self, gate_up, down, num_experts, act_fn):
        self.gate_up_proj, self.down_proj = gate_up, down
        self.num_experts = num_experts
        self.act_fn = act_fn
        self.has_gate, self.has_bias, self.is_transposed, self._is_expert_parallel = True, False, False, False

    def _apply_gate(self, gate_up_out):
        gate, up = gate_up_out.chunk(2, dim=-1)
        return self.act_fn(gate) * up


class NVFP4Experts(nn.Module):
    """Drop-in for Qwen4ExpTextExperts: same call (hidden [T, H], top_k_index [T, k], top_k_weights [T, k])."""

    def __init__(self, config):
        super().__init__()
        from transformers.activations import ACT2FN
        self.config = config
        self.num_experts = config.num_experts
        self.hidden_dim = config.hidden_size
        self.intermediate_dim = config.moe_intermediate_size
        self.act_fn = ACT2FN[config.hidden_act]
        self.fmt = None
        for n in ("gu_q", "gu_s", "gu_s2", "dn_q", "dn_s", "dn_s2", "gu_in", "dn_in",                 # nvfp4
                  "g_qw", "g_qz", "g_s", "u_qw", "u_qz", "u_s", "d_qw", "d_qz", "d_s"):               # gptq
            self.register_buffer(n, None, persistent=False)

    def weights(self) -> tuple[torch.Tensor, torch.Tensor]:
        if self.fmt == "gptq":
            n_i = self.g_qw.shape[2]                                  # gate rows, then up rows (fused gate_up layout)
            gate_up = torch.empty(self.g_qw.shape[0], 2 * n_i, self.g_qw.shape[1] * 8, dtype=torch.bfloat16,
                                  device=self.g_qw.device)
            dequant_gptq(self.g_qw, self.g_qz, self.g_s, out=gate_up[:, :n_i])
            dequant_gptq(self.u_qw, self.u_qz, self.u_s, out=gate_up[:, n_i:])
            return gate_up, dequant_gptq(self.d_qw, self.d_qz, self.d_s)
        if self.gu_q is None:
            raise RuntimeError("NVFP4Experts: packed weights not loaded (call nvfp4_experts.load_packed)")
        return dequant(self.gu_q, self.gu_s, self.gu_s2), dequant(self.dn_q, self.dn_s, self.dn_s2)

    def forward(self, hidden_states, top_k_index, top_k_weights):
        gate_up, down = self.weights()
        t = hidden_states.shape[0]
        if t <= TOKEN_CHUNK:
            return _grouped(gate_up, down, hidden_states, top_k_index, top_k_weights, self.num_experts, self.act_fn)
        # token chunks: the expert path is per token, and at ~100k tokens its sorted copies (10 rows per token) are
        # what ran out of memory (2-Oct ladder: 5.2-5.6 GiB allocations at 109k-118k tokens)
        grad = torch.is_grad_enabled() and hidden_states.requires_grad
        outs = []
        for a in range(0, t, TOKEN_CHUNK):
            b = min(t, a + TOKEN_CHUNK)
            args = (gate_up, down, hidden_states[a:b], top_k_index[a:b], top_k_weights[a:b], self.num_experts, self.act_fn)
            outs.append(checkpoint(_grouped, *args, use_reentrant=False) if grad else _grouped(*args))
        return torch.cat(outs, dim=0)


def _grouped(gate_up, down, hidden_states, top_k_index, top_k_weights, num_experts, act_fn):
    from transformers.integrations.moe import grouped_mm_experts_forward
    return grouped_mm_experts_forward(_Shim(gate_up, down, num_experts, act_fn), hidden_states, top_k_index,
                                      top_k_weights)


def install_placeholder() -> None:
    """Build every Qwen4ExpTextExperts as an (empty) NVFP4Experts from now on; the BF16 expert keys are skipped.
    The model's weight initializer special-cases the experts class by name (it would init gate_up_proj), so it
    skips NVFP4Experts here (2-Oct ladder hit this)."""
    m = _m()
    if _STATE["orig"] is None:
        _STATE["orig"] = m.Qwen4ExpTextExperts
        _STATE["orig_init"] = orig_init = m.Qwen4ExpPreTrainedModel._init_weights

        def _init_weights(self, module):
            if isinstance(module, NVFP4Experts):
                return None
            return orig_init(self, module)

        m.Qwen4ExpPreTrainedModel._init_weights = _init_weights
        m.Qwen4ExpTextExperts = NVFP4Experts


def uninstall_placeholder() -> None:
    m = _m()
    if _STATE["orig"] is not None:
        m.Qwen4ExpTextExperts = _STATE["orig"]
        m.Qwen4ExpPreTrainedModel._init_weights = _STATE.pop("orig_init")
        _STATE["orig"] = None


def read_layer(nvfp4_dir: str | Path, layer: int, num_experts: int, weight_map: dict | None = None) -> dict:
    """Stacked packed tensors of one decoder layer's experts (CPU)."""
    from safetensors import safe_open
    d = Path(nvfp4_dir)
    wm = weight_map or json.loads((d / "model.safetensors.index.json").read_text())["weight_map"]
    pre = f"model.language_model.layers.{layer}.mlp.experts."
    names = {f"{pre}{e}.{p}.{t}" for e in range(num_experts) for p in ("gate_proj", "up_proj", "down_proj")
             for t in ("weight", "weight_scale", "weight_scale_2", "input_scale")}
    by_file: dict[str, list[str]] = {}
    for n in names:
        by_file.setdefault(wm[n], []).append(n)
    got: dict[str, torch.Tensor] = {}
    for f, ns in by_file.items():
        with safe_open(str(d / f), framework="pt") as sf:
            for n in ns:
                got[n] = sf.get_tensor(n)

    def stack(p, t):
        return torch.stack([got[f"{pre}{e}.{p}.{t}"] for e in range(num_experts)])

    g_q, u_q, d_q = stack("gate_proj", "weight"), stack("up_proj", "weight"), stack("down_proj", "weight")
    g_s, u_s, d_s = (stack(p, "weight_scale") for p in ("gate_proj", "up_proj", "down_proj"))
    g_s2, u_s2, d_s2 = (stack(p, "weight_scale_2").float().reshape(num_experts) for p in ("gate_proj", "up_proj", "down_proj"))
    g_in, u_in, d_in = (stack(p, "input_scale").float().reshape(num_experts) for p in ("gate_proj", "up_proj", "down_proj"))
    rows_g, rows_d = g_q.shape[1], d_q.shape[1]
    return {
        # gate rows first, then up rows: the layout of transformers' fused gate_up_proj
        "gu_q": torch.cat([g_q, u_q], dim=1), "gu_s": torch.cat([g_s, u_s], dim=1),
        "gu_s2": torch.cat([g_s2[:, None].expand(-1, rows_g), u_s2[:, None].expand(-1, u_q.shape[1])], dim=1).contiguous(),
        "dn_q": d_q, "dn_s": d_s, "dn_s2": d_s2[:, None].expand(-1, rows_d).contiguous(),
        "gu_in": torch.stack([g_in, u_in], dim=1), "dn_in": d_in,
    }


def read_layer_gptq(ckpt_dir: str | Path, layer: int, num_experts: int, weight_map: dict | None = None) -> dict:
    """Stacked GPTQ tensors of one decoder layer's experts (CPU): per projection qweight, qzeros, scales."""
    from safetensors import safe_open
    d = Path(ckpt_dir)
    wm = weight_map or json.loads((d / "model.safetensors.index.json").read_text())["weight_map"]
    pre = f"model.language_model.layers.{layer}.mlp.experts."
    names = {f"{pre}{e}.{p}.{t}" for e in range(num_experts) for p in ("gate_proj", "up_proj", "down_proj")
             for t in ("qweight", "qzeros", "scales")}
    by_file: dict[str, list[str]] = {}
    for n in names:
        by_file.setdefault(wm[n], []).append(n)
    got: dict[str, torch.Tensor] = {}
    for f, ns in by_file.items():
        with safe_open(str(d / f), framework="pt") as sf:
            for n in ns:
                got[n] = sf.get_tensor(n)
    out = {}
    for short, proj in (("g", "gate_proj"), ("u", "up_proj"), ("d", "down_proj")):
        for key, t in (("qw", "qweight"), ("qz", "qzeros"), ("s", "scales")):
            out[f"{short}_{key}"] = torch.stack([got[f"{pre}{e}.{proj}.{t}"] for e in range(num_experts)])
    return out


def load_packed(model, nvfp4_dir: str | Path) -> dict:
    """Fill every decoder layer's packed experts from the served checkpoint (RadixArk NVFP4 or Daniel's Intel GPTQ
    int4, detected from the tensor names), on the device of that layer's router."""
    m = _m()
    wm = json.loads((Path(nvfp4_dir) / "model.safetensors.index.json").read_text())["weight_map"]
    fmt = checkpoint_format(wm)
    n, gib = 0, 0.0
    for name, mod in model.named_modules():
        if not isinstance(mod, m.Qwen4ExpTextDecoderLayer) or ".mtp." in f".{name}.":
            continue
        experts = mod.mlp.experts
        if not isinstance(experts, NVFP4Experts):
            raise RuntimeError(f"{name}: experts are {type(experts).__name__}; call install_placeholder() before loading")
        layer = int(name.rsplit(".", 1)[-1])
        dev = mod.mlp.gate.weight.device
        reader = read_layer_gptq if fmt == "gptq" else read_layer
        packed = reader(nvfp4_dir, layer, experts.num_experts, wm)
        for k, v in packed.items():
            setattr(experts, k, v.to(dev))
            gib += v.numel() * v.element_size() / 2**30
        experts.fmt = fmt
        n += 1
    return {"format": fmt, "packed_layers": n, "packed_gib": round(gib, 1)}
