"""Pregame proof that only time, not a token target, reaches the model."""
import hashlib
import json


def attest_time_guidance(agent, cfg, directory):
    reminder = agent._budget_reminder
    assert cfg['recipe']['extra_environment']['ARC3_BUDGET_GUIDANCE'] == 'time_only'
    assert reminder.mode == 'time_only' and reminder.target_tokens is None
    assert cfg['recipe']['limits']['generated_policy'] == 'disabled'
    assert cfg['recipe']['limits']['generated_target_per_game'] is None
    cases = []
    for tokens in (0, 108001, 216001, 1000000):
        request, receipt = reminder.prepare(
            [{'role':'system','content':agent._system_prompt}, {'role':'user','content':'Current playable frame.'}],
            status={'game_remaining_seconds':500.9,'suite_remaining_seconds':123.4}, generated_tokens=tokens)
        line = receipt['text']
        assert line == '[Runtime budget] time left 123s (game 500s, suite 123s).'
        assert 'soft target' not in json.dumps(request) and 'reported generated' not in json.dumps(request)
        assert receipt['generated_tokens_reported'] == tokens and receipt['target_tokens'] is None
        cases.append({'reported_generated': tokens, 'text': line})
    assert len({x['text'] for x in cases}) == 1
    report = {
        'status':'passed', 'version':'time_guidance_v1', 'config_id':cfg['config_id'],
        'canary_only':True, 'gameplay_actions':0, 'guidance_mode':reminder.mode,
        'token_target':None, 'model_visible_token_target':False, 'cases':cases,
        'reminder_text_sha256':hashlib.sha256(cases[0]['text'].encode()).hexdigest(),
    }
    (directory/'TIME_GUIDANCE_RUNTIME_RECEIPT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
