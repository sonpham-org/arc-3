"""Installed prompt/API attestation before gameplay; directed canary is not adoption."""
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


def prompt_surfaces(agent):
    from inference.agent import tool_agent as ta, input_access as api, prompt_ablation as pa
    actual = dict(system=agent._system_prompt, tool=ta._python_tool_description(),
                  first_user=agent._build_user_prompt(0,valid_actions=['MOUSE','RIGHT']),
                  user=agent._build_user_prompt(1,valid_actions=['MOUSE','RIGHT']))
    expressions = [n.value for n in ast.walk(ast.parse(Path(ta.__file__).read_text()))
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='followup_prompt' for t in n.targets)
        and isinstance(n.value,ast.JoinedStr)]
    assert len(expressions)==1
    retry=eval(compile(ast.Expression(expressions[0]),'installed-retry','eval'),
               dict(vars(ta),followup_prefix='You have not acted yet. Investigate first. '))
    actual['retry']=pa.transform(retry,'retry')
    malformed=eval(compile(ast.Expression(expressions[0]),'installed-malformed-retry','eval'),
        dict(vars(ta),followup_prefix='We detected `<tool_call>` markup. Use the native tool channel. '))
    actual['malformed_retry']=pa.transform(malformed,'retry')
    return actual


def attest_prompt(agent, cfg, directory):
    from inference.agent import tool_agent as ta, input_access as api, prompt_ablation as pa, loop_variants as lv
    expected = json.loads((directory/'EXPECTED_PROMPTS.json').read_text())
    actual=prompt_surfaces(agent)
    declared=cfg['recipe']['extra_environment']
    checks={key:actual[key]==expected.get(key) for key in actual}
    checks.update(exact_surfaces=set(actual)==set(expected), input_api=api.enabled()==(declared[api.FLAG]=='1'),
        loop_variant=lv.mode()==declared[lv.FLAG] and lv.mode() in 'abcde',
        version=api.VERSION=='obs_access_v1',
        flags=pa.enabled_flags()=={k:declared[v]=='1' for k,v in pa.FLAGS.items()},
        image_environment=all(os.environ.get(k)==declared[k] for k in ('MULTIMODAL_CONTEXT','MULTIMODAL_UPSCALE')))
    receipt=dict(status='passed' if all(checks.values()) else 'failed',config_id=cfg['config_id'],
        version=api.VERSION,checks=checks,canary_only=True,gameplay_actions=0,
        hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in actual.items()})
    (directory/'ACTUAL_PROMPTS.json').write_text(json.dumps(actual,indent=2))
    (directory/'PROMPT_RUNTIME_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    (directory/'PROMPT_RUNTIME.diff').write_text(''.join(line for k in actual for line in
        difflib.unified_diff(expected.get(k,'').splitlines(True),actual[k].splitlines(True),
                             fromfile='expected/'+k,tofile='actual/'+k)),encoding='utf-8')
    assert all(checks.values()),checks
    return receipt


def attest_loop_api(agent,cfg,directory,*,live=True):
    """Directed synthetic integration test, never a gameplay action or adoption."""
    from inference.agent import tool_agent as ta,loop_variants as lv
    from inference.agent.runtime_state import Frame,HistoryEntry,write_runtime_state
    mode=lv.mode();assert mode in 'abcde'
    with tempfile.TemporaryDirectory(prefix='loop-canary-') as tmp:
        path=Path(tmp)/'state.json';frames=[Frame(((0,0),),0,1)];calls=[]
        def save():
            write_runtime_state(path,current_frame=frames[-1],history=[HistoryEntry('' if i==0 else 'RIGHT',f) for i,f in enumerate(frames)])
        save();agent._ensure_session(path);agent._current_valid_actions=['RIGHT']
        capability=json.loads(agent._run_python_tool(path,{'code':"result=['checked_action' in dir(),'execute_checked' in dir()]"}).content)
        assert capability.get('result')==[mode=='d',mode=='e'],capability
        model_usage=None;usage=None;checks=None
        if mode in ('d','e'):
            def step(request):
                assert request=={'actions':[{'action':'RIGHT'}]},request
                calls.append(request);n=len(calls);frames.append(Frame(((0,n),),n,1));save()
                return dict(executed=True,executed_count=1,requested_count=1,valid_actions=['RIGHT'],
                            action_num=n,level=1,score=0,board_changed=True,done=False)
            code=("checked_action('RIGHT',lambda o:o.ascii,expected='Ww')" if mode=='d' else
                  "execute_checked(['RIGHT','RIGHT'],lambda o:o.ascii,expected=['Ww','Wg'])")
            arguments={'code':code}
            if live:
                sys.path.insert(0,'/opt/arc3/execution-selftest')
                from canary_retry import verified_call
                messages=[{'role':'system','content':agent._system_prompt},
                    {'role':'user','content':'Directed synthetic checked-action integration test, not gameplay. Call python once with exactly this code.\n<exact_code>\n'+code+'\n</exact_code>'}]
                reply,arguments=verified_call(agent,ta,messages,agent._tools(path),code,directory/'loop-canary-attempts.json')
                model_usage=reply.usage
            old_callback=agent._step_env_callback
            try:
                agent._step_env_callback=step
                dispatch=agent._run_python_tool(path,arguments);result=json.loads(dispatch.content)
            finally:agent._step_env_callback=old_callback
            assert dispatch.step_executed and not result.get('error'),result
            checks=result['checks'];count=1 if mode=='d' else 2
            assert len(calls)==checks['executed']==checks['matched']==count and checks['status']=='matched',result
            usage=json.loads(path.with_name(path.stem+'_checked_usage.jsonl').read_text().splitlines()[-1])
            assert usage['completed'] and not usage['tool_error'] and usage['usage']['report']==checks,usage
        report=dict(status='passed',config_id=cfg['config_id'],version=lv.VERSION,mode=mode,
            capabilities=capability['result'],model_canary=live and mode in ('d','e'),canary_only=True,
            synthetic_actions=len(calls),gameplay_actions=0,spontaneous_adoption=False,checks=checks,usage=usage,
            completion_usage=model_usage)
        (directory/'LOOP_RUNTIME_RECEIPT.json').write_text(json.dumps(report,indent=2))
        return report


def attest_input_api(agent,cfg,directory,*,live=True):
    from inference.agent import tool_agent as ta, input_access as api
    from inference.agent.runtime_state import Frame,HistoryEntry,write_runtime_state
    if not api.enabled():
        assert cfg['recipe']['extra_environment'][api.FLAG]=='0'
        from inference.agent import loop_variants as lv
        assert lv.mode()=='a'
        code="names=set(dir()); result={'new_names':[n in names for n in ('obs','current_obs','obs_diff','frame_diff')],'legacy':[current_frame.step,previous_frame.step,history[-1].frame.step,len(history)],'action':callable(action),'segmentation':sorted(current_frame.segmentation)}"
        expected={'new_names':[False]*4,'legacy':[5,4,5,6],'action':True,'segmentation':['adjacency_list','nodes']}
        with tempfile.TemporaryDirectory(prefix='a-noobs-canary-') as tmp:
            state=Path(tmp)/'state.json'
            frames=[Frame(((0,i),),i,1) for i in range(6)]
            write_runtime_state(state,current_frame=frames[-1],history=[HistoryEntry('' if i==0 else 'RIGHT',f) for i,f in enumerate(frames)])
            arguments={'code':code}; model_usage=None
            if live:
                sys.path.insert(0,'/opt/arc3/execution-selftest')
                from canary_retry import verified_call
                messages=[{'role':'system','content':agent._system_prompt},{'role':'user','content':'Directed input API OFF integration check, not gameplay. Call python once with exactly this code. Do not call action.\n<exact_code>\n'+code+'\n</exact_code>'}]
                reply,arguments=verified_call(agent,ta,messages,agent._tools(state),code,directory/'input-canary-attempts.json')
                model_usage=reply.usage
            dispatch=agent._run_python_tool(state,arguments); result=json.loads(dispatch.content)
            assert not dispatch.step_executed and not result.get('error') and result.get('result')==expected,result
            usage_path=state.with_name(state.stem+'_input_access_usage.jsonl')
            usage=json.loads(usage_path.read_text().splitlines()[-1]) if usage_path.exists() else None
            if usage:assert usage['completed'] and not usage['usage']['counts'],usage
            report=dict(status='passed',config_id=cfg['config_id'],version=api.VERSION,flag=api.FLAG,
                enabled=False,model_canary=live,canary_only=True,gameplay_actions=0,spontaneous_adoption=False,
                result=result['result'],usage=usage,completion_usage=model_usage,code_sha256=hashlib.sha256(code.encode()).hexdigest())
            (directory/'INPUT_ACCESS_RUNTIME_RECEIPT.json').write_text(json.dumps(report,indent=2))
            return report
    frames=[Frame(((0,i),),i,1) for i in range(6)]
    code="result={'steps':[o.step for o in obs[:]],'same':current_obs is obs[0],'old':obs[5].ascii,'cells':obs_diff(detail='cells')['items'],'alias':frame_diff is obs_diff}"
    expected={'steps':[5,4,3,2,1,0],'same':True,'old':'WW','cells':[[0,1,4,5]],'alias':True}
    with tempfile.TemporaryDirectory(prefix='obs-access-canary-') as tmp:
        state=Path(tmp)/'tool_runtime_state.json'
        write_runtime_state(state,current_frame=frames[-1],history=[HistoryEntry('' if i==0 else 'RIGHT',f) for i,f in enumerate(frames)])
        arguments={'code':code}
        model_usage=None
        if live:
            sys.path.insert(0,'/opt/arc3/execution-selftest')
            from canary_retry import verified_call
            messages=[{'role':'system','content':agent._system_prompt},
                {'role':'user','content':'Directed input API integration check, not gameplay. Call python once with exactly this code. Do not call action.\n<exact_code>\n'+code+'\n</exact_code>'}]
            reply,arguments=verified_call(agent,ta,messages,agent._tools(state),code,
                                          directory/'input-canary-attempts.json')
            model_usage=reply.usage
        result=json.loads(agent._run_python_tool(state,arguments).content)
        assert not result.get('error'),result
        assert result.get('result')==expected,result
        usage_file=state.with_name(state.stem+'_input_access_usage.jsonl')
        usage=json.loads(usage_file.read_text().splitlines()[-1])
        assert usage['completed'] and usage['usage']['counts']['obs_diff']==1,usage
        report=dict(status='passed',config_id=cfg['config_id'],version=api.VERSION,
            flag=api.FLAG,enabled=api.enabled(),model_canary=live,canary_only=True,
            gameplay_actions=0,spontaneous_adoption=False,result=result['result'],usage=usage,
            completion_usage=model_usage,code_sha256=hashlib.sha256(code.encode()).hexdigest())
        (directory/'INPUT_ACCESS_RUNTIME_RECEIPT.json').write_text(json.dumps(report,indent=2))
        return report
