"""After another pre-script: is the GPU still usable? nvidia-smi + a CUDA context + a tiny kernel (kfuse 4-Oct)."""
import json, subprocess, time
r = {}
for attempt in range(3):
    p = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,compute_mode", "--format=csv,noheader"],
                       capture_output=True, text=True)
    r[f"nvidia_smi_{attempt}"] = (p.returncode, (p.stdout or p.stderr)[-200:])
    try:
        import torch
        x = torch.ones(1024, device="cuda"); torch.cuda.synchronize()
        r[f"torch_{attempt}"] = float(x.sum().item())
    except Exception as e:
        r[f"torch_{attempt}"] = repr(e)[:300]
    if p.returncode == 0:
        break
    time.sleep(5)
p = subprocess.run("dmesg 2>&1 | grep -i -E 'xid|nvrm' | tail -5", shell=True, capture_output=True, text=True)
r["dmesg"] = p.stdout[-800:]
print(json.dumps(r))
