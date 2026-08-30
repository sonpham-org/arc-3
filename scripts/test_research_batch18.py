"""Qualification and recordings for research Batch 18."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q109","q118","q128","q138","q148","q158","q168","q178","q188","q198"]
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
def plans_q109(m):
 out=[]
 for l in m.LEVELS:
  rot=0;p=[]
  for world in l["world"]:p.append((m.body_action(world,rot),{}));rot=(rot+1)%4
  out.append(p)
 return out
def plans_q118(m):
 out=[]
 for l in m.LEVELS:
  p=[(5,{})]*len(l["maps"])
  for target in l["route"]:
   choices=[a for a in range(1,5) if m.compose(a,l["maps"])==target];assert len(choices)==1
   p.append((choices[0],{}))
  out.append(p+[(6,{})])
 return out
def plans_q128(m):return [[(a,{}) for a in l["route"]] for l in m.LEVELS]
def plans_q138(m):return [[x for command in l["commands"] for x in ([(a,{}) for a in command]+[(5,{})])] for l in m.LEVELS]
def plans_q148(m):return [[(a,{}) for a in l["route"]]+[(5,{}),(6,{})] for l in m.LEVELS]
def plans_q158(m):return [[(l["perm"][i-1],{}) for i in m.BASE] for l in m.LEVELS]
def plans_q168(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,n in enumerate(l["target"]):
   p += [(1,{})]*n
   if i<len(l["target"])-1:p.append((4,{}))
  out.append(p+[(6,{})])
 return out
def plans_q178(m):
 out=[]
 for l in m.LEVELS:
  mods=tuple(l["mods"])
  def ex(s):yield(1,{}),((s[0]+1)%mods[0],s[1]);yield(2,{}),(s[0],(s[1]+1)%mods[1]);yield(5,{}),((s[0]+1)%mods[0],(s[1]+1)%mods[1])
  out.append(bfs(tuple(l["start"]),lambda s:s==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q188(m):return [[(a,{}) for a in l["early"]]+[(5,{})]+[(a,{}) for a in l["future"]] for l in m.LEVELS]
def plans_q198(m):
 out=[]
 for l in m.LEVELS:
  p=[];i=0;t=l["target"]
  while i<len(t):
   if t[i:i+len(m.MACRO_SEQ)]==m.MACRO_SEQ:p.append((5,{}));i+=len(m.MACRO_SEQ)
   else:p.append((t[i],{}));i+=1
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q109":[(2,{})],"q118":[(1,{})],"q128":[(2,{})],"q138":[(5,{})],"q148":[(6,{})],"q158":[(2,{})],"q168":[(6,{})],"q178":[(6,{})],"q188":[(2,{})],"q198":[(6,{})]}
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
def test_batch18_plans_and_losses():qualify()
def test_batch18_fuzz():
 rng=random.Random(18181)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch18_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch18_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch18-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
