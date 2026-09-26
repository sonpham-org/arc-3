"""Read-only pregame attestation for one frozen clean/reminder deployment.

Not a generic feature adapter: unsupported recipes are refused by deploy.py.
Only declared prompt text changes; solver and sandbox are unchanged.
"""
import ast,hashlib,inspect,json,os,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
import contract

def sha(b):return hashlib.sha256(b).hexdigest()
def enc(x):return (json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
HERE=Path(__file__).resolve().parent

def attest(bm, target, suite_minutes):
    from inference.agent import tool_agent as ta
    from inference.agent import python_tool_sandbox as sandbox
    from inference.agent.runtime_state import Frame,write_runtime_state
    from inference.framework import solver
    cfg=json.loads((HERE/'CONFIG_FLAGS.json').read_text())
    manifest=json.loads(Path('/opt/arc3/execution-release-manifest.json').read_text())
    actual={}
    for name,digest in manifest['candidate_files'].items():
        raw=(Path('/opt/arc3/bundle')/name).read_bytes();actual[name]=sha(raw)
        assert actual[name]==digest,name
        if name.startswith('src/ARC3-Inference/inference/'):
            installed=Path(ta.__file__).resolve().parents[1]/name.split('/inference/',1)[1]
            assert sha(installed.read_bytes())==digest,str(installed)
    source_hash=sha(enc(actual));assert source_hash==cfg['recipe']['source_sha256']
    agent=ta.ToolAgent()
    from prompt_probe import attest_prompt
    attest_prompt(agent, cfg, HERE)
    from time_guidance_probe import attest_time_guidance
    guidance_receipt=attest_time_guidance(agent, cfg, HERE)
    from inference.agent import half_context_swap as rc
    assert os.environ.get(rc.FLAG) == cfg['recipe']['extra_environment'][rc.FLAG] == '1'
    assert agent._half_swap is not None and rc.VERSION == 'half_context_swap_v2_on_demand_compaction' and agent._half_swap.compact is True
    assert os.environ.get('ARC3_ROLLING_HALF_CHECKPOINT') == cfg['recipe']['extra_environment']['ARC3_ROLLING_HALF_CHECKPOINT'] == '0'
    gate=json.loads(Path('/opt/arc3/half-swap-live-gate.json').read_text())
    assert gate['status']=='passed' and gate['no_generation_verified']
    assert gate['generation_calls']==0 and gate['retained_tail_byte_equal']
    assert gate['module_sha256']==sha(Path(rc.__file__).read_bytes())
    assert gate['input_budget']==agent._context_budget_tokens==72192
    process_list=subprocess.check_output(['ps','-eo','args'],text=True)
    serving=json.loads(subprocess.check_output(['docker','inspect','flashnext'],text=True))[0]
    args=serving['Config']['Cmd'];assert serving['State']['Running']
    assert '--kv-transfer-config' not in args and '--cpu-offload-gb' not in args
    assert args[args.index('--gpu-memory-utilization')+1]=='0.95'
    assert args[args.index('--kv-cache-dtype')+1]=='fp8_e4m3'
    assert args[args.index('--max-model-len')+1]=='80896'
    assert args[args.index('--max-num-seqs')+1]=='6'
    with tempfile.TemporaryDirectory(prefix='clean-config-canary-') as tmp:
        path=Path(tmp)/'state.json'
        write_runtime_state(path,current_frame=Frame(((0,1),(1,0)),0,1),history=[])
        agent._last_animation={'animation_frame_count':2,'animation_changed_frame_count':1}
        result=agent._run_python_tool(path,{'code':"a=current_frame.segmentation\nresult={'segmentation_cache': a is current_frame.segmentation, 'composition': hasattr(current_frame, 'composition'), 'toolkit': 'vision' in dir(), 'symbolic': 'symbolic_search' in dir(), 'workspace': 'workspace' in dir(), 'replay': 'replay' in dir(), 'saved_helpers': 'load_helper' in dir(), 'memory_write': remember(ready=False).get('accepted', False)}"})
        payload=json.loads(result.content)
        # Exact dispatch output is retained; not counted as gameplay adoption.
        probe=payload['result'];assert isinstance(probe,dict),payload
        schema=agent._tools(path)
    fields=solver._HarnessGameSession.__dataclass_fields__
    checkpoint=bool(fields['animation_checkpoint_enabled'].default_factory())
    hud=int(fields['animation_hud_border'].default_factory())
    story_budget=int(fields['animation_storyboard_max_tokens'].default_factory())
    source_files=set(actual)
    optional=lambda stem:any('/'+stem+'.py' in n for n in source_files)
    common_text,_=ta._common_themes_prompt_block()
    present=lambda name:ta._get_env_bool(name,False)
    flags={
      'memory':bool(agent._persistent_game_model),'execution':bool(agent._execution_enabled),
      'symbolic':bool(agent._symbolic_search_enabled or probe['symbolic']),
      'workspace':bool(agent._programmatic_workspace_enabled or probe['workspace']),
      'animation_metadata':optional('visual_transition'),'animation_images':optional('visual_transition') and os.getenv('ARC3_VISUAL_TRANSITION_MODE') in ('additive','replace'),
      'toolkit':bool(probe['toolkit']),'reminder':agent._budget_reminder is not None,
      'curator_learning':any(n in process_list for n in ('nvfp4_cross_game_curator.py','cross_game_theme_influence_sidecar.py')),
      'curator_injection':bool(common_text),'static_priors':bool(common_text),
      'reflection':present('ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED'),
      'refinement':optional('champion_refinement'),'replay':bool(probe['replay']),
      'repeat_reminder':present('ARC3_REPLAY_TRIGGER_REMINDER'),
      'stall_termination':present('ARC3_STALL140_ONLY'),'dynamic_slack':present('ARC3_DYNAMIC_SLACK_ENABLED'),
      'object_composition':bool(probe['composition']),'small_model_observer':optional('small_model_observer'),
      'cpu_kv_parking':'--kv-transfer-config' in args,'kv_async_prefetch':'--kv-transfer-config' in args,
      'rule_preservation':bool(agent._persistent_game_model and probe['memory_write']),
      'legacy_animation_tools':'class AnimationView:' in sandbox._SANDBOX_BOOTSTRAP,
      'animation_storyboard':checkpoint and story_budget>0 and callable(solver._build_animation_storyboard),
      'animation_checkpoint':checkpoint,
      'no_change_notice':'did not show a confirmed board change' in agent._describe_last_outcome({'board_changed':False}),
      'hud_factoring':hud>0,'segmentation_cache':bool(probe['segmentation_cache']),
      'vision_result_cache':bool(probe['toolkit']) and optional('vision_tools'),
      'saved_python_helpers':bool(probe['saved_helpers'] or probe['workspace']),
      'reasoning_router':agent._execution_mode is not None,
    }
    assert agent._full_context_tokens is not None
    assert not probe['memory_write']
    assert agent._model.model_id==cfg['recipe']['model']['id']
    assert target.actual_run_as_submission is False and target.is_competition_rerun is False
    limits={'lanes':bm.solver.concurrency,'context_tokens':ta._LOCAL_ANALYZER_CONTEXT_WINDOW,
      'input_tokens':agent._context_budget_tokens,'game_seconds':bm.solver.max_runtime_s_per_game,
      'suite_gameplay_minutes':suite_minutes,'vm_lifetime_seconds':14400,
      'generated_target_per_game':agent._budget_reminder.target_tokens,'generated_policy':('disabled' if agent._budget_reminder.mode=='time_only' else 'advisory'),
      'games':len(bm.games),'evaluation_mode':'gcp_local_25'}
    receipt=contract.assert_runtime(cfg,source_sha256=source_hash,observed_flags=flags,effective_limits=limits,
      prompt_sha256=sha(agent._system_prompt.encode()),tool_schema_sha256=sha(enc(schema)))
    receipt.update(canary_only=True,gameplay_actions=0,sandbox_result=payload,budget_guidance=guidance_receipt,
      source_file_count=len(actual),serving_arguments=args,
      fixed_family_absences='Absent feature modules + exact installed 84-file source digest; flags describe this frozen family only.',
      vm_lifetime_evidence='GCP accepted scheduling.maxRunDuration is verified by deploy.py status; startup retains the original 14400-second watchdog.')
    (HERE/'CONFIG_RUNTIME_RECEIPT.json').write_bytes(enc(receipt))
    print('CONFIG_RUNTIME_VERIFIED '+cfg['config_id'],flush=True)

def main():
    runner=Path('/opt/arc3/v12_run.py');raw=runner.read_text()
    expected=json.loads((HERE/'ADAPTER.json').read_text())
    assert sha(runner.read_bytes())==expected['effective_runner_sha256']
    anchor='soft_end = datetime.now() + timedelta(minutes=132)'
    assert raw.count(anchor)==1
    replacement="from runtime_probe import attest\nattest(bm,target,132)\n"+anchor
    # Only adds the no-action attestation before the original gameplay clock.
    exec(compile(raw.replace(anchor,replacement),str(runner),'exec'),{'__name__':'__main__','__file__':str(runner)})

if __name__=='__main__':main()
