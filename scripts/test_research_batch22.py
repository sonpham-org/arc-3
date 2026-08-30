"""Qualification and recordings for research Batch 22."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q212","q243","q274","q305","q336","q367","q398","q429","q460","q491"]
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
def plans_q212(m):
 out=[]
 for l in m.LEVELS:
  target=(tuple(l["start"]),(0,1),0)
  for a in l["plan"]:target=m.advance(target,a,l["rates"])
  def ex(s):
   for a in (1,2,3):yield(a,{}),m.advance(s,a,l["rates"])
  out.append(bfs((tuple(l["start"]),(0,1),0),lambda s:s[:2]==target[:2],ex)+[(6,{})])
 return out
def plans_q243(m):
 out=[]
 for l in m.LEVELS:
  offers=[i%3+1 for i in range(l["probes"])];p=[(a,{}) for a in offers]
  if sum(m.RULES[l["rule"]][a-1] for a in offers)%2:p.append((4,{}))
  out.append(p+[(5,{}),(l["rule"]+1,{})])
 return out
def plans_q274(m):
 out=[]
 for l in m.LEVELS:
  outer=0;k=0
  while outer!=l["outer"]:outer=(outer+l["model"]+1)%4;k+=1;assert k<5
  out.append([(1,{}),(2,{})]+[(4,{})]*k+[(5,{})]*l["model"]+[(6,{})])
 return out
def plans_q305(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  def ex(s):
   vals,cursor,h=s;nxt=(cursor+1)%3
   yield(3,{}),(vals,nxt,h)
   for a in (1,2):
    if len(h)>=2 and h[-2:]==(a,a):continue
    v=list(vals)
    if a==1:
     if v[cursor]==0:continue
     v[cursor]-=1;v[nxt]+=1
    else:
     if v[nxt]==0:continue
     v[nxt]-=1;v[cursor]+=1
    yield(a,{}),(tuple(v),cursor,(h+(a,))[-2:])
  goal=lambda s:s[0]==tuple(l["target"]) and (len(s[2])<2 or s[2][-1]!=s[2][-2])
  try:p=bfs((tuple(l["start"]),0,()),goal,ex)
  except AssertionError as exc:raise AssertionError(f"q305 authored level {i+1} is unsolved") from exc
  out.append(p+[(6,{})])
 return out
def plans_q336(m):
 out=[]
 for l in m.LEVELS:
  n=l["n"];need=target=0;rot=0
  for a in l["plan"]:need|=m.rotate(l["masks"][a-1],rot,n);target+=l["delta"][a-1];rot=(rot+1)%n
  def ex(s):
   seen,used,r,meter=s
   if used<l["budget"]:
    for a,(mask,d) in enumerate(zip(l["masks"],l["delta"]),1):yield(a,{}),(seen|m.rotate(mask,r,n),used+1,(r+1)%n,meter+d)
   yield(5,{}),(seen,used,(r+1)%n,meter)
  out.append(bfs((0,0,0,0),lambda s:(s[0]&need)==need and s[3]==target,ex)+[(6,{})])
 return out
def plans_q367(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for a in l["target"]:p += [(a,{}),(4,{})]
  p += [(4,{})]*l["cursor"];out.append(p+[(5,{}),(6,{})])
 return out
def one_pass(pairs):return[x for a,b in pairs for x in ((a,{}),(3,{}),(b,{}),(3,{}))]
def plans_q398(m):return [one_pass(l["pairs"])+[(5,{})]+one_pass(l["pairs"])+[(6,{})] for l in m.LEVELS]
def plans_q429(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i in range(len(l["route"])):
   if i in l["build"]:p.append((4,{}))
   p.append((m.expected(l,i),{}))
  out.append(p)
 return out
def plans_q460(m):
 out=[]
 for i,l in enumerate(m.LEVELS):
  perm=[1,2,3]
  for a in l["ops"]:perm=m.transform(perm,a)
  ta,tb=tuple(l["a"]),tuple(l["b"]);sa=(sum(ta),0,0);sb=(sum(tb),0,0)
  def ex(s):
   a,b,cursor=s;nxt=(cursor+1)%3;yield(5,{}),(a,b,nxt)
   if a[cursor]>0:v=list(a);v[cursor]-=1;v[nxt]+=1;yield(3,{}),(tuple(v),b,cursor)
   if b[cursor]>0:v=list(b);v[cursor]-=1;v[nxt]+=1;yield(4,{}),(a,tuple(v),cursor)
  goal=lambda s:s[0]==ta and s[1]==tb and perm[s[2]]==l["target_id"]
  try:p=bfs((sa,sb,0),goal,ex)
  except AssertionError as exc:raise AssertionError(f"q460 authored level {i+1} is unsolved") from exc
  out.append([(a,{}) for a in l["ops"]]+p+[(6,{})])
 return out
def plans_q491(m):
 out=[]
 for l in m.LEVELS:
  p=[];cursor=0;completed=0;n=len(l["deps"])
  for node in range(n):p += [(2,{})]*((node-cursor)%n);cursor=node;p.append((4 if completed<l["wear"] else 5,{}));completed+=1
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS.update({"q243":[(5,{})],"q274":[(6,{})],"q305":[(6,{})],"q367":[(6,{})],"q398":[(6,{})],"q429":[(2,{})],"q460":[(6,{})],"q491":[(6,{})]})
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
def test_batch22_plans_and_losses():qualify()
def test_batch22_fuzz():
 rng=random.Random(22222)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch22_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch22_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch22-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
