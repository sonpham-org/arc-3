# daniel-draft (Slice and dice the brain): serving speed + drafters on Daniel Franzen's ARC-AGI-3 SGLang stack

Source mirror of `D:\codex-work\daniel-draft` (code only: no notebooks, wheels, captures, checkpoints, profiles).
Owner: the "Slice and dice the brain" thread (kernels, MTP chain drafter, block/DFlash drafters, captures).

- `make_variant_notebook.py` - the shipping notebook builder (patch sets ride the --rs shadow wheel; a later set may
  supersede an earlier copy of the same file only when both start from the same original).
- `make_bench_notebook.py` - 25-min speed-bench builder (--patch-set, --server-args, --spec-off, --pre-script).
- `kernels/<set>/` - patch sets: `orig/` = byte copies of the files in Daniel's SGLang fork wheel (Apache-2.0,
  SGLang project) used for sha checks, `patched/` = our modified copies, `README.md` = what/why/exactness/off-switch.
  kfast, kfast128, kfuse/kfuse8, kq8/kq8r, kdsamp, kconv, kdhead8, ktsamp (ours); kidx/kidxr, khc, kglue, kpdl, klmh,
  kgdn (Kernel optimizations thread).
- `replay/` - regenerate drafter training data from saved request logs (replay through his server + capture hook).
- `lab/` - lab VM worker/launcher for offline drafter training (`dlab_worker.sh`, `launch_dlab.py`).
- `live/` - run readers: `bench_report.py`, `settle.py` (speed settles in 15-20 min), grid/tokmatch tools.
- `spectree/`, `blockdraft/` - draft trees / segment study, block-drafter scoping.
The drafter trainer itself lives in `../sglang-scored/lobotomy/mtp/` (train_draft.py: multi-GPU via torchrun,
resumable train_state.pt, --resume-state; draft_torch.py; capture_io.py; replay_rows.py).
