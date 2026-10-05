"""Source dump from his venv (4-Oct-2026, Kernel optimizations thread). Pre-server script, CPU only.
Packs the installed flashinfer gdn_kernels package (not in the 0.6.17 wheel we have locally: it carries his
gated_delta_rule_mtp_wy_output_only build) and a few sglang kernel modules into /kaggle/working/src_dump.tgz.
"""
import importlib
import inspect
import json
import os
import tarfile

OUT = "/kaggle/working/src_dump.tgz"
MODS = ["flashinfer.gdn_kernels", "flashinfer.gdn_decode", "flashinfer.gdn_prefill",
        "sglang.kernels.ops.attention.fla.fused_sigmoid_gating_recurrent",
        "sglang.srt.layers.attention.linear.kernels.gdn_flashinfer"]


def main():
    added, info = [], {}
    with tarfile.open(OUT, "w:gz") as t:
        for m in MODS:
            try:
                mod = importlib.import_module(m)
                path = os.path.dirname(mod.__file__) if mod.__file__.endswith("__init__.py") else mod.__file__
                t.add(path, arcname=m)
                added.append(m)
                info[m] = path
            except Exception as e:
                info[m] = "ERR " + repr(e)[:200]
        try:
            import flashinfer.gdn_kernels as G
            f = getattr(G, "gated_delta_rule_mtp_wy_output_only", None)
            if f is not None:
                info["wy_output_only_file"] = inspect.getsourcefile(f)
                src = inspect.getsource(f)
                p = "/kaggle/working/wy_output_only_src.py"
                open(p, "w").write(src)
                t.add(p, arcname="wy_output_only_src.py")
        except Exception as e:
            info["wy"] = "ERR " + repr(e)[:200]
        try:
            import flashinfer
            info["flashinfer_version"] = flashinfer.__version__
        except Exception:
            pass
    print(json.dumps(dict(kind="dump", added=added, info=info, out=OUT)), flush=True)
    print(json.dumps(dict(verdict="PASS")), flush=True)


if __name__ == "__main__":
    main()
