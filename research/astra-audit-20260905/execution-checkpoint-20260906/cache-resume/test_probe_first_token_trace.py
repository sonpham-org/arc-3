"""Targeted telemetry tests; all inference calls are local mocks."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import probe_first_token as original
import probe_first_token_trace as trace

HELPER = Path(__file__).resolve().parent / 'qsa-cpu-offload/probe/probe_restore.py'


class TelemetryTests(unittest.TestCase):
    def setup_case(self, directory):
        log = Path(directory) / 'vllm.log'
        log.write_bytes(b'prefix\n')
        args = SimpleNamespace(base_url='http://127.0.0.1:1234', model='model', timeout=17,
                               producer_tokens=32, server_log=log)
        helper = trace.load_helpers(HELPER)
        helper.wait_idle = lambda base: None
        calls = []

        def http(base, path, payload=None, timeout=60):
            calls.append((base, path, copy.deepcopy(payload), timeout))
            with log.open('ab') as stream:
                stream.write(b'trace\n')
            count = payload['max_tokens']
            return {'choices': [{'prompt_token_ids': payload['prompt'], 'token_ids': [7] * count,
                                 'logprobs': {'token_logprobs': [-0.25] * count,
                                              'top_logprobs': [{'token_id:7': -0.25}] * count}}],
                    'usage': {'prompt_tokens': len(payload['prompt']), 'completion_tokens': count}}

        helper.http = http
        return helper, args, calls, http

    def check_interval(self, row):
        self.assertLessEqual(datetime.fromisoformat(row['request_started_utc']),
                             datetime.fromisoformat(row['request_finished_utc']))
        self.assertEqual(row['trace_log']['end_offset'] - row['trace_log']['start_offset'], 6)
        self.assertEqual(row['server_log_byte_offset_before'], row['trace_log']['start_offset'])
        self.assertEqual(row['server_log_byte_offset_after'], row['trace_log']['end_offset'])
        self.assertTrue(row['server_log_same_file_and_nonshrinking'])

    def test_next_token_payload_and_existing_report_fields_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            helper, args, calls, http = self.setup_case(directory)
            with patch.object(trace.uuid, 'uuid4', return_value=SimpleNamespace(hex='fixed-request')):
                old = original.next_token(helper, args, [1, 2, 3], 'salt', 'resident', 0)
                sink = []
                new = trace.next_token(helper, args, [1, 2, 3], 'salt', 'resident', 0, sink)
            self.assertEqual(calls[0], calls[1])
            for key in old:
                if key != 'elapsed_seconds': self.assertEqual(new[key], old[key])
            self.assertEqual(len(sink), 1)
            self.assertEqual(sink[0]['request_id'], new['request_id'])
            self.assertIs(helper.http, http)
            self.check_interval(new)

    def test_producer_uses_unchanged_pinned_helper_and_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            helper, args, calls, http = self.setup_case(directory)
            self.assertEqual(hashlib.sha256(HELPER.read_bytes()).hexdigest(), trace.HELPER_SHA256)
            with patch.object(trace.uuid, 'uuid4', return_value=SimpleNamespace(hex='fixed-producer')):
                old = helper.completion(args.base_url, args.model, [1, 2], 32, 'salt', 'producer', args.timeout)
                sink = []
                new = trace.producer_completion(helper, args, [1, 2], 'salt', sink)
            self.assertEqual(calls[0], calls[1])
            for key in old:
                if key != 'elapsed_seconds': self.assertEqual(new[key], old[key])
            self.assertEqual(sink[0]['request_id'], new['request_id'])
            self.assertIs(helper.http, http)
            self.check_interval(new)

    def test_http_failure_preserves_exception_and_records_finished_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            helper, args, _, _ = self.setup_case(directory)
            failure = TimeoutError('inference timed out')
            def broken(*args, **kwargs): raise failure
            helper.http = broken
            sink = []
            with self.assertRaises(TimeoutError) as observed:
                trace.next_token(helper, args, [1], 'salt', 'cold', 0, sink)
            self.assertIs(observed.exception, failure)
            self.assertIs(helper.http, broken)
            self.assertEqual(sink[0]['request_error_type'], 'TimeoutError')
            self.assertIn('request_finished_utc', sink[0])
            json.dumps(sink)

    def test_missing_or_rotated_log_does_not_change_http_result(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = SimpleNamespace(http=lambda *a, **k: {'ok': True})
            missing = Path(directory) / 'missing.log'
            with trace.capture_completion_http(helper, missing) as sink:
                reply = helper.http('base', '/v1/completions', {'request_id': 'one'}, 10)
            self.assertEqual(reply, {'ok': True})
            self.assertEqual(sink[0]['trace_log'], {'start_offset': None, 'end_offset': None})
            self.assertFalse(sink[0]['server_log_same_file_and_nonshrinking'])
            with patch.object(trace, 'log_position', side_effect=[
                    {'byte_offset': 50, 'device': 1, 'inode': 1},
                    {'byte_offset': 4, 'device': 1, 'inode': 2}]):
                with trace.capture_completion_http(helper, missing) as rotated:
                    helper.http('base', '/v1/completions', {'request_id': 'two'}, 10)
            self.assertFalse(rotated[0]['server_log_same_file_and_nonshrinking'])


if __name__ == '__main__': unittest.main()
