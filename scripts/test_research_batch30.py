"""Qualification and fuzz coverage for research Batch 30."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q505","q536","q567","q598","q629","q660","q691","q722","q753","q784"]
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
def plans_q505(m):return [[(a,{}) for a in x["plan"]]+[(6,{})] for x in m.LEVELS]
def plans_q536(m):
 out=[]
 for x in m.LEVELS:
  p=[(5,{})]*len(x["demo"])
  for desired,ctx,ok in x["demo"]:
   if ok:p.append((x["maps"][ctx].index(desired)+1,{}))
  out.append(p+[(6,{})])
 return out
def plans_q567(m):
 out=[]
 for x in m.LEVELS:
  p=[]
  for i in range(0,len(x["pattern"]),x["cap"]):p += [(a,{}) for a in x["pattern"][i:i+x["cap"]]]+[(4,{})]
  tactic=(sum(x["pattern"])-1)%3+1;out.append(p+[(5,{}),(tactic%3+1,{})])
 return out
def plans_q598(m):
 out=[]
 for x in m.LEVELS:
  p=[]
  for g,cmd in enumerate(x["cmd"]):p += [(((a-1-x["shift"]-g)%4)+1,{}) for a in cmd]+[(5,{})]
  out.append(p+[(6,{})])
 return out
def plans_q629(m):return [[(1,{}),(3,{}),(2,{}),(3,{})]+[(4,{})]*x["policy"]+[(5,{})] for x in m.LEVELS]
def plans_q660(m):return [[(a,{}) for a in m.route(x["source"])]+[(5,{})]+[(a,{}) for a in m.route(x["target"])] for x in m.LEVELS]
def plans_q691(m):
 out=[]
 for x in m.LEVELS:
  scores=[0,0,0];idx=0;p=[]
  while True:
   c,w=x["samples"][idx];scores[c]+=w;idx+=1;p.append((1,{}));rem=sum(w for _,w in x["samples"][idx:])
   if m.safe(scores,rem):break
  step=2 if idx>=x["at"] else 1;winner=m.lead(scores);k=next(i for i in range(3) if i*step%3==winner);p += [(2,{})]*k+[(6,{})];out.append(p)
 return out
def plans_q722(m):
 out=[]
 for x in m.LEVELS:
  def ex(s):
   v,c,sw=s;n=(c+1)%3
   if v[c]:a=list(v);a[c]-=1;a[n]+=1;yield 1,(tuple(a),c,sw)
   if v[n]:a=list(v);a[n]-=1;a[c]+=1;yield 2,(tuple(a),c,sw)
   yield 3,(v,n,sw)
   if not sw:yield 4,(v,c,True)
  p=bfs((tuple(x["start"]),0,False),lambda s:s[0]==tuple(x["target"]) and s[2],ex);out.append([(a,{}) for a in p]+[(6,{})])
 return out
def plans_q753(m):return [[(x["identity"],{})]+[(3,{})]*x["delay"]+[(4,{})]*m.parity(x)+[(5,{}),(x["identity"],{})] for x in m.LEVELS]
def plans_q784(m):
 out=[]
 for x in m.LEVELS:
  need=x["chunks"]
  def ex(s):
   a,b,ch,t=s;yield 2,(a,b,ch,(t+1)%4);yield 3,((a+1)%x["mods"][0],b,ch,t);yield 4,(a,(b+1)%x["mods"][1],ch,t);yield 5,((a+3)%x["mods"][0],(b+3)%x["mods"][1],min(need,ch+1),t)
  p=bfs((0,0,0,0),lambda s:list(s[:2])==x["target"] and s[2]>=need and s[3]==x["token"],ex);out.append([(a,{}) for a in p]+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS.update({"q536":[(1,{})],"q567":[(5,{})],"q598":[(5,{})],"q629":[(5,{})]})
def valid(r):a=r.frame[-1];assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def qualify(write=False):
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[];plans=PLANS[c](m)
  for i,p in enumerate(plans):
   assert g.level_index==i
   for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
   levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
  assert r.state==GameState.WIN,(c,r.state);win={"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels};g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
  assert r.state==GameState.GAME_OVER,(c,r.state);loss={"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":dig(r)}
  if write:d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(c,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")
def test_batch30_plans_and_losses():qualify()
def test_batch30_fuzz():
 rng=random.Random(30303)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch30_visuals():
 sig=set()
 for c in CODES:m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch30_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch30-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  m=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/m["artifacts"]["source"]).read_bytes()).hexdigest()==m["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
