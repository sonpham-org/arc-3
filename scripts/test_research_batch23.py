"""Qualification and recordings for research Batch 23."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q521","q552","q583","q614","q645","q676","q707","q738","q769","q800"]
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
def plans_q521(m):
 out=[]
 for l in m.LEVELS:
  t=(l["start"],0,0)
  for a in l["plan"]:t=m.advance(t,a,l["n"],l["wear"])
  def ex(s):
   if s[2]<20:
    for a in (1,2,3):yield(a,{}),m.advance(s,a,l["n"],l["wear"])
  out.append(bfs((l["start"],0,0),lambda s:s[0]==t[0] and s[2]>=l["wear"],ex)+[(6,{})])
 return out
def plans_q552(m):
 out=[]
 for l in m.LEVELS:
  p=[(5,{})]*len(l["demo"])
  for base,context,effective in l["demo"]:
   if effective:p.append((l["maps"][context].index(base)+1,{}))
  out.append(p+[(6,{})])
 return out
def plans_q583(m):return [[(l["desired"],{})]*l["window"]+[(4,{}),((l["desired"]%3)+1,{})] for l in m.LEVELS]
def plans_q614(m):return [[(((a-1-l["shift"])%4)+1,{}) for a in l["target"]]+[(6,{})] for l in m.LEVELS]
def plans_q645(m):return [[(1,{}),(3,{}),(2,{}),(3,{})]+[(4,{})]*l["policy"]+[(5,{})] for l in m.LEVELS]
def plans_q676(m):return [[x for a in ([l["dock"][i-1] for i in m.BASE]+[l["actor"][i-1] for i in m.BASE]) for x in ((5,{}),(a,{}))] for l in m.LEVELS]
def phase_plan(samples):
 scores=[0,0];p=[]
 for i,(c,w) in enumerate(samples):
  scores[c]+=w;p.append((1,{}));remain=sum(x[1] for x in samples[i+1:])
  if abs(scores[0]-scores[1])>remain:break
 leader=max(range(2),key=lambda j:scores[j])
 if leader:p.append((2,{}))
 return p+[(5,{})]
def plans_q707(m):return [phase_plan(l["sets"][0])+phase_plan(l["sets"][1]) for l in m.LEVELS]
def plans_q738(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  def ex(s):
   vals,cursor,phase=s;nxt=(cursor+(2 if l["fault"] else 1))%3;yield(3,{}),(vals,(cursor+1)%3,phase);yield(4,{}),(vals,cursor,(phase+1)%4)
   if vals[cursor]>0:v=list(vals);v[cursor]-=1;v[nxt]+=1;yield(1,{}),(tuple(v),cursor,phase)
   if vals[nxt]>0:v=list(vals);v[nxt]-=1;v[cursor]+=1;yield(2,{}),(tuple(v),cursor,phase)
  try:p=bfs((tuple(l["start"]),0,0),lambda s:s[0]==tuple(l["target"]) and s[2]==l["phase"],ex)
  except AssertionError as exc:raise AssertionError(f"q738 authored level {i+1} is unsolved") from exc
  out.append([(5,{})]+p+[(6,{})])
 return out
def plans_q769(m):
 out=[]
 for l in m.LEVELS:
  p=[(l["identity"],{})];phase=[0,0]
  for _ in range(l["rewards"]):
   p += [(3,{})]*((l["target"][0]-phase[0])%l["mods"][0]);phase[0]=l["target"][0]
   p += [(4,{})]*((l["target"][1]-phase[1])%l["mods"][1]);phase[1]=l["target"][1];p.append((5,{}));phase=[(x+1)%n for x,n in zip(phase,l["mods"])]
  out.append(p+[(l["identity"],{})])
 return out
def plans_q800(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):yield(4,{}),(s+3)%l["period"];yield(5,{}),(s+1)%l["period"]
  out.append([(l["helper"],{})]+bfs(0,lambda s:s==l["window"],ex)+[(3,{}),(l["helper"],{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS.update({"q552":[(1,{})],"q583":[(4,{})],"q614":[(6,{})],"q645":[(5,{})],"q676":[(1,{})],"q707":[(5,{})],"q738":[(1,{})],"q769":[(3,{})],"q800":[(3,{})]})
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
def test_batch23_plans_and_losses():qualify()
def test_batch23_fuzz():
 rng=random.Random(23232)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch23_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch23_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch23-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
