"""Qualification and recordings for research Batch 10."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q105","q115","q125","q135","q145","q155","q165","q175","q185","q195"]
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
def plans_q105(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["start"])
  def ex(s):
   vals,c,p=s;yield(3,{}),(vals,(c-1)%n,p);yield(4,{}),(vals,(c+1)%n,p);yield(5,{}),(vals,c,(p+1)%l["period"])
   if p in l["align"]:yield(1,{}),(m.transfer(vals,c),c,p)
  out.append(bfs((tuple(l["start"]),0,0),lambda s:s[0]==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q115(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   value,steps=s
   if steps<4+len(out):
    for a in range(1,5):yield(a,{}),(m.apply(value,a,l["mod"]),steps+1)
  out.append(bfs((l["start"],0),lambda s:s[0]==l["end"] and s[1]>0,ex)+[(6,{})])
 return out
def plans_q125(m):return [[x for w in l["windows"] for x in ([(1,{})]*w+[(2,{})])] for l in m.LEVELS]
def plans_q135(m):return [[(m.decode(x),{}) for x in l["groups"]] for l in m.LEVELS]
def plans_q145(m):
 out=[]
 for l in m.LEVELS:
  i=l["target"];right=i%len(l["ops"]);left=(-i)%len(l["ops"]);a=4 if right<=left else 3;out.append([(a,{})]*min(right,left)+[(1,{}),(2,{}),(6,{})])
 return out
def plans_q155(m):return [[(m.role(x,l["axis"]),{}) for x in l["queries"]] for l in m.LEVELS]
def plans_q165(m):
 out=[]
 for l in m.LEVELS:
  p=[(5,{})]*len(l["evidence"]);i=l["target"];right=i%l["count"];left=(-i)%l["count"];a=4 if right<=left else 3;out.append(p+[(a,{})]*min(right,left)+[(6,{})])
 return out
def plans_q175(m):
 out=[]
 for l in m.LEVELS:
  phase=0;p=[]
  for w in l["windows"]:
   while phase!=w:p.append((5,{}));phase=(phase+1)%l["period"]
   p.append((6,{}));phase=(phase+2)%l["period"]
  out.append(p)
 return out
def plans_q185(m):return [[(1 if x else 2,{}) for x in l["accept"]]+[(5,{})]*sum(l["accept"])+[(6,{})] for l in m.LEVELS]
def plans_q195(m):
 out=[]
 for l in m.LEVELS:
  t=0;p=[]
  for r in l["rhythm"]:
   for _ in range(r*l["scale"]):p.append((5,{}));t+=1
   p.append((6,{}))
  out.append(p)
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q105":[(6,{})],"q115":[(6,{})],"q125":[(2,{})],"q135":[(1,{})],"q145":[(6,{})],"q155":[(2,{})],"q165":[(6,{})],"q175":[(6,{})],"q185":[(2,{})],"q195":[(6,{})]}
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
def test_batch10_plans_and_losses():qualify()
def test_batch10_fuzz():
 rng=random.Random(9010)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch10_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch10_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch10-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
