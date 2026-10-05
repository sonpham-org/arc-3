"""Mutation check for the CPU emulation: each deliberate bug must fail at least one
case (scales_token_major is a valid alternative layout and is expected to pass).
"""
import os, subprocess, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "patched", "sglang", "srt", "mem_cache", "pool_host", "mha.py")
WORK = os.environ.get("TEMP", HERE)
code = open(SRC, encoding="utf-8").read()
mutations = {
    "swap_backup_page_ids": ("                    dst_indices, src_indices = pages\n", "                    src_indices, dst_indices = pages\n"),
    "row_bytes_for_page_items": ("            segment.item_bytes = segment.row_bytes * per_item\n", "            segment.item_bytes = segment.row_bytes\n"),
    "drop_scale_route": ("            rows, scales = self._segments[0], self._segments[1]\n            return (\n", "            rows, scales = self._segments[0], self._segments[1]\n            return (\n                (\n                    rows,\n                    host_layer_id,\n                    device_pool.k_buffer[device_layer_id],\n                    device_pool.v_buffer[device_layer_id],\n                ),\n            )\n            return (\n"),
    "draft_layer_off_by_one": ("                host_layer_id - self._packed_layer_num,\n", "                host_layer_id - self._packed_layer_num + 1,\n"),
    "staged_wrong_layer_count": ("            (self.staging_token_capacity, rows.num_layers, *rows.row_shape),\n", "            (self.staging_token_capacity, rows.num_layers + 1, *rows.row_shape),\n"),
    "scales_token_major": ("                page_major=True,\n", "                page_major=rows_per_page,\n"),
}
out = {}
for name, (old, new) in mutations.items():
    assert code.count(old) == 1, (name, code.count(old))
    path = os.path.join(WORK, f"qsakv4h_mha_{name}.py")
    open(path, "w", encoding="utf-8").write(code.replace(old, new))
    env = dict(os.environ, MHA_PATH=path)
    r = subprocess.run([sys.executable, os.path.join(HERE, "run_emu.py")], capture_output=True, text=True, env=env, timeout=900)
    try:
        failed = json.loads(r.stdout)["failed"]
    except Exception:
        failed = ["<crash> " + (r.stderr or r.stdout)[-300:]]
    out[name] = len(failed)
    print(name, "-> failing cases:", len(failed), failed[:2])
print("caught:", {k: v > 0 for k, v in out.items()})
