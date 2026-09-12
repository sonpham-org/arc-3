"""Read-only, bounded PLE readahead and loader telemetry. No tensor mutation.

The original vLLM iterator, tensor objects, ordering, load_weights method and
inference thread settings are preserved. Only a dedicated CPU-worker call site
is wrapped. Read-ahead bytes are a window, NOT a bound on the OS page cache.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import threading
import time

_SESSION = None


def snapshot():
    result = {"monotonic": time.monotonic(), "pid": os.getpid()}
    try:
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF)
        result.update(user_seconds=r.ru_utime, system_seconds=r.ru_stime,
                      minor_faults=r.ru_minflt, major_faults=r.ru_majflt,
                      max_rss_kib=r.ru_maxrss)
    except ImportError:
        pass
    for filename, selected in (("/proc/meminfo", {"MemAvailable", "MemTotal", "Cached", "SwapFree", "SwapTotal"}),
                               ("/proc/self/status", {"VmRSS", "VmSize", "RssAnon", "RssFile", "Threads"}),
                               ("/proc/self/io", {"read_bytes", "rchar", "syscr"})):
        try:
            for line in Path(filename).read_text().splitlines():
                key, value = line.split(":", 1)
                if key in selected:
                    result[key] = int(value.strip().split()[0])
        except (OSError, ValueError):
            pass
    return result


def mapped_name(name, mapper):
    if mapper is None:
        return name
    values = mapper.apply_list([name])
    return values[0] if values else None


def is_ple(name, prefixes, mapper):
    mapped = mapped_name(name, mapper)
    return mapped is not None and mapped.startswith(prefixes)


def header(path):
    """Read only a bounded safetensors header; never materialize tensor data."""
    with Path(path).open("rb") as stream:
        size = stream.read(8)
        if len(size) != 8:
            raise ValueError("Truncated safetensors length")
        length = struct.unpack("<Q", size)[0]
        if not 2 <= length <= 16 * 1024 * 1024:
            raise ValueError("Invalid/oversized safetensors header")
        raw = stream.read(length)
        if len(raw) != length:
            raise ValueError("Truncated safetensors header")
    return json.loads(raw), 8 + length


def make_plan(model_dir, prefixes, mapper):
    model_dir = Path(model_dir).resolve()
    index = json.loads((model_dir / "model.safetensors.index.json").read_text())
    weight_map = index["weight_map"]
    wanted = {name: shard for name, shard in weight_map.items() if is_ple(name, prefixes, mapper)}
    if not wanted:
        raise ValueError("No PLE tensors in checkpoint index")
    cache, result = {}, []
    for name, shard in wanted.items():
        # Published checkpoints use flat filenames. Reject path traversal.
        if Path(shard).name != shard or "/" in shard or "\\" in shard or not shard.endswith(".safetensors"):
            raise ValueError("Unsafe checkpoint shard name")
        path = model_dir / shard
        if shard not in cache:
            cache[shard] = (*header(path), path.stat().st_size)
        contents, base, file_size = cache[shard]
        start, end = contents[name]["data_offsets"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= file_size - base:
            raise ValueError("Invalid safetensors data offsets")
        result.append({"name": name, "shard": shard, "path": str(path),
                       "offset": base + start, "bytes": end - start})
    return sorted(result, key=lambda x: (x["shard"], x["offset"], x["name"]))


class ReadAhead:
    def __init__(self, plan, config, emit, available=None):
        self.plan, self.config, self.emit = plan, config, emit
        self.available = available or (lambda: snapshot().get("MemAvailable", 0) * 1024)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.consumed, self.reserved = set(), {}
        self.completed = set()
        self.bytes_read = 0
        self.read_seconds = 0.0
        self.errors = []
        self.pressure_waits = 0
        self.peak_ahead_bytes = 0
        self.thread = threading.Thread(target=self._run, name="ARC3-PLE-Readahead", daemon=True)

    def start(self):
        self.thread.start()

    def consume(self, name):
        with self.lock:
            self.consumed.add(name)
            self.reserved.pop(name, None)

    def _pick(self):
        with self.lock:
            ahead = sum(self.reserved.values())
            for entry in self.plan:
                name = entry["name"]
                if name in self.consumed or name in self.completed or name in self.reserved:
                    continue
                amount = min(entry["bytes"], self.config["max_ahead_bytes"])
                if ahead + amount > self.config["max_ahead_bytes"]:
                    return None
                self.reserved[name] = amount
                self.peak_ahead_bytes = max(self.peak_ahead_bytes, ahead + amount)
                return entry, amount
        return None

    def _run(self):
        buffer = bytearray(self.config["read_chunk_bytes"])
        while not self.stop.is_set():
            if self.available() < self.config["min_available_bytes"]:
                self.pressure_waits += 1
                self.stop.wait(0.25)
                continue
            picked = self._pick()
            if picked is None:
                self.stop.wait(0.05)
                continue
            entry, amount = picked
            count, started = 0, time.monotonic()
            try:
                with open(entry["path"], "rb", buffering=0) as stream:
                    stream.seek(entry["offset"])
                    while count < amount and not self.stop.is_set():
                        with self.lock:
                            already_consumed = entry["name"] in self.consumed
                        if already_consumed or self.available() < self.config["min_available_bytes"]:
                            break
                        part = memoryview(buffer)[:min(len(buffer), amount - count)]
                        got = stream.readinto(part)
                        if not got:
                            raise EOFError("Short read in validated tensor range")
                        count += got
                self.bytes_read += count
            except Exception as exc:
                self.errors.append({"tensor": entry["name"], "error": type(exc).__name__ + ": " + str(exc)})
                # Do not create retry storms or change the model iterator.
            finally:
                elapsed = time.monotonic() - started
                self.read_seconds += elapsed
                with self.lock:
                    self.completed.add(entry["name"])
                self.emit("prefetch_range", name=entry["name"], shard=entry["shard"],
                          bytes_read=count, requested_bytes=amount, seconds=elapsed)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=10)
        return {"bytes_read": self.bytes_read, "read_seconds": self.read_seconds,
                "errors": self.errors, "pressure_waits": self.pressure_waits,
                "peak_ahead_bytes": self.peak_ahead_bytes,
                "thread_stopped": not self.thread.is_alive()}


class Session:
    def __init__(self, model_dir, prefixes, mapper, config, output):
        self.config, self.output = config, Path(output)
        self.output.mkdir(exist_ok=True)
        self.log_lock = threading.Lock()
        self.started = time.monotonic()
        self.rows, self.seen = [], set()
        self.plan = make_plan(model_dir, prefixes, mapper)
        self.prefetch = ReadAhead(self.plan, config, self.emit) if config["prefetch"] else None
        self.sample_stop = threading.Event()
        self.sampler = threading.Thread(target=self._sample, name="ARC3-PLE-Sampler", daemon=True)
        self.emit("begin", config=config, tensors=len(self.plan),
                  bytes=sum(x["bytes"] for x in self.plan), shards=len({x["shard"] for x in self.plan}),
                  process=snapshot())
        self.sampler.start()
        if self.prefetch:
            self.prefetch.start()

    def emit(self, event, **values):
        row = {"event": event, "elapsed": time.monotonic() - self.started, **values}
        with self.log_lock:
            with (self.output / "loader-events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _sample(self):
        while not self.sample_stop.wait(5):
            self.emit("sample", process=snapshot())

    def finish(self, status, error=None):
        prefetch = self.prefetch.close() if self.prefetch else {"bytes_read": 0, "thread_stopped": True, "errors": []}
        self.sample_stop.set()
        self.sampler.join(timeout=2)
        if not prefetch["thread_stopped"] or self.sampler.is_alive():
            status, error = "failed", "Research background thread still running"
        report = {"status": status, "error": error, "config": self.config,
                  "seconds": time.monotonic() - self.started,
                  "planned_tensors": len(self.plan), "observed_tensors": len(self.seen),
                  "missing_tensors": sorted({x["name"] for x in self.plan} - self.seen),
                  "planned_bytes": sum(x["bytes"] for x in self.plan),
                  "prefetch": prefetch, "tensor_timings": self.rows,
                  "process": snapshot(), "tensor_mutation": False,
                  "iterator_order_changed": False, "thread_settings_changed": False}
        (self.output / "loader-report.json").write_text(json.dumps(report, indent=2) + "\n")
        self.emit("finished", status=status, seconds=report["seconds"], prefetch=prefetch)
        print("ARC3_PLE_RESEARCH_FINISHED", json.dumps({k: report[k] for k in ("status", "seconds", "observed_tensors", "prefetch")}), flush=True)
        if status != "passed":
            raise RuntimeError("PLE loader research failed: " + str(error))


def tracked_weights(weights, model_config, prefixes, mapper):
    """Pass through the identical named tensor objects in identical order."""
    global _SESSION
    if _SESSION is not None:
        raise RuntimeError("PLE research hook invoked twice")
    config = json.loads(Path(os.environ["ARC3_PLE_RESEARCH_CONFIG"]).read_text())
    if config["prefetch"] not in (True, False) or type(config["prefetch"]) is not bool:
        raise ValueError("prefetch must be boolean")
    if not 0 < config["read_chunk_bytes"] <= config["max_ahead_bytes"] <= 2 * 1024**3:
        raise ValueError("Unsafe prefetch window")
    if config["min_available_bytes"] < 8 * 1024**3:
        raise ValueError("Insufficient prefetch memory guard")
    session = _SESSION = Session(model_config.model, prefixes, mapper, config,
                                 os.environ["ARC3_PLE_RESEARCH_OUTPUT"])
    iterator = iter(weights)
    try:
        while True:
            start = time.monotonic()
            try:
                name, tensor = next(iterator)
            except StopIteration:
                break
            iterator_seconds = time.monotonic() - start
            selected = is_ple(name, prefixes, mapper)
            before = snapshot() if selected else None
            consumer_start = time.monotonic()
            yield name, tensor
            if selected:
                elapsed = time.monotonic() - consumer_start
                session.seen.add(name)
                if session.prefetch:
                    session.prefetch.consume(name)
                row = {"name": name, "iterator_seconds": iterator_seconds,
                       "consumer_seconds": elapsed, "before": before, "after": snapshot()}
                session.rows.append(row)
                session.emit("tensor_consumed", **row)
    except BaseException as exc:
        session.finish("failed", type(exc).__name__ + ": " + str(exc))
        raise


def finish_weights():
    """Called only after vLLM's own completeness checks/postprocessing pass."""
    if _SESSION is None:
        raise RuntimeError("Missing PLE loader session")
    missing = {x["name"] for x in _SESSION.plan} - _SESSION.seen
    if missing:
        _SESSION.finish("failed", "Indexed PLE tensors were not all consumed")
    _SESSION.finish("passed")
