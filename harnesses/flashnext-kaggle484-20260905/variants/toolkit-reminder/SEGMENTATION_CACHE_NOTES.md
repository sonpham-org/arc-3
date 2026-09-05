# Transparent segmentation caching

This candidate extends the optional CPU vision library with RAM reuse for the existing `current_frame.segmentation` property. Existing snippets and saved helpers keep the same API. The prompt and original segmentation algorithm are unchanged.

On first property access, the guest asks the host for an exact grid/dimensions/palette match in a versioned cache namespace. On a miss, the original algorithm runs inside the guest under the existing Python-tool timeout. Only a completed result is offered to the host cache. Unsupported inputs and rejected or oversized results remain usable through the original local computation.

The same FrameView keeps its existing mutable result object. Other FrameViews and later Python calls receive independent copies, so editing one result cannot poison the host cache. History, transition and animation FrameViews use their own actual grids. Segmentation is geometric, so identical grids can reuse results across steps within a game; temporal vision results keep their separate observation keys.

The cache belongs to the game agent and full runtime-state path. It survives context rotation and fresh Python subprocesses, and resets for a new game path or host-process restart. Segmentation shares the existing 128-entry/4 MiB encoded-result LRU with optional vision queries. This bounds retained serialized results, not total process RSS. Eviction changes reuse, not the returned segmentation.

Existing vision telemetry includes `api_calls.segmentation` and shared hit/miss/computation counters. No segmentation data, cache inventory or new capability text is automatically inserted into Qwen's context. Existing explicit prints/results behave as before.

This is a local CPU optimization candidate. Cache lookup, serialization and RPC add overhead to first-time frames; savings depend on repeated access to identical frames. Score and token improvements require gameplay evaluation. Production Linux launch and GPU evaluation have not been performed by this change. Runtime/curator configuration and the separate preserved-rules arm are unchanged from the parent release.
