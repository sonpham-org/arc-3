import unittest
from probe_first_token import compare_next, summarize


def row(token=1, logprob=-.3, prompt='same', category='resident'):
    return {'token_ids': [token], 'token_logprobs': [logprob], 'prompt_sha256': prompt,
            'top_logprobs': {'token_id:1': -.3, 'token_id:2': -.4}, 'category': category}


class ConditioningTests(unittest.TestCase):
    def test_different_inputs_rejected(self):
        with self.assertRaises(ValueError):
            compare_next(row(), row(prompt='other'))

    def test_no_cross_token_logprob_comparison(self):
        result = compare_next(row(), row(token=2))
        self.assertIsNone(result['selected_token_logprob_error'])
        self.assertFalse(result['selected_token_gate_pass'])
        self.assertEqual(result['common_top_token_count'], 2)

    def test_single_prediction_only(self):
        value = row()
        value['token_ids'] = [1, 2]
        with self.assertRaises(ValueError):
            compare_next(value, row())

    def test_drift_cannot_pass_on_matching_ids(self):
        self.assertFalse(compare_next(row(), row(logprob=-.31))['selected_token_gate_pass'])

    def test_other_token_probability_drift_does_not_pass(self):
        value = row()
        value['top_logprobs']['token_id:2'] = -.5
        result = compare_next(row(), value)
        self.assertTrue(result['selected_token_gate_pass'])
        self.assertFalse(result['pass'])

    def test_missing_top_distribution_cannot_pass(self):
        value = row()
        value['top_logprobs'] = {}
        self.assertFalse(compare_next(value, value)['pass'])

    def test_cold_is_not_restore_evidence(self):
        result = summarize([row(), row(), row(category='cold'), row(category='cold')], 1e-4)
        self.assertNotIn('resident_vs_cpu', result)
        self.assertTrue(result['resident_repeatability']['pass'])

    def test_single_repeat_does_not_establish_repeatability(self):
        self.assertFalse(summarize([row()], 1e-4)['resident_repeatability']['pass'])

    def test_cpu_drift_separate_from_resident_repeatability(self):
        result = summarize([row(), row(), row(category='cpu-restored', logprob=-.32),
                            row(category='cpu-restored', logprob=-.32)], 1e-4)
        self.assertTrue(result['resident_repeatability']['pass'])
        self.assertTrue(result['cpu-restored_repeatability']['pass'])
        self.assertFalse(result['resident_vs_cpu']['pass'])


if __name__ == '__main__':
    unittest.main()
