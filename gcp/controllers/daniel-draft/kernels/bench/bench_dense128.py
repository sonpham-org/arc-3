"""bench_dense.py at 64-128 rows (deeper drafts / more lanes; 3-Oct-2026 kfuse follow-up): cuBLAS vs skinny."""
import os, runpy, sys
os.environ["DENSE_MS"] = "78,96,128,64"
os.environ["DENSE_SHAPES"] = "gdn_in_proj_qkvzba,gdn_out_proj,qsa_qkv_gate,qsa_o_proj,shared_gate_up,shared_down,router_gate"
sys.argv = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_dense.py")]
runpy.run_path(sys.argv[0], run_name="__main__")
