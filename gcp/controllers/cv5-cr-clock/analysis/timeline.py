import re, sys
from pathlib import Path
src = Path(sys.argv[1]); text = src.read_text(encoding="utf-8", errors="replace")
parts = re.split(r"^(\[[A-Z][A-Z ]+(?: [^\]]*)?\])\s*$", text, flags=re.M)
blocks = [(parts[i], parts[i+1]) for i in range(1, len(parts), 2)]
n = 0; think = ""; lines = []; level = "?"; acts_total = 0
for label, body in blocks:
    if label.startswith("[THINKING"): think = re.sub(r"\s+", " ", body.strip())[:150]
    elif label.startswith("[TOOL CALL"):
        n += 1; code_acts = len(re.findall(r"action\(", body)); loop = bool(re.search(r"\bfor\b.*\baction\(|while.*action\(", body, re.S))
        remember = "remember(" in body; expect = "expect(" in body or "verify(" in body or "replay(" in body or "rule(" in body or "symbolic_search(" in body or "plan(" in body or "save(" in body
        cur = dict(n=n, code_acts=code_acts, loop=loop, mem=remember, v2=expect, think=think)
    elif label.startswith("[TOOL RESULT"):
        ea = [len(re.findall(r"'[A-Z]+(?:\([^)]*\))?'", m)) for m in re.findall(r"executed_actions'?\"?: \[([^\]]*)\]", body)]
        execd = sum(ea) if ea else len(re.findall(r"['\"]executed['\"]: [Tt]rue", body)); lv = re.findall(r"['\"]level['\"]: (\d+)", body)
        if lv: level = lv[-1]
        done = len(re.findall(r"['\"]level_completed['\"]: [Tt]rue", body)); err = "Traceback" in body or "error:" in body
        acts_total += execd
        lines.append(f"{cur['n']:3d} L{level} acts={execd:2d} tot={acts_total:4d}{' LEVEL+' if done else '      '}{' ERR' if err else '    '}{' loop' if cur['loop'] else '     '}{' mem' if cur['mem'] else '    '}{' v2' if cur['v2'] else '   '} | {cur['think']}")
dst = src.with_suffix(".timeline.txt"); dst.write_text("\n".join(lines), encoding="utf-8"); print(dst.name, len(lines), "calls", acts_total, "actions")
