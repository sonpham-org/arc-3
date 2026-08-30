"""Qualification and recordings for research Batch 24."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q222","q253","q284","q315","q346","q377","q408","q439","q470","q481"]
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
def plans_q222(m):
 out=[]
 for l in m.LEVELS:
  v=tuple(l["start"]);p=0
  for a in l["plan"]:v,p=m.advance(v,p,a,l["rates"])
  def ex(s):
   for a in (1,2,3):yield(a,{}),m.advance(s[0],s[1],a,l["rates"])
  out.append([(4,{}),(5,{})]+bfs((tuple(l["start"]),0),lambda s:s[0]==v,ex)+[(6,{})])
 return out
def plans_q253(m):return [[(1,{}),(2,{}),(3,{})]+[(5,{})]*l["rule"]+[(6,{})] for l in m.LEVELS]
def plans_q284(m):
 out=[]
 for l in m.LEVELS:
  p=[(1,{}),(2,{})]+[(4,{})]*l["model"];phase=2
  while phase!=l["window"]:p.append((5,{}));phase=(phase+3)%l["period"]
  out.append(p+[(6,{})])
 return out
def plans_q315(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  def ex(s):
   vals,cursor,diff=s;nxt=(cursor+1)%3;yield(3,{}),(vals,nxt,diff)
   if vals[cursor]>0 and diff<8:v=list(vals);v[cursor]-=1;v[nxt]+=1;yield(1,{}),(tuple(v),cursor,diff+1)
   if vals[nxt]>0 and diff>-8:v=list(vals);v[nxt]-=1;v[cursor]+=1;yield(2,{}),(tuple(v),cursor,diff-1)
  try:p=bfs((tuple(l["start"]),0,0),lambda s:s[0]==tuple(l["target"]) and abs(s[2])<=1,ex)
  except AssertionError as exc:raise AssertionError(f"q315 authored level {i+1} is unsolved") from exc
  out.append(p+[(6,{})])
 return out
def plans_q346(m):
 out=[]
 for l in m.LEVELS:
  masks=[list(x) for x in l["masks"]];need=0;c=1
  for a in l["plan"]:need|=masks[c][(a-1)%2];c=1-c
  def ex(s):
   seen,used,controller,marked=s
   if not marked:yield(5,{}),(seen,used,1-controller,True)
   elif used<l["budget"]:
    for a in range(1,5):yield(a,{}),(seen|masks[controller][(a-1)%2],used+1,controller,False)
  out.append(bfs((0,0,0,False),lambda s:(s[0]&need)==need,ex)+[(6,{})])
 return out
def plans_q377(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for a in l["tool"]:p += [(a,{}),(4,{})]
  p.append((5,{}));p += [(l["map"].index(a)+1,{}) for a in m.BASE];out.append(p+[(6,{})])
 return out
def plans_q408(m):
 out=[]
 for l in m.LEVELS:
  p=[(5,{})]
  for a,b in l["pairs"]:p += [(((a-1+l["fault"])%2)+1,{}),(3,{}),(((b-1+l["fault"])%2)+1,{}),(3,{})]
  out.append(p+[(6,{})])
 return out
def plans_q439(m):
 out=[]
 for l in m.LEVELS:
  p=[(m.expected(l,i),{}) for i in range(len(l["route"]))];phase=[len(l["route"])%l["mods"][0],len(l["route"])%l["mods"][1]]
  p += [(4,{})]*((l["target"][0]-phase[0])%l["mods"][0]);p += [(5,{})]*((l["target"][1]-phase[1])%l["mods"][1]);out.append(p+[(6,{})])
 return out
def plans_q470(m):
 out=[]
 for l in m.LEVELS:
  perm=[1,2,3]
  for a in l["ops"]:perm=m.transform(perm,a)
  pos=perm.index(l["helper"]);out.append([(a,{}) for a in l["ops"]]+[(3,{})]*pos+[(5,{})]+[(4,{})]*len(l["ops"])+[(6,{})])
 return out
def plans_q481(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  n=len(l["deps"])
  def ex(s):
   done,cursor,completed=s;rewired=completed>=l["rewire"];yield(1,{}),(done,(cursor-1)%n,completed);yield(2,{}),(done,(cursor+(2 if rewired else 1))%n,completed)
   if not done&(1<<cursor) and all(done&(1<<d) for d in l["deps"][cursor]):yield(5,{}),(done|(1<<cursor),cursor,completed+1)
  try:p=bfs((0,0,0),lambda s:s[0]==(1<<n)-1,ex)
  except AssertionError as exc:raise AssertionError(f"q481 authored level {i+1} is unsolved") from exc
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS.update({"q253":[(6,{})],"q284":[(6,{})],"q315":[(6,{})],"q346":[(6,{})],"q377":[(5,{})],"q408":[(1,{})],"q439":[(6,{})],"q470":[(6,{})],"q481":[(6,{})]})
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
def test_batch24_plans_and_losses():qualify()
def test_batch24_fuzz():
 rng=random.Random(24242)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch24_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch24_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch24-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
