#!/usr/bin/env python3
"""
Author: Claude Opus 5 (Bubba sub-agent, label arc3-round4w-gameplay-eval)
Date: 20-September-2026
PURPOSE: Extract per-game and per-arm gameplay metrics from one ARC3-Inference run dir for
  the round-4 arm-W held-out evaluation. Reads the run's own artifacts only -- levels, score
  and actions from artifacts/*_viewer_data.json, and turn count, per-turn deliberation wall
  time, tool validity and vLLM read-timeout losses from transcripts/*.txt. Emits one JSON
  blob per run dir so that arms can be diffed without re-reading raw logs.
SRP/DRY check: Pass -- measurement is produced by the ARC3 harness; this script only reads
  and aggregates its artifacts. It defines no game fence and no scoring of its own. The
  held-out fence is owned by distill/extract_sft.py and is passed in, not redefined here.

Metric definitions, fixed here so every arm is counted identically:
  turns      -- analyzer turn blocks in the transcript
  err        -- turns that recorded `request_error` (vLLM read timeout: no response at all)
  answered   -- turns - err
  tool_ok    -- answered turns that emitted at least one tool call
  in_flight  -- turns with no response recorded yet (mid-run snapshots only); excluded
                from every denominator
  tool_pct   -- tool_ok / answered. `err` turns are excluded from the denominator because a
                turn that received no response has nothing that could be malformed. This is
                the correction PR #59 applied to its own first cut.
  mean_turn_s-- mean gap between consecutive turn timestamps (last turn measured to run end)
"""
import json, os, re, sys, datetime

TURN_RE = re.compile(r'^--- analysis_step=(\d+) \| action=(\d+) \| (\d{2}:\d{2}:\d{2}) \| ')

def parse_transcript(path):
    """Split a transcript into turn blocks and score each one."""
    if not os.path.exists(path):
        return None
    raw = open(path, errors='replace').read()
    lines = raw.split('\n')
    starts = []
    for i, ln in enumerate(lines):
        m = TURN_RE.match(ln)
        if m:
            starts.append((i, m.group(3)))
    turns = []
    for idx, (ln_i, ts) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = '\n'.join(lines[ln_i:end])
        tc = re.search(r'^tool_call_count: (\d+)', block, re.M)
        turns.append({
            'ts': ts,
            'tool_calls': int(tc.group(1)) if tc else 0,
            # A turn with neither a response-meta block nor a request_error is still in
            # flight. It is neither answered nor failed and must not land in either
            # denominator, or a mid-run snapshot reads as a tool-validity regression.
            'complete': (tc is not None) or ('request_error' in block),
            'error': 'request_error' in block,
            'reasoning_chars': int(m.group(1)) if (m := re.search(r'^reasoning_chars: (\d+)', block, re.M)) else 0,
        })
    # deliberation: gap to the next turn. The final turn has no successor, so it is left None
    # and excluded from the mean rather than guessed at.
    for i in range(len(turns) - 1):
        a = datetime.datetime.strptime(turns[i]['ts'], '%H:%M:%S')
        b = datetime.datetime.strptime(turns[i + 1]['ts'], '%H:%M:%S')
        d = (b - a).total_seconds()
        if d < 0:            # midnight rollover
            d += 86400
        turns[i]['dur_s'] = d
    if turns:
        turns[-1]['dur_s'] = None
    return turns

def collect(run_dir, games):
    out = {'run_dir': run_dir, 'games': {}}
    cfg = json.load(open(os.path.join(run_dir, 'run_config.json')))
    out['model'] = cfg.get('model')
    out['run_config'] = cfg
    for g in games:
        vd_p = os.path.join(run_dir, 'artifacts', f'{g}_p0_viewer_data.json')
        tr_p = os.path.join(run_dir, 'transcripts', f'{g}_p0.txt')
        if not os.path.exists(vd_p):
            out['games'][g] = {'missing': True}
            continue
        vd = json.load(open(vd_p))
        turns = parse_transcript(tr_p) or []
        err = [t for t in turns if t['error']]
        answered = [t for t in turns if t['complete'] and not t['error']]
        in_flight = [t for t in turns if not t['complete']]
        tool_ok = [t for t in answered if t['tool_calls'] >= 1]
        durs = [t['dur_s'] for t in turns if t.get('dur_s') is not None]
        err_durs = [t['dur_s'] for t in err if t.get('dur_s') is not None]
        apl = vd.get('actions_per_level') or {}
        if isinstance(apl, dict):
            actions = sum(apl.values())
        else:
            actions = sum(apl)
        out['games'][g] = {
            'levels_completed': vd.get('levels_completed'),
            'total_levels': vd.get('total_levels'),
            'final_score': vd.get('final_score'),
            'status': vd.get('status'),
            'actions': actions,
            'turns': len(turns),
            'in_flight_turns': len(in_flight),
            'err_turns': len(err),
            'answered_turns': len(answered),
            'tool_ok_turns': len(tool_ok),
            'tool_pct': (100.0 * len(tool_ok) / len(answered)) if answered else None,
            'mean_turn_s': (sum(durs) / len(durs)) if durs else None,
            'wall_lost_to_timeouts_s': sum(err_durs),
            'mean_reasoning_chars': (sum(t['reasoning_chars'] for t in answered) / len(answered)) if answered else None,
        }
    tot = {k: 0 for k in ('levels_completed', 'actions', 'turns', 'err_turns',
                          'answered_turns', 'tool_ok_turns', 'wall_lost_to_timeouts_s')}
    tot['final_score'] = 0.0
    n_dur, sum_dur = 0, 0.0
    for g, r in out['games'].items():
        if r.get('missing'):
            continue
        for k in tot:
            v = r.get(k)
            if isinstance(v, (int, float)):
                tot[k] += v
        if r.get('mean_turn_s') is not None:
            sum_dur += r['mean_turn_s'] * max(r['turns'] - 1, 0)
            n_dur += max(r['turns'] - 1, 0)
    tot['mean_turn_s'] = (sum_dur / n_dur) if n_dur else None
    tot['tool_pct'] = (100.0 * tot['tool_ok_turns'] / tot['answered_turns']) if tot['answered_turns'] else None
    # Deliberation, weighted by answered turns. reasoning_chars is the box-invariant view:
    # seconds-per-turn on this box is just chars / 4.26 tok/s, so a cross-box seconds
    # comparison would measure the GPU, not the adapter. Round 3's falsifier is about how
    # much the model thinks, not how long the hardware took to emit it.
    num = sum((r.get('mean_reasoning_chars') or 0) * r.get('answered_turns', 0)
              for r in out['games'].values() if not r.get('missing'))
    tot['mean_reasoning_chars'] = (num / tot['answered_turns']) if tot['answered_turns'] else None
    out['total'] = tot
    return out

if __name__ == '__main__':
    GAMES = ['ar25-0c556536', 're86-8af5384d', 'sb26-7fbdac44', 'su15-1944f8ab',
             'tr87-cd924810', 'tu93-0768757b', 'vc33-5430563c']
    res = collect(sys.argv[1], GAMES)
    if len(sys.argv) > 2:
        json.dump(res, open(sys.argv[2], 'w'), indent=2)
    t = res['total']
    print(f"model={res['model']}  dir={os.path.basename(res['run_dir'])}")
    print(f"{'game':16s} {'lv':>3s}/{'tot':<3s} {'score':>8s} {'act':>5s} {'turns':>5s} "
          f"{'err':>4s} {'tool%':>6s} {'reasChr':>8s} {'meanTurn':>9s} {'lostS':>7s} {'status':>10s}")
    for g in GAMES:
        r = res['games'][g]
        if r.get('missing'):
            print(f"{g[:4]:16s} MISSING"); continue
        mt = f"{r['mean_turn_s']:.1f}" if r['mean_turn_s'] is not None else "-"
        tp = f"{r['tool_pct']:.1f}" if r['tool_pct'] is not None else "-"
        sc = r['final_score'] if r['final_score'] is not None else 0
        rc = f"{r['mean_reasoning_chars']:.0f}" if r['mean_reasoning_chars'] is not None else "-"
        print(f"{g[:4]:16s} {r['levels_completed']:>3}/{r['total_levels']:<3} {sc:>8.3f} "
              f"{r['actions']:>5} {r['turns']:>5} {r['err_turns']:>4} {tp:>6s} {rc:>8s} {mt:>9s} "
              f"{r['wall_lost_to_timeouts_s']:>7.0f} {str(r['status']):>10s}")
    mt = f"{t['mean_turn_s']:.1f}" if t['mean_turn_s'] is not None else "-"
    tp = f"{t['tool_pct']:.1f}" if t['tool_pct'] is not None else "-"
    rc = f"{t['mean_reasoning_chars']:.0f}" if t.get('mean_reasoning_chars') is not None else "-"
    print(f"{'TOTAL':16s} {t['levels_completed']:>3}/{'-':<3} {t['final_score']:>8.3f} "
          f"{t['actions']:>5} {t['turns']:>5} {t['err_turns']:>4} {tp:>6s} {rc:>8s} {mt:>9s} "
          f"{t['wall_lost_to_timeouts_s']:>7.0f}")
