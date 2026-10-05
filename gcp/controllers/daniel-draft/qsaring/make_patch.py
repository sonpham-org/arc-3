"""QSA ring widening for Daniel Franzen's SGLang fork (3-Oct-2026, daniel-draft; Son: "go lift the 4-token cap").

His fork keeps each request's not-yet-compressed QSA index keys in a ring of `compress_ratio` (4) slots addressed by
position % 4, and refuses a target verify wider than 4 tokens ("the pending index-key ring holds one group"). That caps
MTP at 3 draft steps and rules out DFlash. A paged forward first stores all of its tokens' keys in the ring, then
compresses every group one of its tokens completes, reading the group's 4 members back from the ring. A verify window
of D tokens starting at p completes the group that started up to 3 positions before p; those older members' slots are
shared (position % ring) with the window's own tail when the ring is shorter than D + ratio - 1, so the compression can
read a key this same forward just overwrote. Widening the ring to R >= D + ratio - 1 slots per request removes every
in-forward overlap; across forwards, rejected positions are always rewritten by the next window before any group reads
them (the next window starts at the first rejected position).

R comes from SGLANG_QSA_RING_SIZE (unset/0 -> R = ratio: his exact original addressing). The verify cap becomes
D <= R - ratio + 1 when R > ratio (his D <= ratio otherwise). Edits (orig/ = his wheel's exact bytes -> patched/):
  mem_cache/qsa_kv_pool.py          ring allocation R per request, pool.qsa_ring_size
  layers/attention/qsa/metadata.py  build_pending_ring_slots / build_group_ring_slots take ring_size
  layers/attention/qsa/graph_metadata.py  CUDA-graph row kernel addresses the ring with RING
  layers/attention/qsa/qsa_indexer.py     eager ring helpers pass the pool's ring size
  layers/attention/qwen_sparse_attn_backend.py  metadata builders pass it; the verify cap follows R
  python make_patch.py      (rewrites patched/ from orig/, compiles each file)
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
EDITS = {}

EDITS["sglang/srt/mem_cache/qsa_kv_pool.py"] = [
    ("from typing import List, Optional\n",
     "import os\nfrom typing import List, Optional\n"),
    ("        self.qsa_num_request_slots = int(num_request_slots)\n"
     "        ring_slots = self.qsa_num_request_slots * self.qsa_compress_ratio\n",
     "        self.qsa_num_request_slots = int(num_request_slots)\n"
     "        # daniel-draft (3-Oct-2026): ring of R >= ratio slots per request, addressed\n"
     "        # req_pool_idx * R + position % R. R = ratio is the original layout. A target\n"
     "        # verify of D tokens needs R >= D + ratio - 1 so its own keys never share a slot\n"
     "        # with the older members of the first group it completes.\n"
     "        self.qsa_ring_size = max(\n"
     "            self.qsa_compress_ratio,\n"
     "            int(os.environ.get(\"SGLANG_QSA_RING_SIZE\", \"0\") or 0),\n"
     "        )\n"
     "        ring_slots = self.qsa_num_request_slots * self.qsa_ring_size\n"),
]

EDITS["sglang/srt/layers/attention/qsa/metadata.py"] = [
    ("    logical_positions: torch.Tensor,\n"
     "    compress_ratio: int,\n"
     "    is_extend: bool,\n"
     ") -> torch.Tensor:\n",
     "    logical_positions: torch.Tensor,\n"
     "    compress_ratio: int,\n"
     "    is_extend: bool,\n"
     "    ring_size: Optional[int] = None,\n"
     ") -> torch.Tensor:\n"),
    ("    rows = token_to_batch_idx.long()[: logical_positions.numel()]\n"
     "    requests = req_pool_indices.long()[rows]\n"
     "    positions = logical_positions.long()\n"
     "    slots = requests * compress_ratio + positions % compress_ratio\n"
     "    if is_extend:\n"
     "        lengths = sequence_lengths.long()[rows]\n"
     "        pending = positions >= (lengths // compress_ratio) * compress_ratio\n"
     "        slots = torch.where(pending, slots, positions % compress_ratio)\n"
     "    return slots\n",
     "    ring = int(ring_size or compress_ratio)  # daniel-draft: ring of R >= ratio slots\n"
     "    rows = token_to_batch_idx.long()[: logical_positions.numel()]\n"
     "    requests = req_pool_indices.long()[rows]\n"
     "    positions = logical_positions.long()\n"
     "    slots = requests * ring + positions % ring\n"
     "    if is_extend:\n"
     "        lengths = sequence_lengths.long()[rows]\n"
     "        pending = positions >= (lengths // compress_ratio) * compress_ratio\n"
     "        slots = torch.where(pending, slots, positions % ring)\n"
     "    return slots\n"),
    ("    sequence_ids: torch.Tensor,\n"
     "    compress_ratio: int,\n"
     ") -> torch.Tensor:\n"
     "    \"\"\"Ring slots of a planned group's members, oldest first.\"\"\"\n",
     "    sequence_ids: torch.Tensor,\n"
     "    compress_ratio: int,\n"
     "    ring_size: Optional[int] = None,\n"
     ") -> torch.Tensor:\n"
     "    \"\"\"Ring slots of a planned group's members, oldest first.\"\"\"\n"
     "    ring = int(ring_size or compress_ratio)  # daniel-draft: ring of R >= ratio slots\n"),
    ("    return requests[:, None] * compress_ratio + positions % compress_ratio\n",
     "    return requests[:, None] * ring + positions % ring\n"),
]

EDITS["sglang/srt/layers/attention/qsa/graph_metadata.py"] = [
    ("    RATIO: tl.constexpr,\n"
     "    FULL_PAGE: tl.constexpr,  # full-KV tokens per page\n",
     "    RATIO: tl.constexpr,\n"
     "    RING: tl.constexpr,  # daniel-draft: pending-ring slots per request (>= RATIO)\n"
     "    FULL_PAGE: tl.constexpr,  # full-KV tokens per page\n"),
    ("    tl.store(state_slots_ptr + row, req * RATIO + (current % RATIO).to(tl.int64))\n",
     "    tl.store(state_slots_ptr + row, req * RING + (current % RING).to(tl.int64))\n"),
    ("        slot = req * RATIO + (member % RATIO).to(tl.int64)\n",
     "        slot = req * RING + (member % RING).to(tl.int64)\n"),
    ("        RATIO=indexer.compress_ratio,\n"
     "        FULL_PAGE=pool.qsa_compressed_page_size * indexer.compress_ratio,\n",
     "        RATIO=indexer.compress_ratio,\n"
     "        RING=int(getattr(pool, \"qsa_ring_size\", indexer.compress_ratio)),\n"
     "        FULL_PAGE=pool.qsa_compressed_page_size * indexer.compress_ratio,\n"),
]

EDITS["sglang/srt/layers/attention/qsa/qsa_indexer.py"] = [
    ("            logical_positions=logical_positions,\n"
     "            compress_ratio=self.compress_ratio,\n"
     "            is_extend=is_extend,\n"
     "        )\n",
     "            logical_positions=logical_positions,\n"
     "            compress_ratio=self.compress_ratio,\n"
     "            is_extend=is_extend,\n"
     "            ring_size=getattr(metadata.token_to_kv_pool, \"qsa_ring_size\", None),\n"
     "        )\n"),
    ("            group_end_positions=group_end_positions,\n"
     "            sequence_ids=sequence_ids,\n"
     "            compress_ratio=self.compress_ratio,\n"
     "        )\n",
     "            group_end_positions=group_end_positions,\n"
     "            sequence_ids=sequence_ids,\n"
     "            compress_ratio=self.compress_ratio,\n"
     "            ring_size=getattr(metadata.token_to_kv_pool, \"qsa_ring_size\", None),\n"
     "        )\n"),
]

B = "sglang/srt/layers/attention/qwen_sparse_attn_backend.py"
EDITS[B] = [
    # the verify cap follows the ring
    ("        draft_tokens = int(getattr(spec_info, \"draft_token_num\", 0) or 0)\n"
     "        if draft_tokens > self.compress_ratio:\n",
     "        draft_tokens = int(getattr(spec_info, \"draft_token_num\", 0) or 0)\n"
     "        # daniel-draft (3-Oct-2026): a ring of R > ratio slots per request takes\n"
     "        # D <= R - ratio + 1 (SGLANG_QSA_RING_SIZE); R = ratio keeps D <= ratio.\n"
     "        ring = self._qsa_ring_size()\n"
     "        limit = (\n"
     "            self.compress_ratio\n"
     "            if ring <= self.compress_ratio\n"
     "            else ring - self.compress_ratio + 1\n"
     "        )\n"
     "        if draft_tokens > limit:\n"),
    ("                f\"index-key ring holds one group; got {draft_tokens}\"\n"
     "            )\n",
     "                f\"index-key ring holds one group; got {draft_tokens} (ring {ring}; \"\n"
     "                f\"set SGLANG_QSA_RING_SIZE >= {draft_tokens + self.compress_ratio - 1})\"\n"
     "            )\n"
     "\n"
     "    def _qsa_ring_size(self) -> int:\n"
     "        pool = self.token_to_kv_pool\n"
     "        if pool is None:\n"
     "            pool = getattr(self.runner, \"token_to_kv_pool\", None)\n"
     "        return int(getattr(pool, \"qsa_ring_size\", self.compress_ratio) or self.compress_ratio)\n"),
    # eager metadata: pending slots + group member slots (two call sites)
    ("                    logical_positions=ring_logical_positions,\n"
     "                    compress_ratio=self.compress_ratio,\n"
     "                    is_extend=group_member_rows is not None,\n"
     "                )\n",
     "                    logical_positions=ring_logical_positions,\n"
     "                    compress_ratio=self.compress_ratio,\n"
     "                    is_extend=group_member_rows is not None,\n"
     "                    ring_size=self._qsa_ring_size(),\n"
     "                )\n"),
    ("                            compress_group_ring_locs = build_group_ring_slots(\n"
     "                                req_pool_indices=row_req_pool_indices,\n"
     "                                group_end_positions=group_positions.long(),\n"
     "                                sequence_ids=group_sequence_ids.long(),\n"
     "                                compress_ratio=self.compress_ratio,\n"
     "                            )\n",
     "                            compress_group_ring_locs = build_group_ring_slots(\n"
     "                                req_pool_indices=row_req_pool_indices,\n"
     "                                group_end_positions=group_positions.long(),\n"
     "                                sequence_ids=group_sequence_ids.long(),\n"
     "                                compress_ratio=self.compress_ratio,\n"
     "                                ring_size=self._qsa_ring_size(),\n"
     "                            )\n"),
    ("                        compress_group_ring_locs = build_group_ring_slots(\n"
     "                            req_pool_indices=row_req_pool_indices,\n"
     "                            group_end_positions=group_positions.long(),\n"
     "                            sequence_ids=group_sequence_ids.long(),\n"
     "                            compress_ratio=self.compress_ratio,\n"
     "                        )\n",
     "                        compress_group_ring_locs = build_group_ring_slots(\n"
     "                            req_pool_indices=row_req_pool_indices,\n"
     "                            group_end_positions=group_positions.long(),\n"
     "                            sequence_ids=group_sequence_ids.long(),\n"
     "                            compress_ratio=self.compress_ratio,\n"
     "                            ring_size=self._qsa_ring_size(),\n"
     "                        )\n"),
    # host-side graph refresh (non-kernel pools)
    ("                logical_positions=current_positions,\n"
     "                compress_ratio=ratio,\n"
     "                is_extend=False,\n"
     "            )\n",
     "                logical_positions=current_positions,\n"
     "                compress_ratio=ratio,\n"
     "                is_extend=False,\n"
     "                ring_size=getattr(pool, \"qsa_ring_size\", None),\n"
     "            )\n"),
    ("                group_end_positions=current_positions,\n"
     "                sequence_ids=metadata.token_to_batch_idx.long(),\n"
     "                compress_ratio=ratio,\n"
     "            ).to(torch.int32)\n",
     "                group_end_positions=current_positions,\n"
     "                sequence_ids=metadata.token_to_batch_idx.long(),\n"
     "                compress_ratio=ratio,\n"
     "                ring_size=getattr(pool, \"qsa_ring_size\", None),\n"
     "            ).to(torch.int32)\n"),
]


def main():
    for name, edits in EDITS.items():
        s = (HERE / "orig" / name).read_text(encoding="utf-8")
        for old, new in edits:
            n = s.count(old)
            assert n == 1, (name, n, old[:120])
            s = s.replace(old, new)
        out = HERE / "patched" / name
        out.write_text(s, encoding="utf-8", newline="\n")
        compile(s, name, "exec")
        print(f"{name}: {len(edits)} edits")


if __name__ == "__main__":
    main()
