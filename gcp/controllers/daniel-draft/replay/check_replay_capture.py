"""Sanity numbers for a replay capture (4-Oct-2026, daniel-draft/replay). CPU only (torch CPU for capture_io).

  python3 check_replay_capture.py CAP_DIR OUT.json [--msteps 3]

Stitch success, dropped chunks, positions captured, training rows (replay_rows.assign) in total and per game,
bytes per million rows.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_io  # noqa: E402
import replay_rows  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("cap")
ap.add_argument("out")
ap.add_argument("--msteps", type=int, default=3)
ap.add_argument("--ckpt", help="also check mm_embeds at text positions against the embed table (storage study)")
a = ap.parse_args()
files = sorted(Path(a.cap).glob("*.mtpc"))
nbytes = sum(p.stat().st_size for p in files)
kinds, dropped = Counter(), 0
for p in files:
    k = p.name.split("_")[1]
    kinds[k] += 1
reqs = capture_io.load_capture(a.cap)
for r in reqs.values():
    for c in r.chunks:
        dropped = max(dropped, int((c[3].get("dropped_before") or {}).get("prefill_chunks", 0)))
failed = capture_io.stitch(reqs)
st = replay_rows.assign(reqs, a.msteps)
positions = sum(c[1] for r in reqs.values() for c in r.chunks)
per_game = defaultdict(lambda: [0, 0, 0])
for r in reqs.values():
    g = replay_rows.game_of(r.rid)
    if g is None:
        continue
    per_game[g][0] += 1
    per_game[g][1] += len(getattr(r, "qrows", None) or [])
    per_game[g][2] += sum(c[1] for c in r.chunks)
rows = st["rows"]
out = {"files": dict(kinds), "gb": round(nbytes / 2 ** 30, 1), "requests": len(reqs),
       "stitch_failed": len(failed), "fail_reasons": Counter(v.split(" ")[0] + " " + v.split(" ")[1] for v in failed.values()),
       "dropped_prefill_chunks": dropped, "positions": positions, "span_stats": st,
       "gb_per_million_rows": round(nbytes / 2 ** 30 / max(1e-9, rows / 1e6), 1),
       "positions_per_row": round(positions / max(1, rows), 2),
       "per_game": {g: {"requests": v[0], "rows": v[1], "positions": v[2]} for g, v in sorted(per_game.items())}}
if a.ckpt:  # storage study: are the stored input embeddings at TEXT positions just embed(token)? Then only image
    import torch  # rows need storing (mm_embeds are about a fifth of a replay capture)
    from draft_torch import SHARED, read_tensors
    emb = read_tensors(a.ckpt, [SHARED[0]])[SHARED[0]].to(torch.bfloat16)
    checked, maxdiff, n_text, n_img, mm_bytes = 0, 0.0, 0, 0, 0
    for r in reqs.values():
        for pos, n, path, h in r.chunks:
            if "mm_embeds" not in h["tensors"]:
                continue
            mm_bytes += h["tensors"]["mm_embeds"][3]
            if checked >= 40 or r.prompt is None:
                continue
            tok = torch.as_tensor(r.prompt[pos:pos + n])
            mme = capture_io.read_tensor(path, h, "mm_embeds")
            text = tok < emb.shape[0]
            text[-1] = False  # each request's last chunk row is re-embedded from the shifted token
            n_text += int(text.sum())
            n_img += int((tok >= emb.shape[0]).sum())
            if text.any():
                maxdiff = max(maxdiff, float((mme[text].float() - emb[tok[text]].float()).abs().max()))
            checked += 1
    out["mm_embeds_gb"] = round(mm_bytes / 2 ** 30, 1)
    out["mm_text_rows_equal_embed"] = {"chunks": checked, "text_rows": n_text, "image_rows": n_img,
                                       "max_abs_diff": maxdiff}
json.dump(out, open(a.out, "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "per_game"}, default=str))
