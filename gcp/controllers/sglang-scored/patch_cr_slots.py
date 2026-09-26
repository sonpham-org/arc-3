"""One-shot patch: add ARC3_SRC (cv5cr|cr), ARC3_SWAP (1|0) and ARC3_SLOTS to derive_sgl.py."""
from pathlib import Path
p = Path(__file__).with_name("derive_sgl.py"); s = p.read_text(encoding="utf-8")
def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:70], s.count(old))
    s = s.replace(old, new)

rep('''SRC = Path(r"D:\\codex-work\\compaction-v5-clean-return132-20260919\\arms\\compaction_v5_clean_return_a")
PARENT_RUN = "g4run-compaction-v5-clean-return-a132-w7-20260919-693e7fd43c"''',
'''SRC_KIND = os.environ.get("ARC3_SRC", "cv5cr")   # cv5cr = compaction v5 + clean return (50% swap + ledger); cr = clean return (50% swap, no ledger)
SRC = {"cv5cr": Path(r"D:\\codex-work\\compaction-v5-clean-return132-20260919\\arms\\compaction_v5_clean_return_a"),
       "cr": Path(r"D:\\codex-work\\clean-return-repeat132-r5-20260917\\arms\\clean_return_repeat132")}[SRC_KIND]
PARENT_RUN = {"cv5cr": "g4run-compaction-v5-clean-return-a132-w7-20260919-693e7fd43c", "cr": "g4run-clean-return-repeat132-w7-20260917-9677f73fbf"}[SRC_KIND]
SWAP = os.environ.get("ARC3_SWAP", "1") == "1"        # ARC3_SWAP=0: no 50% half-context swap either -> plain oldest-turn trimming at the budget
SLOTS = int(os.environ.get("ARC3_SLOTS", os.environ.get("ARC3_LANES", "5")))   # server decode slots; LANES > SLOTS = games parked in the host cache''')
rep('assert LANES * CTX <= 520_000, (LANES, CTX, "does not fit the 520k-token GPU pool at mem 0.95")',
    'assert SLOTS * CTX <= 520_000, (SLOTS, CTX, "does not fit the 520k-token GPU pool at mem 0.95")\nassert SLOTS <= LANES')
rep('ARM_NAME = f"cv5cr_sgl_c{CTX//1024}k_w{LANES}" + ("" if LANES in (5, 7) else f"_g{GAME_S}")',
    'ARM_NAME = f"{SRC_KIND}_sgl_c{CTX//1024}k_w{LANES}" + (f"_s{SLOTS}" if SLOTS != LANES else "") + ("" if LANES in (5, 7) else f"_g{GAME_S}") + ("" if SWAP else "_noswap")')

# probe: slots + swap
rep('''    p = sub1(r"'--max-num-seqs'\\)\\+1\\]=='7'", f"'--max-num-seqs')+1]=='{LANES}'", p)''',
    '''    p = sub1(r"'--max-num-seqs'\\)\\+1\\]=='7'", f"'--max-num-seqs')+1]=='{SLOTS}'", p)
elif SLOTS != LANES:
    p = sub1(r"'--max-num-seqs'\\)\\+1\\]=='7'", f"'--max-num-seqs')+1]=='{SLOTS}'", p)
if not SWAP:
    p = lit1("    assert os.environ.get(rc.FLAG) == cfg['recipe']['extra_environment'][rc.FLAG] == '1'\\n    assert agent._half_swap is not None and rc.VERSION == 'half_context_swap_v1'\\n",
             "    assert os.environ.get(rc.FLAG) == cfg['recipe']['extra_environment'][rc.FLAG] == '0'   # no half-context swap in this arm\\n    assert agent._half_swap is None\\n", p)
    p = lit1("    gate=json.loads(Path('/opt/arc3/half-swap-live-gate.json').read_text())\\n    assert gate['status']=='passed' and gate['no_generation_verified']\\n    assert gate['generation_calls']==0 and gate['retained_tail_byte_equal']\\n    assert gate['module_sha256']==sha(Path(rc.__file__).read_bytes())\\n    assert gate['input_budget']==agent._context_budget_tokens==" + str(BUDGET) + "\\n",
             "    gate=json.loads(Path('/opt/arc3/half-swap-live-gate.json').read_text())\\n    assert gate['status']=='skipped' and gate['half_swap']=='off'\\n    assert agent._context_budget_tokens==" + str(BUDGET) + "\\n", p)''')

# config: swap flag + serving tag + run id
rep('rec["extra_environment"]["ARC3_SERVING_SPECULATIVE"] = f"sglang-nextn3-c{CTX}-w{LANES}"',
    'rec["extra_environment"]["ARC3_SERVING_SPECULATIVE"] = f"sglang-nextn3-c{CTX}-w{LANES}-s{SLOTS}"\nif not SWAP:\n    assert rec["extra_environment"]["ARC3_HALF_CONTEXT_SWAP"] == "1"; rec["extra_environment"]["ARC3_HALF_CONTEXT_SWAP"] = "0"')
rep('cfg["run_id"] = f"g4run-cv5cr-sgl-c{CTX//1024}k-a132-w{LANES}-20260925"',
    'cfg["run_id"] = f"g4run-{SRC_KIND}-sgl-c{CTX//1024}k-a132-w{LANES}" + (f"s{SLOTS}" if SLOTS != LANES else "") + ("" if SWAP else "-noswap") + "-20260925"')

# manifest env swap flag
rep('assert str(OLD_CTX) not in json.dumps(man)\nsource_sha256',
    'if not SWAP:\n    mt = json.dumps(man); assert mt.count(\'"ARC3_HALF_CONTEXT_SWAP": "1"\') >= 1\n    man = json.loads(mt.replace(\'"ARC3_HALF_CONTEXT_SWAP": "1"\', \'"ARC3_HALF_CONTEXT_SWAP": "0"\'))\nassert str(OLD_CTX) not in json.dumps(man)\nsource_sha256')

# serve: slots
rep('''    --max-model-len __CTX__ --max-num-seqs __LANES__
  nohup docker logs''', '''    --max-model-len __CTX__ --max-num-seqs __SLOTS__
  nohup docker logs''')
rep(""".replace("__MEMFRAC__", MEMFRAC).replace("__LANES__", str(LANES)).replace("__CTX__", str(CTX))
s = s[:srv_a] + sgl_serve + s[srv_b:]""", """.replace("__MEMFRAC__", MEMFRAC).replace("__LANES__", str(LANES)).replace("__SLOTS__", str(SLOTS)).replace("__CTX__", str(CTX))
s = s[:srv_a] + sgl_serve + s[srv_b:]""")
rep('"requested_server_sequences": __LANES__,', '"requested_server_sequences": __SLOTS__,\n    "games_in_flight": __LANES__,')
rep(""".replace("__HICACHE_GB__", str(HICACHE_GB)).replace("__LANES__", str(LANES)).replace("__CTX__", str(CTX))
s = s[:cut_a] + sgl_build + s[cut_b:]""", """.replace("__HICACHE_GB__", str(HICACHE_GB)).replace("__LANES__", str(LANES)).replace("__SLOTS__", str(SLOTS)).replace("__CTX__", str(CTX))
s = s[:cut_a] + sgl_build + s[cut_b:]""")

# startup: swap off
rep('''# ---- (8b) telemetry upload list''', '''# ---- (8a) half-context swap off: env, skip the live gate (write the receipt the probe reads), keep the unit tests ----
if not SWAP:
    s = lit1("export ARC3_HALF_CONTEXT_SWAP=1" + NL, "export ARC3_HALF_CONTEXT_SWAP=0   # no 50% swap: oldest-turn trimming at the budget" + NL, s)
    s = lit1("timeout --kill-after=10 300 ./.venv/bin/python -B /opt/arc3/execution-selftest/live_half_swap_gate.py 2>&1 | tee /opt/arc3/half-swap-live-gate.log",
             "echo '{\\"status\\": \\"skipped\\", \\"half_swap\\": \\"off\\"}' | tee /opt/arc3/half-swap-live-gate.json /opt/arc3/half-swap-live-gate.log", s)
# ---- (8b) telemetry upload list''')
rep('''"ARC3_ACTION_CAP_MODE=return", "ARC3_CONTEXT_COMPACTION=1", "live_half_swap_gate.py", "test_half_swap.py", "WATCHDOG_PID",''',
    '''"ARC3_ACTION_CAP_MODE=return", "test_half_swap.py", "WATCHDOG_PID", *(("ARC3_CONTEXT_COMPACTION=1",) if SRC_KIND == "cv5cr" else ()),
             *(("live_half_swap_gate.py", "ARC3_HALF_CONTEXT_SWAP=1") if SWAP else ("ARC3_HALF_CONTEXT_SWAP=0",)),''')

# ARM.json
rep('''    "context_tokens": CTX, "input_tokens": BUDGET,
    "serving":''', '''    "context_tokens": CTX, "input_tokens": BUDGET, "slots": SLOTS, "half_context_swap": SWAP, "source_kind": SRC_KIND,
    "serving":''')
rep('"source_arm": "compaction_v5_clean_return_a (19-Sep, 132 min)"', '"source_arm": SRC.name + (" (19-Sep, 132 min)" if SRC_KIND == "cv5cr" else " (17-Sep, 132 min)")')
rep('"run_id_prefix": f"g4run-cv5cr-sgl-c{CTX//1024}k-a132-w{LANES}", "instance_prefix": f"arc3-g4-cv5sgl{CTX//1024}kw{LANES}", "tag": "cv5sgl",',
    '"run_id_prefix": cfg["run_id"].rsplit("-", 1)[0], "instance_prefix": f"arc3-g4-{SRC_KIND}sgl{CTX//1024}kw{LANES}" + (f"s{SLOTS}" if SLOTS != LANES else "") + ("" if SWAP else "ns"), "tag": f"{SRC_KIND}sgl",')
p.write_text(s, encoding="utf-8", newline="\n"); print("patched")
