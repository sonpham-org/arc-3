

# ---------------------------------------------------------------------------------------------------------------
# daniel-draft kfuse (3-Oct-2026): RecoverSSM commit without the dead slot-0 work. The boundary pass (mamba radix
# tracking) runs over every row and points rows that cross no track boundary at the reserved padding slot 0, as the
# main recovery does for CUDA-graph pad rows; each such CTA still reads and writes a full 48x128x128 state (~1.1 ms
# per step at 13 lanes). The recovery launches below use a copy of flashinfer's gdn_decode_bf16_state module whose
# gdn_wide_vec_kernel skips CTAs with output slot 0 (one guard; real rows run the identical code: bit-identical
# states). SGLANG_KFUSE_GDN_SKIP=0 restores flashinfer's module. Slot 0 is never a request's slot
# (MambaSlotAllocator hands out 1..size).
_KFUSE_GDN_MTP = None


def _kfuse_gdn_patch_source(src: str) -> str:
    head = "def gdn_wide_vec_kernel(\n"
    a = src.index(head)
    anchor = "    i_h = i_hv // (HV // H)\n"
    b = src.index(anchor, a) + len(anchor)
    end_marker = "# ==============================================================================\n# T=1 LEGACY KERNEL"
    e = src.index(end_marker, b)
    body = src[b:e]
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


def _kfuse_gated_delta_rule_mtp():
    global _KFUSE_GDN_MTP
    if _KFUSE_GDN_MTP is not None:
        return _KFUSE_GDN_MTP
    from flashinfer.gdn_kernels import gdn_decode_bf16_state as _fi_mod

    fn = _fi_mod.gated_delta_rule_mtp
    if os.environ.get("SGLANG_KFUSE_GDN_SKIP", "1") == "1":
        try:
            import importlib.util
            import sys
            import tempfile

            src = open(_fi_mod.__file__, encoding="utf-8").read()
            new = _kfuse_gdn_patch_source(src)
            d = os.path.join(tempfile.gettempdir(), "kfuse_gdn")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, "kfuse_gdn_decode_bf16_state.py")
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != new:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
            spec = importlib.util.spec_from_file_location(
                "kfuse_gdn_decode_bf16_state", path
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules["kfuse_gdn_decode_bf16_state"] = mod
            spec.loader.exec_module(mod)
            fn = mod.gated_delta_rule_mtp
            logger.info(
                "[kfuse] GDN recovery: flashinfer bf16-state MTP kernel with slot-0 rows skipped (%s)",
                path,
            )
        except Exception as e:  # never break serving: fall back to flashinfer's kernel
            logger.warning(
                "[kfuse] GDN slot-0 skip unavailable (%r); using flashinfer's kernel", e
            )
    _KFUSE_GDN_MTP = fn
    return fn
