"""Training rows for REPLAY captures (4-Oct-2026, daniel-draft/replay; train_draft.py --span-rows / --split named).

A replay capture (daniel-draft/replay/make_replay_notebook.py) re-posts saved requests with max_tokens=1, so it holds
prefill hc only: the model's answers appear inside LATER prompts as assistant turns (preserve_thinking keeps the
thinking). The generated text of a turn is everything after the generation prompt <|im_start|>assistant\\n<think>\\n
up to and including its <|im_end|>; its rows are the ones the served draft predicted from: row p = g0 - 1 (prompt end)
.. g1 - 2 - msteps, exactly train_draft.query_rows' range for a live request whose prompt ended at g0.
Each turn trains once: in the first request (log order, per run and game) whose prompt carries it; a turn repeated
after a context drain is the same tokens and is skipped.
Request ids: rp~<run>~<game>~<k>.
"""
import hashlib

import numpy as np

IM_START, IM_END, ASSISTANT, NL, THINK = 248045, 248046, 74455, 198, 248068


def parse_rid(rid):
    """(run, game, k) of a replay request id, else None."""
    p = str(rid).split("~")
    if len(p) == 4 and p[0] == "rp":
        return p[1], p[2], int(p[3])
    return None


def game_of(rid):
    """Short game id (e.g. 'ar25') of a replay request, else None."""
    p = parse_rid(rid)
    return p[1].split("-")[0] if p else None


def spans(prompt):
    """[(g0, g1)] generated spans of the assistant turns in prompt ids (g1 exclusive, includes <|im_end|>); the final
    generation prompt has no <|im_end|> after it and is skipped."""
    out = []
    n = len(prompt)
    for i in np.nonzero(prompt == IM_START)[0]:
        i = int(i)
        if i + 3 < n and prompt[i + 1] == ASSISTANT and prompt[i + 2] == NL and prompt[i + 3] == THINK:
            g0 = i + 4 + (1 if i + 4 < n and prompt[i + 4] == NL else 0)
            e = np.nonzero(prompt[g0:] == IM_END)[0]
            if e.size:
                out.append((g0, g0 + int(e[0]) + 1))
    return out


def assign(reqs, msteps):
    """Set r.qrows (training rows) and r.gen_spans (spans this request owns) on every stitched replay request of one
    capture ({rid: Request}); other requests are left alone (train_draft.query_rows' live rule applies to them).
    Returns counts."""
    by_game = {}
    for r in reqs.values():
        p = parse_rid(r.rid)
        if p is not None and r.segments and r.prompt is not None:
            by_game.setdefault(p[:2], []).append((p[2], r))
    stats = {"replay_requests": 0, "spans": 0, "dup_spans": 0, "uncovered_spans": 0, "rows": 0}
    for key, rs in by_game.items():
        seen = set()
        for _, r in sorted(rs, key=lambda x: x[0]):
            cover = r.segments[-1][1]
            rows, own = [], []
            for g0, g1 in spans(r.prompt):
                h = hashlib.blake2b(np.ascontiguousarray(r.prompt[g0:g1]).tobytes(), digest_size=16).digest()
                if h in seen:
                    stats["dup_spans"] += 1
                    continue
                if g1 > cover or g0 < 1:
                    stats["uncovered_spans"] += 1
                    continue
                seen.add(h)
                own.append((g0, g1))
                rows.extend(range(g0 - 1, g1 - 1 - msteps))
            r.qrows, r.gen_spans = rows, own
            stats["replay_requests"] += 1
            stats["spans"] += len(own)
            stats["rows"] += len(rows)
    return stats
