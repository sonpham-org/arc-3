# --- daniel-base port cell: noborder (Son 1-Oct-2026: "try switching the border rule off") ---
# Turns off Daniel's 4-cell border rule (deciding whether a move changed the game while ignoring the outer 4 cells,
# where timer and step bars live) and everything that acts on it or explains it. Nothing else changes.
#   ARC3_NOOP_GUARD_BORDER=0         change detection uses the whole board (gameplay_changed == board_changed);
#                                    also disables the batch no-op stop (it requires a border > 0)
#   ARC3_BATCH_NOOP_BLOCK=0          no batch stop at the first do-nothing move (explicit)
#   ARC3_STALE_STATE_BLOCK=0         no refusal of the next move after a do-nothing move
#   ARC3_EXPLAIN_GAMEPLAY_CHANGED=0  system prompt no longer explains board_changed vs gameplay_changed
#   ARC3_REPORT_GAMEPLAY_CHANGED=0   turn opener reports the whole-board change line (Tufa's original)
#   ARC3_NEW_CHANGED_PROMPTS=0       guard / outcome wording back to "changed nothing" (no "inside the board area")
# Side effect: his changed-cells images now include edge cells too.
NOBORDER = {
    'ARC3_NOOP_GUARD_BORDER': '0',
    'ARC3_BATCH_NOOP_BLOCK': '0',
    'ARC3_STALE_STATE_BLOCK': '0',
    'ARC3_EXPLAIN_GAMEPLAY_CHANGED': '0',
    'ARC3_REPORT_GAMEPLAY_CHANGED': '0',
    'ARC3_NEW_CHANGED_PROMPTS': '0',
}
_before = {k: os.environ.get(k) for k in NOBORDER}
os.environ.update(NOBORDER)
assert not any(m.startswith(('inference', 'taaf')) for m in sys.modules), 'harness imported before the port cell'
print('daniel-base port noborder:', {k: f'{_before[k]} -> {v}' for k, v in NOBORDER.items()})

# --- port: ARC hot-token map for the drafter (Son 2-Oct-2026: "0.4% is STILL important. Squeeze every gain") ---
# FR-Spec: the drafter only proposes tokens in a 64k list. His list (pennyroyal hot_tokens_64k.pt) covers 98.70% of
# the tokens the model generates in ARC play (our 201.6M-token count), so ~1 token in 77 can never be drafted. Our
# ARC-built list (lobotomy/mtp/assets/arc-hot-64k.json, same 248,044-token vocabulary and added tokens as his Intel
# model) covers 99.99% on held-out games. Lossless: the target still verifies every token. Our A/B: 557 vs 555 tok/s.
# The launcher cell reads ARC3_FRSPEC_MAP (build_daniel_notebook.py --frspec-map-env) instead of his pinned file.
import base64 as _b64, json as _json, zlib as _zlib, hashlib as _hl
_bits = _zlib.decompress(_b64.b64decode(
    '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'
'n1OgXLsnsjCO/39ID9g+8X9Zf+pd'))
_ids = [i for i in range(len(_bits) * 8) if _bits[i >> 3] >> (i & 7) & 1]
assert len(_ids) == 65536 and _hl.sha256(_json.dumps(_ids).encode()).hexdigest() == '6338da5e47b13fa4a56ae90118b68034cb8d544709a95233104765257d928d17', 'ARC hot map decode'
import torch as _torch
_map = '/kaggle/working/arc-hot-64k.pt'
_torch.save(_ids, _map)
assert _torch.load(_map) == _ids
os.environ['ARC3_FRSPEC_MAP'] = _map
print('daniel-base port hotarc:', _map, len(_ids), 'ids, sha(ids)', '6338da5e47b1')

# --- port: tuned MTP drafter (Slice and dice, 2-Oct-2026; live +6.4% accept, +5.6% tok/s on GCP) ---
# His drafter dir with only the dense mtp.* tensors retrained on his own target's play; experts, embed, lm_head, config
# byte-identical. Needs the daniel-draft input mirror (his inputs + models/cellens/daniel-drafter-tuned).
_TUNED = '/kaggle/input/models/cellens/daniel-drafter-kv4/transformers/default/1'
assert os.path.isfile(os.path.join(_TUNED, 'TUNED.json')) and os.path.isfile(os.path.join(_TUNED, 'config.json')), _TUNED
print('daniel-base port tuned drafter: DRAFT_MODEL_DIR', DRAFT_MODEL_DIR, '->', _TUNED)
DRAFT_MODEL_DIR = _TUNED
