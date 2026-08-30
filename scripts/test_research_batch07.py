"""Qualification and recordings for research Batch 07."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q005","q014","q024","q034","q044","q054","q064","q074","q084","q094"]
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
def plans_q005(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["start"])
  def ex(s):
   vals,lit,c,t=s;yield(3,{}),(vals,lit,(c-1)%n,t);yield(4,{}),(vals,lit,(c+1)%n,t);z=set(lit);z.symmetric_difference_update({c});yield(5,{}),(vals,frozenset(z),c,t)
   if t:yield(6,{}),(m.evolve(vals,lit),lit,c,t-1)
  out.append(bfs((tuple(l["start"]),frozenset(),0,l["ticks"]),lambda s:s[0]==tuple(l["target"]) and s[3]==0,ex)+[(1,{})])
 return out
def plans_q014(m):return [[(m.result(l["rule"],g),{}) for g in l["groups"]] for l in m.LEVELS]
def plans_q024(m):
 out=[]
 for l in m.LEVELS:
  pc=hc=0;p=[]
  for x in l["required"]:
   right=(x-pc)%len(l["probes"]);left=(pc-x)%len(l["probes"]);a=4 if right<=left else 3;p += [(a,{})]*min(right,left)+[(5,{})];pc=x
  right=(l["target"]-hc)%4;left=(hc-l["target"])%4;a=2 if right<=left else 1;p += [(a,{})]*min(right,left)+[(6,{})];out.append(p)
 return out
def plans_q034(m):
 out=[]
 for l in m.LEVELS:
  i=l["areas"].index(l["target"]);right=i%len(l["areas"]);left=(-i)%len(l["areas"]);a=4 if right<=left else 3;out.append([(a,{})]*min(right,left)+[(5,{})]*l["turns"]+[(6,{})])
 return out
def plans_q044(m):
 out=[]
 for l in m.LEVELS:
  c=0;p=[]
  for i in l["need"]:
   right=(i-c)%len(l["regions"]);left=(c-i)%len(l["regions"]);a=4 if right<=left else 3;p += [(a,{})]*min(right,left)+[(5,{})];c=i
  p.append((6,{}));c=0
  for i in range(len(l["need"])):
   p.append((6,{}))
   if i<len(l["need"])-1:p.append((4,{}))
  out.append(p)
 return out
def plans_q054(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,(a,b) in enumerate(zip(l["start"],l["target"])):
   p += [(5,{})]*(b-a)
   if i<len(l["start"])-1:p.append((4,{}))
  out.append(p+[(6,{})])
 return out
def plans_q064(m):return [[(l["mapping"][x],{}) for x in l["reports"]] for l in m.LEVELS]
def plans_q074(m):return [[(5,{})]+[((x-1-l["rot"])%4+1,{}) for x in l["route"]] for l in m.LEVELS]
def plans_q084(m):
 out=[]
 for l in m.LEVELS:
  walls=set(l["walls"])
  def ex(s):
   pos,active=s;pos=list(pos)
   for a,(dx,dy) in m.DIRS.items():
    p=pos[active];n=(p[0]+dx,p[1]+dy);np=list(pos);na=active
    if n==pos[1-active]:na=1-active
    elif 0<=n[0]<m.W and 0<=n[1]<m.H and n not in walls:np[active]=n
    yield(a,{}),(tuple(np),na)
  p=bfs((tuple(l["pos"]),0),lambda s:list(s[0])==l["goals"],ex);assert len(p)<40;out.append(p+[(6,{})])
 return out
def plans_q094(m):
 out=[]
 for l in m.LEVELS:
  c=0;p=[]
  for i in range(l["target"]+1):
   right=(i-c)%len(l["parents"]);left=(c-i)%len(l["parents"]);a=4 if right<=left else 3;p += [(a,{})]*min(right,left)+[(5,{})];c=i
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q005":[(1,{})],"q014":[(2,{})],"q024":[(6,{})],"q034":[(6,{})],"q044":[(5,{}),(6,{}),(6,{})],"q054":[(6,{})],"q064":[(1,{})],"q074":[(1,{})],"q084":[(6,{})],"q094":[(6,{})]}
def valid(r):g=r.frame[-1];assert g.shape==(64,64) and 0<=int(g.min())<=int(g.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def win(c,m,p):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[]
 for i,plan in enumerate(p):
  assert g.level_index==i
  for a,d in plan:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
  levels.append({"level":i+1,"actions":[[a] for a,_ in plan],"post_transition_frame_sha256":dig(r)})
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
def test_batch07_plans_and_losses():qualify()
def test_batch07_fuzz():
 rng=random.Random(8707)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch07_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch07_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch07-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
