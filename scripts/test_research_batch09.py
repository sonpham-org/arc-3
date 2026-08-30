"""Qualification and recordings for research Batch 09."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q006","q015","q025","q035","q045","q055","q065","q075","q085","q095"]
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
def plans_q006(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["ops"])
  def ex(s):
   vals,c,w=s;yield(3,{}),(vals,(c-1)%n,w);yield(4,{}),(vals,(c+1)%n,w)
   for a,i in ((1,l["ops"][c][0]),(2,l["ops"][c][1])):
    z=set(w);z.symmetric_difference_update({i});yield(a,{}),(vals,c,frozenset(z))
   yield(5,{}),(m.move(vals,l["ops"][c],w),c,w)
  out.append(bfs((tuple(l["start"]),0,frozenset()),lambda s:s[0]==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q015(m):return [[(m.reply(h,l["rule"]),{}) for h in l["hist"]] for l in m.LEVELS]
def plans_q025(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["start"])
  def ex(s):
   vals,c=s;yield(3,{}),(vals,(c-1)%n);yield(4,{}),(vals,(c+1)%n);yield(5,{}),(m.turn(vals,l["links"],c),c)
  out.append(bfs((tuple(l["start"]),0),lambda s:s[0]==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q035(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["ops"])
  def ex(s):
   vals,c=s;yield(3,{}),(vals,(c-1)%n);yield(4,{}),(vals,(c+1)%n);yield(5,{}),(m.collide(vals,l["ops"][c]),c)
  out.append(bfs((tuple(l["start"]),0),lambda s:s[0]==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q045(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["rays"])
  def ex(s):
   seen,c,b=s;yield(3,{}),(seen,(c-1)%n,b);yield(4,{}),(seen,(c+1)%n,b)
   if b:yield(5,{}),(seen|l["rays"][c],c,b-1)
  out.append(bfs((0,0,l["bank"]),lambda s:s[0]&l["target"]==l["target"],ex)+[(6,{})])
 return out
def plans_q055(m):
 out=[]
 for l in m.LEVELS:
  c=0;p=[]
  for i in l["need"]:
   right=(i-c)%l["segments"];left=(c-i)%l["segments"];a=4 if right<=left else 3;p += [(a,{})]*min(right,left)+[(5,{})];c=i
  out.append(p+[(6,{})])
 return out
def plans_q065(m):return [[x for item in l["items"] for x in ((5,{}),(1 if item[0]==item[1] else 2,{}))] for l in m.LEVELS]
def plans_q075(m):return [[((x if i<l["wear"] else 1-x)+1,{}) for i,x in enumerate(l["cues"])] for l in m.LEVELS]
def plans_q085(m):
 out=[]
 for l in m.LEVELS:
  c=0;p=[]
  for q in l["query"]:
   i=l["trails"].index(q);right=(i-c)%len(l["trails"]);left=(c-i)%len(l["trails"]);a=4 if right<=left else 3;p += [(a,{})]*min(right,left)+[(6,{})];c=i
  out.append(p)
 return out
def plans_q095(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i in range(l["nodes"]):p.append((5,{}));p += [] if i==l["nodes"]-1 else [(4,{})]
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
LOSS={"q006":[(6,{})],"q015":[(1,{})],"q025":[(6,{})],"q035":[(6,{})],"q045":[(6,{})],"q055":[(6,{})],"q065":[(1,{})],"q075":[(2,{})],"q085":[(4,{}),(6,{})],"q095":[(6,{})]}
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
def test_batch09_plans_and_losses():qualify()
def test_batch09_fuzz():
 rng=random.Random(8909)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch09_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch09_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch09-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
