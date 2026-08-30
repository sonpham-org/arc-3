"""Qualification and recordings for research Batch 15."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q020","q030","q040","q050","q060","q070","q080","q090","q100","q106"]
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
 raise AssertionError("unsolved authored level")
def cyc(cur,target,n,left,right):
 r=(target-cur)%n;l=(cur-target)%n;return ([(right,{})]*r,target) if r<=l else ([(left,{})]*l,target)
def plans_q020(m):return [[(5,{})]+[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q030(m):return [[(1,{})]+[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q040(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,s in enumerate(l["target"]):
   p.append((1,{}))
   if s:p.append((5,{}))
   if i<len(l["target"])-1:p.append((4,{}))
  out.append(p+[(6,{})])
 return out
def plans_q050(m):
 out=[]
 for l in m.LEVELS:
  p=[];cur=0
  for i in l["solution"]:z,cur=cyc(cur,i,len(l["tiles"]),3,4);p+=z+[(5,{})]
  out.append(p+[(6,{})])
 return out
def plans_q060(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,c in enumerate(l["program"]):
   p += [(1,{})]*(c+1)
   if i<len(l["program"])-1:p.append((4,{}))
  out.append(p+[(5,{}),(6,{})])
 return out
def plans_q070(m):return [[(5,{})]+[(4,{})]*l["target"][0]+[(2,{})]*l["target"][1]+[(6,{})] for l in m.LEVELS]
def plans_q080(m):return [[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q090(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,t in enumerate(l["traits"]):
   p.append((1,{}))
   if not t:p.append((5,{}))
   if i<len(l["traits"])-1:p.append((4,{}))
  out.append(p+[(6,{})])
 return out
def plans_q100(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for t in l["params"]:
   z,_=cyc(0,t,4,1,2);p+=z+[(5,{})]
  out.append(p+[(6,{})])
 return out
def plans_q106(m):
 out=[]
 for level_index,l in enumerate(m.LEVELS):
  gravity=list(map(tuple,l["gravity"]));goal=tuple(l["goal"])
  def ex(pos):
   for a in range(1,5):yield(a,{}),m.advance(pos,a,gravity,goal)
  try:p=bfs(tuple(l["start"]),lambda s:s==goal,ex)
  except AssertionError as exc:raise AssertionError(f"q106 authored level {level_index+1} is unsolved") from exc
  assert len(p)<40;out.append(p)
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS["q106"]=[(1,{})]*40
def valid(r):g=r.frame[-1];assert g.shape==(64,64) and 0<=int(g.min())<=int(g.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def win(c,m,plans):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[]
 for i,p in enumerate(plans):
  assert g.level_index==i,(c,i,g.level_index)
  for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
  levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
 assert r.state==GameState.WIN,(c,r.state);return{"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels}
def lose(c,m):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
 for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
 assert r.state==GameState.GAME_OVER,(c,r.state);return{"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":dig(r)}
def qualify(write=False):
 for c in CODES:
  m=load(c);p=PLANS[c](m);w=win(c,m,p);l=lose(c,m)
  if write:
   d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(w,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(l,indent=2)+"\n")
  print(c,"levels",len(p),"actions",sum(map(len,p)),"qualified")
def test_batch15_plans_and_losses():qualify()
def test_batch15_fuzz():
 rng=random.Random(15151)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch15_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch15_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch15-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
