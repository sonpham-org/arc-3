"""Qualification and recordings for research Batch 08."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q104","q114","q124","q134","q144","q154","q164","q174","q184","q194"]
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
def plans_q104(m):
 out=[]
 for l in m.LEVELS:
  board=l["board"]
  def ex(s):
   p,t=s;b=board[t]
   for a,d in m.DIRS.items():yield(a,{}),(((p[0]+d[0]+l["belt"][0]+b[0])%m.W,(p[1]+d[1]+l["belt"][1]+b[1])%m.H),(t+1)%len(board))
  p=bfs((l["start"],0),lambda s:s[0]==l["goal"],ex);assert len(p)<30;out.append(p)
 return out
def plans_q114(m):return [[(a,{}) for a,e in l["demo"] if e] for l in m.LEVELS]
def plans_q124(m):return [[(l["map"][m.tactic(h)],{}) for h in l["hist"]] for l in m.LEVELS]
def plans_q134(m):return [[(m.relay(x,l["rules"]),{}) for x in l["signals"]] for l in m.LEVELS]
def plans_q144(m):return [[(5,{}),(6,{})]+[(a,{}) for a in l["route"]] for l in m.LEVELS]
def plans_q154(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["ops"])
  def ex(s):
   vals,c=s;yield(3,{}),(vals,(c-1)%n);yield(4,{}),(vals,(c+1)%n);yield(5,{}),(m.move(vals,l["caps"],l["ops"][c]),c)
  out.append(bfs((tuple(l["start"]),0),lambda s:s[0]==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q164(m):return [[(5,{})]*l["stop"]+[(l["choice"],{})] for l in m.LEVELS]
def plans_q174(m):
 out=[]
 for l in m.LEVELS:
  t=0;p=[]
  for _ in range(l["target"]):
   while t!=l["phase"]:p.append((2,{}));t=(t+1)%l["period"]
   p.append((1,{}));t=(t+1)%l["period"]
  out.append(p+[(5,{})])
 return out
def plans_q184(m):
 out=[]
 for l in m.LEVELS:
  c=0;p=[]
  for i in range(l["plots"]):
   if l["target"]&(1<<i):
    right=(i-c)%l["plots"];left=(c-i)%l["plots"];a=4 if right<=left else 3;p += [(a,{})]*min(right,left)+[(5,{})];c=i
  out.append(p+[(6,{})]*l["seasons"])
 return out
def plans_q194(m):
 out=[]
 for l in m.LEVELS:
  phase=0;p=[]
  for w in l["windows"]:
   while phase!=w:p.append((5,{}));phase=(phase+1)%l["period"]
   p.append((6,{}));phase=(phase+1)%l["period"]
  out.append(p)
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q104":[(5,{})],"q114":[(2,{})],"q124":[(4,{})],"q134":[(4,{})],"q144":[(1,{})],"q154":[(6,{})],"q164":[(1,{})],"q174":[(5,{})],"q184":[(6,{}),(6,{})],"q194":[(6,{})]}
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
def test_batch08_plans_and_losses():qualify()
def test_batch08_fuzz():
 rng=random.Random(8808)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch08_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch08_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch08-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
