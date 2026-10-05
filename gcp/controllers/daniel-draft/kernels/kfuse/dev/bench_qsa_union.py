"""bench_qsa.py in union mode (gather once per request: qsa_union.py), W = 4 and 6 verify rows per request."""
import os, runpy, sys
os.environ["KF_QSA_MODE"] = "union"
sys.argv = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_qsa.py")]
runpy.run_path(sys.argv[0], run_name="__main__")
