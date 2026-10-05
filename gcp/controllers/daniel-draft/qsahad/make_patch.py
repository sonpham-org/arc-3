"""Hadamard-rotated KV for the QSA attention layers of Daniel Franzen's fork (3-Oct-2026, daniel-draft; Son: 4-bit KV
recipe step 1, "fix the error at the source").

4-bit (nvfp4_qsa) KV costs ~0.006-0.009 nats of mean logprob vs FP8 on the recorded-response probe, and neither BF16
unpack nor a global-scale sweep removes it: the loss is the E2M1 rounding itself, which outlier channels make worse.
A fixed orthonormal Hadamard rotation H (256 x 256, symmetric, H @ H = I) per head spreads outliers across the head's
dims before K and V are stored. Exactness: q.k = (qH).(kH) and sum_j p_j v_j = (sum_j p_j v_j H) H, so rotating q, k
and v after RoPE / q-k norms and un-rotating the attention output (before the sigmoid gate and o_proj) leaves the layer
unchanged in exact arithmetic; only the cached K/V live in the rotated basis. The QSA indexer uses its own projections
and is untouched. Fixed shapes, plain matmuls: CUDA-graph safe. Off unless SGLANG_QSA_KV_HADAMARD=1.
  python make_patch.py          (orig/ = his wheel's exact bytes -> patched/)
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "sglang/srt/models/qwen4_exp.py"

HELPER = '''

# ---- daniel-draft: Hadamard-rotated KV for the QSA layers (3-Oct-2026) ----
_QSA_KV_HADAMARD = os.environ.get("SGLANG_QSA_KV_HADAMARD", "0") == "1"
_HADAMARD_CACHE = {}


def _hadamard_matrix(n: int, device) -> torch.Tensor:
    """Orthonormal Sylvester Hadamard matrix (symmetric, H @ H = I), cached per device."""
    key = (n, str(device))
    h = _HADAMARD_CACHE.get(key)
    if h is None:
        if n & (n - 1):
            raise ValueError(f"SGLANG_QSA_KV_HADAMARD needs a power-of-two head_dim, got {n}")
        h = torch.ones(1, 1, dtype=torch.float32)
        while h.shape[0] < n:
            h = torch.cat([torch.cat([h, h], 1), torch.cat([h, -h], 1)], 0)
        h = (h / math.sqrt(n)).to(device)
        _HADAMARD_CACHE[key] = h
    return h


def _hadamard_rotate(x: torch.Tensor, head_dim: int) -> torch.Tensor:
    """Rotate every head_dim-sized head vector of x by H (its own inverse)."""
    h = _hadamard_matrix(head_dim, x.device)
    y = x.reshape(-1, head_dim).float() @ h
    return y.to(x.dtype).reshape(x.shape)
'''

EDITS = [
    ("import math\nimport mmap\n", "import math\nimport mmap\nimport os\n"),
    # helpers right before the attention decoder layer class
    ("\n\nclass Qwen4ExpAttentionDecoderLayer(", HELPER + "\n\nclass Qwen4ExpAttentionDecoderLayer("),
    ("        q, k, v, gate = self._prepare_qkv_gate(\n"
     "            positions=positions,\n"
     "            hidden_states=hidden_states,\n"
     "            forward_batch=forward_batch,\n"
     "        )\n",
     "        q, k, v, gate = self._prepare_qkv_gate(\n"
     "            positions=positions,\n"
     "            hidden_states=hidden_states,\n"
     "            forward_batch=forward_batch,\n"
     "        )\n"
     "        kv_rotate = self.is_qsa and _QSA_KV_HADAMARD\n"
     "        if kv_rotate:  # daniel-draft: cached K/V in the Hadamard basis (exact)\n"
     "            q = _hadamard_rotate(q, self.head_dim)\n"
     "            k = _hadamard_rotate(k, self.head_dim)\n"
     "            v = _hadamard_rotate(v, self.head_dim)\n"),
    ("        attn_output = self.attn(q, k, v, forward_batch, **attention_kwargs)\n",
     "        attn_output = self.attn(q, k, v, forward_batch, **attention_kwargs)\n"
     "        if kv_rotate:  # back to the model's basis before the gate and o_proj\n"
     "            attn_output = _hadamard_rotate(attn_output, self.head_dim)\n"),
]


def main():
    s = (HERE / "orig" / NAME).read_text(encoding="utf-8")
    for old, new in EDITS:
        n = s.count(old)
        assert n == 1, (n, old[:90])
        s = s.replace(old, new, 1)
    (HERE / "patched" / NAME).write_text(s, encoding="utf-8", newline="\n")
    compile(s, NAME, "exec")
    print(f"{NAME}: {len(EDITS)} edits")


if __name__ == "__main__":
    main()
