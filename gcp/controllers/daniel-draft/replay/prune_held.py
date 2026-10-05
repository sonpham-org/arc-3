"""List the capture files only held-out games need (4-Oct-2026, replay storage cap): a file is deletable when no request
of a kept game reads it (own chunks, req header, or any stitched segment, e.g. the shared system prompt that another
game first prefilled). Writes OUT.json {"delete": [file names], "bytes": n, "keep_files": k}.

  python prune_held.py CAP_DIR --hold dc22,ka59,lp85,sp80,tu93 --out OUT.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_io  # noqa: E402
import replay_rows  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("cap")
ap.add_argument("--hold", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
held = set(a.hold.split(","))
files = sorted(Path(a.cap).glob("*.mtpc"))
rid_of = {}
for p in files:
    h = capture_io.read_header(p)
    rid_of[p] = h.get("rid")  # decode files have rids (a list) and no "rid": kept
reqs = capture_io.load_capture(a.cap)
capture_io.stitch(reqs)
keep = set()
for r in reqs.values():
    if replay_rows.game_of(r.rid) in held:
        continue
    keep.update(c[2] for c in r.chunks)
    for s, e, path, head, row in (r.segments or []):
        keep.add(path)
for p, rid in rid_of.items():
    if rid is None or replay_rows.game_of(rid) not in held:
        keep.add(p)
delete = [p for p in files if p not in keep]
out = {"delete": [p.name for p in delete], "bytes": sum(p.stat().st_size for p in delete), "keep_files": len(keep),
       "files": len(files)}
json.dump(out, open(a.out, "w"))
print(json.dumps({k: v for k, v in out.items() if k != "delete"}))
