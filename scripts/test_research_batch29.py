"""Qualification and fuzz coverage for research Batch 29."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q204","q235","q266","q297","q328","q359","q390","q421","q452","q484"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def bfs(start,goal,expand):
 q=deque([start]);par={start:None};act={}
 while q:
  s=q.popleft()
  if goal(s):
   out=[]
   while par[s] is not None:out.append(act[s]);s=par[s]
   return out[::-1]
  for a,n in expand(s):
   if n not in par:par[n]=s;act[n]=a;q.append(n)
 raise AssertionError("unsolved")
def plans_q204(m):return [[(a,{}) for a in x["plan"]]+[(6,{})] for x in m.LEVELS]
def plans_q235(m):return [[(1,{}),(2,{})]+[(3,{})]*x["rule"]+[(5,{})] for x in m.LEVELS]
def plans_q266(m):return [[(a,{}) for a in x["need"]]+[(4,{})]*x["model"]+[(5,{})] for x in m.LEVELS]
def plans_q297(m):
 out=[]
 for x in m.LEVELS:
  def ex(s):
   v,c,store=s;n=(c+1)%3
   if v[c] and store<x["cap"]:a=list(v);a[c]-=1;yield 1,(tuple(a),c,store+1)
   if store:a=list(v);a[n]+=1;yield 2,(tuple(a),c,store-1)
   if not store:yield 3,(v,n,0)
  p=bfs((tuple(x["start"]),0,0),lambda s:s[0]==tuple(x["target"]) and not s[2],ex);out.append([(a,{}) for a in p]+[(6,{})])
 return out
def plans_q328(m):return [[(a,{}) for a in x["solution"]]+[(5,{}),(5,{}),(6,{})] for x in m.LEVELS]
def plans_q359(m):
 out=[]
 for x in m.LEVELS:
  p=[]
  for mod in x["modules"]:p += [(a,{}) for a in mod]+[(4,{})]
  out.append(p+[(5,{}),(6,{})])
 return out
def plans_q390(m):
 out=[]
 for x in m.LEVELS:
  p=[(1,{})]+[(3,{})]*((-1)%x["mods"][0])+[(4,{})]*((-2)%x["mods"][1])+[(2,{}),(1,{})]+[(5,{})]*(x["clues"][0]^x["clues"][1])+[(6,{})];out.append(p)
 return out
def plans_q421(m):
 out=[]
 for x in m.LEVELS:
  cursor=x["boundary"]%3;k=next(i for i in range(3) if (cursor+2*i)%3==x["spot"]);out.append([(1,{})]*x["boundary"]+[(4,{})]*k+[(2,{})]+[(3,{})]*x["rule"]+[(6,{})])
 return out
def plans_q452(m):
 out=[]
 for x in m.LEVELS:
  p=(0,1,2)
  for z in x["ops"]:p=m.transform(p,z)
  out.append([(a,{}) for a in x["ops"]]+[(3,{})]*p.index(x["ancestor"])+[(6,{})])
 return out
def plans_q484(m):
 out=[]
 for x in m.LEVELS:
  n=len(x["deps"]);cursor=0;p=[]
  for target in x["order"]:
   k=(cursor-target)%n;p += [(1,{})]*k;cursor=(cursor-k)%n;p.append((5,{}))
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS["q266"]=[(5,{})]
def valid(r):a=r.frame[-1];assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def qualify(write=False):
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[];plans=PLANS[c](m)
  for i,p in enumerate(plans):
   assert g.level_index==i
   for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
   levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
  assert r.state==GameState.WIN,(c,r.state);win={"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels};g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
  assert r.state==GameState.GAME_OVER,(c,r.state);loss={"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":dig(r)}
  if write:d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(c,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")
def test_batch29_plans_and_losses():qualify()
def test_batch29_fuzz():
 rng=random.Random(29292)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch29_visuals():
 sig=set()
 for c in CODES:m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch29_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch29-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  m=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/m["artifacts"]["source"]).read_bytes()).hexdigest()==m["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
