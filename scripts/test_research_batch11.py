"""Qualification and recordings for research Batch 11."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q007","q016","q026","q036","q046","q056","q066","q076","q086","q096"]
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
def plans_q007(m):
 out=[]
 for l in m.LEVELS:
  walls=set(l["walls"]);pat=l["guard"]
  def ex(s):
   pos,phase,health,watched=s
   for a in range(1,6):
    p=pos;ph=phase;h=health;w=watched
    if a==5:w=not w
    else:
     dx,dy=m.DIRS[a];z=(p[0]+dx,p[1]+dy);blocked=walls|({l["gate"]} if h else set())
     if 0<=z[0]<m.W and 0<=z[1]<m.H and z not in blocked and z!=pat[ph]:p=z
    if w:h=max(0,h-1)
    else:ph=(ph+1)%len(pat)
    if p!=pat[ph]:yield(a,{}),(p,ph,h,w)
  p=bfs((l["start"],0,l["decay"],False),lambda s:s[0]==l["goal"],ex);assert len(p)<50;out.append(p)
 return out
def plans_q016(m):return [[(a,{}) for a in l["route"]] for l in m.LEVELS]
def plans_q026(m):
 out=[]
 for l in m.LEVELS:
  s=l["target"];b=s%len(l["barriers"]);p=[];right=s%len(l["seeds"]);left=(-s)%len(l["seeds"]);a=4 if right<=left else 3;p += [(a,{})]*min(right,left);right=b%len(l["barriers"]);left=(-b)%len(l["barriers"]);a=2 if right<=left else 1;p += [(a,{})]*min(right,left)+[(5,{}),(6,{})];out.append(p)
 return out
def plans_q036(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["ops"])
  def ex(s):
   vals,c=s;yield(3,{}),(vals,(c-1)%n);yield(4,{}),(vals,(c+1)%n);yield(5,{}),(m.flow(vals,l["ops"][c]),c)
  out.append(bfs((tuple(l["start"]),0),lambda s:s[0]==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q046(m):
 out=[]
 for l in m.LEVELS:
  i=l["target"];right=i%l["rules"];left=(-i)%l["rules"];a=2 if right<=left else 1;out.append([(5,{})]+[(a,{})]*min(right,left)+[(6,{})])
 return out
def plans_q056(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,v in enumerate(l["target"]):p.append((v+1,{}));p += [] if i==len(l["target"])-1 else [(4,{})]
  out.append(p+[(6,{})])
 return out
def plans_q066(m):return [[(a,{}) for a in l["signals"]] for l in m.LEVELS]
def plans_q076(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   v,t=s;yield(1,{}),(v,min(2,t+1));yield(2,{}),(v,max(0,t-1));yield(3,{}),(m.apply(v,t,3,l["mod"]),t);yield(4,{}),(m.apply(v,t,4,l["mod"]),t)
  out.append(bfs((l["start"],1),lambda s:s[0]==l["target"],ex)+[(6,{})])
 return out
def plans_q086(m):
 out=[]
 for l in m.LEVELS:
  k=l["tests"].index(l["original"])+1;i=l["original"];right=i%l["count"];left=(-i)%l["count"];a=4 if right<=left else 3;out.append([(5,{})]*k+[(a,{})]*min(right,left)+[(6,{})])
 return out
def plans_q096(m):
 out=[]
 for l in m.LEVELS:
  cache=set();cursor=1;p=[]
  for t in l["tasks"]:
   if t in cache:p.append((6,{}));continue
   right=(t-cursor)%4;left=(cursor-t)%4;a=4 if right<=left else 3;p += [(a,{})]*min(right,left)+[(5,{})];cursor=t;cache.add(t)
  out.append(p)
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q007":[(6,{})],"q016":[(1,{})],"q026":[(6,{})],"q036":[(6,{})],"q046":[(6,{})],"q056":[(6,{})],"q066":[(2,{})],"q076":[(6,{})],"q086":[(6,{})],"q096":[(6,{})]}
def valid(r):g=r.frame[-1];assert g.shape==(64,64) and 0<=int(g.min())<=int(g.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def win(c,m,plans):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[]
 for i,p in enumerate(plans):
  assert g.level_index==i
  for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
  levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
 assert r.state==GameState.WIN;return{"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels}
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
def test_batch11_plans_and_losses():qualify()
def test_batch11_fuzz():
 rng=random.Random(9111)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch11_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch11_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch11-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
