"""Qualification and fuzz coverage for research Batch 28."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q504","q535","q566","q597","q628","q659","q690","q721","q752","q783"]
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
 raise AssertionError("unsolved")
def plans_q504(m):return [[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q535(m):
 out=[]
 for l in m.LEVELS:
  p=[(5,{})]*len(l["demo"]);frame=0
  for desired,ctx,ok in l["demo"]:
   if ok:i=l["maps"][ctx].index(desired);p.append((((i-frame)%4)+1,{}));frame=(frame+1)%4
  out.append(p+[(6,{})])
 return out
def plans_q566(m):return [[(a,{}) for a in l["pattern"]]+[(4,{}),(((sum(l["pattern"])-1)%3+1)%3+1,{})] for l in m.LEVELS]
def plans_q597(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for group,cmd in enumerate(l["commands"]):p += [(((a-1-l["shift"]-group)%4)+1,{}) for a in cmd]+[(5,{})]
  out.append(p)
 return out
def plans_q628(m):return [[(1,{}),(3,{}),(2,{}),(3,{})]+[(4,{})]*l["policy"]+[(5,{}),(5,{}),(6,{})] for l in m.LEVELS]
def plans_q659(m):return [[(a,{}) for a in m.route(l["source"])]+[(5,{}),(6,{})]+[(a,{}) for a in m.route(l["target"])] for l in m.LEVELS]
def plans_q690(m):
 out=[]
 for l in m.LEVELS:
  scores=[0,0,0];idx=cursor=stored=0;p=[];phase=[0,0]
  while True:
   p += [(1,{})]*((-phase[0])%l["mods"][0])+[(2,{})]*((-phase[1])%l["mods"][1]);p.append((3,{}));c,w=l["samples"][idx];scores[c]+=w;idx+=1;stored+=1;phase=[1%l["mods"][0],2%l["mods"][1]]
   if stored==l["cap"] or idx==len(l["samples"]):p.append((4,{}));stored=0
   rem=sum(w for _,w in l["samples"][idx:])
   if not stored and m.safe(scores,rem):break
  winner=m.lead(scores);p += [(5,{})]*((winner-cursor)%3)+[(6,{})];out.append(p)
 return out
def plans_q721(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   v,c,k=s;step=2 if k>=l["at"] else 1;j=(c+step)%3;nk=min(l["at"],k+1)
   if v[c]:a=list(v);a[c]-=1;a[j]+=1;yield 1,(tuple(a),c,nk)
   if v[j]:a=list(v);a[j]-=1;a[c]+=1;yield 2,(tuple(a),c,nk)
   yield 3,(v,j,nk)
  p=bfs((tuple(l["start"]),0,0),lambda s:s[0]==tuple(l["target"]) and s[2]>=l["at"],ex);out.append([(a,{}) for a in p]+[(6,{})])
 return out
def plans_q752(m):return [[(l["identity"],{})]+[(3,{})]*l["delay"]+[(4,{}),(5,{}),(l["identity"],{})] for l in m.LEVELS]
def plans_q783(m):
 out=[]
 for l in m.LEVELS:
  need=l["chunks"]
  def ex(s):
   a,b,ch,claim=s;yield 2,(a,b,ch,1-claim);yield 3,((a+1)%l["mods"][0],b,ch,claim);yield 4,(a,(b+1)%l["mods"][1],ch,claim);yield 5,((a+3)%l["mods"][0],(b+3)%l["mods"][1],min(need,ch+1),claim)
  p=bfs((0,0,0,0),lambda s:list(s[:2])==l["target"] and s[2]>=need and s[3]==m.parity(l),ex);out.append([(a,{}) for a in p]+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS["q597"]=[(5,{})]
def valid(r):a=r.frame[-1];assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def qualify(write=False):
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[];plans=PLANS[c](m)
  for i,p in enumerate(plans):
   for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
   levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
  assert r.state==GameState.WIN,(c,r.state);win={"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels};g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
  assert r.state==GameState.GAME_OVER;loss={"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":dig(r)}
  if write:d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(c,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")
def test_batch28_plans_and_losses():qualify()
def test_batch28_fuzz():
 rng=random.Random(28282)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch28_visuals():
 sig=set()
 for c in CODES:m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch28_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch28-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  m=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/m["artifacts"]["source"]).read_bytes()).hexdigest()==m["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
