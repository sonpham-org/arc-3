"""Batch-aware expert routing for Daniel Franzen's SGLang fork (3-Oct-2026, daniel-draft; Son: "try with 22 lanes,
I want to see the gains first").

Decode on this model reads the weights of every expert any token in the step picked (W4A16 Marlin MoE, ~45% of a
decode step). Each token keeps its own top-k0 experts; its other k - k0 slots go to the best-ranked experts within its
top KEXT that some token of this batch already loads through its top-k0 (OEA-style piggyback), so the batch reads
fewer distinct experts. Unfilled slots point at the token's own top expert with weight 0. Weights = softmax over the
kept logits, scaled to the original per-token weight sum (= renormalized top-k with norm_topk_prob). Fixed shapes,
pure tensor ops: CUDA-graph safe. Padded graph rows neither load experts nor change.

Env (read at import): SGLANG_BA_K0 (0 = off: his exact path), SGLANG_BA_KEXT (32), SGLANG_BA_MIN_TOKENS (24) /
SGLANG_BA_MAX_TOKENS (1024): only batches in that token range reroute (skips prefill chunks).
Applies in TopK.forward_cuda's STANDARD branch (the Marlin path), never with fused shared experts.
  python make_patch.py      (orig/ = his wheel's exact bytes -> patched/)
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "sglang/srt/layers/moe/topk.py"

HELPER = '''

# ---- daniel-draft: batch-aware expert routing (3-Oct-2026; OEA-style piggyback) ----
import os as _ba_os

_BA_K0 = int(_ba_os.environ.get("SGLANG_BA_K0", "0") or 0)
_BA_KEXT = int(_ba_os.environ.get("SGLANG_BA_KEXT", "32") or 32)
_BA_MIN = int(_ba_os.environ.get("SGLANG_BA_MIN_TOKENS", "24") or 24)
_BA_MAX = int(_ba_os.environ.get("SGLANG_BA_MAX_TOKENS", "1024") or 1024)


def _batch_aware_reroute(topk_output, topk_config, num_token_non_padded):
    """Keep each token's top-k0 experts; refill its other slots from experts the batch already loads."""
    w, ids, logits = topk_output.topk_weights, topk_output.topk_ids, topk_output.router_logits
    if logits is None or ids.dim() != 2 or topk_config.num_fused_shared_experts:
        return topk_output
    T, K = ids.shape
    k0 = min(_BA_K0, K)
    if k0 <= 0 or k0 >= K or T < _BA_MIN or T > _BA_MAX:
        return topk_output
    E = logits.shape[-1]
    kext = min(max(_BA_KEXT, K), E)
    dev = ids.device
    lg = logits[:T].float()
    cand_lg, cand_ids = lg.topk(kext, dim=1)  # best first
    core = cand_ids[:, :k0]
    rows = torch.arange(T, device=dev)
    if num_token_non_padded is not None:
        real = rows < num_token_non_padded
    else:
        real = torch.ones(T, dtype=torch.bool, device=dev)
    loaded = torch.zeros(E + 1, dtype=torch.bool, device=dev)
    loaded.index_fill_(0, torch.where(real[:, None], core, E).reshape(-1), True)
    loaded = loaded[:E]
    ranks = torch.arange(kext, device=dev)
    pick = loaded[cand_ids] & (ranks >= k0)[None, :]
    key = torch.where(pick, ranks[None, :], ranks[None, :] + kext)
    order = key.argsort(dim=1)[:, : K - k0]
    ok = key.gather(1, order) < kext
    extra_ids = torch.where(ok, cand_ids.gather(1, order), core[:, :1])
    extra_lg = torch.where(ok, cand_lg.gather(1, order), torch.full_like(cand_lg[:, : K - k0], float("-inf")))
    new_ids = torch.cat([core, extra_ids], dim=1)
    new_w = torch.softmax(torch.cat([cand_lg[:, :k0], extra_lg], dim=1), dim=1)
    new_w = new_w * w.float().sum(dim=1, keepdim=True)
    new_ids = torch.where(real[:, None], new_ids, ids.long())
    new_w = torch.where(real[:, None], new_w, w.float())
    return StandardTopKOutput(new_w.to(w.dtype), new_ids.to(ids.dtype), logits)
'''

EDITS = [
    # helper after the StandardTopKOutput definition (module level)
    ("    @property\n"
     "    def format(self) -> TopKOutputFormat:\n"
     "        return TopKOutputFormat.STANDARD\n"
     "\n"
     "\n"
     "# ===== TO BE REFACTORED ====\n",
     "    @property\n"
     "    def format(self) -> TopKOutputFormat:\n"
     "        return TopKOutputFormat.STANDARD\n"
     + HELPER +
     "\n"
     "\n"
     "# ===== TO BE REFACTORED ====\n"),
    # call site: STANDARD branch of forward_cuda
    ("                topk_output = select_experts(\n"
     "                    hidden_states=hidden_states,\n"
     "                    layer_id=self.layer_id,\n"
     "                    router_logits=router_logits,\n"
     "                    topk_config=self.topk_config,\n"
     "                    num_token_non_padded=num_token_non_padded,\n"
     "                    expert_location_dispatch_info=expert_location_dispatch_info,\n"
     "                )\n"
     "        return self._apply_waterfill(topk_output, hidden_states.shape[0])\n",
     "                topk_output = select_experts(\n"
     "                    hidden_states=hidden_states,\n"
     "                    layer_id=self.layer_id,\n"
     "                    router_logits=router_logits,\n"
     "                    topk_config=self.topk_config,\n"
     "                    num_token_non_padded=num_token_non_padded,\n"
     "                    expert_location_dispatch_info=expert_location_dispatch_info,\n"
     "                )\n"
     "            if _BA_K0 and isinstance(topk_output, StandardTopKOutput):\n"
     "                topk_output = _batch_aware_reroute(\n"
     "                    topk_output, self.topk_config, num_token_non_padded\n"
     "                )\n"
     "        return self._apply_waterfill(topk_output, hidden_states.shape[0])\n"),
]


def main():
    s = (HERE / "orig" / NAME).read_text(encoding="utf-8")
    for old, new in EDITS:
        n = s.count(old)
        assert n == 1, (n, old[:100])
        s = s.replace(old, new)
    (HERE / "patched" / NAME).write_text(s, encoding="utf-8", newline="\n")
    compile(s, NAME, "exec")
    print(f"{NAME}: {len(EDITS)} edits")


if __name__ == "__main__":
    main()
