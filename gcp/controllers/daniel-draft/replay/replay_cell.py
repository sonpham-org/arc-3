# --- daniel-draft replay cell (4-Oct-2026; replay/make_replay_notebook.py) ---
# Drafter training data from SAVED conversations, without playing: every logged request of the chosen runs is posted
# again to his server (capture hook on) with max_tokens=1, game by game in its original order (the radix cache keeps
# each game's shared prefix, so only new tokens are prefilled and captured). The model's answers come back inside the
# next request's prompt (preserve_thinking keeps the thinking), so the capture holds the target's hc at every
# generated position too. Request ids: rp~<run>~<game>~<k> (k = request index in that game's log).
# Inputs: /kaggle/replay/<run>/<game>_p0_requests.jsonl (read-only mount). Outputs: /kaggle/working/replay_log.jsonl
# (per request: original vs replayed prompt tokens, cached tokens, seconds), replay_summary.json.
import json as _rj, os as _ro, threading as _rt, time as _rtm, urllib.request as _ru
from concurrent.futures import ThreadPoolExecutor as _RPool
from pathlib import Path as _RP

_RCFG = __CFG__
_RSRC = _RP('/kaggle/replay')
_RLOG = _RP('/kaggle/working/replay_log.jsonl')
_RLOCK = _rt.Lock()
_RURL = f'http://127.0.0.1:{SERVED_MODEL_PORT}'


def _rwait_health(limit=3600):
    t0 = _rtm.time()
    while _rtm.time() - t0 < limit:
        try:
            with _ru.urlopen(_RURL + '/health', timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        _rtm.sleep(5)
    return False


def _rjobs():
    jobs = []
    for rd in sorted(p for p in _RSRC.iterdir() if p.is_dir()):
        if _RCFG.get('runs') and rd.name not in _RCFG['runs']:
            continue
        for f in sorted(rd.glob('*_p0_requests.jsonl')):
            game = f.name.split('_p0_')[0]
            short = game.split('-')[0]
            if _RCFG.get('games') and short not in _RCFG['games'] and game not in _RCFG['games']:
                continue
            if _RCFG.get('skip_games') and (short in _RCFG['skip_games'] or game in _RCFG['skip_games']):
                continue
            rg = (_RCFG.get('run_games') or {}).get(rd.name)
            if rg and short not in rg and game not in rg:
                continue
            jobs.append((rd.name, game, f))
    return sorted(jobs, key=lambda j: -j[2].stat().st_size)  # biggest logs first (balance the tail)


def _rpost(body, timeout=3600):
    req = _ru.Request(_RURL + '/v1/chat/completions', data=_rj.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
    with _ru.urlopen(req, timeout=timeout) as r:
        return _rj.loads(r.read())


def _rgame(job):
    run, game, path = job
    stats = {'run': run, 'game': game, 'requests': 0, 'errors': 0, 'prompt_tokens': 0, 'cached': 0,
             'orig_prompt_mismatch': 0, 'seconds': 0.0}
    pending = None  # the last request posted, waiting for its original response record (usage)
    k = 0
    t_game = _rtm.time()
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = _rj.loads(line)
            except ValueError:
                continue  # a torn last line
            if d.get('event') == 'response':
                if pending is not None and pending.get('orig') is None:
                    u = d.get('usage') or {}
                    pending['orig'] = u.get('prompt_tokens')
                    pending['orig_cached'] = (u.get('prompt_tokens_details') or {}).get('cached_tokens')
                    if pending['orig'] is not None and pending.get('prompt') is not None and pending['orig'] != pending['prompt']:
                        stats['orig_prompt_mismatch'] += 1
                    with _RLOCK, open(_RLOG, 'a') as lf:
                        lf.write(_rj.dumps(pending) + '\n')
                    pending = None
                continue
            if d.get('event') != 'request':
                continue
            if pending is not None:  # previous request had no response record
                with _RLOCK, open(_RLOG, 'a') as lf:
                    lf.write(_rj.dumps(pending) + '\n')
            if (_RCFG.get('run_max_requests') or {}).get(run) and k >= _RCFG['run_max_requests'][run]:
                pending = None
                break
            if _RCFG.get('max_requests') and k >= _RCFG['max_requests']:
                pending = None
                break
            body = {'model': SERVED_MODEL_NAME, 'messages': d['messages'], 'max_tokens': 1, 'temperature': 0.0,
                    'rid': f'rp~{run}~{game}~{k:05d}'}
            for key in ('tools', 'tool_choice', 'chat_template_kwargs'):
                if key in d:
                    body[key] = d[key]
            rec = {'run': run, 'game': game, 'k': k, 'step': d.get('analysis_step'), 'action': d.get('action'),
                   'idx': d.get('request_index_within_turn'), 'orig': None}
            t = _rtm.time()
            try:
                out = _rpost(body)
                u = out.get('usage') or {}
                rec.update(prompt=u.get('prompt_tokens'),
                           cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens'),
                           sec=round(_rtm.time() - t, 2))
                stats['prompt_tokens'] += rec['prompt'] or 0
                stats['cached'] += rec['cached'] or 0
            except Exception as e:
                rec.update(error=repr(e)[:300], sec=round(_rtm.time() - t, 2))
                stats['errors'] += 1
            stats['requests'] += 1
            pending = rec
            k += 1
    if pending is not None:
        with _RLOCK, open(_RLOG, 'a') as lf:
            lf.write(_rj.dumps(pending) + '\n')
    stats['seconds'] = round(_rtm.time() - t_game, 1)
    print('replay', run, game, stats, flush=True)
    return stats


def _rcapture_settled(cap, quiet=30, limit=1800):
    t0, last = _rtm.time(), None
    while _rtm.time() - t0 < limit:
        names = sorted(p.name for p in _RP(cap).glob('*'))
        busy = any(n.endswith('.tmp') for n in names)
        sig = (len(names), busy)
        if not busy and sig == last:
            return len(names)
        last = sig
        _rtm.sleep(quiet)
    return -1


def _rmetrics():
    try:
        txt = _ru.urlopen(_RURL + '/metrics', timeout=20).read().decode()
        keep = ('prompt_tokens_total', 'cached_tokens_total', 'generation_tokens_total', 'num_requests_total')
        return {l.rpartition(' ')[0]: float(l.rpartition(' ')[2]) for l in txt.splitlines()
                if not l.startswith('#') and any(k in l for k in keep) and '_created' not in l}
    except Exception as e:
        return {'error': repr(e)[:200]}


_rt0 = _rtm.time()
assert _rwait_health(), 'replay: server never became healthy'
_rjob_list = _rjobs()
print('daniel-draft replay:', len(_rjob_list), 'game logs |', _RCFG, flush=True)
with _RPool(int(_RCFG.get('workers', 8))) as _rex:
    _rstats = list(_rex.map(_rgame, _rjob_list))
_rt1 = _rtm.time()
_rcap = _ro.environ.get('ARC3_MTP_CAPTURE', '')
_rfiles = _rcapture_settled(_rcap) if _rcap else None
_rsum = {'cfg': _RCFG, 'games': _rstats, 'replay_seconds': round(_rt1 - _rt0, 1),
         'settle_seconds': round(_rtm.time() - _rt1, 1), 'capture_files': _rfiles,
         'requests': sum(s['requests'] for s in _rstats), 'errors': sum(s['errors'] for s in _rstats),
         'prompt_tokens': sum(s['prompt_tokens'] for s in _rstats), 'cached': sum(s['cached'] for s in _rstats),
         'orig_prompt_mismatch': sum(s['orig_prompt_mismatch'] for s in _rstats), 'metrics': _rmetrics()}
_rsum['prefilled_tokens'] = _rsum['prompt_tokens'] - _rsum['cached']
_rsum['prefill_tok_per_s'] = round(_rsum['prefilled_tokens'] / max(1.0, _rsum['replay_seconds']), 1)
_RP('/kaggle/working/replay_summary.json').write_text(_rj.dumps(_rsum, indent=1))
print('daniel-draft replay done:', {k: v for k, v in _rsum.items() if k not in ('games', 'metrics')}, flush=True)
