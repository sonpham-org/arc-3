# Optional CPU vision library

This candidate adds `vision.objects()`, `vision.changes()`, and `vision.help()` inside the existing Python tool. It extends the separately verified persistent-Python-helpers candidate. The new library uses CPU calculations and host RAM only. No model call, background curator, GPU model, or new top-level tool is added by this patch.

Scene features are computed on demand. No feature tables or cache inventory are injected into model context. The permanent prompt addition is one short capability description and a selective-output example. Calling a method returns ordinary Python data to the sandbox; only the snippet's explicit stdout/result is included in the normal tool response.

## Usage

```python
# Full component data stays inside Python; return only selected fields.
objects = vision.objects()
result = [(o['id'], o['bbox'], o['point']) for o in objects if o['color'] == 'R']
```

```python
change = vision.changes()
result = {key: change[key] for key in ('status', 'action', 'changed_count', 'bbox')}
```

```python
helpers.save(
    'red_click_points',
    "def red_click_points():\n    return [o['point'] for o in vision.objects() if o['color'] == 'R']",
    'Current-frame member pixels of red components',
)
result = helpers.red_click_points()
```

Saved functions query the current host observation each time. Ordinary local Python lists already returned by a query remain snapshots; query again after an action to obtain fresh data.

## API

- `vision.objects(frame='current', connectivity=4)` returns all same-color components in reading order, including background. `frame` can be `current` or `previous`; connectivity can be 4 or 8. Each component contains `id`, `frame_id`, `color`, `bbox`, `pixels`, `point`, and `shape_hash`.
- `bbox` is inclusive `[row_min, col_min, row_max, col_max]`. `pixels` is area. `point` is an actual member pixel nearest the bounding-box center, with deterministic tie breaking; it therefore cannot land in a component's hole. The API does not decide whether a component is a useful click target.
- `shape_hash` describes exact normalized geometry, independent of translation and color; orientation is preserved. IDs are local to a frame, not stable tracked game-object identities. Multicolor sprites can comprise multiple components.
- `vision.changes(details=False)` reports the latest chronological pair of settled observations, including the last actual action when known. It returns before/after frame IDs, `status`, `changed_count`, an overall bounding box, exact color-transition counts, and bounded connected changed-region summaries.
- Region summaries use 4-connectivity and include at most 64 regions, with `region_count` and `regions_truncated`. `details=True` additionally returns exact `[row, col, before_color, after_color]` cells, at most 4,096. Detail queries do not automatically print the data.
- Status values are `ok`, `unchanged`, `missing_current`, `missing_previous`, `reset_boundary`, `level_boundary`, `shape_boundary`, and `nonconsecutive`. Missing/boundary results have null counts instead of fabricated deltas. `unchanged` describes visible pixels; it does not prove an action had no hidden effect.
- In a batch, changes describe the final actual action's before/after pair, not the batch's accumulated reward or full displacement. Animation analysis remains separate.
- `vision.help()` returns bounded documentation; `vision.help('objects')` or `vision.help('changes')` narrows it. Invalid names/options are rejected explicitly.

## Cache and lifecycle

One cache belongs to a game agent and full runtime-state path. It survives context eviction and fresh Python subprocesses. New game paths create independent caches, including paths sharing an artifacts directory. No state is persisted across host-process/VM restart.

The host ingests existing current/history observations at tool entry and after executed actions. Inspection-only calls do not advance observation identity or erase the last transition. Only bounded current/previous frame state is retained; the existing full history is not duplicated. Reset and level boundaries get separate temporal identities.

Object computations cache exact frame content/dimensions and connectivity. Observation-specific frame IDs are attached on retrieval, so a repeated screenshot can reuse geometry while still identifying the new observation. Temporal results also use session/epoch/observation/action identity. Caller mutations never alter cached results.

The LRU holds at most 128 entries and 4 MiB of serialized result bytes. This is an encoded-cache limit, not a total-process RSS guarantee: keys, Python bookkeeping, current/previous frames, transient decoded results, and the guest's own variables have additional bounded or caller-dependent costs. Eviction affects speed, not the answer.

## Adoption telemetry

After an API is used, the host atomically updates `<runtime_state_stem>_vision_metrics.json` with method-call counts and cache counters/limits. It contains no frames or component tables and is not fed to Qwen. No API use means no new telemetry file. Telemetry write failure does not fail the tool or an executed action. Existing transcripts retain the model's Python call code and selected output.

These metrics reveal whether Qwen adopts the library and whether repeated queries hit the cache. Actual score and generated-token savings still require live-model evaluation.

## Validation and scope

The release includes synthetic geometry/delta/cache tests, real-subprocess integration tests, and the existing persistent-helper regression suite. CPU benchmarks cover representative and fragmented 64x64 boards, cold and cached calls, and observation ingestion. Benchmarks measure local host functions, not full RPC latency, model throughput, or game scores.

Windows integration tests use the previously documented test-only bootstrap-file and timeout-cleanup adaptations. Production Linux subprocess launch and sandbox policy are unchanged. An unmodified Linux smoke test and live-Qwen gameplay evaluation remain pending.

This patch does not combine the separate preserved-rules experimental arm. It does not change solver, serving, action cap, level stopping, warmup, or curator configuration. Apply the approved curator-off configuration equally when comparing the persistent-helper control and this candidate. The original archive's historical FEATURE_ENV/setup metadata is not the authoritative runtime contract; use the release manifest and locked runtime parameters.

The candidate is packaged locally and has not been published or launched. Deployment tooling must explicitly identify the modified source bundle; do not weaken exact-baseline identity checks to label it as the unchanged baseline.
