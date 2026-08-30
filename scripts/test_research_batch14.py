"""Qualification and recordings for research Batch 14."""
from collections import deque
from itertools import combinations
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q010","q019","q029","q039","q049","q059","q069","q079","q089","q099"]
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
def cycle(cur,target,n,left,right):
 r=(target-cur)%n;l=(cur-target)%n;return ([(right,{})]*r,target) if r<=l else ([(left,{})]*l,target)
def plans_q010(m):return [[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q019(m):return [[(l["rule"].index(a)+1,{}) for a in l["route"]]+[(5,{})] for l in m.LEVELS]
def plans_q029(m):
 out=[]
 for l in m.LEVELS:
  p=[];cur=0
  for t in sorted(set(range(l["count"]))-set(l["needed"])):z,cur=cycle(cur,t,l["count"],3,4);p+=z+[(5,{})]
  out.append(p+[(6,{})])
 return out
def plans_q039(m):
 out=[]
 for l in m.LEVELS:
  edges=list(map(tuple,l["edges"]))
  def ex(s):
   vals,c,r=s;yield(1,{}),(m.pair(vals,edges[c],r,1),c,r);yield(2,{}),(m.pair(vals,edges[c],r,-1),c,r);yield(3,{}),(vals,(c-1)%len(edges),r);yield(4,{}),(vals,(c+1)%len(edges),r);yield(5,{}),(vals,c,not r)
  p=bfs((tuple(l["start"]),0,False),lambda s:s[0]==tuple(l["target"]),ex);assert len(p)<50;out.append(p+[(6,{})])
 return out
def plans_q049(m):
 out=[]
 for l in m.LEVELS:
  t=l["candidates"][l["target"]];best=None
  for size in range(1,l["limit"]+1):
   for bits in combinations(range(l["bits"]),size):
    if all(i==l["target"] or any(((t>>b)&1)!=((v>>b)&1) for b in bits) for i,v in enumerate(l["candidates"])):best=bits;break
   if best is not None:break
  assert best is not None;p=[];cur=0
  for b in best:z,cur=cycle(cur,b,l["bits"],1,2);p+=z+[(5,{})]
  z,_=cycle(0,l["target"],len(l["candidates"]),3,4);out.append(p+z+[(6,{})])
 return out
def plans_q059(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,v in enumerate(l["target"]):
   if i:p.append((4,{}))
   p += [(1,{})]*((v-1)%3)
  p += [(5,{})]*l["tests"]+[(6,{})];out.append(p)
 return out
def plans_q069(m):return [[(l["mapping"].index(v)+1,{}) for v in l["outputs"]] for l in m.LEVELS]
def plans_q079(m):return [[(m.response(c,e),{}) for c,e in zip(l["commands"],l["exceptions"])] for l in m.LEVELS]
def plans_q089(m):
 out=[]
 for l in m.LEVELS:
  p=[];vehicles=list(range(l["count"]));passenger=0
  for _ in range(l["handoffs"]):i=vehicles.index(passenger);passenger=vehicles[(i+1)%len(vehicles)];p += [(3,{}),(5,{})]
  pos=vehicles.index(passenger);left=(pos-l["gate"])%l["count"];right=(l["gate"]-pos)%l["count"];p += [(1,{})]*left if left<=right else [(2,{})]*right;out.append(p+[(6,{})])
 return out
def plans_q099(m):
 out=[]
 for l in m.LEVELS:
  p=[];cur=0
  for t in l["path"]:z,cur=cycle(cur,t,l["nodes"],3,4);p+=z+[(5,{})]
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS["q019"]=[(5,{})];LOSS["q029"]=[(5,{})];LOSS["q069"]=[(2,{})];LOSS["q079"]=[(2,{})]
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
def test_batch14_plans_and_losses():qualify()
def test_batch14_fuzz():
 rng=random.Random(14141)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch14_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch14_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch14-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
