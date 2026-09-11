"""Bounded, synchronous diagnostic provenance; never use for throughput runs.

Raw storage checks include padding/aliases. Semantic checks select only tensor
owners of the checkpoint's cache group. No cache references or policy change.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
import hashlib
import json

from vllm.v1.simple_kv_offload.metadata import SimpleCPUOffloadMetadata


@dataclass
class QSAResumeAuditMetadata(SimpleCPUOffloadMetadata):
    qsa_audit: dict = field(default_factory=dict)


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def family(name):
    if name.endswith('.indexer.compressed_key_cache'):
        return 'compressed'
    if name.endswith('.indexer.raw_key_cache'):
        return 'raw'
    if name.endswith('.linear_attn'):
        return 'gdn'
    if name.endswith('.ple'):
        return 'ple'
    if name.endswith('.self_attn.attn'):
        return 'main'
    raise ValueError('Unknown semantic cache owner: ' + name)


def check_pairs(cpu_ids, gpu_ids, page_bytes):
    if len(cpu_ids) != len(gpu_ids) or not cpu_ids:
        raise RuntimeError('Invalid audit transfer mapping')
    if any(type(x) is not int or x < 0 for x in cpu_ids + gpu_ids):
        raise RuntimeError('Invalid audit block ID')
    if len(cpu_ids) * page_bytes > 2 * 1024**3:
        raise RuntimeError('Audit transfer exceeds 2GiB diagnostic bound')


class ResumeAuditMixin:
    """Composed before the existing connector parent; no serving logic edits."""

    def _audit_init(self, config):
        self._audit_groups = {
            g: {'owners': list(group.layer_names),
                'block_size': group.kv_cache_spec.block_size,
                'cacheable': group.kv_cache_spec.prefix_cacheable}
            for g, group in enumerate(config.kv_cache_groups)
        }
        self._audit_epoch = 0
        self._audit_worker_epoch = 0
        self._audit_known = {}
        self._audit_ledger = {}
        self._audit_store_pending = {}
        self._audit_load_pending = {}
        self._audit_last = {'store': -1, 'load': -1}
        self._audit_events = {'store': 0, 'load': 0, 'watch': 0}
        self._audit_step = 0
        self._audit_seen_step = -1

    def _audit_emit(self, event, **data):
        from vllm.logger import init_logger
        init_logger(__name__).info('QSA_RESUME_AUDIT %s', json.dumps(
            {'event': event, 'epoch': self._audit_worker_epoch, **data},
            sort_keys=True, separators=(',', ':')))

    def _audit_register(self, kv_caches):
        # Keep semantic views, never clones or additional cache-manager refs.
        self._audit_tensors = kv_caches
        self._audit_num_gpu = self.worker_handler.kv_cache_config.num_blocks
        self._audit_emit('registered', groups=self._audit_groups,
                         raw_storages=len(self.worker_handler.gpu_kv_caches),
                         timing_valid=False)

    def _audit_raw(self, side, block_id):
        worker = self.worker_handler
        caches = worker.gpu_kv_caches if side == 'gpu' else worker.cpu_kv_caches
        out = {}
        for name, tensor in sorted(caches.items()):
            if not 0 <= block_id < tensor.shape[0]:
                raise RuntimeError('Audit raw block out of bounds')
            row = tensor[block_id].detach().cpu().contiguous()
            out[name] = fingerprint(row.numpy().tobytes())
        return out

    def _audit_semantic(self, desc):
        import torch
        group = self._audit_groups[desc['group']]
        if not group['cacheable']:
            raise RuntimeError('Noncacheable group in checkpoint audit')
        out = {}
        for owner in group['owners']:
            value = self._audit_tensors[owner]
            values = value if isinstance(value, (tuple, list)) else [value]
            for part, tensor in enumerate(values):
                axes = [d for d, size in enumerate(tensor.shape)
                        if size == self._audit_num_gpu]
                if len(axes) != 1:
                    raise RuntimeError('Ambiguous semantic block axis: ' + owner)
                # select + contiguous strips physical padding/shared-owner bytes.
                row = tensor.select(axes[0], desc['gpu']).detach().cpu().contiguous()
                out[owner + ':' + str(part)] = {
                    'family': family(owner), 'dtype': str(row.dtype),
                    'shape': list(row.shape),
                    'sha256': fingerprint(row.view(torch.uint8).numpy().tobytes()),
                }
        return out

    def build_connector_meta(self, scheduler_output):
        base = super().build_connector_meta(scheduler_output)
        manager = self.scheduler_manager
        if manager is None:
            return base
        self._audit_step += 1
        requests = {}
        if base.store_cpu_blocks or base.load_cpu_blocks:
            for table in (manager._reqs_to_store, manager._reqs_to_load):
                for req_id, state in table.items():
                    requests[req_id] = state.request
        # Hash boundary is authoritative across hybrid groups. Do not infer it
        # from a recycled physical block ID or from optimistic computed counts.
        boundaries = {}
        for req_id, req in requests.items():
            for i, key in enumerate(req.block_hashes):
                boundaries.setdefault(bytes(key), []).append(
                    (req_id, (i + 1) * manager.hash_block_size))

        def describe(cpu_id, gpu_id, request_ids):
            key = manager.cpu_block_pool.blocks[cpu_id].block_hash
            if not isinstance(key, bytes) or len(key) <= 4:
                raise RuntimeError('Audit missing CPU checkpoint key')
            group_id = int.from_bytes(key[-4:], 'big')
            group = self._audit_groups[group_id]
            matches = [(rid, n) for rid, n in boundaries.get(key[:-4], [])
                       if rid in request_ids]
            return {'cpu': cpu_id, 'gpu': gpu_id, 'key': key.hex(),
                    'group': group_id,
                    'families': sorted({family(n) for n in group['owners']}),
                    'group_block_size': group['block_size'],
                    'request_ids': list(request_ids),
                    'boundaries': [[rid, n] for rid, n in matches]}

        stores, loads = [], []
        if base.store_cpu_blocks:
            req_ids = manager._store_event_to_reqs.get(base.store_event, [])
            stores = [describe(c, g, req_ids) for c, g in
                      zip(base.store_cpu_blocks, base.store_gpu_blocks)]
        if base.load_cpu_blocks:
            req_ids = base.load_event_to_reqs.get(base.load_event, [])
            loads = [describe(c, g, req_ids) for c, g in
                     zip(base.load_cpu_blocks, base.load_gpu_blocks)]

        # Validate each binding again on the scheduler. Watches never pin it.
        watches, rebound = [], 0
        boundary_step = bool(scheduler_output.scheduled_new_reqs or
                             scheduler_output.finished_req_ids)
        for cpu_id, desc in list(self._audit_known.items()):
            cpu_key = manager.cpu_block_pool.blocks[cpu_id].block_hash
            gpu_key = manager._gpu_block_pool.blocks[desc['gpu']].block_hash
            if cpu_key is None or gpu_key is None or cpu_key.hex() != desc['key'] or gpu_key.hex() != desc['key']:
                self._audit_known.pop(cpu_id)
                rebound += 1
            elif boundary_step:
                watches.append(desc)
        # At most one sampled checkpoint per group, preferring the highest known
        # token boundary, regardless of dictionary order after CPU slot reuse.
        chosen = {}
        for desc in watches:
            previous = chosen.get(desc['group'])
            rank = max((n for _, n in desc['boundaries']), default=-1)
            old_rank = max((n for _, n in previous['boundaries']), default=-1) if previous else -1
            if previous is None or rank >= old_rank:
                chosen[desc['group']] = desc
        watches = list(chosen.values())[-16:]
        for desc in stores + loads:
            self._audit_known[desc['cpu']] = desc
        payload = {'epoch': self._audit_epoch, 'step': self._audit_step,
                   'stores': stores, 'loads': loads, 'watches': watches,
                   'rebound_skipped': rebound,
                   'new_request_ids': [r.req_id for r in scheduler_output.scheduled_new_reqs],
                   'finished_request_ids': sorted(scheduler_output.finished_req_ids)}
        return QSAResumeAuditMetadata(**{f.name: getattr(base, f.name)
                                        for f in fields(SimpleCPUOffloadMetadata)},
                                      qsa_audit=payload)

    def _audit_before(self):
        worker = self.worker_handler
        meta = getattr(worker, '_connector_metadata', None)
        if meta is None:
            return
        data = getattr(meta, 'qsa_audit', None)
        if not data:
            raise RuntimeError('Diagnostic worker missing serialized audit metadata')
        epoch = data['epoch']
        if epoch != self._audit_worker_epoch:
            if self._audit_store_pending or self._audit_load_pending:
                raise RuntimeError('Diagnostic external reset with pending transfers')
            self._audit_ledger.clear()
            self._audit_worker_epoch = epoch
            self._audit_emit('external_reset')
        fresh_step = data['step'] != self._audit_seen_step
        if fresh_step:
            self._audit_seen_step = data['step']
            if data['watches']:
                if self._audit_events['watch'] >= 128:
                    raise RuntimeError('Diagnostic checkpoint watch bound reached')
                self._audit_events['watch'] += 1
                for desc in data['watches']:
                    key = (desc['cpu'], desc['key'])
                    checkpoint = self._audit_ledger.get(key)
                    actual = self._audit_semantic(desc)
                    expected = checkpoint['semantic'] if checkpoint else None
                    self._audit_emit('resident_checkpoint_watch', descriptor=desc,
                        origin_store_event=checkpoint['store_event'] if checkpoint else None,
                        exact=None if expected is None else actual == expected,
                        semantic=actual, coverage='missing_store_provenance' if expected is None else 'semantic_owners',
                        new_request_ids=data['new_request_ids'],
                        finished_request_ids=data['finished_request_ids'])
            if data['rebound_skipped']:
                self._audit_emit('watch_binding_reused', skipped=data['rebound_skipped'])
        for kind in ('store', 'load'):
            event = getattr(meta, kind + '_event')
            cpu_ids = list(getattr(meta, kind + '_cpu_blocks'))
            gpu_ids = list(getattr(meta, kind + '_gpu_blocks'))
            pending = getattr(self, '_audit_' + kind + '_pending')
            if not cpu_ids or event <= self._audit_last[kind] or event in pending:
                continue
            if self._audit_events[kind] >= 256:
                raise RuntimeError('Diagnostic transfer event bound reached')
            check_pairs(cpu_ids, gpu_ids, self._qsa_page_bytes)
            descs = data[kind + 's']
            if [(d['cpu'], d['gpu']) for d in descs] != list(zip(cpu_ids, gpu_ids)):
                raise RuntimeError('Audit provenance/transfer mapping differs')
            snapshots = []
            for desc in descs:
                snapshots.append({'descriptor': desc,
                    'raw': self._audit_raw('gpu' if kind == 'store' else 'cpu',
                                          desc['gpu' if kind == 'store' else 'cpu']),
                    'semantic': self._audit_semantic(desc) if kind == 'store' else None})
            pending[event] = snapshots
            self._audit_events[kind] += 1
            self._audit_emit(kind + '_captured', transfer_event=event,
                             descriptors=descs, phase='after_forward_before_submit')

    def _audit_after(self):
        worker = self.worker_handler
        if worker is None:
            return
        for kind in ('store', 'load'):
            pending = getattr(self, '_audit_' + kind + '_pending')
            hwm = getattr(worker, '_' + kind + '_hwm')
            for event in sorted(list(pending)):
                if event > hwm:
                    continue
                for snapshot in pending[event]:
                    desc = snapshot['descriptor']
                    key = (desc['cpu'], desc['key'])
                    actual = self._audit_raw('cpu' if kind == 'store' else 'gpu',
                                             desc['cpu' if kind == 'store' else 'gpu'])
                    exact = actual == snapshot['raw']
                    self._audit_emit(kind + '_raw_copy', transfer_event=event,
                        descriptor=desc, exact=exact,
                        source_raw_sha256=snapshot['raw'], destination_raw_sha256=actual,
                        source_semantic=snapshot['semantic'],
                        scope='deduplicated_full_storage_including_padding_and_aliases')
                    if not exact:
                        raise RuntimeError('QSA audit ' + kind + ' source/destination mismatch')
                    if kind == 'store':
                        # Physical slots can be legitimately reused after eviction.
                        for old in [k for k in self._audit_ledger if k[0] == desc['cpu']]:
                            self._audit_ledger.pop(old)
                        self._audit_ledger[key] = {**snapshot, 'store_event': event}
                    else:
                        origin = self._audit_ledger.get(key)
                        semantic = self._audit_semantic(desc)
                        self._audit_emit('load_origin', transfer_event=event,
                            descriptor=desc,
                            origin_store_event=origin['store_event'] if origin else None,
                            origin_descriptor=origin['descriptor'] if origin else None,
                            cpu_unchanged_since_store=None if origin is None else snapshot['raw'] == origin['raw'],
                            semantic_exact=None if origin is None else semantic == origin['semantic'],
                            semantic=semantic,
                            coverage='semantic_owners' if origin else 'missing_store_provenance')
                self._audit_last[kind] = event
                del pending[event]

    def _audit_reset(self):
        self._audit_epoch += 1
        self._audit_known.clear()
