"""Multi-depth MTP capture: the target's hyper-connection stream after chosen layers, next to the layer-47 stream the
capture already records (4-Oct-2026, Son: "why not get more layers like DFlash?"; DFlash plan phase 2/3).

Builds on make_capture_cell.py's port cell (border off + capture hook V6 + Daniel-port edits, shadow wheel), adding:
  qwen4_exp.py     Qwen4ExpModel.forward: after layer i in ARC3_AUX_LAYERS, copy its stream state [T, 10240] into a
                   fixed GPU buffer (allocated once, rows <= ARC3_AUX_MAX_ROWS). A plain copy into a fixed buffer is
                   recorded into CUDA graphs and replayed (his fork graphs decode and may graph prefill), unlike the
                   fork's captured_last_layer_outputs list (Python, and ignored by the Qwen4Exp layers).
  eagle_worker_v2  both capture calls get the widened state cat(hc_47, aux rows) [T, 10240 * (1 + n_aux)]: the hook
                   sizes its pinned slots/pages from that width, so files, writer and stitcher work unchanged. The
                   draft still receives only hc_47 (nothing it consumes changes).
Rows match: the hook reads the aux buffer on the main stream right after the target forward of the same batch
(prefill: the batch's extend tokens; decode: the bs * D verify rows), before any later forward can overwrite it.
Offline: capture_io reads hc [n, 10240 * (1 + n_aux)]; hc[:, :10240] is the layer-47 stream (what the draft reads),
hc[:, 10240 * (k + 1): 10240 * (k + 2)] the stream after ARC3_AUX_LAYERS[k] (train_block.py --aux).

  python make_aux_capture_cell.py --out aux_capture_cell.py [--layers 11,23,35] [--minutes 30] [--max-gb 330]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, r"D:\codex-work\daniel-draft")
import make_capture_cell as MC  # noqa: E402

Q4 = "sglang/srt/models/qwen4_exp.py"
Q4_LOOP_ANCHOR = '''                    captured_last_layer_outputs=(
                        aux_hidden_states
                        if getattr(layer, "_is_layer_to_capture", False)
                        else None
                    ),
                )
'''
Q4_LOOP_NEW = Q4_LOOP_ANCHOR + '''                if _ARC3_AUX_ON and i in _ARC3_AUX_IDX:  # ARC3_AUX_CAPTURE
                    _arc3_aux_put(_ARC3_AUX_IDX[i], hidden_states)
'''
Q4_HELPER_ANCHOR = "\nALL_DECODER_LAYER_TYPES = {"
Q4_HELPER = '''
# ARC3_AUX_CAPTURE (4-Oct-2026): the stream after chosen layers -> one fixed GPU buffer (CUDA-graph safe) that the MTP
# capture hook appends to the layer-47 stream. Inert unless ARC3_AUX_LAYERS and ARC3_MTP_CAPTURE are both set.
import os as _arc3_aux_os
_ARC3_AUX_LAYERS = [int(x) for x in _arc3_aux_os.environ.get("ARC3_AUX_LAYERS", "").split(",") if x.strip()]
_ARC3_AUX_ON = bool(_ARC3_AUX_LAYERS) and bool(_arc3_aux_os.environ.get("ARC3_MTP_CAPTURE", ""))
_ARC3_AUX_IDX = {_l: _k for _k, _l in enumerate(_ARC3_AUX_LAYERS)}
_ARC3_AUX_ROWS = int(_arc3_aux_os.environ.get("ARC3_AUX_MAX_ROWS", "8448"))
_ARC3_AUX = {"buf": None, "oversize": 0}


def _arc3_aux_put(k, hs):
    flat = hs.reshape(hs.shape[0], -1)
    n, w = flat.shape
    buf = _ARC3_AUX["buf"]
    if buf is None:
        buf = _ARC3_AUX["buf"] = torch.zeros(_ARC3_AUX_ROWS, len(_ARC3_AUX_LAYERS) * w, dtype=flat.dtype,
                                             device=flat.device)
    if n <= buf.shape[0] and buf.shape[1] == len(_ARC3_AUX_LAYERS) * w:
        buf[:n, k * w:(k + 1) * w].copy_(flat)
    else:
        _ARC3_AUX["oversize"] += 1

'''
EW_PREFILL_OLD = "_arc3_mtp_capture(batch, target_hidden_states, mm_input_embeds)"
EW_PREFILL_NEW = "_arc3_mtp_capture(batch, _arc3_aux_widen(target_hidden_states), mm_input_embeds)"
EW_DECODE_OLD = "        hidden = result.logits_output.hidden_states\n"
EW_DECODE_NEW = "        hidden = _arc3_aux_widen(result.logits_output.hidden_states)  # ARC3_AUX_CAPTURE\n"
EW_HELPER_ANCHOR = "\ndef _arc3_mtp_capture(batch, hidden, mm_embeds):"
EW_HELPER = '''
def _arc3_aux_widen(h):
    """ARC3_AUX_CAPTURE: cat(layer-47 stream, the aux layers' rows of the same forward); h itself when off/unsure."""
    try:
        import sglang.srt.models.qwen4_exp as _q4
        buf = _q4._ARC3_AUX["buf"] if _q4._ARC3_AUX_ON else None
    except Exception:  # noqa: BLE001
        return h
    if buf is None or h is None or h.dim() != 2 or h.shape[0] > buf.shape[0]:
        return h
    return torch.cat((h, buf[: h.shape[0]].to(h.dtype)), -1)

'''

# extra cell code: runs inside the capture cell right after its own wheel rewrite (shadow wheel _out exists), patches
# qwen4_exp.py and widens the two capture calls in the already-patched eagle_worker_v2.py, RECORD updated for both
CELL_ADD = r"""
# --- blockdraft: multi-depth capture (make_aux_capture_cell.py, 4-Oct-2026) ---
_AUX_EDITS = __AUX_EDITS__
_tmp = _out.with_suffix('.aux.whl')
with _zf.ZipFile(_out) as _zin2, _zf.ZipFile(_tmp, 'w') as _zout2:
    _changed = {}
    for _name, _edits in _AUX_EDITS.items():
        _t = _zin2.read(_name).decode('utf-8')
        for _old, _new2, _count in _edits:
            assert _t.count(_old) == _count, ('aux capture anchor', _name, _old[:60], _t.count(_old))
            _t = _t.replace(_old, _new2)
        compile(_t, _name, 'exec')
        _changed[_name] = _t.encode('utf-8')
    _n_rec = 0
    for _info in _zin2.infolist():
        _data = _zin2.read(_info.filename)
        if _info.filename in _changed:
            _data = _changed[_info.filename]
        elif _info.filename.endswith('.dist-info/RECORD'):
            _lines = _data.decode('utf-8').splitlines()
            for _name, _b in _changed.items():
                _hits = [i for i, l in enumerate(_lines) if l.startswith(_name + ',')]
                assert len(_hits) == 1, (_name, _hits)
                _dg = _b64.urlsafe_b64encode(_hl.sha256(_b).digest()).rstrip(b'=').decode()
                _lines[_hits[0]] = f'{_name},sha256={_dg},{len(_b)}'
            _n_rec += 1
            _data = ('\n'.join(_lines) + '\n').encode('utf-8')
        _zout2.writestr(_info, _data)
    assert _n_rec == 1
_tmp.replace(_out)
_os.environ['ARC3_AUX_LAYERS'] = '__LAYERS__'
_os.environ['ARC3_AUX_MAX_ROWS'] = '8448'
print('blockdraft aux capture: layers', _os.environ['ARC3_AUX_LAYERS'], '| patched', sorted(_changed), '| wheel', _out)
"""
CELL_ANCHOR = "WHEELHOUSE_DIR = str(_SHADOW)\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "aux_capture_cell.py")
    ap.add_argument("--layers", default="11,23,35")
    ap.add_argument("--minutes", default="30")
    ap.add_argument("--max-gb", default="330")
    a = ap.parse_args()
    import base64
    b64 = base64.b64encode(MC.PATCH.read_bytes()).decode()
    cell = (MC.CELL.replace("__PATCH_B64__", repr(b64)).replace("__MINUTES__", str(a.minutes))
            .replace("__MAX_GB__", str(a.max_gb)))
    edits = {
        Q4: [(Q4_LOOP_ANCHOR, Q4_LOOP_NEW, 1), (Q4_HELPER_ANCHOR, Q4_HELPER + Q4_HELPER_ANCHOR, 1)],
        "sglang/srt/speculative/eagle_worker_v2.py": [(EW_PREFILL_OLD, EW_PREFILL_NEW, 1), (EW_DECODE_OLD, EW_DECODE_NEW, 1),
                                                      (EW_HELPER_ANCHOR, EW_HELPER + EW_HELPER_ANCHOR, 1)],
    }
    add = CELL_ADD.replace("__AUX_EDITS__", repr(edits)).replace("__LAYERS__", a.layers)
    assert cell.count(CELL_ANCHOR) == 1
    cell = cell.replace(CELL_ANCHOR, CELL_ANCHOR + add)
    compile(cell, "aux_capture_cell", "exec")
    a.out.write_text(cell, encoding="utf-8", newline="\n")
    print("wrote", a.out, len(cell), "chars | layers", a.layers)


if __name__ == "__main__":
    main()
