"""Build a wave-2 pack: the wave-1 pack minus every branch that already has a 'done' result, with group
indices renumbered so shards stay balanced by checkpoint. usage: python make_remaining_plan.py <pack_v1> <results_dir> <pack_out>"""
import json, shutil, sys
from pathlib import Path
src, res, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
done = set()
for f in res.glob("*.jsonl"):
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            if r.get("status") == "done": done.add(r["job_id"])
plan = json.loads((src / "plan.json").read_text(encoding="utf-8"))
# checkpoints past a timeout-truncated snippet cannot be replayed (the recorded loop ran N actions before the 30 s
# sandbox timeout; a replay under different load runs a different N): wave 1 showed g50t step 53 and lf52 step 68.
UNREPLAYABLE = {"g50t-5849a774": 53, "lf52-271a04aa": 68}
rem = [j for j in plan if j["job_id"] not in done and not (j["game_id"] in UNREPLAYABLE and j["replay_through_step"] >= UNREPLAYABLE[j["game_id"]])]
skipped = [j for j in plan if j["game_id"] in UNREPLAYABLE and j["replay_through_step"] >= UNREPLAYABLE[j["game_id"]]]
print(f"unreplayable (excluded): {len(skipped)} jobs / {len({j['group'] for j in skipped})} checkpoints")
groups = sorted({j["group"] for j in rem}, key=lambda g: min(j["group_index"] for j in rem if j["group"] == g))
order = {g: k for k, g in enumerate(groups)}
for j in rem: j["group_index"] = order[j["group"]]
if out.exists(): shutil.rmtree(out)
shutil.copytree(src, out)
(out / "plan.json").write_text(json.dumps(rem, indent=0), encoding="utf-8")
print(f"done={len(done)} remaining={len(rem)} checkpoints={len(groups)} turn-units={sum(j['orig_remaining_turns'] for j in rem)}")
