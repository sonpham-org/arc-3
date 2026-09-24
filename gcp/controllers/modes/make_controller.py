"""Build the modes controller from the cv5-cr-clock controller: copy derive/verify/launch/watchdog and turn
derive_arms into derive_modes (five arms = act/verify/probe/batch/router, all on the solver prompt)."""
import re, shutil
from pathlib import Path

SRC = Path(r"D:\codex-work\cv5-cr-396-20260923"); DST = Path(r"D:\codex-work\modes-20260925")
for f in ("verify_396.py", "launch_396.py", "watchdog.py"):
    shutil.copy(SRC / f, DST / f)
s = (SRC / "derive_arms.py").read_text(encoding="utf-8")


def rep(a, b, count=1):
    global s
    assert s.count(a) >= 1, a[:80]
    s = s.replace(a, b, count)


# --- ARMS: five mode arms, every one on the solver prompt (all five ablations), no feature flags
start = s.index("ARMS = {"); end = s.index("\n}\n", start) + 3
s = s[:start] + '''SOLVER_ABL = {"search", "loop", "priors", "transition", "coords"}
# Per-turn modes on the shared solver prompt (patch_modes.py). patch_candidate="modes:<policy>" exports
# ARC3_TURN_MODE=<policy> after the bundled selftests, like the selfcheck flag.
ARMS = {m: dict(features=set(), execution_version="none", symbolic_version="none", ablations=set(SOLVER_ABL),
                patch_candidate=f"modes:{m}", feature_arm="baseline") for m in ("act", "verify", "probe", "batch", "router")}
''' + s[end:]
# --- patch dispatch
rep('''    elif spec["patch_candidate"]:
        sys.path.insert(0, str(HERE)); import patch_v2
        patch_v2.apply(cand_dir / "src" / "ARC3-Inference", spec["patch_candidate"])
        candidate_bytes = repack(cand_dir, cand_names)''',
    '''    elif str(spec["patch_candidate"]).startswith("modes:"):
        sys.path.insert(0, str(HERE)); import patch_modes
        patch_modes.apply(cand_dir / "src" / "ARC3-Inference")
        candidate_bytes = repack(cand_dir, cand_names)''')
# --- env: ARC3_TURN_MODE instead of the selfcheck / v2 flags
rep('''    if spec["patch_candidate"] is True:
        rec["extra_environment"]["ARC3_PREDICTION_CHECK"] = "1"   # exported after the selftest matrix (see startup)
    elif spec["patch_candidate"]:
        rec["extra_environment"]["ARC3_V2_BATCH_GATE"] = "1"      # v2 arms: same placement, gates multi-action batches''',
    '''    rec["extra_environment"]["ARC3_TURN_MODE"] = spec["patch_candidate"].split(":", 1)[1]   # exported after the selftests''')
rep('''    if spec["patch_candidate"] is True:
        # after EVERY bundled selftest (test_action_cap_modes.py also drives action() bare), right before gameplay
        s = sub1(r"^capture_gameplay_metrics start$", "export ARC3_PREDICTION_CHECK=1" + NL + "capture_gameplay_metrics start", s, re.M)
    elif spec["patch_candidate"]:
        s = sub1(r"^capture_gameplay_metrics start$", "export ARC3_V2_BATCH_GATE=1" + NL + "capture_gameplay_metrics start", s, re.M)''',
    '''    # after EVERY bundled selftest (they drive action() bare), right before gameplay
    s = sub1(r"^capture_gameplay_metrics start$", f"export ARC3_TURN_MODE={spec['patch_candidate'].split(':', 1)[1]}" + NL + "capture_gameplay_metrics start", s, re.M)''')
# --- names
rep('ARM_NAME = f"cv5cr_{SCOPE}_{args.arm}_{SUITE_MIN}"', 'ARM_NAME = f"modes_{SCOPE}_{args.arm}_{SUITE_MIN}"')
rep('cfg["run_id"] = f"g4run-cv5cr-{SCOPE}-{args.arm}-{SUITE_MIN}-w7-20260925"', 'cfg["run_id"] = f"g4run-modes-{SCOPE}-{args.arm}-{SUITE_MIN}-w7-20260925"')
rep('''"run_id_prefix": f"g4run-cv5cr-{SCOPE}-{args.arm}-{SUITE_MIN}-w7", "instance_prefix": f"arc3-g4-{'a25' if ALL25 else 'h7'}{args.arm[:4]}-{SUITE_MIN}",''',
    '''"run_id_prefix": f"g4run-modes-{SCOPE}-{args.arm}-{SUITE_MIN}-w7", "instance_prefix": f"arc3-g4-md{'a25' if ALL25 else 'h7'}{args.arm[:4]}-{SUITE_MIN}",''')
rep('rec["source_family"] = rec["source_family"].replace("clean_return_a_v1", f"clean_return_{SCOPE}_{args.arm}_v1")',
    'rec["source_family"] = rec["source_family"].replace("clean_return_a_v1", f"clean_return_modes_{SCOPE}_{args.arm}_v1")')
# notes text: the candidate description
s = re.sub(r'    cand_note = \(.*?\n    cfg\["evidence"\]\["notes"\] = \[', '''    cand_note = (f"PATCHED by patch_modes.py: shared solver system prompt, per-turn mode paragraph in the user message, host gates "
                 f"(action cap, expect() requirement); ARC3_TURN_MODE={spec['patch_candidate'].split(':', 1)[1]}")
    cfg["evidence"]["notes"] = [''', s, count=1, flags=re.S)
s = s.replace('"September24 user: five intensive-harness arms measured on the hard seven only', '"September25 user: per-turn mode switching on a shared minimal system prompt, measured on the hard seven only')
compile(s, "derive_modes.py", "exec")
(DST / "derive_modes.py").write_text(s, encoding="utf-8", newline="\n")

# --- verify: recognise the modes candidate
v = (DST / "verify_396.py").read_text(encoding="utf-8")
v = v.replace('''                    "symbolic_v2": ["_CODE_STORES", "def check_model(last", "def plan(goal", "_gate_batch"]}[armcfg["patched_candidate"]]''',
              '''                    "symbolic_v2": ["_CODE_STORES", "def check_model(last", "def plan(goal", "_gate_batch"]}.get(armcfg["patched_candidate"], ["mode_gates", "def expect(check)", "[mode cap]"])''')
v = v.replace('''            if armcfg["patched_candidate"] is not True:
                ok("store_key=str(state_path.parent)"''', '''            if armcfg["patched_candidate"] is not True and not str(armcfg["patched_candidate"]).startswith("modes:"):
                ok("store_key=str(state_path.parent)"''')
assert "mode_gates" in v and 'startswith("modes:")' in v
v = v.replace('    ok(cfg["recipe"]["extra_environment"].get("ARC3_GAME_SUBSET", "") == subset, "CONFIG extra_environment subset matches")',
              '    ok(cfg["recipe"]["extra_environment"].get("ARC3_GAME_SUBSET", "") == subset, "CONFIG extra_environment subset matches")\n'
              '    if str(armcfg.get("patched_candidate", "")).startswith("modes:"):\n'
              '        mode = armcfg["patched_candidate"].split(":", 1)[1]\n'
              '        ok(f"export ARC3_TURN_MODE={mode}" in startup and cfg["recipe"]["extra_environment"].get("ARC3_TURN_MODE") == mode, f"ARC3_TURN_MODE={mode} exported after selftests and in CONFIG")\n'
              '        ok((tmp_mr := (ARM / "candidate.tgz")).exists(), "candidate present")')
compile(v, "verify_396.py", "exec")
(DST / "verify_396.py").write_text(v, encoding="utf-8", newline="\n")
print("controller built:", sorted(p.name for p in DST.iterdir()))
