"""Build the --early port cell for an MTP-capture run of Daniel Franzen's notebook (2-Oct-2026).

Son: retrain the draft recipe on Daniel's own target (Intel W4A16 AutoRound, unpruned, Pennyroyal SGLang v2.5.3 =
sglang 0.5.19+gd00d88efc8d6); reuse nothing trained on ours. The draft reads the target's layer-47 pre-mixer stream,
so the training data has to come from his server.

The cell (runs after his setup cell, before his pre-cache and launcher cells, nothing imported yet):
  1. border-off env (the variant the deploy A/B compares against: variants/noborder/early.py);
  2. a patched copy of his SGLang wheel: eagle_worker_v2.py + our capture hook (lobotomy/mtp/install_mtp_capture_patch.py,
     embedded below), inert unless ARC3_MTP_CAPTURE is set, with three port edits:
       - prefill slots 10 x 8192 tokens (his --chunked-prefill-size 8192; our 4096 slots would drop every chunk),
       - decode pages for <= 16 requests (he runs 10),
       - prefill copies on the MAIN stream (his fork can CUDA-graph prefill, so a side-stream copy could read a
         graph buffer after it is reused); decode already copies on the main stream;
     RECORD updated for the changed file;
  3. a shadow wheelhouse in /tmp (symlinks to every original file, the patched SGLang wheel in place of his), and
     WHEELHOUSE_DIR pointed at it (his lock pins sglang by version only, no hashes, so the patched wheel installs);
  4. ARC3_MTP_CAPTURE=/kaggle/working/mtp-capture (synced to GCS by the runner), minutes / byte budget.

  python make_capture_cell.py --out capture_cell.py [--minutes 30] [--max-gb 110]
"""
import argparse
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCH = Path(r"D:\codex-work\arc3-sglang-parking\gcp\controllers\sglang-scored\lobotomy\mtp\install_mtp_capture_patch.py")

CELL = r'''# --- daniel-draft port cell: MTP draft capture on Daniel's own target (2-Oct-2026; make_capture_cell.py) ---
# Border off (variants/noborder/early.py) + a patched SGLang wheel with our capture hook + ARC3_MTP_CAPTURE.
import base64 as _b64, hashlib as _hl, os as _os, sys as _sys, zipfile as _zf
from pathlib import Path as _P

NOBORDER = {
    'ARC3_NOOP_GUARD_BORDER': '0', 'ARC3_BATCH_NOOP_BLOCK': '0', 'ARC3_STALE_STATE_BLOCK': '0',
    'ARC3_EXPLAIN_GAMEPLAY_CHANGED': '0', 'ARC3_REPORT_GAMEPLAY_CHANGED': '0', 'ARC3_NEW_CHANGED_PROMPTS': '0',
}
_os.environ.update(NOBORDER)
assert not any(m.startswith(('inference', 'taaf')) for m in _sys.modules), 'harness imported before the port cell'

_PATCH_SRC = _b64.b64decode(__PATCH_B64__).decode('utf-8')
_cap = {'__name__': 'arc3_capture_patch'}
exec(compile(_PATCH_SRC, 'install_mtp_capture_patch.py', 'exec'), _cap)

def _port_edits(text):
    edits = [
        ('PREFILL_SLOTS, SLOT_TOKENS = 16, 4096', 'PREFILL_SLOTS, SLOT_TOKENS = 10, 8192  # Daniel port: his 8192-token chunks'),
        ('PAGES, PAGE_STEPS, MAX_BS = 6, 64, 32', 'PAGES, PAGE_STEPS, MAX_BS = 6, 64, 16  # Daniel port: <= 10 running'),
        ('            self.stream.wait_stream(main)\n            with torch.cuda.stream(self.stream):\n',
         '            if True:  # Daniel port: prefill copies on the main stream (his fork may CUDA-graph prefill)\n'),
        ('                event = torch.cuda.Event()\n                event.record(self.stream)\n',
         '                event = torch.cuda.Event()\n                event.record(main)\n'),
    ]
    for old, new in edits:
        assert text.count(old) == 1, ('capture port edit anchor', old[:60], text.count(old))
        text = text.replace(old, new)
    return text.replace('# ARC3_MTP_CAPTURE_V6\n', '# ARC3_MTP_CAPTURE_V6 (Daniel port)\n', 1)

_SRC_WH = _P(WHEELHOUSE_DIR)
_wheels = sorted((_SRC_WH / 'wheels').glob('sglang-*.whl'))
assert len(_wheels) == 1, _wheels
_EW = 'sglang/srt/speculative/eagle_worker_v2.py'
_SHADOW = _P('/tmp/arc3-wheelhouse')
(_SHADOW / 'wheels').mkdir(parents=True, exist_ok=True)
for _p in _SRC_WH.iterdir():
    if _p.name != 'wheels' and not (_SHADOW / _p.name).exists():
        (_SHADOW / _p.name).symlink_to(_p)
for _p in (_SRC_WH / 'wheels').iterdir():
    if _p != _wheels[0] and not (_SHADOW / 'wheels' / _p.name).exists():
        (_SHADOW / 'wheels' / _p.name).symlink_to(_p)
_out = _SHADOW / 'wheels' / _wheels[0].name
with _zf.ZipFile(_wheels[0]) as _zin, _zf.ZipFile(_out, 'w') as _zout:
    _new = _port_edits(_cap['patch_text'](_zin.read(_EW).decode('utf-8'))).encode('utf-8')
    compile(_new, _EW, 'exec')
    _digest = _b64.urlsafe_b64encode(_hl.sha256(_new).digest()).rstrip(b'=').decode()
    _record_line = f'{_EW},sha256={_digest},{len(_new)}'
    _n_record = 0
    for _info in _zin.infolist():
        _data = _zin.read(_info.filename)
        if _info.filename == _EW:
            _data = _new
        elif _info.filename.endswith('.dist-info/RECORD'):
            _lines = _data.decode('utf-8').splitlines()
            _hits = [i for i, l in enumerate(_lines) if l.startswith(_EW + ',')]
            assert len(_hits) == 1, _hits
            _lines[_hits[0]] = _record_line
            _n_record += 1
            _data = ('\n'.join(_lines) + '\n').encode('utf-8')
        _zout.writestr(_info, _data)
    assert _n_record == 1
WHEELHOUSE_DIR = str(_SHADOW)

_os.environ['ARC3_MTP_CAPTURE'] = '/kaggle/working/mtp-capture'
_os.environ['ARC3_MTP_CAPTURE_MINUTES'] = '__MINUTES__'
_os.environ['ARC3_MTP_CAPTURE_MAX_GB'] = '__MAX_GB__'
print('daniel-draft capture port: border off', sorted(NOBORDER), '| patched wheel', _out, len(_new), 'bytes',
      '| WHEELHOUSE_DIR ->', WHEELHOUSE_DIR, '| capture', _os.environ['ARC3_MTP_CAPTURE'],
      _os.environ['ARC3_MTP_CAPTURE_MINUTES'], 'min', _os.environ['ARC3_MTP_CAPTURE_MAX_GB'], 'GB')
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "capture_cell.py")
    ap.add_argument("--minutes", default="30")
    ap.add_argument("--max-gb", default="110")
    a = ap.parse_args()
    b64 = base64.b64encode(PATCH.read_bytes()).decode()
    cell = (CELL.replace("__PATCH_B64__", repr(b64)).replace("__MINUTES__", str(a.minutes))
            .replace("__MAX_GB__", str(a.max_gb)))
    a.out.write_text(cell, encoding="utf-8", newline="\n")
    print("wrote", a.out, len(cell), "chars")


if __name__ == "__main__":
    main()
