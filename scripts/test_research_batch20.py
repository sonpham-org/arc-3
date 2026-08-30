"""Qualification and recordings for research Batch 20."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q201","q232","q263","q294","q325","q356","q387","q418","q449","q480"]
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
def plans_q201(m):
 out=[]
 for l in m.LEVELS:
  v=tuple(l["start"]);p=0
  for a in l["plan"]:v,p=m.advance(v,p,a,l["rates"])
  target=v
  def ex(s):
   for a in (1,2,5):yield(a,{}),m.advance(s[0],s[1],a,l["rates"])
  out.append(bfs((tuple(l["start"]),0),lambda s:s[0]==target,ex)+[(6,{})])
 return out
def plans_q232(m):return [[(1,{})]*l["probes"]+[(5,{}),(l["rule"]+1,{})] for l in m.LEVELS]
def plans_q263(m):return [[(1,{}),(2,{})]+[(4,{})]*l["model"]+[(5,{})] for l in m.LEVELS]
def plans_q294(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  def ex(s):
   vals,cursor,tick,outer=s;nxt=(cursor+1)%3
   for a in (1,2,3,5):
    v=list(vals);c=cursor
    if a==1:
     if v[c]==0:continue
     v[c]-=1;v[nxt]+=1
    elif a==2:
     if v[nxt]==0:continue
     v[nxt]-=1;v[c]+=1
    elif a==3:c=nxt
    t=tick+1;o=outer
    if t==l["cycle"]:t=0;o=(o+1)%l["outer"]
    yield(a,{}),(tuple(v),c,t,o)
  goal=lambda s:s[0]==tuple(l["target"]) and s[3]==l["phase"]
  try:p=bfs((tuple(l["start"]),0,0,0),goal,ex)
  except AssertionError as exc:raise AssertionError(f"q294 authored level {i+1} is unsolved") from exc
  out.append(p+[(6,{})])
 return out
def plans_q325(m):
 out=[]
 for l in m.LEVELS:
  n=l["n"];need=0;rot=0
  for a in l["plan"]:need|=m.rotate(l["masks"][a-1],rot,n);rot=(rot+1)%n
  def ex(s):
   seen,used,r=s
   if used<l["budget"]:
    for a,mask in enumerate(l["masks"],1):yield(a,{}),(seen|m.rotate(mask,r,n),used+1,(r+1)%n)
   yield(5,{}),(seen,used,(r+1)%n)
  out.append(bfs((0,0,0),lambda s:(s[0]&need)==need,ex)+[(6,{})])
 return out
def plans_q356(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,a in enumerate(l["target"]):p.append((a,{}));p.append((4,{}))
  out.append(p+[(5,{}),(5,{}),(6,{})])
 return out
def plans_q387(m):
 out=[]
 for l in m.LEVELS:
  p=[];stored=0
  for a,b in l["pairs"]:
   if stored==l["capacity"]:p.append((5,{}));stored=0
   p += [(a,{}),(3,{}),(b,{}),(3,{})];stored+=1
  if stored:p.append((5,{}))
  out.append(p+[(6,{})])
 return out
def plans_q418(m):
 out=[]
 for l in m.LEVELS:
  sealed=l["seal"];p=[(5,{})] if sealed else []
  p += [(m.expected(l,i,sealed),{}) for i in range(len(l["route"]))];out.append(p)
 return out
def plans_q449(m):
 out=[]
 for l in m.LEVELS:
  perm=list(range(4))
  for a in l["ops"]:perm=m.transform(perm,a)
  pos=perm.index(l["target"]);out.append([(a,{}) for a in l["ops"]]+[(3,{})]*pos+[(5,{})]+[(4,{})]*len(l["ops"])+[(6,{})])
 return out
def plans_q480(m):
 out=[]
 for l in m.LEVELS:
  p=[];cursor=0;phase=[0,0]
  for node in range(len(l["deps"])):
   p += [(2,{})]*((node-cursor)%len(l["deps"]));cursor=node
   p += [(3,{})]*((-phase[0])%l["mods"][0]);phase[0]=0
   p += [(4,{})]*((-phase[1])%l["mods"][1]);phase[1]=0
   p.append((5,{}));phase=[1%l["mods"][0],1%l["mods"][1]]
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q201":[(6,{})],"q232":[(5,{})],"q263":[(5,{})],"q294":[(6,{})],"q325":[(6,{})],"q356":[(6,{})],"q387":[(6,{})],"q418":[(2,{})],"q449":[(6,{})],"q480":[(6,{})]}
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
def test_batch20_plans_and_losses():qualify()
def test_batch20_fuzz():
 rng=random.Random(20202)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch20_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch20_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch20-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
