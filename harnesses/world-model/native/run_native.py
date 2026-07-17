import sys, os, json, traceback
sys.path.insert(0, "/opt/native")
import env, wm
games = os.environ.get("WM_GAMES", "ls20 ft09").split()
out = {}
for g in games:
    try:
        E = env.ArcEnv(g, env_root="/opt/native/environment_files")
        E.reset()
        res = wm.cegis(E, n_transitions=16, max_rounds=3)
        out[g] = {"admitted": res["admitted"], "passed": res["passed"],
                  "total": res["total"], "rounds": res["rounds"], "code": res["code"]}
        print(f"=== {g}: admitted={res['admitted']} {res['passed']}/{res['total']} rounds={res['rounds']} ===", flush=True)
    except Exception as e:
        out[g] = {"error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1500:]}
        print(f"=== {g}: ERROR {e} ===", flush=True)
json.dump(out, open("/opt/native/native_results.json", "w"), indent=1)
print("WROTE native_results.json", flush=True)
