"""Qualification, recordings, fuzzing, and artifact checks for research Batch 25."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q501","q532","q563","q594","q625","q656","q687","q718","q749","q780"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def bfs(start,goal,expand):
 q=deque([start]);parent={start:None};action={}
 while q:
  state=q.popleft()
  if goal(state):
   out=[]
   while parent[state] is not None:out.append(action[state]);state=parent[state]
   return out[::-1]
  for a,nxt in expand(state):
   if nxt not in parent:parent[nxt]=state;action[nxt]=a;q.append(nxt)
 raise AssertionError("unsolved authored level")
def plans_q501(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  s=(l["start"],0,0,0);t=s
  for a in l["plan"]:t=m.advance(t,a,l["n"])
  try:p=bfs(s,lambda x:x[0]==t[0] and x[3]!=0,lambda x:((a,m.advance(x,a,l["n"])) for a in (1,2,3)))
  except AssertionError as e:raise AssertionError(f"q501 level {i+1} unsolved") from e
  out.append([(a,{}) for a in p]+[(6,{})])
 return out
def plans_q532(m):
 out=[]
 for l in m.LEVELS:
  valid=[x for x in l["demo"] if x[2]];p=[(5,{})]*len(l["demo"])
  p += [(l["maps"][context].index(a)+1,{}) for a,context,_ in valid];out.append(p+[(6,{})])
 return out
def plans_q563(m):return [[(l["desired"],{})]*l["window"]+[(4,{}),((l["desired"]%3)+1,{})] for l in m.LEVELS]
def plans_q594(m):
 out=[]
 for l in m.LEVELS:
  p=[];local=outer=0
  for command in l["commands"]:
   for desired in command:
    raw=((desired-1-l["shift"]-outer)%4)+1;p.append((raw,{}));local+=1
    if local==l["cycle"]:local=0;outer=(outer+1)%4
   p.append((5,{}));local+=1
   if local==l["cycle"]:local=0;outer=(outer+1)%4
  out.append(p)
 return out
def plans_q625(m):return [[(1,{}),(3,{}),(2,{}),(3,{})]+[(4,{})]*l["policy"]+[(5,{})] for l in m.LEVELS]
def plans_q656(m):return [[(a,{}) for a in m.route(l["source"])+m.route(l["target"])] for l in m.LEVELS]
def plans_q687(m):
 out=[]
 for l in m.LEVELS:
  scores=[0,0,0];idx=cursor=0;p=[]
  while True:
   take=min(l["capacity"],len(l["samples"])-idx)
   if not take:raise AssertionError("q687 exhausted evidence without a margin")
   p += [(1,{})]*take
   for c,w in l["samples"][idx:idx+take]:scores[c]+=w
   idx+=take;p.append((3,{}));remaining=sum(w for _,w in l["samples"][idx:])
   if m.guaranteed(scores,remaining):break
  winner=m.leader(scores);p += [(2,{})]*((winner-cursor)%3)+[(5,{}),(6,{})];out.append(p)
 return out
def plans_q718(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  sealed=l["intervene"];prefix=[(5,{})] if sealed else []
  def expand(s):
   amounts,cursor,phase=s;n=(cursor+1)%3
   if amounts[cursor]:v=list(amounts);v[cursor]-=1;v[n]+=1;yield 1,(tuple(v),cursor,phase)
   if amounts[n]:v=list(amounts);v[n]-=1;v[cursor]+=1;yield 2,(tuple(v),cursor,phase)
   yield 3,(amounts,n,phase);yield 4,(amounts,cursor,(phase+1)%l["mod"])
  goalphase=(l["phase"]-(1 if sealed else 0))%l["mod"]
  try:p=bfs((tuple(l["start"]),0,0),lambda s:s[0]==tuple(l["target"]) and s[2]==goalphase,expand)
  except AssertionError as e:raise AssertionError(f"q718 level {i+1} unsolved") from e
  out.append(prefix+[(a,{}) for a in p]+[(6,{})])
 return out
def plans_q749(m):return [[(l["identity"],{})]+[(3,{})]*l["delay"]+[(5,{})]+[(4,{})]*l["delay"]+[(l["identity"],{})] for l in m.LEVELS]
def plans_q780(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  need=l["chunks"]
  def expand(s):
   a,b,ch=s;yield 3,((a+1)%l["mods"][0],b,ch);yield 4,(a,(b+1)%l["mods"][1],ch);yield 5,((a+3)%l["mods"][0],(b+3)%l["mods"][1],min(need,ch+1))
  try:p=bfs((0,0,0),lambda s:list(s[:2])==l["target"] and s[2]>=need,expand)
  except AssertionError as e:raise AssertionError(f"q780 level {i+1} unsolved") from e
  out.append([(a,{}) for a in p]+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={c:[(6,{})] for c in CODES};LOSS.update({"q532":[(1,{})],"q563":[(4,{})],"q594":[(5,{})],"q625":[(5,{})],"q687":[(5,{})],"q749":[(3,{})]})
def valid(r):
 a=r.frame[-1];assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def digest(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def win(c,m,plans):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[]
 for i,p in enumerate(plans):
  assert g.level_index==i,(c,i,g.level_index)
  for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
  levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":digest(r)})
 assert r.state==GameState.WIN,(c,r.state);return{"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels}
def lose(c,m):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
 for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
 assert r.state==GameState.GAME_OVER,(c,r.state);return{"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":digest(r)}
def qualify(write=False):
 for c in CODES:
  m=load(c);p=PLANS[c](m);w=win(c,m,p);l=lose(c,m)
  if write:
   d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(w,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(l,indent=2)+"\n")
  print(c,"levels",len(p),"actions",sum(map(len,p)),"qualified")
def test_batch25_plans_and_losses():qualify()
def test_batch25_fuzz():
 rng=random.Random(25252)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch25_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch25_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch25-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
