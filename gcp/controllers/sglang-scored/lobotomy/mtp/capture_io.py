"""Read MTP capture files (install_mtp_capture_patch.py V4 .mtpc) and stitch them into full-context requests.

A capture directory holds three kinds of file (each: b"ARC3MTPC", uint64 header length, JSON header, raw tensors):
  req      one per request: rid, prompt_ids (the request's full prompt, origin_input_ids)
  prefill  a prompt chunk the server computed: rid, pos (first position), ids (token p+1 at row p), hc [n, 10240]
  decode   64 verify steps of the whole batch: rids (one per request-step), meta [seq_len, accept_len, predict[D],
           draft_token[D]] per request-step, hc = the accepted rows only, in request-step order
Stitching: a request's tokens are its prompt + what it generated; its hc at [prefix, prompt end) are its own prefill
chunks, after that its own decode rows; the cached prefix [0, prefix) came from an earlier request whose tokens share
at least that prefix (the radix cache matched it), so those positions take that request's hc, recursively.
"""
import json
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

DT = {"bfloat16": torch.bfloat16, "int32": torch.int32, "float32": torch.float32, "int64": torch.int64}


def read_header(path):
    with open(path, "rb") as f:
        assert f.read(8) == b"ARC3MTPC", path
        (hl,) = struct.unpack("<Q", f.read(8))
        head = json.loads(f.read(hl))
    head["_base"] = 16 + hl
    return head


def read_tensor(path, head, name, rows=None):
    """Tensor `name` from a file whose header is `head`; rows=(a, b) reads only rows a..b-1 of a 2-D tensor."""
    dtype, shape, off, nbytes = head["tensors"][name]
    dt = DT[dtype]
    with open(path, "rb") as f:
        if rows is None:
            f.seek(head["_base"] + off)
            buf = bytearray(f.read(nbytes))
            return torch.frombuffer(buf, dtype=dt).reshape(shape) if nbytes else torch.empty(shape, dtype=dt)
        a, b = rows
        row_bytes = nbytes // shape[0]
        f.seek(head["_base"] + off + a * row_bytes)
        buf = bytearray(f.read((b - a) * row_bytes))
        return torch.frombuffer(buf, dtype=dt).reshape([b - a] + list(shape[1:]))


class Request:
    def __init__(self, rid):
        self.rid, self.prompt, self.first_seq = rid, None, None
        self.chunks = []   # (pos, n, path, head)
        self.steps = []    # (seq_len, acc, predict[D], draft[D], path, head, hc_row)
        self.tokens = None
        self.segments = None  # [(start, end, path, head, row)] hc rows for positions start..end-1
        self.ancestor = None  # rid of the request whose cached tokens this one continues
        self.mpos, self.mdelta = None, None  # V6: MRoPE positions of the prompt [3, n] and the text delta after it

    @property
    def prefix(self):
        return min(c[0] for c in self.chunks) if self.chunks else None


def load_capture(cap_dir):
    reqs = {}
    get = lambda rid: reqs.setdefault(rid, Request(rid))  # noqa: E731
    for path in sorted(Path(cap_dir).glob("*.mtpc")):
        head = read_header(path)
        kind = head["kind"]
        if kind == "req":
            r = get(head["rid"])
            r.prompt = read_tensor(path, head, "prompt_ids").numpy().astype(np.int64)
            r.first_seq = head["seq"]
            if "mrope_positions" in head["tensors"]:
                r.mpos = read_tensor(path, head, "mrope_positions").numpy().astype(np.int64)
            r.mdelta = head.get("mrope_delta")
        elif kind == "prefill":
            get(head["rid"]).chunks.append((head["pos"], head["tensors"]["ids"][1][0], path, head))
        elif kind == "decode":
            meta = read_tensor(path, head, "meta").numpy()
            D = head["draft"]
            row = 0
            for k, rid in enumerate(head["rids"]):
                seq, acc = int(meta[k, 0]), int(meta[k, 1])
                get(rid).steps.append((seq, acc, meta[k, 2:2 + D].copy(), meta[k, 2 + D:].copy(), path, head, row))
                row += acc
    for r in reqs.values():
        r.chunks.sort(key=lambda c: c[0])
        r.steps.sort(key=lambda s: s[0])
    return reqs


def build_tokens(r):
    """Prompt + generated tokens. Decode step rows are positions seq..seq+acc-1 with input tokens draft_token[0..acc);
    the last step's bonus (predict[acc-1]) is the final generated token."""
    toks = list(r.prompt)
    for seq, acc, pred, drf, *_ in r.steps:
        if seq != len(toks):
            break  # a gap (dropped step or retraction): stop at the last contiguous position
        toks.extend(int(t) for t in drf[:acc])
    if r.steps and r.steps[-1][0] + r.steps[-1][1] == len(toks):
        toks.append(int(r.steps[-1][2][r.steps[-1][1] - 1]))
    r.tokens = np.asarray(toks, dtype=np.int64)
    return r.tokens


def lcp(a, b):
    n = min(len(a), len(b))
    if n == 0:
        return 0
    d = np.nonzero(a[:n] != b[:n])[0]
    return int(d[0]) if d.size else n


def stitch(reqs):
    """Fill r.segments for every request whose context can be completed. Returns {rid: reason} for the rest."""
    order = sorted((r for r in reqs.values() if r.prompt is not None), key=lambda r: r.first_seq)
    for r in order:
        build_tokens(r)
    failed = {}
    done = []
    for r in order:
        if not r.chunks:
            failed[r.rid] = "no prefill chunk"
            continue
        segs = []
        p0 = r.prefix
        if p0 > 0:
            anc = None
            for q in reversed(done):  # latest earlier request that shares the whole cached prefix
                if q.segments and q.segments[-1][1] >= p0 and lcp(q.tokens, r.tokens) >= p0:
                    anc = q
                    break
            if anc is None:
                failed[r.rid] = f"no ancestor covers prefix {p0}"
                continue
            r.ancestor = anc.rid
            for s, e, path, head, row in anc.segments:
                if s >= p0:
                    break
                segs.append((s, min(e, p0), path, head, row))
        pos = p0
        for cpos, n, path, head in r.chunks:
            if cpos != pos:
                break
            segs.append((cpos, cpos + n, path, head, 0))
            pos = cpos + n
        if pos == len(r.prompt):
            for seq, acc, pred, drf, path, head, row in r.steps:
                if seq != pos:
                    break
                segs.append((seq, seq + acc, path, head, row))
                pos = seq + acc
        r.segments = segs
        done.append(r)
    return failed


IMAGE_PAD_ID = 248056  # <|image_pad|>; SGLang replaces image tokens in prompt ids with hash values >= vocab


def emb_plan(r, end):
    """What the SERVED draft embedded at each row p < end (eagle_worker_v2 + qwen4_exp_mtp._prepare_input_embeds):
    normally embed(token p+1); but in a prefill chunk computed with images (head["mm"]) the draft reads the TARGET's
    input embeddings, i.e. the unshifted embedding of token p (vision features at image positions), except each
    request's last row of the chunk, which is re-embedded from the shifted token. Returns (tok, vecs): tok[p] = token
    whose embedding row p used (-1 where an exact vector is given; image hash values stay >= vocab), vecs = list of
    (first position, count, path, head, file row) holding captured input embeddings (V5 mm_embeds)."""
    tok = r.tokens[1:end + 1].copy()
    vecs = []
    for s, e, path, head, row in r.segments:
        if s >= end:
            break
        e2 = min(e, end)
        if head.get("kind") == "prefill" and head.get("mm"):
            last = head["pos"] + head["tensors"]["ids"][1][0] - 1
            b = min(e2, last)
            if b > s:
                if "mm_embeds" in head["tensors"]:
                    tok[s:b] = -1
                    vecs.append((s, b - s, path, head, row))
                else:
                    tok[s:b] = r.tokens[s:b]
    return tok, vecs


def load_embeddings(r, end, embed, vocab=248320):
    """[end, hidden] draft input embeddings for rows 0..end-1 (see emb_plan); image positions without captured
    vectors fall back to embed(<|image_pad|>) (V4 capture) and are counted."""
    tok, vecs = emb_plan(r, end)
    t = torch.as_tensor(tok)
    approx = int((t >= vocab).sum())
    t = torch.where(t >= vocab, torch.full_like(t, IMAGE_PAD_ID), t)
    t = torch.where(t < 0, torch.zeros_like(t), t)
    e = embed[t.to(embed.device)]
    for s, n, path, head, row in vecs:
        e[s:s + n] = read_tensor(path, head, "mm_embeds", rows=(row, row + n)).to(e.device, e.dtype)
    return e, {"approx_image_rows": approx, "exact_vec_rows": sum(v[1] for v in vecs)}


MROPE_SHAPES = {}  # image run length (merged patches) -> (h, w), learned from V6 captures (learn_mrope_shapes)


def image_runs(prompt, vocab=248320):
    """(start, length) of each image in prompt ids: SGLang writes one hash value (>= vocab) per image token."""
    runs, i, n = [], 0, len(prompt)
    while i < n:
        if prompt[i] >= vocab:
            j = i
            while j < n and prompt[j] == prompt[i]:
                j += 1
            runs.append((i, j - i))
            i = j
        else:
            i += 1
    return runs


def mrope_from_ids(prompt, shapes=None, vocab=248320):
    """Rebuild [3, n] MRoPE positions and the text delta from prompt ids (SGLang mrope_rope_index.get_rope_index,
    qwen4_exp, images only): text consecutive on all axes; an h x w image at t = s, h = s + row, w = s + col where s
    is where it starts; the text after it resumes at s + max(h, w). Returns None if a run's shape is unknown."""
    shapes = MROPE_SHAPES if shapes is None else shapes
    n = len(prompt)
    pos = np.zeros((3, n), dtype=np.int64)
    st_idx, st = 0, 0
    for start, length in image_runs(prompt, vocab):
        if length not in shapes:
            return None
        h, w = shapes[length]
        text_len = start - st
        pos[:, st:start] = np.arange(text_len) + st_idx
        base = st_idx + text_len
        pos[0, start:start + length] = base
        pos[1, start:start + length] = base + np.repeat(np.arange(h), w)
        pos[2, start:start + length] = base + np.tile(np.arange(w), h)
        st_idx = base + max(h, w)
        st = start + length
    pos[:, st:] = np.arange(n - st) + st_idx
    return pos, int(pos.max() + 1 - n) if n else 0


def learn_mrope_shapes(reqs, vocab=248320):
    """Run length -> (h, w) from requests that carry recorded MRoPE positions (V6)."""
    shapes = {}
    for r in reqs.values():
        if r.mpos is None or r.prompt is None:
            continue
        for start, length in image_runs(r.prompt, vocab):
            seg = r.mpos[:, start:start + length]
            shapes.setdefault(length, (int(seg[1].max() - seg[1].min() + 1), int(seg[2].max() - seg[2].min() + 1)))
    return shapes


def rope_positions(r, end):
    """[end, 3] rotary (t, h, w) positions of logical positions 0..end-1 as served: the prompt's recorded MRoPE
    positions (V6 capture), generated tokens at index + delta (SGLang: seq_len + mrope_position_delta). Without V6
    data: the logical positions on all axes (exact only for text-only requests)."""
    p = np.arange(end, dtype=np.int64)
    out = np.repeat(p[:, None], 3, axis=1)
    mpos, mdelta = r.mpos, r.mdelta
    if mpos is None and r.prompt is not None and (r.prompt >= 248320).any():
        rebuilt = mrope_from_ids(r.prompt)  # V4/V5 captures: rebuild from the ids with shapes learned from V6
        if rebuilt is not None:
            mpos, mdelta = rebuilt
    if mpos is not None:
        n = min(mpos.shape[1], end)
        out[:n] = mpos[:, :n].T
        if mdelta is not None:
            out[n:] += int(mdelta)
    return torch.as_tensor(out)


def load_hc(r, end=None):
    """hc [end, 10240] bf16 for positions 0..end-1 of a stitched request."""
    end = end or r.segments[-1][1]
    parts, pos = [], 0
    for s, e, path, head, row in r.segments:
        if s >= end:
            break
        assert s == pos, (r.rid, s, pos)
        e2 = min(e, end)
        parts.append(read_tensor(path, head, "hc", rows=(row, row + e2 - s)))
        pos = e2
    assert pos == end, (r.rid, pos, end)
    return torch.cat(parts)
