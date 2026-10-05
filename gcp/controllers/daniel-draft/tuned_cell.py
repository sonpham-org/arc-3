# --- daniel-draft port cell: tuned MTP draft (2-Oct-2026; daniel-draft lab) ---
# Border off (variants/noborder/early.py, the control the deploy A/B compares against) + DRAFT_MODEL_DIR -> his drafter
# with its dense layers retrained on his own target's play (plain KL, lr 2e-5, experts frozen, whole games held out).
# Everything else in the drafter dir is byte-identical to his: INT4 experts, embed, lm_head, config, tokenizer.
import os as _os, sys as _sys

NOBORDER = {
    'ARC3_NOOP_GUARD_BORDER': '0', 'ARC3_BATCH_NOOP_BLOCK': '0', 'ARC3_STALE_STATE_BLOCK': '0',
    'ARC3_EXPLAIN_GAMEPLAY_CHANGED': '0', 'ARC3_REPORT_GAMEPLAY_CHANGED': '0', 'ARC3_NEW_CHANGED_PROMPTS': '0',
}
_os.environ.update(NOBORDER)
assert not any(m.startswith(('inference', 'taaf')) for m in _sys.modules), 'harness imported before the port cell'
_TUNED = '/kaggle/input/models/cellens/daniel-drafter-tuned/transformers/default/1'
assert _os.path.isfile(_os.path.join(_TUNED, 'TUNED.json')) and _os.path.isfile(_os.path.join(_TUNED, 'config.json')), _TUNED
print('daniel-draft tuned port: border off', sorted(NOBORDER), '| DRAFT_MODEL_DIR', DRAFT_MODEL_DIR, '->', _TUNED)
DRAFT_MODEL_DIR = _TUNED
