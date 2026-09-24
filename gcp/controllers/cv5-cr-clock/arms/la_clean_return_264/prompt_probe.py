"""Hash the actual installed prompt surfaces and check the single ablation."""
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path


def attest_prompt(agent, cfg, directory):
    from inference.agent import tool_agent as ta
    from inference.agent import prompt_ablation as pa
    expected = json.loads((directory / 'EXPECTED_PROMPTS.json').read_text())
    flags = pa.enabled_flags()
    declared = {arm: cfg['recipe']['extra_environment'][env] == '1' for arm, env in pa.FLAGS.items()}
    actual = {
        'system': agent._system_prompt,
        'tool': ta._python_tool_description(),
        'first_user': agent._build_user_prompt(0, valid_actions=['MOUSE', 'RIGHT']),
        'user': agent._build_user_prompt(1, valid_actions=['MOUSE', 'RIGHT']),
    }
    # Also check both retry branches against the installed function's real AST.
    source = Path(ta.__file__).read_text()
    tree = ast.parse(source)
    expressions = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'followup_prompt' for t in n.targets)
                   and isinstance(n.value, ast.JoinedStr)]
    assert len(expressions) == 1
    scope = dict(vars(ta), followup_prefix='You have not acted yet. Investigate first. ')
    retry = eval(compile(ast.Expression(expressions[0]), 'installed-retry', 'eval'), scope)
    actual['retry'] = pa.transform(retry, 'retry')
    environment = {k: os.environ.get(k, '') for k in ('MULTIMODAL_CONTEXT', 'MULTIMODAL_UPSCALE')}
    expected_environment = {k: cfg['recipe']['extra_environment'].get(k) for k in environment}
    checks = {k: actual[k] == expected.get(k) for k in actual}
    checks.update(exact_surfaces=set(actual) == set(expected),
                  flags=flags == declared and sum(flags.values()) == 2,
                  image_environment=environment == expected_environment)
    passed = all(checks.values())
    result = {'status': 'passed' if passed else 'failed', 'version': pa.VERSION, 'config_id': cfg['config_id'],
              'flags': flags, 'canary_only': True, 'gameplay_actions': 0,
              'checks': checks, 'environment': environment, 'expected_environment': expected_environment,
              'hashes': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in actual.items()}}
    # Always retain evidence before raising: failed startup must remain diagnosable.
    (directory / 'PROMPT_RUNTIME_RECEIPT.json').write_text(json.dumps(result, indent=2))
    (directory / 'ACTUAL_PROMPTS.json').write_text(json.dumps(actual, indent=2))
    (directory / 'PROMPT_RUNTIME.diff').write_text(''.join(
        line for key in actual for line in difflib.unified_diff(
            expected.get(key, '').splitlines(True), actual[key].splitlines(True),
            fromfile='expected/' + key, tofile='actual/' + key)), encoding='utf-8')
    assert passed, checks
    return result
