"""Turn digest of an ARC3 harness transcript: per tool call, the code (trimmed), the result head, actions and level.

usage: python digest.py <transcript> [max_code_lines] [max_result_lines]  -> writes <transcript>.digest.txt
"""
import re, sys
from pathlib import Path

src = Path(sys.argv[1]); mc = int(sys.argv[2]) if len(sys.argv) > 2 else 14; mr = int(sys.argv[3]) if len(sys.argv) > 3 else 10
text = src.read_text(encoding="utf-8", errors="replace")
# blocks are "[LABEL ...]" headers on their own line
parts = re.split(r"^(\[[A-Z][A-Z ]+(?: [^\]]*)?\])\s*$", text, flags=re.M)
blocks = []
for i in range(1, len(parts), 2):
    blocks.append((parts[i], parts[i + 1]))
out = []; n_call = 0; level = None; total_actions = 0
for label, body in blocks:
    if label.startswith("[TOOL CALL"):
        n_call += 1
        code = body.strip().splitlines()
        m = re.search(r"\((\d+) chars", label)
        acts = len(re.findall(r"action\(", body))
        out.append(f"\n### call {n_call} | {label} | action( calls in code: {acts}")
        out.append("\n".join("    " + l for l in code[:mc]) + ("\n    ... (%d more lines)" % (len(code) - mc) if len(code) > mc else ""))
    elif label.startswith("[TOOL RESULT"):
        res = body.strip().splitlines()
        lv = re.search(r"level[\"']?\s*[:=]\s*(\d+)", body)
        if lv: level = lv.group(1)
        na = len(re.findall(r"\"action\"\s*:\s*\"?[A-Z]", body)) or len(re.findall(r"executed", body))
        lvl_done = "LEVEL_COMPLETED" if re.search(r"level_completed[\"']?\s*:\s*true", body, re.I) else ""
        out.append(f"  -> result ({len(body)} chars) level={level} {lvl_done}")
        out.append("\n".join("      " + l[:200] for l in res[:mr]) + ("\n      ... (%d more lines)" % (len(res) - mr) if len(res) > mr else ""))
    elif label.startswith("[THINKING"):
        th = body.strip()
        out.append("  [thinking %d chars] %s" % (len(th), re.sub(r"\s+", " ", th)[:400]))
    elif label.startswith("[RUNTIME BUDGET"):
        b = re.sub(r"\s+", " ", body.strip())[:160]
        out.append("  [budget] " + b)
dst = src.with_suffix(".digest.txt"); dst.write_text("\n".join(out), encoding="utf-8")
print(dst, "calls", n_call, "digest chars", dst.stat().st_size)
