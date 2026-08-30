"""Qualification and fuzz coverage for research Batch 38."""
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1]
CODES=["q213","q244","q275","q306","q337","q368","q399","q430","q461","q493"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def plans_q213(m):return [[(a,{}) for a in x["plan"]]+[(6,{})] for x in m.LEVELS]
def plans_q244(m):return [[(a,{}) for a in x["need"]]+[(4,{})]*x["role"]+[(5,{})]*x["key"]+[(6,{})] for x in m.LEVELS]
def plans_q275(m):return [[(a,{}) for a in x["plan"]]+[(5,{})]*x["model"]+[(6,{})] for x in m.LEVELS]
def plans_q306(m):return [[(a,{}) for a in x["plan"]]+[(5,{}),(5,{}),(6,{})] for x in m.LEVELS]
def plans_q337(m):return [[y for a in x["solution"] for y in ((a,{}),(4,{}),(5,{}))]+[(6,{})] for x in m.LEVELS]
def plans_q368(m):
 out=[]
 for x in m.LEVELS:
  timer=latch=0;p=[]
  for component,target_timer,target_latch in x["recipe"]:
   if latch!=target_latch:p.append((6,{}));latch=1-latch
   p += [(5,{})]*((target_timer-timer)%x["mod"])+[(component,{}),(4,{})]
   timer=(target_timer+2*component+1)%x["mod"];latch^=component%2
  out.append(p)
 return out
def plans_q399(m):return [[(a,{}) for a in x["flow"]]+[(5,{})]*x["target"]+[(6,{})] for x in m.LEVELS]
def plans_q430(m):return [[(3,{}),(4,{})]+[(1,{})]*(x["boundary"]-1)+[(3,{}),(4,{}),(2,{})]+[(5,{})]*x["new"]+[(6,{})] for x in m.LEVELS]
def plans_q461(m):return [[(a,{}) for a in x["ops"]]+[(5,{})]*m.result(x)[1]+[(6,{})] for x in m.LEVELS]
def plans_q493(m):
 out=[]
 for x in m.LEVELS:
  n=len(x["deps"]);cursor=0;built=set();p=[]
  for target in x["order"]:
   p += [(5,{})]*((target-cursor)%n);cursor=target
   p += [(((brace-len(built))%3)+1,{}) for brace in x["deps"][target][1]]+[(4,{})];built.add(target)
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS["q368"]=[(4,{})]
def valid(r):
 a=r.frame[-1];assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def qualify(write=False):
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[];plans=PLANS[c](m)
  for i,p in enumerate(plans):
   assert g.level_index==i,(c,i,g.level_index)
   for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
   levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
  assert r.state==GameState.WIN,(c,r.state);win={"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels}
  g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
  assert r.state==GameState.GAME_OVER,(c,r.state);loss={"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":dig(r)}
  if write:
   d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(c,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")
def test_batch38_plans_and_losses():qualify()
def test_batch38_fuzz():
 rng=random.Random(38383)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch38_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch38_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch38-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  m=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/m["artifacts"]["source"]).read_bytes()).hexdigest()==m["artifacts"]["source_sha256"]
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
