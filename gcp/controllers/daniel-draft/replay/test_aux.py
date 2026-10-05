"""Unit checks for draft_torch's multi-layer input (add_aux / aux_term / fuse / forward_steps aux), on GPU, random
weights (4-Oct-2026, drafter idea 2). Prints one JSON line; exits 1 on a failed check.
  1. aux_fc = 0 (as initialized): fuse and forward_steps with aux equal the plain drafter exactly;
  2. aux_fc random: guess-1 outputs move, gradients reach aux_fc and aux_norm;
  3. fuse without an aux argument is the plain fuse (guesses >= 2 call it that way);
  4. aux_term's row chunking gives the same result as one chunk.
"""
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_torch as D  # noqa: E402

torch.manual_seed(0)
dev = torch.device("cuda")
d = D.Draft(16).to(dev)
with torch.no_grad():
    for n, p in d.named_parameters():
        p.normal_(0, 0.02)
    d.embed = torch.randn(1000, D.H, device=dev, dtype=torch.bfloat16) * 0.02
    d.lm_head = torch.randn(1000, D.H, device=dev, dtype=torch.bfloat16) * 0.02
    d.gate_up = torch.randn(16, 2 * D.E_INTER, D.H, device=dev, dtype=torch.bfloat16) * 0.02
    d.down = torch.randn(16, D.H, D.E_INTER, device=dev, dtype=torch.bfloat16) * 0.02
T = 300
hc = torch.randn(T, D.HC * D.H, device=dev) * 3
aux = torch.randn(T, 3 * D.HC * D.H, device=dev) * 3
toks = torch.randint(0, 1000, (T + 8,), device=dev)
e_in = d.embed[toks[1:T + 1]]
rows = torch.arange(200, 240, device=dev)
out = {}
with torch.no_grad():
    base = d.forward_steps(hc, e_in, rows, toks, 3)
    d.add_aux(3)
    same = d.forward_steps(hc, e_in, rows, toks, 3, aux=aux)
    out["zero_init_max_diff"] = max(float((a - b).abs().max()) for a, b in zip(base, same))
    d.aux_fc.normal_(0, 0.02)
    moved = d.forward_steps(hc, e_in, rows, toks, 3, aux=aux)
    out["guess1_moved"] = float((moved[0] - base[0]).abs().max())
    f_plain = d.fuse(None, hc[:50], e_in[:50])
    f_none = d.fuse(None, hc[:50], e_in[:50], None)
    out["no_aux_arg_diff"] = float((f_plain - f_none).abs().max())
    t1 = d.aux_term(aux[:100], chunk=7)
    t2 = d.aux_term(aux[:100], chunk=8192)
    out["chunk_diff"] = float((t1 - t2).abs().max())
d.aux_fc.requires_grad_(True)
d.aux_norm.requires_grad_(True)
o = d.forward_steps(hc, e_in, rows, toks, 2, aux=aux)
sum(x.float().pow(2).mean() for x in o).backward()
out["grad_aux_fc"] = float(d.aux_fc.grad.abs().sum())
out["grad_aux_norm"] = float(d.aux_norm.grad.abs().sum())
ok = (out["zero_init_max_diff"] == 0.0 and out["guess1_moved"] > 0 and out["no_aux_arg_diff"] == 0.0
      and out["chunk_diff"] < 1e-5 and out["grad_aux_fc"] > 0 and out["grad_aux_norm"] > 0)
out["ok"] = ok
print(json.dumps(out))
sys.exit(0 if ok else 1)
