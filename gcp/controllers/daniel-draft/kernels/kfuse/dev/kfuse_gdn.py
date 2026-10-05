"""daniel-draft kfuse (3-Oct-2026): flashinfer's BF16-state GDN MTP kernel with slot-0 rows skipped.

His RecoverSSM path (gdn_mtp_cache_mode=none) runs, after every verify, one gated_delta_rule_mtp launch per GDN
layer to rebuild the accepted state, plus (mamba radix tracking on) a boundary pass that recomputes the
track-checkpoint state. In both, rows that need no output are pointed at the reserved padding slot 0 (graph pad
rows; boundary rows that cross no track boundary), yet every CTA still reads and writes a full 48x128x128 state.
This loads flashinfer's own module source, adds one guard to gdn_wide_vec_kernel (CTAs whose output slot is 0 do
nothing), and imports it as a separate module. Real rows run the identical instruction stream: bit-identical.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile

_MOD = None


def patch_source(src: str) -> str:
    head = "def gdn_wide_vec_kernel(\n"
    a = src.index(head)
    anchor = "    i_h = i_hv // (HV // H)\n"
    b = src.index(anchor, a) + len(anchor)
    end_marker = "# ==============================================================================\n# T=1 LEGACY KERNEL"
    e = src.index(end_marker, b)
    body = src[b:e]
    # trailing blank lines stay outside the guarded block
    stripped = body.rstrip("\n")
    tail = body[len(stripped):]
    lines = stripped.split("\n")
    ind = "\n".join(("    " + l) if l.strip() else l for l in lines)
    guard = (
        "    # daniel-draft kfuse: a row whose output slot is the reserved padding slot 0 (CUDA-graph pad rows,\n"
        "    # boundary-pass rows that cross no track boundary) writes nothing anyone reads: skip the whole CTA.\n"
        "    kfuse_out_slot = cutlass.Int32(h0_out_indices[i_n])\n"
        "    if kfuse_out_slot != cutlass.Int32(0):\n"
    )
    out = src[:b] + guard + ind + tail + src[e:]
    assert out.count("kfuse_out_slot") == 2
    return out


def load(force_path: str | None = None):
    """Patched copy of flashinfer.gdn_kernels.gdn_decode_bf16_state (cached)."""
    global _MOD
    if _MOD is not None:
        return _MOD
    from flashinfer.gdn_kernels import gdn_decode_bf16_state as orig

    src = open(orig.__file__, encoding="utf-8").read()
    new = patch_source(src)
    d = force_path or os.path.join(tempfile.gettempdir(), "kfuse_gdn")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "kfuse_gdn_decode_bf16_state.py")
    if not os.path.exists(path) or open(path, encoding="utf-8").read() != new:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    spec = importlib.util.spec_from_file_location("kfuse_gdn_decode_bf16_state", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kfuse_gdn_decode_bf16_state"] = mod
    spec.loader.exec_module(mod)
    _MOD = mod
    return mod
