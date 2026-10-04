"""Build the RL rollout-server notebook: a scored build + coach hooks + state snapshots + server.

Author: Claude Opus 5.5 (3-Oct-2026; --base-build 4-Oct-2026).

  C:/Python312/python.exe build_rl_notebook.py --out D:/codex-work/gtree-rl/nb [--budget-s 7200] [--lanes N]
                                               [--restorers N] [--base-build DIR | --legacy] [--upload]

Default (4-Oct, Son: "optimize the rollout ... as fast as possible"): --base-build = the fastest scored build,
D:/codex-work/clkchk/daniel-nb/sbt06tfrskv4s13 (notebook e7e455081e62: border off, hot map, tuned drafter, T0.6,
toolfast, rejection sampling, 4-bit QSA KV, 13 slots x 131k; 52.8 over 2 runs, Kaggle 3-Oct). Its notebook is taken
as built (launcher, server patches and its check cells untouched); three cells change:
  port      its port cell -> + the coach hooks (variants/coach/build_early.py COACH_PART) -> + the gtree port
            (build_port.early_cell, same env as the legacy build)
  launcher  + --enable-cache-report --enable-metrics (RL_LAUNCH_ADD)
  override  the daniel-base override + rollout_driver.bind(bm) (same 25 games / 7920 s as its bench override)
Lanes default to its server's slot count (ARC3_SRV_MAXREQ, 13). --legacy builds the 3-Oct composition below.

Legacy (3-Oct): the target harness is D:/codex-work/clkchk/daniel-nb/sbt06hic11 (gs://.../daniel-base/notebooks/f40b168002b8):
make_variant_notebook.py --base-early variants/subbuild/t06/early.py --frspec-map-env --oa 11 --hicache-gb 32
(border off, ARC hot map, tuned drafter, T0.6, 11 games over 10 server slots + 32 GB host KV tier). This build is the
same notebook with three additions in the port cell and one in the override cell:
  port   t06/early.py (verbatim) -> the coach hooks (variants/coach/build_early.py COACH_PART, current arc3_coach.py:
         policy @file reload, assign_next) -> his host tier + over-admission (make_hicache_notebook.PORT_ADD, 11 / 32)
         -> the gtree port (build_port.early_cell): arc3_state.py + the analyze hook, the driver payload, and
         ARC3_ROLLOUT=server, ARC3_ROLLOUT_LANES, ARC3_ROLLOUT_BUDGET_S, ARC3_STATE_SNAPSHOTS=1, ARC3_COACH=policy,
         ARC3_COACH_POLICY=@/kaggle/rollout/policy/current.json
  launcher his host-tier flags (make_hicache_notebook.LAUNCH_ADD) + --enable-cache-report --enable-metrics (cached
         tokens in each response's usage and /metrics: the prefix-sharing proof; neither changes what is generated)
  override the daniel-base override + rollout_driver.bind(bm): his run cell awaits bm.run = the rollout server
Left out on purpose: his host-tier reload CHECK cell (it fills 1.4M tokens before the first game; the tier itself
was checked exact on 6 runs). In server mode the driver sets ARC3_MAX_ACTIVE_STREAMS=0: the lanes are the admission
control (his gate would hold forked children's slots); the gate changes ordering only, never a prompt.
Writes <out>/notebook.ipynb, port_cell.py, override.py, BUILD.json; --upload copies the notebook to
gs://cellens-ai-artifacts/arc3-duck/daniel-base/notebooks/<sha12>/notebook.ipynb (a file in our bucket, not a
launch or a publication).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_port  # noqa: E402

DRAFT = Path(r"D:\codex-work\daniel-draft")
T06 = Path(r"D:\codex-work\daniel-base-20261001\variants\subbuild\t06\early.py")
COACH_BUILD = Path(r"D:\codex-work\daniel-base-20261001\variants\coach\build_early.py")
TARGET = Path(r"D:\codex-work\clkchk\daniel-nb\sbt06hic11")
BASE_BUILD = Path(r"D:\codex-work\clkchk\daniel-nb\sbt06tfrskv4s13")
RL_LAUNCH_ADD = '''
if os.environ.get("ARC3_ROLLOUT"):  # gtree-rollout: cached tokens in usage + /metrics (proof of prefix sharing)
    args += ["--enable-cache-report", "--enable-metrics"]
'''


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def src(c) -> str:
    return "".join(c["source"]) if isinstance(c["source"], list) else c["source"]


def port_cell(env: dict[str, str]) -> str:
    be = _load(COACH_BUILD, "_rl_coach_build")
    H = _load(DRAFT / "make_hicache_notebook.py", "_rl_hicache")
    base = be.arm_cell(T06.read_text(encoding="utf-8"), {}, True).rstrip("\n") + "\n"
    base += H.PORT_ADD.replace("__OA__", "11").replace("__GB__", "32")
    return build_port.early_cell(env, base)


def rollout_env(lanes: int, budget_s: int, restorers: int) -> dict[str, str]:
    env = {"ARC3_ROLLOUT": "server", "ARC3_ROLLOUT_LANES": str(lanes), "ARC3_ROLLOUT_BUDGET_S": str(budget_s),
           "ARC3_STATE_SNAPSHOTS": "1", "ARC3_COACH": "policy",
           "ARC3_COACH_POLICY": "@/kaggle/rollout/policy/current.json"}
    if restorers:
        env["ARC3_ROLLOUT_RESTORERS"] = str(restorers)
    return env


def finish(out: Path, nb: dict, build: dict, upload: bool, H) -> int:
    data = (json.dumps(nb, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    (out / "notebook.ipynb").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = f"{H.BUCKET}/{sha[:12]}/notebook.ipynb"
    build.update(notebook_sha256=sha, gcs_object=obj, uploaded=False)
    if upload:
        subprocess.run(H.GCLOUD + ["storage", "cp", "-q", str(out / "notebook.ipynb"), obj], check=True)
        build["uploaded"] = True
    (out / "BUILD.json").write_text(json.dumps(build, indent=1), encoding="utf-8")
    print(obj if upload else f"built {out / 'notebook.ipynb'} ({len(data)} bytes); --upload would write {obj}")
    return 0


def build_on(base_dir: Path, out: Path, a, H) -> int:
    """The rollout server on a finished scored build: its notebook as built, with the port, launcher and override
    cells changed (module docstring)."""
    bb = json.loads((base_dir / "BUILD.json").read_text(encoding="utf-8"))
    lanes = a.lanes or int((bb.get("bench") or {}).get("ARC3_SRV_MAXREQ") or 10)
    env = rollout_env(lanes, a.budget_s, a.restorers)
    env.update(dict(kv.split("=", 1) for kv in a.set))       # after the base cell's own settings, so these win
    be = _load(COACH_BUILD, "_rl_coach_build_on")
    base_port = (base_dir / "port_cell.py").read_text(encoding="utf-8")
    port = build_port.early_cell(env, be.arm_cell(base_port, {}, True))
    override = build_port.override_cell()
    for name, text in (("port_cell.py", port), ("override.py", override)):
        compile(text, name, "exec")
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    nb = json.loads((base_dir / "notebook.ipynb").read_text(encoding="utf-8"))
    base_override = (base_dir / "override.py").read_text(encoding="utf-8")
    code = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"]
    ports = [i for i in code if src(nb["cells"][i]).rstrip() == base_port.rstrip()]
    overs = [i for i in code if src(nb["cells"][i]).rstrip() == base_override.rstrip()]
    launch = [i for i in code if H.LAUNCH_ANCHOR in src(nb["cells"][i])]
    assert len(ports) == len(overs) == len(launch) == 1, (ports, overs, launch)
    assert src(nb["cells"][launch[0]]).count(H.LAUNCH_ANCHOR) == 1
    assert "max_runtime_s_per_game = 7920" in base_override and "concurrency = 25" in base_override, \
        "the base build's override is not the 25-game / 7920 s shape the rollout override assumes"
    nb["cells"][ports[0]]["source"] = port
    nb["cells"][overs[0]]["source"] = override
    s = src(nb["cells"][launch[0]])
    nb["cells"][launch[0]]["source"] = s.replace(H.LAUNCH_ANCHOR, RL_LAUNCH_ADD + H.LAUNCH_ANCHOR)
    for i in (ports[0], overs[0], launch[0]):
        nb["cells"][i]["outputs"], nb["cells"][i]["execution_count"] = [], None
    build = {"target": f"{str(bb.get('notebook_sha256', ''))[:12]} ({base_dir})", "base_build": str(base_dir),
             "env": env, "lanes": lanes, "cells": {"port": ports[0], "launcher": launch[0], "override": overs[0]},
             "base_bench": bb.get("bench")}
    return finish(out, nb, build, a.upload, H)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget-s", type=int, default=7200)
    ap.add_argument("--lanes", type=int, default=0, help="0 = the base build's server slots (legacy: 10)")
    ap.add_argument("--restorers", type=int, default=0, help="0 = lanes // 5 + 2")
    ap.add_argument("--base-build", default=str(BASE_BUILD),
                    help="a finished scored build dir (BUILD.json, notebook.ipynb, port_cell.py, override.py)")
    ap.add_argument("--legacy", action="store_true", help="the 3-Oct composition on f40b168002b8")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="extra env after the base build's (e.g. ARC3_SRV_MAXREQ=16 with --lanes 16)")
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    H = _load(DRAFT / "make_hicache_notebook.py", "_rl_hicache2")
    if not a.legacy:
        return build_on(Path(a.base_build), out, a, H)
    env = rollout_env(a.lanes or 10, a.budget_s, a.restorers)
    port = port_cell(env)
    override = build_port.override_cell()
    for name, text in (("port_cell.py", port), ("override.py", override)):
        compile(text, name, "exec")
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    # the target build's port cell must be a prefix-equivalent of ours: same t06 cell, same host-tier block
    tgt = (TARGET / "port_cell.py").read_text(encoding="utf-8")
    t06 = T06.read_text(encoding="utf-8").rstrip("\n")
    assert tgt.startswith(t06) and t06 in port, "t06 port cell changed since the target build"
    hic = H.PORT_ADD.replace("__OA__", "11").replace("__GB__", "32").strip()
    assert hic in tgt and hic in port, "host-tier block differs from the target build"
    base = out / "base"
    cmd = [sys.executable, str(H.BUILDER), "--source", str(H.SOURCE), "--early", str(out / "port_cell.py"),
           "--override", str(out / "override.py"), "--compile-threads", "1", "--frspec-map-env", "--out", str(base)]
    subprocess.run(cmd, check=True, capture_output=True)
    nb = json.loads((base / "notebook.ipynb").read_text(encoding="utf-8"))
    hits = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code" and H.LAUNCH_ANCHOR in src(c)]
    assert len(hits) == 1, hits
    li = hits[0]
    s = src(nb["cells"][li])
    nb["cells"][li]["source"] = s.replace(H.LAUNCH_ANCHOR, H.LAUNCH_ADD + RL_LAUNCH_ADD + H.LAUNCH_ANCHOR)
    if not src(nb["cells"][li]).lstrip().startswith("%"):
        compile(src(nb["cells"][li]), "launcher", "exec")
    build = {"target": "f40b168002b8 (clkchk/daniel-nb/sbt06hic11)", "env": env, "launcher_cell": li}
    return finish(out, nb, build, a.upload, H)


if __name__ == "__main__":
    raise SystemExit(main())
