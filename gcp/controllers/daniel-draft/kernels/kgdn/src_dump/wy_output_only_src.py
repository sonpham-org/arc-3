def gated_delta_rule_mtp(
    A_log: torch.Tensor,
    a: torch.Tensor,
    dt_bias: torch.Tensor,
    softplus_beta: float = 1.0,
    softplus_threshold: float = 20.0,
    q: Optional[torch.Tensor] = None,
    k: Optional[torch.Tensor] = None,
    v: Optional[torch.Tensor] = None,
    b: Optional[torch.Tensor] = None,
    initial_state_source: Optional[torch.Tensor] = None,
    initial_state_indices: Optional[torch.Tensor] = None,
    output_state_indices: Optional[torch.Tensor] = None,
    intermediate_states_buffer: Optional[torch.Tensor] = None,
    accepted_steps: Optional[torch.Tensor] = None,
    ssm_state_indices: Optional[torch.Tensor] = None,
    disable_state_update: bool = False,
    use_qk_l2norm_in_kernel: bool = True,
    scale: Optional[float] = None,
    output: Optional[torch.Tensor] = None,
    disable_output: bool = False,
    recovery_steps: int = 0,
) -> torch.Tensor:
    """GDN MTP decode (BF16 state), bank-conflict-eliminated no-prepack kernel.

    Output-only / frozen-state: computes ``output`` for all T tokens and never
    writes ``initial_state_source`` back. Signature mirrors
    ``gdn_decode_bf16_state.gated_delta_rule_mtp`` so it is a drop-in for that
    kernel's output-only path; the state-update / recovery / cache / per-request
    features are not implemented and raise ``NotImplementedError``.

    Returns ``output`` of shape ``[B, T, HV, V]`` (bf16).
    """
    assert q is not None and k is not None and v is not None
    assert b is not None and initial_state_source is not None

    # --- output-only kernel: reject the fused/state-update features ---
    if recovery_steps != 0:
        raise NotImplementedError(
            "gdn_decode_bf16_wy_output_only: recovery_steps>0 is not supported "
            "(this is an output-only / frozen-state kernel)."
        )
    if disable_output:
        raise NotImplementedError(
            "gdn_decode_bf16_wy_output_only: disable_output=True (state-only mode) "
            "is not supported (this kernel always emits output)."
        )
    if intermediate_states_buffer is not None:
        raise NotImplementedError(
            "gdn_decode_bf16_wy_output_only: intermediate-state caching is not supported."
        )
    if accepted_steps is not None or ssm_state_indices is not None:
        raise NotImplementedError(
            "gdn_decode_bf16_wy_output_only: per-request K / FLA-scatter is not supported."
        )
    if output_state_indices is not None:
        raise NotImplementedError(
            "gdn_decode_bf16_wy_output_only: split-pool (output_state_indices) is not supported."
        )
    # softplus_beta / softplus_threshold are hardcoded in the kernel (beta=1,
    # overflow-safe exp); reject non-default values rather than silently ignoring.
    assert softplus_beta == 1.0, (
        f"softplus_beta={softplus_beta} not supported (kernel hardcodes beta=1.0)."
    )
    assert softplus_threshold == 20.0, (
        f"softplus_threshold={softplus_threshold} not supported (kernel ignores "
        "the threshold; pass 20.0 for signature compatibility)."
    )
    # The kernel always applies Q/K L2 normalization internally; reject False
    # rather than silently returning un-normalized-semantics results.
    assert use_qk_l2norm_in_kernel, (
        "gdn_decode_bf16_wy_output_only: use_qk_l2norm_in_kernel=False is not supported "
        "(the kernel always applies Q/K L2 normalization)."
    )
    assert initial_state_source.dtype == torch.bfloat16, (
        f"initial_state_source must be bf16 (pool, HV, V, K); got {initial_state_source.dtype}."
    )

    B, T, H, K_dim = q.shape
    HV = v.shape[2]
    V_dim = v.shape[3]
    device = q.device
    assert K_dim == K_DIM and V_dim == V_DIM_C, (
        f"this kernel requires K==V=={K_DIM}; got K={K_dim}, V={V_dim}."
    )
    T_KERNEL = 16  # kernel is hardcoded T=16

    if scale is None:
        scale = 1.0 / math.sqrt(K_dim)
    if initial_state_indices is None:
        initial_state_indices = torch.arange(B, dtype=torch.int32, device=device)
    else:
        initial_state_indices = initial_state_indices.contiguous()
    _io_dtype = q.dtype
    HK = k.shape[2]

    # A_log / dt_bias are read as bf16 by the kernel. They are per-layer constants, so
    # cache the bf16 cast by storage identity (one-time at warm-up; absent from the
    # captured graph). Falls back to a plain cast if already bf16-contiguous.
    A_log = _cached_bf16(A_log)
    dt_bias = _cached_bf16(dt_bias)
    h0 = initial_state_source.contiguous()
    # n_valid = token rows actually present in the q/k tensors handed to the kernel.
    # Native-short-T (FLASHINFER_GDN_WY_NATIVE_T): pass q/k as the real [B,T,...] tensors
    # (n_valid=T); the kernel loads only those rows and zeros its sK/sQ smem tail,
    # skipping the two big q/k gmem->gmem staging copies. Otherwise q/k are staged
    # into a T_KERNEL-row zero-padded buffer (n_valid=T_KERNEL = original behavior).
    # Native-short-T is gated to T in {4, 8}: only there does T == t_disc, so (a) the
    # t_input-gated output STG writes exactly T rows (compact [B,T] output is safe) and
    # (b) the smem-tail zeroing aligns with the kernel's working-set masking. T=4 is the
    # draft-len-3 verify shape. Other T (1-3,5-7,9-15) fall back to full staging.
    _native = _NATIVE_T and (T == 4 or T == 8)
    n_valid = T if _native else T_KERNEL

    # Contiguity: tensors the kernel reads DIRECTLY from gmem need canonical-compact
    # strides for the CuTe descriptor; staged tensors get this for free from .copy_().
    _qkv_rs = 0  # >0 => strided q/k/v read (token stride = conv_dim); see _STRIDED_QKV
    _ab_native_flag = (
        False  # True => a/b read native [B,n_valid,HV] (no staging); _NATIVE_AB
    )
    if T == T_KERNEL:
        q = q.contiguous()
        k = k.contiguous()
        v = v.contiguous()
        a = a.contiguous()
        b = b.contiguous()
    elif _native:
        # q/k/v are read natively (kernel loads n_valid rows + zeros its smem tail).
        # Default: .contiguous() so the kernel's compact-stride descriptor is valid.
        # Strided-qkv: q/k/v are the fused conv-output column slices (token stride =
        # conv_dim, features contiguous within a token). Pass that row stride to the
        # kernel and skip the copies — bit-identical (same values, strided gmem read).
        if _STRIDED_QKV and q.stride(1) == k.stride(1) == v.stride(1):
            _qkv_rs = q.stride(1)
        else:
            q = q.contiguous()
            k = k.contiguous()
            v = v.contiguous()

    # For T<T_KERNEL, stage the inputs into persistent, pre-zeroed T_KERNEL-row
    # buffers (keyed by shape AND T so rows [T:T_KERNEL) stay zero) and copy only the
    # T valid rows per call. Those zero rows are load-bearing: the kernel's
    # ldmatrix/MMA reads the full tile (NaN-tail probe confirmed). The native path
    # stages only a/b and moves the q/k/v zero-fill into the kernel (smem tail).
    if T < T_KERNEL:
        if _native and _NATIVE_AB and a.is_contiguous() and b.is_contiguous():
            # Native-a/b: pass the real [B, T(=n_valid), HV] tensors straight to the kernel
            # (batch stride = n_valid*HV, contiguous). The kernel gates the warp-3 load/compute
            # by n_valid, so no T_KERNEL zero-pad staging copy is needed. Bit-exact on the
            # compact [B,T] output (causal prefix-sum isolates the unloaded tail rows).
            _ab_native_flag = True
            # q, k, v and a, b all stay native [B, T, ...].
        elif _native:
            skey: tuple = (str(device), B, HV, str(_io_dtype), T, "ab")
            buf = _STAGE.get(skey)
            _fresh = buf is None
            if _fresh:
                with torch.inference_mode(False):
                    buf = (
                        torch.zeros(B, T_KERNEL, HV, dtype=_io_dtype, device=device),
                        torch.zeros(B, T_KERNEL, HV, dtype=_io_dtype, device=device),
                    )
                _STAGE[skey] = buf
            ab, bb = buf
            if _fresh or _RESTAGE:
                ab[:, :T].copy_(a)
                bb[:, :T].copy_(b)
            a, b = ab, bb
            # q, k, v stay as the native [B, T, ...] tensors.
        else:
            skey = (str(device), B, H, HK, HV, K_dim, V_dim, str(_io_dtype), T)
            buf = _STAGE.get(skey)
            _fresh = buf is None
            if _fresh:
                # (local patch) allocate OUTSIDE inference_mode so they are normal
                # tensors; otherwise the in-place .copy_() is rejected during
                # sglang CUDA-graph capture ("Inplace update to inference tensor").
                with torch.inference_mode(False):
                    buf = (
                        torch.zeros(
                            B, T_KERNEL, H, K_dim, dtype=_io_dtype, device=device
                        ),
                        torch.zeros(
                            B, T_KERNEL, HK, K_dim, dtype=_io_dtype, device=device
                        ),
                        torch.zeros(
                            B, T_KERNEL, HV, V_dim, dtype=_io_dtype, device=device
                        ),
                        torch.zeros(B, T_KERNEL, HV, dtype=_io_dtype, device=device),
                        torch.zeros(B, T_KERNEL, HV, dtype=_io_dtype, device=device),
                    )
                _STAGE[skey] = buf
            qb, kb, vb, ab, bb = buf
            if _fresh or _RESTAGE:  # always fill a fresh buffer; else honor _RESTAGE
                qb[:, :T].copy_(q)
                kb[:, :T].copy_(k)
                vb[:, :T].copy_(v)
                ab[:, :T].copy_(a)
                bb[:, :T].copy_(b)
            q, k, v, a, b = qb, kb, vb, ab, bb

    _num_sms = torch.cuda.get_device_properties(device).multi_processor_count
    # One CTA per (b, hv) — full V tile per CTA. Per-CTA SMEM ~29.8 KB -> <=7 CTAs/SM (ncu, B200).
    _total_ctas = HV * B
    _needed = math.ceil(_total_ctas / _num_sms)
    # Cap raised 4 -> 8 (measured on B200, T=16/HV=64): launch bounds mbp=8 makes the
    # compiler fit 64 regs/thread (was 73 -> 80 allocated -> 6-CTA register limit),
    # unlocking the 7-CTA SMEM limit (29.8 KB/CTA): theoretical occupancy 37.5% -> 43.75%,
    # ~1-7% faster across BS=16..256 with bit-identical output. mbp=12 (40 regs) gains no
    # further occupancy (SMEM-capped at 7 CTAs) and is slower — do not raise past 8.
    mbp = max(1, min(_needed + 1, 8))
    # T-aware Phase-2 squaring depth.
    t_disc = 4 if T <= 4 else (8 if T <= 8 else 16)
    # n_valid in the key: native (n_valid<T) vs staged (n_valid=T_KERNEL) compile to
    # different kernels (different q/k batch stride + the smem-tail-zero path).
    # B / pool_size are NOT in the key: the batch (mode-0) dim of every per-batch
    # tensor is marked shape-dynamic below, so one cubin serves all batch and pool
    # sizes (grid derives B from gH0idx at launch; the H0 TMA descriptor takes the
    # pool extent at launch). mbp still varies with B, but only over <=4 buckets.
    # Exception: the strided-qkv opt-in path passes non-compact q/k/v whose
    # descriptors stay fully static, so it keeps B/pool in the key (fallback).
    # HV/H/V_dim MUST be in the key: they are runtime Int32 kernel args, but the
    # compiled artifact bakes in the captured tensors' layouts (H0 TMA descriptor,
    # q/k/v/out head+feature strides — only the batch mode-0 dim is dynamic). A
    # process mixing HV values (e.g. HV=32 then HV=64) previously reused the first
    # compile and read H0 with the wrong strides -> ~3e-01 garbage outputs. Found
    # by the intense correctness sweep; invisible to the tests/benches, which use
    # one HV per process.
    cc = torch.cuda.get_device_capability(device)
    cache_key: tuple = (
        str(device),
        cc,
        mbp,
        t_disc,
        n_valid,
        _qkv_rs,
        _ab_native_flag,
        HV,
        H,
        V_dim,
    )
    if _qkv_rs > 0:
        cache_key = cache_key + (B, h0.shape[0])
    mk = from_dlpack

    def mk_dyn(t):
        # Batch/pool-dynamic compact marking: mode-0 (leading) dim dynamic, inner
        # dims static so the kernel keeps constexpr tile geometry. Requires a
        # compact (contiguous) tensor — every tensor below is either staged into
        # a contiguous buffer or .contiguous()'d by this wrapper.
        if _qkv_rs > 0:
            return mk(t, 16)  # strided fallback: fully static descriptor
        return mk(t, 16).mark_compact_shape_dynamic(
            mode=0, stride_order=tuple(range(t.dim())), divisibility=1
        )

    # The kernel always writes a full T=16 output tile. If the caller did not
    # provide `output`, write into a fresh [B,16,HV,V] buffer and return a
    # [:, :T] VIEW (zero-copy). If the caller provided `output`, honor it:
    # T==16 writes straight in; T<16 uses a scratch tile and copies the T valid
    # rows back.
    if output is not None and T == T_KERNEL:
        out16 = output
    elif _native:
        # Native (T in {4,8}): the STG writes exactly T rows, so a compact [B,T,HV,V]
        # output is correct. Returning it contiguous makes the caller's
        # reshape(1, B*T, ...) a free view instead of a ~5us materializing copy.
        out16 = torch.empty(B, T, HV, V_dim, dtype=_io_dtype, device=device)
    else:
        out16 = torch.empty(B, T_KERNEL, HV, V_dim, dtype=_io_dtype, device=device)

    stream = cuda.CUstream(torch.cuda.current_stream(device=device).cuda_stream)
    args = [
        mk_dyn(q),
        mk_dyn(k),
        mk_dyn(v),
        mk_dyn(a),
        mk_dyn(b),
        mk(A_log, 16),
        mk(dt_bias, 16),
        mk_dyn(h0),
        mk_dyn(initial_state_indices),
        mk_dyn(out16),
        scale,
        HV,
        V_dim,
        H,
        stream,
    ]

    if cache_key not in _CACHE:
        kernel = GdnDecodeKernel(
            disable_state_update=True,
            min_blocks_per_mp=mbp,
            t_input=t_disc,
            n_valid=n_valid,
            qkv_row_stride=_qkv_rs,
            ab_native=_ab_native_flag,
        )
        options = _compile_options(device)
        _CACHE[cache_key] = (
            cute.compile[options](kernel, *args)
            if options
            else cute.compile(kernel, *args)
        )
    _CACHE[cache_key](*args)

    if output is None:
        return out16[:, :T]  # zero-copy view of the valid tokens
    if T < T_KERNEL:
        output.copy_(out16[:, :T])
    return output
