"""Qualification and recordings for research Batch 12."""
from collections import deque
from itertools import combinations
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q008","q017","q027","q037","q047","q057","q067","q077","q087","q097"]
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
def cycle_plan(cur,target,n,left,right):
 r=(target-cur)%n;l=(cur-target)%n;return ([(right,{})]*r,target) if r<=l else ([(left,{})]*l,target)
def plans_q008(m):
 out=[]
 for l in m.LEVELS:
  p=[];cur=0
  for i,(s,t) in enumerate(zip(l["start"],l["target"])):
   z,cur=cycle_plan(cur,i,len(l["start"]),1,2);p+=z;d=(t-s)%l["mod"]
   if d:p += [(3,{})]+[(5,{})]*d+[(3,{})]
  out.append(p+[(6,{})])
 return out
def plans_q017(m):return [[(1,{})]+[(5,{})]*l["target"]+[(6,{})] for l in m.LEVELS]
def plans_q027(m):return [[(1,{})]*((l["target"]-l["role"])%l["count"])+[(5,{})] for l in m.LEVELS]
def plans_q037(m):
 return [[(2,{})]*(max(0,l["target"]-l["start"]))+[(3,{})]*(max(0,l["start"]-l["target"]))+[(6,{})] for l in m.LEVELS]
def plans_q047(m):
 out=[]
 for l in m.LEVELS:
  target=l["candidates"][l["target"]];best=None
  for size in range(1,len(l["costs"])+1):
   for bits in combinations(range(len(l["costs"])),size):
    cost=sum(l["costs"][b] for b in bits)
    if cost>l["budget"]:continue
    if all(i==l["target"] or any(((target>>b)&1)!=((v>>b)&1) for b in bits) for i,v in enumerate(l["candidates"])):
     candidate=(cost,len(bits),bits)
     if best is None or candidate<best:best=candidate
  assert best is not None
  p=[];cur=0
  for b in best[2]:z,cur=cycle_plan(cur,b,len(l["costs"]),1,2);p+=z+[(5,{})]
  z,_=cycle_plan(0,l["target"],len(l["candidates"]),3,4);out.append(p+z+[(6,{})])
 return out
def plans_q057(m):
 out=[]
 for l in m.LEVELS:
  p=[];x=y=0
  for tx,ty in sorted(map(tuple,l["target"]),key=lambda z:(z[1],z[0])):
   p += [(2,{})]*(ty-y) if ty>=y else [(1,{})]*(y-ty);y=ty
   p += [(4,{})]*(tx-x) if tx>=x else [(3,{})]*(x-tx);x=tx;p.append((5,{}))
  out.append(p+[(6,{})])
 return out
def plans_q067(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,r in enumerate(l["rotations"]):
   if i:p.append((2,{}))
   p += [(4,{})]*r if r<=2 else [(3,{})]*(4-r)
  out.append(p+[(6,{})])
 return out
def plans_q077(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   v,aa,ab=s;yield(1,{}),((v+l["a"][min(aa,len(l["a"])-1)])%l["mod"],min(aa+1,len(l["a"])-1),ab);yield(2,{}),((v+l["b"][min(ab,len(l["b"])-1)])%l["mod"],aa,min(ab+1,len(l["b"])-1))
  p=bfs((l["start"],0,0),lambda s:s[0]==l["target"],ex);assert len(p)<20;out.append(p+[(6,{})])
 return out
def plans_q087(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   pa,pb,ca,sel=s;pos=[pa,pb];cap=[ca,1-ca]
   for a in (1,2):
    q=pos.copy();d=l["steps"][cap[sel]]*(-1 if a==1 else 1);n=q[sel]+d
    if 0<=n<=m.LIMIT:q[sel]=n
    yield(a,{}),(q[0],q[1],ca,sel)
   yield(3,{}),(pa,pb,ca,0);yield(4,{}),(pa,pb,ca,1);yield(5,{}),(pa,pb,1-ca,sel)
  p=bfs((l["start"][0],l["start"][1],0,0),lambda s:list(s[:2])==l["dest"],ex);assert len(p)<32;out.append(p+[(6,{})])
 return out
def plans_q097(m):
 out=[]
 for l in m.LEVELS:
  p=[];cur=0
  for target in l["plan"]:z,cur=cycle_plan(cur,target,len(l["recipes"]),3,4);p+=z+[(5,{})]
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES}
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
def test_batch12_plans_and_losses():qualify()
def test_batch12_fuzz():
 rng=random.Random(12121)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch12_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==0).mean()<.1
 assert len(sig)==10
def test_batch12_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch12-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
