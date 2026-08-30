"""Qualification and recordings for research Batch 19."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q110","q119","q129","q139","q149","q159","q169","q179","q189","q199"]
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
def plans_q110(m):
 out=[]
 for l in m.LEVELS:
  mod=l["mod"]
  def ex(s):
   player,phase=s
   for i in range(2):yield(i+1,{}),((l["bases"][i]+l["vel"][i]*phase+l["offset"][i])%mod,(phase+1)%mod)
   yield(5,{}),(player,(phase+1)%mod)
  out.append(bfs((l["start"],0),lambda s:s[0]==l["target"],ex)+[(6,{})])
 return out
def plans_q119(m):
 out=[]
 for l in m.LEVELS:
  p=[(5,{})]*len(l["demo"])
  for target in l["demo"]:
   choices=[a for a in range(1,5) if m.transfer(a,l["flow"],l["skin"])==target];assert len(choices)==1;p.append((choices[0],{}))
  out.append(p+[(6,{})])
 return out
def plans_q129(m):
 out=[]
 for l in m.LEVELS:
  decoy=4 if l["target"]!=4 else 3;out.append([(decoy,{})]*l["lessons"]+[(5,{}),(l["target"],{})])
 return out
def plans_q139(m):
 out=[]
 for l in m.LEVELS:
  p=[];content=0;phase=[0,0]
  for c,a,b in l["messages"]:
   z,content=cyc(content,c,3,3,4);p+=z
   p += [(1,{})]*((a-phase[0])%l["mods"][0]);phase[0]=a
   p += [(2,{})]*((b-phase[1])%l["mods"][1]);phase[1]=b;p.append((5,{}))
  out.append(p)
 return out
def plans_q149(m):
 out=[]
 for l in m.LEVELS:
  full=(1<<l["n"])-1;masks=[full-sum(1<<i for i in cut) for cut in l["cuts"]]
  def ex(s):
   for i,mask in enumerate(masks):yield(i+1,{}),s&mask
  out.append(bfs(full,lambda s:s==(1<<l["target"]),ex)+[(5,{})])
 return out
def plans_q159(m):return [[(l["local"][i-1],{}) for i in m.BASE]+[(l["global"][i-1],{}) for i in m.BASE] for l in m.LEVELS]
def plans_q169(m):return [[((2 if l["hub"] else 1),{})]*l["reveal"]+[(l["target"]+2,{})] for l in m.LEVELS]
def plans_q179(m):
 out=[]
 for l in m.LEVELS:
  p=[];vectors=list(l["initial"]);cursor=0
  for phase,target in enumerate(l["targets"]):
   for i in range(len(vectors)):
    while cursor!=i:p.append((4,{}));cursor=(cursor+1)%len(vectors)
    z,vectors[i]=cyc(vectors[i],target,4,2,1);p+=z
   p.append((5,{}))
   if phase<len(l["targets"])-1:vectors=[(v+1+(i%2))%4 for i,v in enumerate(vectors)]
  out.append(p)
 return out
def plans_q189(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   r,p,d,salv=s
   if p<l["work"] and r>=1:yield(1,{}),(r-1,p+1,d+1,salv)
   if p<l["work"] and r>=2:yield(2,{}),(r-2,p+1,d,salv)
   if r>=1:yield(3,{}),(r-1,p,max(0,d-1),salv)
   if l["salvage"] and not salv:yield(4,{}),(r+2,p,d+1,True)
  goal=lambda s:s[1]==l["work"] and s[0]>=l["need"] and s[2]<=l["max_damage"]
  out.append(bfs((l["initial"],0,0,False),goal,ex)+[(5,{})])
 return out
def advance(pending,completed,action,delays,target):
 p=list(pending);c=list(completed)
 if action in (1,2,3):p.append((action,delays[action-1]))
 n=[]
 for a,t in p:
  if t<=1:c.append(a)
  else:n.append((a,t-1))
 if tuple(c)!=target[:len(c)] or len(n)>8:return None
 return tuple(n),tuple(c)
def plans_q199(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  target=tuple(l["target"])
  def ex(s):
   for a in (1,2,3,5):
    n=advance(s[0],s[1],a,l["delays"],target)
    if n is not None:yield(a,{}),n
  try:p=bfs(((),()),lambda s:not s[0] and s[1]==target,ex)
  except AssertionError as exc:raise AssertionError(f"q199 authored level {i+1} is unsolved") from exc
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q110":[(6,{})],"q119":[(1,{})],"q129":[(5,{})],"q139":[(5,{})],"q149":[(5,{})],"q159":[(2,{})],"q169":[(3,{})],"q179":[(5,{})],"q189":[(5,{})],"q199":[(6,{})]}
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
def test_batch19_plans_and_losses():qualify()
def test_batch19_fuzz():
 rng=random.Random(19191)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch19_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch19_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch19-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
