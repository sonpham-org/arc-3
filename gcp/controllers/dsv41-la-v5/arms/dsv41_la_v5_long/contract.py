"""Canonical ARC3 recipe identity and evidence-aware labels. Standard library only.

This is a configuration/reporting boundary, not a rewrite of legacy feature gates.
Frozen historical recipes may contain unknowns. New launch recipes fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

FLAGS = {
    'memory': ('M', 'ARC3_PERSISTENT_GAME_MODEL'),
    'execution': ('E', 'ARC3_EXECUTION_MODE'),
    'symbolic': ('S', 'ARC3_SYMBOLIC_SEARCH'),
    'workspace': ('W', 'ARC3_PROGRAMMATIC_WORKSPACE'),
    'animation_metadata': ('A', None),
    'animation_images': ('I', None),
    'toolkit': ('T', 'ARC3_CPU_TOOLKIT_ENABLED'),
    'reminder': ('R', 'ARC3_BUDGET_REMINDER_ENABLED'),
    'curator_learning': ('CL', None),
    'curator_injection': ('CI', None),
    'static_priors': ('SP', None),
    'reflection': ('RF', None),
    'refinement': ('RN', None),
    'replay': ('RP', 'ARC3_REPLAY_ENABLED'),
    'repeat_reminder': ('RR', 'ARC3_REPLAY_TRIGGER_REMINDER'),
    'stall_termination': ('ST', None),
    'dynamic_slack': ('DS', None),
    'object_composition': ('OC', None),
    'small_model_observer': ('VLM', None),
    'cpu_kv_parking': ('KVP', None),
    'kv_async_prefetch': ('KVA', None),
    'rule_preservation': ('PR', None),
    'legacy_animation_tools': ('LAT', None),
    'animation_storyboard': ('AS', None),
    'animation_checkpoint': ('AC', 'ARC3_ANIMATION_CHECKPOINT_ENABLED'),
    'no_change_notice': ('NC', None),
    'hud_factoring': ('HUD', None),
    'segmentation_cache': ('SC', None),
    'vision_result_cache': ('VC', None),
    'saved_python_helpers': ('PH', None),
    'reasoning_router': ('ER', None),
}
MODEL_KEYS = {'id','revision','weights','kv_dtype','ple_dtype','gpu_memory_utilization'}
LIMIT_KEYS = {'lanes','context_tokens','input_tokens','game_seconds','suite_gameplay_minutes',
              'vm_lifetime_seconds','generated_target_per_game','generated_policy','games','evaluation_mode'}
RECIPE_KEYS = {'source_family','source_sha256','execution_version','symbolic_version','model','limits','history','flags','extra_environment'}
ROOT_KEYS = {'schema_version','mode','run_id','config_id','recipe','requested_flags','evidence'}
EVIDENCE_KEYS = {'confidence','verified_flags','adoption','sources','notes'}

class ConfigError(ValueError): pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def config_id(recipe):return digest(recipe)

def exact_keys(value, keys, path):
    if not isinstance(value,dict):raise ConfigError(f'{path}: expected an object')
    if set(value)!=keys:
        raise ConfigError(f'{path}: missing {sorted(keys-set(value))}, unknown {sorted(set(value)-keys)}')

def boolean(value, path):
    if value is not None and type(value) is not bool:raise ConfigError(f'{path}: expected true, false or null')

def validate(record, *, for_launch=False):
    exact_keys(record,ROOT_KEYS,'record')
    if record['schema_version']!=1:raise ConfigError('Unsupported schema_version')
    if record['mode'] not in {'historical_snapshot','planned'}:raise ConfigError('Unknown mode')
    if not isinstance(record['run_id'],str) or not record['run_id']:raise ConfigError('Missing run_id')
    recipe=record['recipe'];exact_keys(recipe,RECIPE_KEYS,'recipe')
    exact_keys(recipe['flags'],set(FLAGS),'recipe.flags')
    exact_keys(record['requested_flags'],set(FLAGS),'requested_flags')
    for name in FLAGS:
        boolean(recipe['flags'][name],'recipe.flags.'+name)
        boolean(record['requested_flags'][name],'requested_flags.'+name)
    exact_keys(recipe['model'],MODEL_KEYS,'model')
    exact_keys(recipe['limits'],LIMIT_KEYS,'limits')
    exact_keys(recipe['history'],{'policy','fixed_assistant_turns'},'history')
    if recipe['history']['policy'] not in {None,'fixed30','full_context','other'}:raise ConfigError('Unknown history policy')
    if recipe['execution_version'] not in {'none','legacy_e1','memory_lease_e2','unknown'}:raise ConfigError('Unknown execution implementation')
    if recipe['symbolic_version'] not in {'none','v1','v2','pinned_source','unknown'}:raise ConfigError('Unknown symbolic implementation')
    for key in ('lanes','context_tokens','input_tokens','game_seconds','suite_gameplay_minutes','vm_lifetime_seconds','generated_target_per_game','games'):
        value=recipe['limits'][key]
        if value is not None and (type(value) not in (int,float) or value<=0):raise ConfigError(f'limits.{key}: expected positive number or null')
    limits=recipe['limits']
    if limits['context_tokens'] is not None and limits['input_tokens'] is not None and limits['input_tokens']>=limits['context_tokens']:
        raise ConfigError('Input budget must leave an output/context reserve')
    if limits['generated_policy'] not in {None,'advisory','enforced','disabled'}:raise ConfigError('Unknown generated-token policy')
    if limits['evaluation_mode'] not in {None,'gcp_local_25','kaggle_readiness','kaggle_competition','other'}:raise ConfigError('Unknown evaluation mode')
    if not isinstance(recipe['extra_environment'],dict):raise ConfigError('extra_environment must be an object')
    for key,value in recipe['extra_environment'].items():
        if not key or any(not (c.isupper() or c.isdigit() or c=='_') for c in key) or not isinstance(value,str):raise ConfigError('Invalid environment entry')
        if any(x in key for x in ('SECRET','PASSWORD','API_KEY','ACCESS_TOKEN','CREDENTIAL')):raise ConfigError('Credentials do not belong in a config receipt')
    evidence=record['evidence'];exact_keys(evidence,EVIDENCE_KEYS,'evidence')
    if evidence['confidence'] not in {'runtime_checked','source_audited','metadata_only','unknown'}:raise ConfigError('Unknown confidence')
    if not isinstance(evidence['verified_flags'],dict) or set(evidence['verified_flags'])-set(FLAGS):raise ConfigError('Unknown runtime flag')
    for key,value in evidence['verified_flags'].items():boolean(value,'verified_flags.'+key)
    if not isinstance(evidence['adoption'],dict) or set(evidence['adoption'])-set(FLAGS):raise ConfigError('Unknown adoption feature')
    for key,value in evidence['adoption'].items():
        exact_keys(value,{'invocations','scope','source'},'adoption.'+key)
        if value['invocations'] is not None and (type(value['invocations']) is not int or value['invocations']<0):raise ConfigError('Invalid invocation count')
        if value['scope'] not in {'gameplay','canary','unknown'}:raise ConfigError('Unknown adoption scope')
    if record['config_id']!=config_id(recipe):raise ConfigError('Config hash mismatch; recipe was edited without re-registering')
    if for_launch:
        if record['mode']!='planned':raise ConfigError('Historical snapshot is evidence, not a launch recipe')
        if any(v is None for v in recipe['flags'].values()):raise ConfigError('Resolve every unknown feature before a new launch')
        # A disabled cumulative-token policy has no target, not an unknown target.
        if any(v is None for k,v in limits.items()
               if not (k=='generated_target_per_game' and limits['generated_policy']=='disabled')):
            raise ConfigError('Resolve all resource limits before a new launch')
        if not isinstance(recipe['source_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',recipe['source_sha256']):raise ConfigError('Pin the exact source digest before launch')
        if any(v is None for v in recipe['model'].values()):raise ConfigError('Pin model, precision and allocation before launch')
        if recipe['history']['policy'] in {None,'other'}:raise ConfigError('History policy is unresolved')
        flags=recipe['flags']
        if record['requested_flags']!=flags:raise ConfigError('New recipes must state dependencies explicitly; requested and resolved flags differ')
        if flags['execution'] and recipe['execution_version'] in {'none','unknown'}:raise ConfigError('Execution flag needs an implementation version')
        if not flags['execution'] and recipe['execution_version']!='none':raise ConfigError('Execution OFF requires implementation none')
        if flags['execution'] and recipe['execution_version']=='memory_lease_e2' and not flags['memory']:raise ConfigError('E2 requires explicit memory ON')
        if flags['symbolic'] and not flags['memory']:raise ConfigError('Current symbolic implementation requires explicit memory ON')
        if flags['symbolic'] and recipe['symbolic_version'] in {'none','unknown'}:raise ConfigError('Symbolic ON needs its version')
        if not flags['symbolic'] and recipe['symbolic_version']!='none':raise ConfigError('Symbolic OFF requires implementation none')
        guidance=recipe['extra_environment'].get('ARC3_BUDGET_GUIDANCE','tokens_and_time')
        if guidance not in {'tokens_and_time','time_only'}:raise ConfigError('Unknown budget guidance mode')
        if guidance=='time_only':
            if not flags['reminder'] or limits['generated_policy']!='disabled' or limits['generated_target_per_game'] is not None:
                raise ConfigError('Time-only guidance requires reminder ON, disabled token policy and no token target')
        elif flags['reminder'] and limits['generated_policy']!='advisory':
            raise ConfigError('Current reminder adapter is advisory; enforcement needs a new implementation')
        if flags['animation_images'] and not flags['animation_metadata']:raise ConfigError('Image/metadata replacement needs an explicit supported adapter')
        for name,(_,env) in FLAGS.items():
            if env and env in recipe['extra_environment'] and recipe['extra_environment'][env]!=str(int(flags[name])):
                raise ConfigError('Conflicting environment override: '+env)
        for key,expected in {'LOCAL_ANALYZER_CONTEXT_WINDOW':limits['context_tokens'],'ARC3_BENCHMARK_CONCURRENCY':limits['lanes'],
                             'ARC3_MAX_RUNTIME_S_PER_GAME':limits['game_seconds'],'ARC3_MAX_RUN_RUNTIME_MINUTES':limits['suite_gameplay_minutes'],
                             'ARC3_HISTORY_MODE':recipe['history']['policy']}.items():
            if key in recipe['extra_environment'] and recipe['extra_environment'][key]!=str(expected):raise ConfigError('Conflicting environment override: '+key)
    return record

def label(record):
    validate(record)
    r=record['recipe'];lim=r['limits'];v=record['evidence']['verified_flags']
    tags=[];conflicts=[]
    for name,(short,_) in FLAGS.items():
        configured=r['flags'][name];effective=v.get(name)
        if effective is not None and configured is not None and effective!=configured:conflicts.append(name)
        value=effective if effective is not None else configured
        if value:
            if name=='execution':short={'legacy_e1':'E1','memory_lease_e2':'E2'}.get(r['execution_version'],'E?')
            if name=='symbolic':short={'v1':'S1','v2':'S2','pinned_source':'S'}.get(r['symbolic_version'],'S?')
            if effective is None and not short.endswith('?'):short+='?'
            tags.append(short)
    unknown=[k for k in FLAGS if r['flags'][k] is None and v.get(k) is None]
    base=f"W{lim['lanes'] or '?'} C{lim['context_tokens'] or '?'} {r['history']['policy'] or '?'} | {'+'.join(tags) or 'no known optional features'} | {lim['suite_gameplay_minutes'] or '?'}m | cfg:{record['config_id'][:10]}"
    if unknown:base+=f' | {len(unknown)} unknown'
    if conflicts:base+=' | CONFLICT:'+','.join(conflicts)
    return base

def diff(left,right):
    validate(left);validate(right);out=[]
    def walk(a,b,path):
        if isinstance(a,dict) and isinstance(b,dict):
            for k in sorted(set(a)|set(b)):walk(a.get(k),b.get(k),path+'.'+k if path else k)
        elif a!=b:out.append({'setting':path,'left':a,'right':b})
    walk(left['recipe'],right['recipe'],'recipe')
    return out

def managed_environment(record):
    """Generate current E2 core variables; never pretend legacy groups are wired."""
    validate(record,for_launch=True)
    r=record['recipe'];flags=r['flags'];limits=r['limits']
    if r['execution_version']=='legacy_e1':raise ConfigError('Legacy E1 is audit-only; it needs its own source adapter')
    # Non-core behavior must be configured by an explicit adapter outside this
    # function and validated against this same file before resource allocation.
    out={env:str(int(flags[name])) for name,(_,env) in FLAGS.items() if env}
    out.update(ARC3_VISUAL_TRANSITION_MODE='additive' if flags['animation_images'] else 'metadata' if flags['animation_metadata'] else 'control',
               ARC3_HISTORY_MODE=r['history']['policy'],LOCAL_ANALYZER_CONTEXT_WINDOW=str(limits['context_tokens']),
               ARC3_BENCHMARK_CONCURRENCY=str(limits['lanes']),ARC3_MAX_RUNTIME_S_PER_GAME=str(limits['game_seconds']),
               ARC3_MAX_RUN_RUNTIME_MINUTES=str(limits['suite_gameplay_minutes']),ARC3_CONFIG_SHA256=record['config_id'])
    for key,value in r['extra_environment'].items():
        if key in out and value!=out[key]:raise ConfigError('Conflicting environment override: '+key)
        out[key]=value
    return out

def assert_runtime(record, *, source_sha256, observed_flags, effective_limits, prompt_sha256, tool_schema_sha256):
    """Final pre-game comparison. Caller must observe real agent/runtime values."""
    validate(record,for_launch=True);r=record['recipe']
    if source_sha256!=r['source_sha256']:raise ConfigError('Runtime source mismatch')
    if set(observed_flags)!=set(FLAGS):raise ConfigError('Runtime probe must cover every declared capability')
    if any(type(x) is not bool for x in observed_flags.values()):raise ConfigError('Unknown runtime capability')
    if observed_flags!=r['flags']:raise ConfigError('Runtime features differ from CONFIG_FLAGS.json')
    if effective_limits!=r['limits']:raise ConfigError('Effective post-unpickle limits differ from CONFIG_FLAGS.json')
    if not all(isinstance(x,str) and re.fullmatch('[0-9a-f]{64}',x) for x in (prompt_sha256,tool_schema_sha256)):raise ConfigError('Missing prompt/tool schema hashes')
    return {'config_id':record['config_id'],'source_sha256':source_sha256,'verified_flags':observed_flags,
            'effective_limits':effective_limits,'prompt_sha256':prompt_sha256,'tool_schema_sha256':tool_schema_sha256,'status':'passed'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['validate','label','diff','core-env']);p.add_argument('file',type=Path);p.add_argument('other',nargs='?',type=Path);p.add_argument('--for-launch',action='store_true');args=p.parse_args()
    record=json.loads(args.file.read_text(encoding='utf-8-sig'))
    try:
        validate(record,for_launch=args.for_launch)
        value={'status':'passed','config_id':record['config_id'],'mode':record['mode']}
        if args.command=='label':value=label(record)
        elif args.command=='core-env':value={'scope':'core environment only; not launch approval','environment':managed_environment(record),'requires_runtime_adapter_for':[k for k,(_,env) in FLAGS.items() if env is None]}
        elif args.command=='diff':
            if args.other is None:p.error('diff needs another file')
            value=diff(record,json.loads(args.other.read_text(encoding='utf-8-sig')))
        print(json.dumps(value,indent=2))
    except ConfigError as exc:
        print(json.dumps({'status':'failed','error':str(exc)}));raise SystemExit(2)

if __name__=='__main__':main()
