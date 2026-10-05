"""kglue: MoE top-k sum folded into the shared-expert gate kernel (5-Oct-2026, Kernel optimizations thread).
Idempotent: rebuilds both files from their bases. python apply_c.py

Decode (CUDA graph, dual stream) per MoE layer today: alt stream ... Marlin -> act -> Marlin -> topk_sum (sum the
top-k expert rows, fp32 sequential, -> bf16) ; main stream waits -> _fused_gate_sigmoid_mul_add (final += sigmoid(h.w)
* shared). With kglue the alt stream stops after the second Marlin and the main-stream gate kernel does the sum itself
(the same fp32 sequential loop and bf16 rounding, then the gate kernel's own code): one kernel and one launch gap less
per MoE layer, every output byte the same. Only in Qwen2MoeSparseMoeBlock.forward_normal_dual_stream with the fused
gate, and only when fused_marlin_moe takes kfast's unit-scale top-k-sum path. SGLANG_KGLUE_GATESUM=0 disables it.
The kernel lives in fused_marlin_moe.py (which already imports triton); qwen2_moe.py imports it lazily.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
WHEEL = HERE.parent.parent / "wheel" / "full"


def build(rel, base, subs):
    s = base.read_text(encoding="utf-8")
    for sub in subs:
        old, new, n = (*sub, 1) if len(sub) == 2 else sub
        assert s.count(old) == n, (rel, old[:70], s.count(old))
        s = s.replace(old, new)
    out = HERE / "patched" / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(s, encoding="utf-8")
    orig = HERE / "orig" / rel
    orig.parent.mkdir(parents=True, exist_ok=True)
    orig.write_bytes((WHEEL / rel).read_bytes())
    compile(s, str(out), "exec")
    print("wrote", out)


KERNEL = '''

# kglue (5-Oct-2026): set by Qwen2MoeSparseMoeBlock around its routed-expert call; when set, the unit-scale top-k sum
# is left to the shared-expert gate kernel, which reads (output, cache3) from _kglue_pending.
_kglue_defer_sum = False
_kglue_pending = None


@triton.jit
def _kglue_topk_sum_gate_kernel(
    hidden_states_ptr,  # [num_tokens, hidden_dim]
    gate_weight_ptr,  # [hidden_dim]
    shared_output_ptr,  # [num_tokens, hidden_dim]
    cache3_ptr,  # [num_tokens, TOPK, hidden_dim] routed expert outputs (top-k weights applied)
    final_hidden_states_ptr,  # [num_tokens, hidden_dim] out
    hidden_dim: tl.constexpr,
    TOPK: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
    USE_PDL: tl.constexpr = False,
):
    # _fused_gate_sigmoid_mul_add_kernel with its `f` load replaced by moe_topk_sum's math (fp32 sequential sum over
    # the top-k rows starting from 0, rounded to bf16): the same bytes as topk_sum followed by the gate kernel.
    pid = tl.program_id(axis=0).to(tl.int64)
    row_offset = pid * hidden_dim

    offsets = tl.arange(0, BLOCK_SIZE)
    mask = offsets < hidden_dim

    w = tl.load(gate_weight_ptr + offsets, mask=mask, other=0.0).to(tl.float32)

    if USE_PDL:
        tl.extra.cuda.gdc_wait()

    h = tl.load(hidden_states_ptr + row_offset + offsets, mask=mask, other=0.0).to(
        tl.float32
    )
    s = tl.load(shared_output_ptr + row_offset + offsets, mask=mask, other=0.0).to(
        tl.float32
    )
    acc = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    for j in tl.static_range(TOPK):
        acc += tl.load(
            cache3_ptr + (pid * TOPK + j) * hidden_dim + offsets, mask=mask, other=0.0
        ).to(tl.float32)
    f = acc.to(tl.bfloat16).to(tl.float32)

    if USE_PDL:
        tl.extra.cuda.gdc_launch_dependents()

    gate_val = tl.sigmoid(tl.sum(h * w, axis=0))
    result = f + gate_val * s

    tl.store(final_hidden_states_ptr + row_offset + offsets, result, mask=mask)


def kglue_topk_sum_gate(hidden_states, gate_weight, shared_output, cache3, final_hidden_states):
    """final = bf16(sum_j cache3[:, j]) + sigmoid(hidden_states @ gate_weight) * shared_output, written into
    final_hidden_states; launch config identical to fused_gate_sigmoid_mul_add."""
    from sglang.kernels.jit.utils import is_arch_support_pdl

    num_tokens, hidden_dim = hidden_states.shape
    topk = cache3.shape[1]
    assert cache3.shape == (num_tokens, topk, hidden_dim) and cache3.is_contiguous()
    assert hidden_states.is_contiguous() and gate_weight.is_contiguous()
    assert shared_output.is_contiguous() and final_hidden_states.is_contiguous()
    config = {
        "BLOCK_SIZE": triton.next_power_of_2(hidden_dim),
        "num_warps": max(min(triton.next_power_of_2(triton.cdiv(hidden_dim, 256)), 32), 4),
    }
    if num_tokens >= 1024:
        config["num_warps"] = min(config["num_warps"], 8)
    use_pdl = is_arch_support_pdl()
    pdl_kwargs = {"launch_pdl": True} if use_pdl else {}
    _kglue_topk_sum_gate_kernel[(num_tokens,)](
        hidden_states,
        gate_weight,
        shared_output,
        cache3,
        final_hidden_states,
        hidden_dim=hidden_dim,
        TOPK=topk,
        USE_PDL=use_pdl,
        **config,
        **pdl_kwargs,
    )
'''

FMM = "sglang/srt/layers/moe/fused_moe_triton/fused_marlin_moe.py"
build(FMM, HERE.parent / "kfast" / "patched" / FMM, [
    ("from sglang.srt.utils.custom_op import register_custom_op\n",
     "from sglang.srt.utils.custom_op import register_custom_op\n" + KERNEL),
    ("""            from sglang.kernels.ops.moe.moe_topk_sum import moe_topk_sum

            moe_topk_sum(intermediate_cache3, output)
            return output""",
     """            global _kglue_pending
            if (
                _kglue_defer_sum
                and _kglue_pending is None
                and intermediate_cache3.dim() == 3
                and output.shape == hidden_states.shape
                and output.dim() == 2
            ):
                _kglue_pending = (output, intermediate_cache3)   # kglue: summed by the gate kernel
                return output

            from sglang.kernels.ops.moe.moe_topk_sum import moe_topk_sum

            moe_topk_sum(intermediate_cache3, output)
            return output"""),
])

Q2 = "sglang/srt/models/qwen2_moe.py"
build(Q2, WHEEL / Q2, [
    ("from sglang.kernels.ops.elementwise.elementwise import fused_gate_sigmoid_mul_add\n",
     """from sglang.kernels.ops.elementwise.elementwise import fused_gate_sigmoid_mul_add

import os as _kglue_os

_KGLUE_GATESUM = _kglue_os.environ.get("SGLANG_KGLUE_GATESUM", "1") != "0"   # kglue (5-Oct-2026)


def _kglue_same_storage(a, b) -> bool:
    return a.data_ptr() == b.data_ptr() and a.shape == b.shape and a.is_contiguous() and b.is_contiguous()
"""),
    ("""        with torch.cuda.stream(self.alt_stream):
            router_output = self._forward_router_experts(hidden_states)

        current_stream.wait_stream(self.alt_stream)
""", """        with torch.cuda.stream(self.alt_stream):
            # kglue: let the gate kernel do the routed top-k sum (see fused_marlin_moe._kglue_pending)
            defer = (
                _KGLUE_GATESUM
                and use_fused_gate
                and shared_output is not None
                and not staged
                and hidden_states.dtype == torch.bfloat16
            )
            if defer:
                from sglang.srt.layers.moe.fused_moe_triton import fused_marlin_moe as _kglue_fmm

                _kglue_fmm._kglue_pending = None
                _kglue_fmm._kglue_defer_sum = True
            try:
                router_output = self._forward_router_experts(hidden_states)
            finally:
                if defer:
                    _kglue_fmm._kglue_defer_sum = False
            pend = None
            if defer:
                pend, _kglue_fmm._kglue_pending = _kglue_fmm._kglue_pending, None
                if pend is not None and not _kglue_same_storage(router_output, pend[0]):
                    # not the tensor we deferred: finish the sum here, before anything else reads it
                    from sglang.kernels.ops.moe.moe_topk_sum import moe_topk_sum

                    moe_topk_sum(pend[1], pend[0])
                    pend = None
            self._kglue_pending_sum = pend

        current_stream.wait_stream(self.alt_stream)
"""),
    ("""        if shared_output is not None:
            if use_fused_gate:
                fused_gate_sigmoid_mul_add(
                    hidden_states,
                    self.shared_expert_gate.weight.squeeze(),
                    shared_output,
                    final_hidden_states,
                )""", """        if shared_output is not None:
            pend = getattr(self, "_kglue_pending_sum", None)
            self._kglue_pending_sum = None
            if use_fused_gate and pend is not None:
                from sglang.srt.layers.moe.fused_moe_triton.fused_marlin_moe import kglue_topk_sum_gate

                kglue_topk_sum_gate(
                    hidden_states,
                    self.shared_expert_gate.weight.squeeze(),
                    shared_output,
                    pend[1],
                    final_hidden_states,
                )
            elif use_fused_gate:
                fused_gate_sigmoid_mul_add(
                    hidden_states,
                    self.shared_expert_gate.weight.squeeze(),
                    shared_output,
                    final_hidden_states,
                )"""),
])
