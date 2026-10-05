"""Build kfuse/patched/.../hybrid_linear_attn_backend.py: his file + gdn_helper_block.py, recovery imports rerouted."""
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(r"D:\codex-work\daniel-draft\kernels\kfuse")
N = "sglang/srt/layers/attention/hybrid_linear_attn_backend.py"
z = zipfile.ZipFile(r"D:\codex-work\daniel-draft\wheel\sglang.whl")
orig = z.read(N)
(ROOT / "orig" / N).parent.mkdir(parents=True, exist_ok=True)
(ROOT / "orig" / N).write_bytes(orig)
s = orig.decode("utf-8")
assert "\r" not in s
helper = (ROOT / "dev" / "gdn_helper_block.py").read_text(encoding="utf-8")
anchor = "logger = logging.getLogger(__name__)\n"
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + helper)
assert s.count("import bisect\nimport logging\n") == 1
s = s.replace("import bisect\nimport logging\n", "import bisect\nimport logging\nimport os\n", 1)
plain = "        from flashinfer.gdn_kernels.gdn_decode_bf16_state import gated_delta_rule_mtp\n"
paren = ("            from flashinfer.gdn_kernels.gdn_decode_bf16_state import (\n"
         "                gated_delta_rule_mtp,\n"
         "            )\n")
print("plain", s.count(plain), "paren", s.count(paren))
s = s.replace(plain, "        gated_delta_rule_mtp = _kfuse_gated_delta_rule_mtp()\n")
s = s.replace(paren, "            gated_delta_rule_mtp = _kfuse_gated_delta_rule_mtp()\n")
left = [l for l in s.splitlines() if "gdn_decode_bf16_state import" in l]
assert not left, left
compile(s, N, "exec")
out = ROOT / "patched" / N
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(s.encode("utf-8"))
print("ok", out, hashlib.sha256(orig).hexdigest()[:16])
