"""Deterministic qualification and recording generation for research Batch 04."""

from __future__ import annotations
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState

ROOT=Path(__file__).resolve().parents[1]
CODES=["q102","q112","q122","q132","q142","q152","q162","q172","q182","q192"]

def load(code):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{code}-v1"/f"{code}.py";s=importlib.util.spec_from_file_location(f"{code}_b04",p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def bfs(start,solved,expand):
 q=deque([start]);parent={start:None};action={}
 while q:
  state=q.popleft()
  if solved(state):
   out=[]
   while parent[state] is not None:out.append(action[state]);state=parent[state]
   return list(reversed(out))
  for move,nxt in expand(state):
   if nxt not in parent:parent[nxt]=state;action[nxt]=move;q.append(nxt)
 raise AssertionError("authored level is not solvable")

def plans_q102(m):
 out=[]
 for l in m.LEVELS:
  walls=set(l["walls"])
  def expand(s):
   origin,local,facing=s
   for a,(dx,dy) in m.DIRS.items():
    loc=(local[0]+dx,local[1]+dy);world=(origin[0]+loc[0],origin[1]+loc[1]);loc=loc if 0<=loc[0]<m.ROOM and 0<=loc[1]<m.ROOM and world not in walls else local;yield(a,{}),(origin,loc,a)
   dx,dy=m.DIRS[facing];org=(origin[0]+dx,origin[1]+dy);world=(org[0]+local[0],org[1]+local[1]);org=org if 0<=org[0]<=m.WORLD-m.ROOM and 0<=org[1]<=m.WORLD-m.ROOM and world not in walls else origin;yield(5,{}),(org,local,facing)
  plan=bfs((l["origin"],l["local"],4),lambda s:(s[0][0]+s[1][0],s[0][1]+s[1][1])==l["goal"],expand);assert len(plan)<=l["budget"],(l["name"],len(plan));out.append(plan)
 return out

def plans_q112(m):return [[(a,{}) for a in l["good"]] for l in m.LEVELS]

def plans_q122(m):
 out=[]
 for l in m.LEVELS:
  walls=set(l["walls"])
  def expand(s):
   pos,guard,stage=s
   for a,(dx,dy) in m.DIRS.items():
    if stage==0:
     intent=(pos[0]+dx,pos[1]+dy);candidate=m.toward(guard,intent);candidate=guard if candidate in walls else candidate;yield(a,{}),(pos,candidate,1)
    else:
     nxt=(pos[0]+dx,pos[1]+dy)
     if 0<=nxt[0]<m.SIZE and 0<=nxt[1]<m.SIZE and nxt not in walls and nxt!=guard:yield(a,{}),(nxt,guard,0)
  plan=bfs((l["start"],l["guard"],0),lambda s:s[0]==l["goal"],expand);assert len(plan)<=l["budget"],(l["name"],len(plan));out.append(plan)
 return out

def plans_q132(m):return [[item for a in l["route"] for item in ((a,{}),(5,{}))] for l in m.LEVELS]

def plans_q142(m):
 out=[]
 for l in m.LEVELS:
  blocked=set(l["walls"])|set(l["traps"])
  def expand(pos):
   for a,(dx,dy) in m.DIRS.items():
    nxt=(pos[0]+dx,pos[1]+dy)
    if 0<=nxt[0]<m.SIZE and 0<=nxt[1]<m.SIZE and nxt not in blocked:yield(a,{}),nxt
  moves=bfs(l["start"],lambda p:p==l["goal"],expand);cursor=1;previews=l["previews"];plan=[]
  for a,_ in moves:
   right=(a-cursor)%4;left=(cursor-a)%4;nav=4 if right<=left else 3;plan.extend([(nav,{})]*min(right,left));cursor=a
   if previews:plan.append((5,{}));previews-=1
   plan.append((6,{}))
  assert len(plan)<=l["budget"],(l["name"],len(plan));out.append(plan)
 return out

def plans_q152(m):return [[(a,{}) for a in l["forces"]] for l in m.LEVELS]

def plans_q162(m):
 out=[]
 for l in m.LEVELS:
  plan=[];revealed=0
  for a in l["route"]:
   if not revealed:plan.append((5,{}));revealed=min(l["span"],len(l["route"]));
   plan.append((a,{}));revealed-=1
  assert len(plan)<=l["budget"],(l["name"],len(plan));out.append(plan)
 return out

def plans_q172(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["ops"])
  def expand(s):
   values,cursor=s;yield(3,{}),(values,(cursor-1)%n);yield(4,{}),(values,(cursor+1)%n);yield(5,{}),(m.pour(values,l["ops"][cursor]),cursor)
  plan=bfs((tuple(map(tuple,l["start"])),0),lambda s:s[0]==tuple(map(tuple,l["target"])),expand)+[(6,{})];assert len(plan)<=l["budget"],(l["name"],len(plan));out.append(plan)
 return out

def plans_q182(m):
 out=[]
 for l in m.LEVELS:
  first,later=l["first"],l["later"]
  def expand(s):
   phase,pos,used=s;grid=first if phase==0 else later
   for a,(dx,dy) in m.DIRS.items():
    nxt=(pos[0]+dx,pos[1]+dy)
    if not(0<=nxt[0]<m.W and 0<=nxt[1]<m.H) or grid[nxt[1]][nxt[0]]=="#" or (phase==1 and grid[nxt[1]][nxt[0]] in used):nxt=pos
    new=set(used);ch=grid[nxt[1]][nxt[0]]
    if phase==0 and ch in "abc":new.add(ch)
    p=phase
    if nxt==m.locate(grid,"G"):
     if phase==0:p,nxt=1,m.locate(later,"S")
     else:p=2
    yield(a,{}),(p,nxt,frozenset(new))
  plan=bfs((0,m.locate(first,"S"),frozenset()),lambda s:s[0]==2,expand);assert len(plan)<=l["budget"],(l["name"],len(plan));out.append(plan)
 return out

def plans_q192(m):
 out=[]
 for l in m.LEVELS:
  fast=slow=0;plan=[]
  for target in l["targets"]:
   while(fast,slow)!=target:
    plan.append((5,{}));fast+=1
    if fast==l["fast"]:fast=0;slow=(slow+1)%l["slow"]
   plan.append((6,{}))
   if target!=l["targets"][-1]:
    fast+=1
    if fast==l["fast"]:fast=0;slow=(slow+1)%l["slow"]
  assert len(plan)<=l["budget"],(l["name"],len(plan));out.append(plan)
 return out

PLANNERS={c:globals()[f"plans_{c}"] for c in CODES}
LOSS={"q102":[(6,{})],"q112":[(1,{})],"q122":[(5,{})],"q132":[(5,{})],"q142":[(1,{})],"q152":[(1,{})],"q162":[(1,{})],"q172":[(6,{})],"q182":[(5,{})],"q192":[(6,{})]}

def validate(r):
 g=r.frame[-1];assert g.shape==(64,64);assert np.issubdtype(g.dtype,np.integer);assert 0<=int(g.min())<=int(g.max())<=15
def digest(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()

def execute(code,m,plans):
 game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True);records=[]
 for i,plan in enumerate(plans):
  assert game.level_index==i;encoded=[]
  for a,data in plan:r=game.perform_action(ActionInput(id=GameAction.from_id(a),data=data),raw=True);validate(r);encoded.append([a,data["x"],data["y"]] if "x" in data else[a])
  records.append({"level":i+1,"actions":encoded,"post_transition_frame_sha256":digest(r)})
 assert r.state==GameState.WIN,(code,r.state);return{"schema_version":1,"game_id":f"{code}-v1","expected_state":"WIN","levels":records}
def execute_loss(code,m):
 game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True);encoded=[]
 for a,data in LOSS[code]:
  r=game.perform_action(ActionInput(id=GameAction.from_id(a),data=data),raw=True);encoded.append([a])
  if r.state==GameState.GAME_OVER:break
 assert r.state==GameState.GAME_OVER,(code,r.state);return{"schema_version":1,"game_id":f"{code}-v1","expected_state":r.state.value,"actions":encoded,"terminal_frame_sha256":digest(r)}
def qualify(write=False):
 for code in CODES:
  m=load(code);plans=PLANNERS[code](m);win=execute(code,m,plans);loss=execute_loss(code,m)
  if write:
   out=ROOT/"research"/"recordings";out.mkdir(parents=True,exist_ok=True);(out/f"{code}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(out/f"{code}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(code,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")

def test_batch04_known_plans_and_losses():qualify(False)
def test_batch04_fuzz():
 rng=random.Random(8404)
 for code in CODES:
  m=load(code);game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in(GameState.GAME_OVER,GameState.WIN):r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   a=rng.choice(range(1,7));data={"x":rng.randrange(64),"y":rng.randrange(64)} if a==6 else{};r=game.perform_action(ActionInput(id=GameAction.from_id(a),data=data),raw=True);validate(r)
def test_batch04_backgrounds_are_unique_and_not_black_dominant():
 signatures=set()
 for code in CODES:
  m=load(code);game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True);grid=r.frame[-1];signature=tuple(int(grid[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1)));assert signature!=(5,5,5,5);assert float((grid==5).sum())/grid.size<0.1;signatures.add(signature)
 assert len(signatures)==len(CODES)
def test_batch04_artifacts():
 batch=json.loads((ROOT/"research"/"gpt-batch04-v1.json").read_text());assert[x["game_id"] for x in batch["games"]]==CODES
 for code in CODES:
  m=load(code);meta=json.loads((ROOT/"research"/"games"/f"{code}-v1.json").read_text());source=ROOT/meta["artifacts"]["source"];assert hashlib.sha256(source.read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
  win=json.loads((ROOT/meta["artifacts"]["win_recording"]).read_text());game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for level in win["levels"]:
   for e in level["actions"]:r=game.perform_action(ActionInput(id=GameAction.from_id(e[0]),data={}),raw=True)
   assert digest(r)==level["post_transition_frame_sha256"]
  assert r.state==GameState.WIN

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
