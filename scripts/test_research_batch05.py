"""Deterministic qualification and recording generation for research Batch 05."""
from __future__ import annotations
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1]
CODES=["q004","q013","q023","q033","q043","q053","q063","q073","q083","q093"]
def load(code):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{code}-v1"/f"{code}.py";s=importlib.util.spec_from_file_location(f"{code}_b05",p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
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
def plans_q004(m):
 out=[]
 for l in m.LEVELS:
  cur=0;plan=[]
  for target in l["route"]:
   right=(target-cur)%4;left=(cur-target)%4;a=4 if right<=left else 3
   plan += [(a,{})]*min(right,left)+[(5,{}),(6,{}),(5,{}),(1,{})];cur=target
  out.append(plan)
 return out
def plans_q013(m):return [[(l["mapping"][s]+1,{}) for s in l["signals"]] for l in m.LEVELS]
def plans_q023(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["responses"]);right=l["odd"]%n;left=(-l["odd"])%n;a=4 if right<=left else 3;out.append([(a,{})]*min(right,left)+[(5,{}),(6,{})])
 return out
def plans_q033(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["ops"]);start=(tuple(l["start"]),0)
  def expand(s):
   vals,c=s;yield(3,{}),(vals,(c-1)%n);yield(4,{}),(vals,(c+1)%n);yield(5,{}),(m.swap(vals,l["ops"][c]),c)
  out.append(bfs(start,lambda s:s[0]==tuple(l["target"]),expand)+[(6,{})])
 return out
def plans_q043(m):
 out=[]
 for l in m.LEVELS:
  rocks=set(l["rocks"])
  def expand(pos):
   for a,(dx,dy) in m.DIRS.items():
    n=(pos[0]+dx,pos[1]+dy)
    if 0<=n[0]<m.W and 0<=n[1]<m.H and n not in rocks:yield(a,{}),n
  route=bfs(l["start"],lambda p:p==l["goal"],expand);assert len(route)<=l["samples"]
  plan=[]
  for i,(a,_) in enumerate(route):plan.extend([(a,{})] if i==len(route)-1 else [(a,{}),(5,{}),(a,{})])
  out.append(plan)
 return out
def plans_q053(m):
 out=[]
 for l in m.LEVELS:
  ops=list(map(m.norm,l["ops"]));cur=0;plan=[]
  for edge in map(m.norm,l["need"]):
   idx=ops.index(edge);right=(idx-cur)%len(ops);left=(cur-idx)%len(ops);a=4 if right<=left else 3;plan += [(a,{})]*min(right,left)+[(5,{})];cur=idx
  out.append(plan+[(6,{})])
 return out
def plans_q063(m):
 out=[]
 for l in m.LEVELS:
  walls=set(l["walls"]);door=l["door"]
  def expand(s):
   pa,pb,active,on=s;poss=[pa,pb]
   for a,(dx,dy) in m.DIRS.items():
    p=poss[active];n=(p[0]+dx,p[1]+dy);blocked=walls|({door} if active==1 and not on else set())
    if not(0<=n[0]<m.W and 0<=n[1]<m.H) or n in blocked:n=p
    nxt=list(poss);nxt[active]=n;yield(a,{}),(nxt[0],nxt[1],active,on)
   yield(5,{}),(pa,pb,1-active,on)
   if active==0 and pa==l["switch"]:yield(6,{}),(pa,pb,active,not on)
  out.append(bfs((l["a"],l["b"],0,False),lambda s:s[1]==l["goal"],expand))
 return out
def plans_q073(m):
 out=[]
 for l in m.LEVELS:
  walls=set(l["walls"]);material=set(l["material"]);threshold=l["threshold"]
  def expand(s):
   pos,e=s
   for a,(dx,dy) in m.DIRS.items():
    n=(pos[0]+dx,pos[1]+dy);blocked=walls|(material if e<threshold else set());n=n if 0<=n[0]<m.W and 0<=n[1]<m.H and n not in blocked else pos;yield(a,{}),(n,e)
   yield(5,{}),(pos,min(threshold,e+1))
  out.append(bfs((l["start"],0),lambda s:s[0]==l["goal"],expand))
 return out
def plans_q083(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["parents"]);right=l["target"]%n;left=(-l["target"])%n;a=4 if right<=left else 3;out.append([(a,{})]*min(right,left)+[(6,{})])
 return out
def plans_q093(m):
 out=[]
 for l in m.LEVELS:
  def unlock(mask):
   u=1
   for pat,count in l["gates"]:
    if mask&pat==pat:u=max(u,count)
   return u
  def expand(s):
   mask,c,u=s;yield(3,{}),(mask,(c-1)%u,u);yield(4,{}),(mask,(c+1)%u,u);nm=mask^l["ops"][c];yield(5,{}),(nm,c,unlock(nm))
  out.append(bfs((0,0,1),lambda s:s[0]==l["target"],expand)+[(6,{})])
 return out
PLANNERS={c:globals()[f"plans_{c}"] for c in CODES}
LOSS={"q004":[(1,{})],"q013":[(2,{})],"q023":[(6,{})],"q033":[(6,{})],"q043":[(6,{})],"q053":[(6,{})],"q063":[(6,{})],"q073":[(6,{})],"q083":[(4,{}),(6,{})],"q093":[(6,{})]}
def validate(r):
 g=r.frame[-1];assert g.shape==(64,64);assert np.issubdtype(g.dtype,np.integer);assert 0<=int(g.min())<=int(g.max())<=15
def digest(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def execute(code,m,plans):
 game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True);records=[]
 for i,plan in enumerate(plans):
  assert game.level_index==i
  for a,data in plan:r=game.perform_action(ActionInput(id=GameAction.from_id(a),data=data),raw=True);validate(r)
  records.append({"level":i+1,"actions":[[a] for a,_ in plan],"post_transition_frame_sha256":digest(r)})
 assert r.state==GameState.WIN,(code,r.state);return{"schema_version":1,"game_id":f"{code}-v1","expected_state":"WIN","levels":records}
def execute_loss(code,m):
 game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True)
 for a,data in LOSS[code]:r=game.perform_action(ActionInput(id=GameAction.from_id(a),data=data),raw=True)
 assert r.state==GameState.GAME_OVER,(code,r.state);return{"schema_version":1,"game_id":f"{code}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[code]],"terminal_frame_sha256":digest(r)}
def qualify(write=False):
 for code in CODES:
  m=load(code);plans=PLANNERS[code](m);win=execute(code,m,plans);loss=execute_loss(code,m)
  if write:
   out=ROOT/"research"/"recordings";out.mkdir(parents=True,exist_ok=True);(out/f"{code}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(out/f"{code}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(code,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")
def test_batch05_known_plans_and_losses():qualify(False)
def test_batch05_fuzz():
 rng=random.Random(8505)
 for code in CODES:
  m=load(code);game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in(GameState.GAME_OVER,GameState.WIN):r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=game.perform_action(ActionInput(id=GameAction.from_id(rng.choice(range(1,7))),data={}),raw=True);validate(r)
def test_batch05_backgrounds_are_unique_and_not_black_dominant():
 signatures=set()
 for code in CODES:
  m=load(code);g=getattr(m,code.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);grid=r.frame[-1];sig=tuple(int(grid[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1)));assert sig!=(5,5,5,5);assert float((grid==5).sum())/grid.size<.1;signatures.add(sig)
 assert len(signatures)==len(CODES)
def test_batch05_artifacts():
 batch=json.loads((ROOT/"research"/"gpt-batch05-v1.json").read_text());assert[x["game_id"] for x in batch["games"]]==CODES
 for code in CODES:
  m=load(code);meta=json.loads((ROOT/"research"/"games"/f"{code}-v1.json").read_text());source=ROOT/meta["artifacts"]["source"];assert hashlib.sha256(source.read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
  win=json.loads((ROOT/meta["artifacts"]["win_recording"]).read_text());game=getattr(m,code.upper())();r=game.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for level in win["levels"]:
   for e in level["actions"]:r=game.perform_action(ActionInput(id=GameAction.from_id(e[0]),data={}),raw=True)
   assert digest(r)==level["post_transition_frame_sha256"]
  assert r.state==GameState.WIN
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
