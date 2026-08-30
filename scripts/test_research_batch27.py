"""Qualification, recordings, fuzzing, and artifacts for research Batch 27."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q203","q234","q265","q296","q327","q358","q389","q420","q451","q483"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def bfs(start,goal,expand):
 q=deque([start]);parent={start:None};action={}
 while q:
  s=q.popleft()
  if goal(s):
   out=[]
   while parent[s] is not None:out.append(action[s]);s=parent[s]
   return out[::-1]
  for a,n in expand(s):
   if n not in parent:parent[n]=s;action[n]=a;q.append(n)
 raise AssertionError("unsolved authored level")
def plans_q203(m):return [[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q234(m):return [[(1,{}),(2,{})]+[(3,{})]*l["rule"]+[(5,{})] for l in m.LEVELS]
def plans_q265(m):return [[(1,{}),(2,{})]+[(3,{})]*l["model"]+[(5,{})] for l in m.LEVELS]
def plans_q296(m):return [[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q327(m):
 out=[]
 for l in m.LEVELS:
  def expand(s):
   seen,used,count=s
   if count<l["budget"]:
    for i,mask in enumerate(l["masks"]):
     if not used&(1<<i):yield i+1,(seen|mask,used|(1<<i),count+1)
  chosen=bfs((0,0,0),lambda s:s[0]&l["need"]==l["need"],expand);p=[];stored=0
  for a in chosen:
   p.append((a,{}));stored+=1
   if stored==l["capacity"]:p.append((5,{}));stored=0
  if stored:p.append((5,{}))
  out.append(p+[(6,{})])
 return out
def plans_q358(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for module in l["modules"]:p += [(a,{}) for a in module]+[(4,{})]
  out.append(p+[(6,{})])
 return out
def plans_q389(m):
 out=[]
 for l in m.LEVELS:out.append([(1,{}),(2,{}),(3,{}),(1,{}),(2,{}),(4,{}),(4,{})]+[(5,{})]*(l["clues"][0]^l["clues"][1])+[(6,{})])
 return out
def plans_q420(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  phase=(l["boundary"]%l["mods"][0],(2*l["boundary"])%l["mods"][1])
  def expand(s):yield 1,((s[0]+1)%l["mods"][0],s[1]);yield 2,(s[0],(s[1]+1)%l["mods"][1])
  try:p=bfs(phase,lambda s:s==(0,0),expand)
  except AssertionError as e:raise AssertionError(f"q420 level {i+1} unsolved") from e
  out.append([(4,{})]*l["boundary"]+[(a,{}) for a in p]+[(3,{})]+[(5,{})]*l["rule"]+[(6,{})])
 return out
def plans_q451(m):
 out=[]
 for l in m.LEVELS:
  p=(0,1,2)
  for z in l["ops"]:p=m.transform(p,z)
  target=p.index(l["ancestor"]);steps=next(k for k in range(3) if (2*k)%3==target);out.append([(a,{}) for a in l["ops"]]+[(3,{})]*steps+[(6,{})])
 return out
def plans_q483(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  n=len(l["deps"]);goal=(1<<n)-1
  def expand(s):
   done,cursor,completed=s;yield 1,(done,(cursor-1)%n,completed);yield 2,(done,(cursor+(2 if completed>=l["rewire"] else 1))%n,completed)
   if not done&(1<<cursor) and all(done&(1<<d) for d in l["deps"][cursor]):yield 5,(done|(1<<cursor),cursor,completed+1)
  try:p=bfs((0,0,0),lambda s:s[0]==goal,expand)
  except AssertionError as e:raise AssertionError(f"q483 level {i+1} unsolved") from e
  out.append([(a,{}) for a in p]+[(3,{})]*m.parity(l)+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS.update({"q234":[(5,{})],"q265":[(5,{})]})
def valid(r):a=r.frame[-1];assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def digest(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def win(c,m,plans):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[]
 for i,p in enumerate(plans):
  assert g.level_index==i,(c,i,g.level_index)
  for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
  levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":digest(r)})
 assert r.state==GameState.WIN,(c,r.state);return{"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels}
def lose(c,m):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
 for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
 assert r.state==GameState.GAME_OVER,(c,r.state);return{"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":digest(r)}
def qualify(write=False):
 for c in CODES:
  m=load(c);p=PLANS[c](m);w=win(c,m,p);l=lose(c,m)
  if write:
   d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(w,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(l,indent=2)+"\n")
  print(c,"levels",len(p),"actions",sum(map(len,p)),"qualified")
def test_batch27_plans_and_losses():qualify()
def test_batch27_fuzz():
 rng=random.Random(27272)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch27_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch27_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch27-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
