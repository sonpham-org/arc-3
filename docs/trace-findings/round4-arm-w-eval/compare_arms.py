#!/usr/bin/env python3
"""
Author: Claude Opus 5 (Bubba sub-agent, label arc3-round4w-gameplay-eval)
Date: 20-September-2026
PURPOSE: Diff the arms of the round-4 arm-W held-out gameplay eval. Runs the ARC-3 oracle's
  own parity() logic over each pass's run_config.json to prove the arms differ only in
  `.model`, then aggregates per-arm gameplay results across passes and prints the head-to-head
  table. Consumes the JSON emitted by collect_results.py; performs no measurement of its own.
SRP/DRY check: Pass -- collect_results.py owns extraction, this owns comparison. The parity
  flatten/ignore set is copied from run_oracle_multipass.sh's parity() deliberately so the
  arms are held to the same standard the banked oracle passes are, rather than a looser one
  invented here.
"""
import json, sys, os, statistics

# Same ignore set as run_oracle_multipass.sh's parity(): fields that legitimately differ
# between two runs of an identical configuration.
IGNORE = {'.generated_at', '.kaggle_competition', '.kaggle_dataset', '.run_name',
          '.started_at', '.run_dir', '.output_dir'}

def flat(d, p=''):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, p + '.' + k if p else '.' + k))
        else:
            out[(p + '.' + k) if p else '.' + k] = v
    return out

def parity(ref_cfg, cfg):
    a, b = flat(ref_cfg), flat(cfg)
    diffs = []
    for k in sorted(set(a) | set(b)):
        if k in IGNORE:
            continue
        if a.get(k) != b.get(k):
            diffs.append((k, a.get(k), b.get(k)))
    return diffs

def load(paths):
    return [json.load(open(p)) for p in paths]

def agg(results):
    """Aggregate one arm's passes. Levels and score are summed within a pass, then
    averaged across passes -- a pass is the unit of replication, not a game."""
    per_pass = []
    for r in results:
        t = r['total']
        per_pass.append({
            'levels': t['levels_completed'], 'score': t['final_score'],
            'actions': t['actions'], 'turns': t['turns'], 'err': t['err_turns'],
            'tool_pct': t['tool_pct'], 'reas': t['mean_reasoning_chars'],
            'mean_turn_s': t['mean_turn_s'], 'lost_s': t['wall_lost_to_timeouts_s'],
        })
    out = {'n_passes': len(per_pass), 'passes': per_pass}
    for k in ('levels', 'score', 'actions', 'turns', 'err', 'tool_pct', 'reas',
              'mean_turn_s', 'lost_s'):
        vals = [p[k] for p in per_pass if p[k] is not None]
        out[k + '_mean'] = statistics.mean(vals) if vals else None
        out[k + '_vals'] = vals
    return out

if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))   # {"arm": ["result1.json", ...], ...}
    arms = {a: load(ps) for a, ps in spec.items()}

    print("=== PARITY: every pass vs base pass 1, oracle ignore set ===")
    ref = arms['base'][0]['run_config']
    ok = True
    for a, rs in arms.items():
        for i, r in enumerate(rs):
            d = parity(ref, r['run_config'])
            keys = [k for k, _, _ in d]
            flag = "OK" if keys in ([], ['.model']) else "*** UNEXPECTED ***"
            if keys not in ([], ['.model']):
                ok = False
            print(f"  {a} pass{i+1}: unexpected_diffs={keys} {flag}")
            for k, x, y in d:
                print(f"      {k}: ref={x!r} this={y!r}")
    print(f"  => arms differ only in .model: {ok}")
    print()

    print("=== PER-ARM GAMEPLAY (mean over passes) ===")
    print(f"{'arm':12s} {'n':>2s} {'levels':>8s} {'score':>9s} {'actions':>8s} {'turns':>6s} "
          f"{'err':>4s} {'tool%':>6s} {'reasChr':>8s} {'meanTurn':>9s} {'lostS':>7s}")
    for a in ('base', 'round3', 'round4W', 'round4W-step44', 'round4W-step22'):
        if a not in arms:
            continue
        g = agg(arms[a])
        def f(k, d=1):
            v = g[k + '_mean']
            return f"{v:.{d}f}" if v is not None else "-"
        print(f"{a:12s} {g['n_passes']:>2d} {f('levels',2):>8s} {f('score',3):>9s} "
              f"{f('actions',1):>8s} {f('turns',1):>6s} {f('err',1):>4s} {f('tool_pct'):>6s} "
              f"{f('reas',0):>8s} {f('mean_turn_s'):>9s} {f('lost_s',0):>7s}")
        print(f"{'':12s}    per-pass levels={g['levels_vals']} score={[round(x,3) for x in g['score_vals']]}")

    print()
    print("=== PER-GAME, pass 1 of each arm ===")
    games = sorted(arms['base'][0]['games'].keys())
    hdr = f"{'game':8s}" + ''.join(f"{a:>18s}" for a in arms)
    print(hdr)
    for gm in games:
        row = f"{gm[:4]:8s}"
        for a in arms:
            r = arms[a][0]['games'][gm]
            sc = r['final_score'] if r['final_score'] is not None else 0.0
            row += f"{str(r['levels_completed'])+'lv/'+format(sc,'.3f'):>18s}"
        print(row)
