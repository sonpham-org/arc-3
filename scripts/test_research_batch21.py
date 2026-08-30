"""Qualification and recordings for research Batch 21."""
from collections import deque
from itertools import product
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q511","q542","q573","q604","q635","q666","q697","q728","q759","q790"]
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
def plans_q511(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  def ex(s):
   for a in (1,2,3):yield(a,{}),m.transition(s,a,l["n"])
   if s[0]==l["switch"] and not s[3]:yield(5,{}),(s[0],(s[1]+1)%l["n"],s[2],True)
  try:p=bfs((l["start"],0,0,False),lambda s:s[0]==l["goal"] and s[3],ex)
  except AssertionError as exc:raise AssertionError(f"q511 authored level {i+1} is unsolved") from exc
  out.append(p+[(6,{})])
 return out
def plans_q542(m):
 out=[]
 for l in m.LEVELS:
  p=[(5,{})]*len(l["demo"])
  for base,context,effective in l["demo"]:
   if effective:p.append((l["maps"][context].index(base)+1,{}))
  out.append(p+[(6,{})])
 return out
def plans_q573(m):
 out=[]
 for l in m.LEVELS:
  history=next(x for x in product((1,2,3),repeat=l["window"]) if m.tactic(list(x),l["window"])==l["desired"]);p=[(a,{}) for a in history]
  if sum(history)%2:p.append((4,{}))
  out.append(p+[(5,{}),((l["desired"]%3)+1,{})])
 return out
def plans_q604(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for command,shift in zip(l["commands"],l["shifts"]):p += [(((a-1-shift)%4)+1,{}) for a in command]+[(5,{})]
  out.append(p)
 return out
def plans_q635(m):return [[(1,{}),(3,{}),(2,{}),(3,{})]+[(4,{})]*l["policy"]+[(5,{})] for l in m.LEVELS]
def plans_q666(m):return [[(l["sight"][i-1],{}) for i in m.BASE]+[(l["actor"][i-1],{}) for i in m.BASE] for l in m.LEVELS]
def plans_q697(m):
 out=[]
 for l in m.LEVELS:
  scores=[0,0];p=[]
  for i,(c,w) in enumerate(l["samples"]):
   scores[c]+=w;p.append((1,{}));remain=sum(x[1] for x in l["samples"][i+1:])
   if abs(scores[0]-scores[1])>remain:break
  leader=max(range(2),key=lambda j:scores[j])
  if leader:p.append((3,{}))
  out.append(p+[(5,{}),(6,{})])
 return out
def plans_q728(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  start=tuple(l["start"])
  def ex(s):
   vals,cursor,phase,evidence=s;nxt=(cursor+1)%3
   if vals[cursor]>0:
    v=list(vals);v[cursor]-=1;v[nxt]+=1;yield(1,{}),(tuple(v),cursor,phase,evidence)
   if vals[nxt]>0:
    v=list(vals);v[nxt]-=1;v[cursor]+=1;yield(2,{}),(tuple(v),cursor,phase,evidence)
   yield(3,{}),(vals,nxt,phase,evidence);yield(4,{}),(vals,cursor,(phase+1)%4,evidence)
   if not evidence and m.influence(vals)>=l["probe"]:yield(5,{}),(start,0,0,True)
  goal=lambda s:s[0]==tuple(l["target"]) and s[2]==l["target_phase"] and (s[3] or not l["evidence"])
  try:p=bfs((start,0,0,False),goal,ex)
  except AssertionError as exc:raise AssertionError(f"q728 authored level {i+1} is unsolved") from exc
  out.append(p+[(6,{})])
 return out
def plans_q759(m):return [[(l["identity"],{})]+[(3,{})]*l["delay"]+[(a,{}) for a in l["tool"]]+[(l["identity"],{})] for l in m.LEVELS]
def plans_q790(m):
 out=[]
 for l in m.LEVELS:
  p=[(1,{})]*l["need"][0]+[(2,{})]*l["need"][1];phase=sum(l["need"])%l["period"]
  def ex(s):yield(4,{}),(s+3)%l["period"];yield(5,{}),(s+1)%l["period"]
  p += bfs(phase,lambda s:s==l["window"],ex);out.append(p+[(3,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q511":[(6,{})],"q542":[(1,{})],"q573":[(5,{})],"q604":[(5,{})],"q635":[(5,{})],"q666":[(2,{})],"q697":[(5,{})],"q728":[(6,{})],"q759":[(3,{})],"q790":[(3,{})]}
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
def test_batch21_plans_and_losses():qualify()
def test_batch21_fuzz():
 rng=random.Random(21212)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch21_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch21_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch21-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
