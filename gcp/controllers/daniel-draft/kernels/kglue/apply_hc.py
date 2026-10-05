"""Build kglue's hyperconnection.py = khc's patched file + the kglue additions (_kglue_src.py). Idempotent: always
starts from khc's patched copy. python apply_hc.py"""
from pathlib import Path

import _kglue_mix as KM
import _kglue_src as K

HERE = Path(__file__).resolve().parent
REL = Path("sglang/srt/layers/hyperconnection.py")
s = (HERE.parent / "khc" / "patched" / REL).read_text(encoding="utf-8")


def sub(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:80], s.count(old))
    s = s.replace(old, new)


sub("""# Default OFF (4-Oct, daniel-bench-khcmix3-1004): bit-identical to the compiled chain but not faster at the first
# tactic (20.0 vs 19.4 us cold at 40 rows); SGLANG_KHC_MIX_MAX_ROWS=64 turns it on for tests.""",
    """# Default OFF: NOT bitwise (99.95% of elements equal the compiled chain; split-K sum order), -0.34 ms/step in-server
# (daniel-bench-khcmixs-1004), greedy inside cross-server noise. SGLANG_KHC_MIX_MAX_ROWS=64 turns it on.""")
sub("import os as _khc_os\n", "import os as _khc_os\nimport weakref as _kglue_weakref\n")
sub("\n\nclass HyperConnectionConfig(msgspec.Struct, frozen=True):",
    K.BLOCK + "\n\nclass HyperConnectionConfig(msgspec.Struct, frozen=True):")
# GatedResidual.__init__: add the link slots right after hc_norm is built
sub("""        self.hc_norm = GroupedGemmaRMSNorm(
            norm_dim, eps=self.config.rms_norm_eps, group_size=norm_group_size
        )
""", """        self.hc_norm = GroupedGemmaRMSNorm(
            norm_dim, eps=self.config.rms_norm_eps, group_size=norm_group_size
        )
""" + K.INIT_ADD)
# GatedResidual.mix (the second 'def mix' in the file; the base class has its own)
old_mix_head = """
    def mix(self, hyper_input: torch.Tensor):
        assert hyper_input.shape[-1] == self.hc_count * self.hidden_size
        if hyper_input.shape[0] == 0:"""
sub(old_mix_head, K.CAN_PRENORM)
sub(K.MIX_OLD, K.MIX_NEW)
sub(K.COMBINE_OLD, K.COMBINE_NEW)
for item in KM.SUBS:   # the fused mix: exact split per shape + PDL
    sub(*item)
out = HERE / "patched" / REL
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(s, encoding="utf-8")
compile(s, str(out), "exec")
print("wrote", out)
