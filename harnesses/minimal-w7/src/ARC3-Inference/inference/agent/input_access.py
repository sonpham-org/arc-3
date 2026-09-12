"""Optional causal input views; no game actions, object inference or hidden state."""
import os

VERSION = "obs_access_v1"
FLAG = "ARC3_INPUT_ACCESS"


def enabled():
    value = os.environ.get(FLAG, "0")
    if value not in ("0", "1"):
        raise ValueError(FLAG + " must be 0 or 1")
    return value == "1"


RUNTIME_GUIDANCE = (
    "- `obs[0]` is the latest observation (`current_obs`, also `current_frame`); "
    "`obs[1]` is one real game action ago. Larger nonnegative indices go further back. "
    "`len(obs)` includes the initial board; `obs[start:stop]` selects a newest-first "
    "range, stop exclusive. Each observation "
    "exposes `.ascii`, `.segmentation`, `.step`, `.level`, `.shape`. This is the current "
    "game's observed initial/post-action history, retained across conversation trimming, "
    "not every intermediate animation frame. Five executed actions produce five new "
    "observations, including no-change actions; inspection-only calls add none. "
    "Indices shift after actions.\n"
    "- `obs_diff(before=1, after=0, rows=None, cols=None, detail='regions', offset=0, "
    "limit=8)` compares entries of `obs` (older to newer); `frame_diff` is an alias. "
    "Row/column pairs are absolute "
    "half-open ranges. Returns changed-cell count and paged connected change-region bounds, "
    "or `[row,col,old_color,new_color]` with `detail='cells'` (numeric color IDs indexing "
    "`WwgGcBMPRbSYOrNp`); `total`, `next_offset`, "
    "`omitted` describe paging (limit 1..64). These are pixel changes, not tracked objects "
    "or inferred HUD. Missing history/level or shape boundaries are explicit. Original "
    "current-frame views and `last_animation` remain available. Read/compute locally; "
    "only `print(...)` or `result` emits text.\n"
)
TOOL_GUIDANCE = (
    " Optional input methods: `obs[0]` / `current_obs` is current; `obs[1]` one real "
    "game action ago. `obs[a:b]` selects initial/post-action observations newest first. "
    "`obs_diff(before=1, after=0, rows=None, cols=None, detail='regions', offset=0, "
    "limit=8)` returns compact paged changes; detail='cells' returns old/new colors. "
    "`frame_diff` is an alias. These methods are optional, not instructions to inspect every turn."
)


class InputUsage:
    def __init__(self):
        self.counts, self.samples, self.omitted = {}, [], 0

    def record(self, method, **data):
        self.counts[method] = self.counts.get(method, 0) + 1
        if len(self.samples) < 24:
            self.samples.append(dict(method=method, **data))
        else:
            self.omitted += 1

    def payload(self):
        return dict(version=VERSION, counts=dict(self.counts), samples=list(self.samples),
                    samples_omitted=self.omitted)


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(name + " must be an integer")
    return value


def _metadata(frame, index):
    return dict(index=index, step=frame.step, level=frame.level, shape=list(frame.shape))


class FrameArchive:
    """Reverse index over existing history, with no second grid archive or replay."""
    def __init__(self, history, current, usage):
        self._history, self._current, self._usage = history, current, usage
        self._length = len(history) if history else int(current is not None)
        if history and current is not None:
            last = history[-1].frame
            if last is None or (last.step, last.level, last._grid) != (current.step, current.level, current._grid):
                raise ValueError("history/current frame mismatch")

    def _get(self, index):
        _integer(index, "frame index")
        if index < 0 or index >= self._length:
            raise IndexError("obs index outside observed history; 0=current, positive=past")
        frame = self._current if index == 0 else self._history[self._length - 1 - index].frame
        if frame is None:
            raise ValueError("requested observation unavailable")
        return frame

    def __len__(self):
        self._usage.record("obs.len", available=self._length)
        return self._length

    def __getitem__(self, key):
        if isinstance(key, slice):
            start = 0 if key.start is None else _integer(key.start, "slice start")
            stop = self._length if key.stop is None else _integer(key.stop, "slice stop")
            stride = 1 if key.step is None else _integer(key.step, "slice stride")
            if start < 0 or stop < 0 or stride <= 0:
                raise ValueError("obs slices need nonnegative bounds and positive stride")
            indices = range(min(start, self._length), min(stop, self._length), stride)
            self._usage.record("obs.slice", start=start, stop=stop, stride=stride, returned=len(indices))
            return [self._get(i) for i in indices]
        result = self._get(key)
        self._usage.record("obs.get", **_metadata(result, key))
        return result

    def __repr__(self):
        self._usage.record("obs.repr", available=self._length)
        return "Observations(available=%d, order=newest_first, 0=current)" % self._length


def _bounds(value, size, name):
    if value is None:
        return 0, size
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise TypeError(name + " must be [start,stop]")
    start, stop = (_integer(v, name) for v in value)
    if not 0 <= start <= stop <= size:
        raise ValueError(name + " outside frame (stop exclusive)")
    return start, stop


def compare_frames(frames, before=1, after=0, rows=None, cols=None,
                   detail="regions", offset=0, limit=8):
    for name, value in (("before", before), ("after", after), ("offset", offset), ("limit", limit)):
        _integer(value, name)
    if before < after or after < 0:
        raise ValueError("require before >= after >= 0 (0=current)")
    if offset < 0 or not 1 <= limit <= 64 or detail not in ("regions", "cells"):
        raise ValueError("invalid detail/page; limit must be 1..64")
    if before >= frames._length:
        return dict(status="unavailable", reason="insufficient_observed_history", available=frames._length)
    old, new = frames._get(before), frames._get(after)
    result = dict(before=_metadata(old, before), after=_metadata(new, after))
    if old.level != new.level or new.step < old.step or old.shape != new.shape:
        return dict(result, status="boundary", reason="level_reset_or_shape_change")
    r0, r1 = _bounds(rows, old.shape[0], "rows")
    c0, c1 = _bounds(cols, old.shape[1], "cols")
    changed = {(r, c): (old._grid[r][c], new._grid[r][c])
               for r in range(r0, r1) for c in range(c0, c1)
               if old._grid[r][c] != new._grid[r][c]}
    if detail == "cells":
        items = [[r, c, *changed[r, c]] for r, c in sorted(changed)]
    else:
        remaining, items = set(changed), []
        for seed in sorted(changed):
            if seed not in remaining:
                continue
            remaining.remove(seed)
            stack, count = [seed], 0
            low_r = high_r = seed[0]
            low_c = high_c = seed[1]
            while stack:
                r, c = stack.pop()
                count += 1
                low_r, high_r = min(low_r, r), max(high_r, r)
                low_c, high_c = min(low_c, c), max(high_c, c)
                for neighbor in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        stack.append(neighbor)
            items.append(dict(rows=[low_r, high_r+1], cols=[low_c, high_c+1], changed_cells=count))
    page = items[offset:offset+limit]
    next_offset = offset + len(page)
    return dict(result, status="ok", rows=[r0, r1], cols=[c0, c1], changed_cells=len(changed),
                detail=detail, items=page, total=len(items), offset=offset,
                next_offset=next_offset if next_offset < len(items) else None,
                omitted=max(0, len(items)-len(page)))


def install_input_access(runtime_globals, history, current, transition, usage):
    frames = FrameArchive(history, current, usage)

    def obs_diff(before=1, after=0, rows=None, cols=None, detail="regions", offset=0, limit=8):
        result = compare_frames(frames, before, after, rows, cols, detail, offset, limit)
        usage.record("obs_diff", before=before, after=after, detail=detail,
                     status=result["status"], changed_cells=result.get("changed_cells"),
                     returned=len(result.get("items", [])), total=result.get("total"))
        return result

    runtime_globals.update(obs=frames, current_obs=current, obs_diff=obs_diff, frame_diff=obs_diff)
