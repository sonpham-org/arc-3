import re
def short(n):
    n2 = re.sub(r"\(.*", "", n)
    m = re.search(r"cutlass_80_\w+", n2)
    if m: return m.group(0).replace("cutlass_80_", "c80_")
    if "Marlin<" in n2: return "Marlin"
    m = re.search(r"at::native::(\w+)<.*?at::native::(?:\(anonymous namespace\)::)?(\w+)", n)
    if m: return f"aten::{m.group(1)}/{m.group(2)}"
    return n2.replace("void ", "")[:70]

