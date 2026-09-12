"""Optional model-authored observation checks. Always uses existing action dispatch."""
import hashlib
import json
import math

CHECKED_VERSION='checked_actions_v1'


class CheckedStop(BaseException):
    """Intentional return to the model, not a Python tool error."""


def checked_value(value):
    count=[0]
    def visit(v,depth=0):
        count[0]+=1
        if count[0]>64 or depth>5:raise ValueError('extracted value is too complex')
        if v is None:raise ValueError('missing or ambiguous extracted value')
        if type(v) in (bool,int,str):return v
        if type(v) is float and math.isfinite(v):return v
        if type(v) in (list,tuple):
            if not v:raise ValueError('empty extracted value')
            return [visit(x,depth+1) for x in v]
        if type(v) is dict:
            if not v or any(type(k) is not str for k in v):raise ValueError('need nonempty string-keyed values')
            return {k:visit(x,depth+1) for k,x in v.items()}
        raise ValueError('extracted value is not finite JSON')
    result=visit(value)
    encoded=json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
    if len(encoded)>256:raise ValueError('extracted value exceeds 256 characters')
    return result,encoded


class CheckedController:
    def __init__(self,mode,globals_,action,normalize):
        self.mode=mode;self.globals=globals_;self.action=action;self.normalize=normalize
        self.checking=False;self.finished=False;self.events=[];self.report=None

    def event(self,event,**fields):
        if len(self.events)<48:self.events.append(dict(event=event,**fields))

    def payload(self):
        return dict(version=CHECKED_VERSION,mode=self.mode,events=self.events,report=self.report)

    def assert_action_allowed(self):
        if self.checking:raise ValueError('observation extractors cannot execute actions')
        if self.finished:raise CheckedStop()

    def stop(self,status,reason,executed=0,matched=0,index=None,**details):
        self.finished=True
        self.report=dict(mode=self.mode,status=status,reason=reason,executed=executed,matched=matched)
        if index is not None:self.report['index']=index
        self.report.update(details)
        self.event('returned',**self.report)
        raise CheckedStop()

    def extract(self,fn,observation):
        self.checking=True
        try:return checked_value(fn(observation))
        finally:self.checking=False

    def prepare(self,commands,fn,expected):
        if not callable(fn):raise ValueError('extract must be callable')
        if not isinstance(commands,(list,tuple)) or not 1<=len(commands)<=14:
            raise ValueError('need 1..14 single actions')
        if not isinstance(expected,(list,tuple)) or len(expected)!=len(commands):
            raise ValueError('one expected value required per action')
        plan=[]
        for command,target in zip(commands,expected):
            if not isinstance(command,(str,dict)):raise ValueError('each command must be one action')
            normalized=self.normalize(command)
            if len(normalized)!=1:raise ValueError('nested batches are not supported')
            cmd=normalized[0]
            if cmd['action']=='MOUSE':
                shape=self.globals['current_frame'].shape
                if any(type(cmd.get(k)) is not int or not 0<=cmd[k]<shape[i] for i,k in enumerate(('row','col'))):
                    raise ValueError('MOUSE needs in-bounds integer row/col')
            value,encoded=checked_value(target)
            plan.append((dict(cmd),value,encoded))
        return plan

    def run(self,commands,fn,expected):
        self.assert_action_allowed()
        executed=matched=0
        try:plan=self.prepare(commands,fn,expected)
        except Exception as exc:self.stop('uncheckable','invalid_prediction',error=str(exc)[:160])
        self.event('plan_registered',steps=len(plan),expected_sha256=hashlib.sha256(
            json.dumps([p[1] for p in plan],sort_keys=True).encode()).hexdigest())
        for index,(command,target,encoded) in enumerate(plan):
            before=self.globals['current_frame']
            prior_result=self.globals.get('last_action_result') or {}
            if (any(prior_result.get(k) for k in ('game_over','run_complete'))
                or (prior_result.get('done') and not prior_result.get('level_completed'))):
                self.stop('stopped','prior_terminal_or_level',executed,matched,index)
            if command['action'] not in self.globals.get('valid_actions',[]):
                self.stop('stopped','invalid_action',executed,matched,index)
            try:self.extract(fn,before)
            except Exception as exc:self.stop('uncheckable','extractor_before',executed,matched,index,error=str(exc)[:160])
            self.event('prediction_registered',index=index,step=before.step,level=before.level,expected=target)
            try:result=self.action(command)
            except Exception as exc:
                # The existing host action-cap interrupt can arrive after an executed action.
                last=self.globals.get('last_action_result') or {}
                if last.get('executed') and self.globals['current_frame'] is not before:executed+=1
                self.stop('stopped',last.get('stop_reason') or 'action_error',executed,matched,index,error=str(exc)[:160])
            actual_count=result.get('executed_count',int(bool(result.get('executed'))))
            executed+=int(bool(result.get('executed')))
            if actual_count!=1 or not result.get('executed'):
                self.stop('stopped',result.get('stop_reason') or 'action_not_executed',executed,matched,index)
            after=self.globals['current_frame']
            if any(result.get(k) for k in ('done','game_over','run_complete')):
                self.stop('stopped','terminal',executed,matched,index)
            if result.get('level_completed') or before.level!=after.level or before.shape!=after.shape or after.step<before.step:
                self.stop('stopped','level_or_shape_boundary',executed,matched,index)
            if result.get('error') or result.get('stop_reason') or result.get('stopped_early'):
                self.stop('stopped',result.get('stop_reason') or 'host_interruption',executed,matched,index)
            try:observed,actual=self.extract(fn,after)
            except Exception as exc:self.stop('uncheckable','extractor_after',executed,matched,index,error=str(exc)[:160])
            verdict='matched' if actual==encoded else 'contradicted'
            self.event('checked',index=index,status=verdict,observed=observed,expected=target)
            if verdict!='matched':self.stop('contradicted','prediction_mismatch',executed,matched,index,expected=target,observed=observed)
            matched+=1
        self.stop('matched','probe_complete' if self.mode=='d' else 'plan_complete',executed,matched)

    def single(self,command,extract,expected):
        return self.run([command],extract,[expected])

    def batch(self,commands,extract,expected):
        return self.run(commands,extract,expected)
