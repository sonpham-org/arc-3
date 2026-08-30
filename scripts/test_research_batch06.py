"""Qualification and recording generation for research Batch 06."""
from collections import deque
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q103","q113","q123","q133","q143","q153","q163","q173","q183","q193"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def bfs(start,solved,expand):
 q=deque([start]);par={start:None};act={}
 while q:
  s=q.popleft()
  if solved(s):
   out=[]
   while par[s] is not None:out.append(act[s]);s=par[s]
   return out[::-1]
  for a,n in expand(s):
   if n not in par:par[n]=s;act[n]=a;q.append(n)
 raise AssertionError("unsolved authored level")
def plans_q103(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   p,i,o=s
   for a in range(1,5):
    dx,dy=m.DIRS[(a-1+i+o)%4];n=(p[0]+dx,p[1]+dy);n=n if 0<=n[0]<m.W and 0<=n[1]<m.H and n not in l["walls"] else p;yield(a,{}),(n,i,o)
   yield(5,{}),(p,(i+1)%4,o);yield(6,{}),(p,i,(o-1)%4)
  p=bfs((l["start"],l["inner"],l["outer"]),lambda s:s[0]==l["goal"],ex);assert len(p)<l["budget"];out.append(p)
 return out
def plans_q113(m):return [[((l["a"] if t==0 else l["b"])[s],{}) for t,s in l["items"]] for l in m.LEVELS]
def plans_q123(m):
 out=[]
 for l in m.LEVELS:
  def ex(s):
   p,last=s
   for a,(dx,dy) in m.DIRS.items():
    n=p;nl=last
    if a!=last:
     z=(p[0]+dx,p[1]+dy)
     if 0<=z[0]<m.W and 0<=z[1]<m.H and z not in l["walls"]:n=z;nl=a
    yield(a,{}),(n,nl)
  p=bfs((l["start"],0),lambda s:s[0]==l["goal"],ex);assert len(p)<24+len(out)*4;out.append(p)
 return out
def plans_q133(m):return [[(m.decode(x),{}) for x in l["items"]] for l in m.LEVELS]
def plans_q143(m):
 out=[]
 for l in m.LEVELS:
  cur=1;p=[]
  for i,target in enumerate(l["route"]):
   right=(target-cur)%4;left=(cur-target)%4;a=4 if right<=left else 3;p += [(a,{})]*min(right,left);cur=target
   if i in l["ambiguous"]:p.append((5,{}))
   p.append((6,{}))
  out.append(p)
 return out
def plans_q153(m):return [[(m.permutation(l["swaps"])[s]+1,{}) for s in l["signals"]] for l in m.LEVELS]
def plans_q163(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,v in enumerate(l["assign"]):p.append((v+1,{}));p += [] if i==len(l["assign"])-1 else [(4,{})]
  out.append(p+[(6,{})])
 return out
def plans_q173(m):
 out=[]
 for l in m.LEVELS:
  n=len(l["ops"])
  def ex(s):
   vals,c=s;yield(3,{}),(vals,(c-1)%n);yield(4,{}),(vals,(c+1)%n);yield(5,{}),(m.drift(vals,l["ops"][c]),c)
  out.append(bfs((tuple(l["start"]),0),lambda s:s[0]==tuple(l["target"]),ex)+[(6,{})])
 return out
def plans_q183(m):return [[(1 if x else 2,{}) for x in l["choices"]]+[(6,{})] for l in m.LEVELS]
def plans_q193(m):
 out=[]
 for l in m.LEVELS:out.append([(a,{}) for a in l["motif"]]+[(5,{})]+[(6,{})]*(l["repeats"]-1)+[(a,{}) for a in l["suffix"]])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES}
def loss(c,m):
 if c=="q103":return [(3,{})]*m.LEVELS[0]["budget"]
 if c=="q123":return [(1,{})]*24
 if c=="q113":return [(((m.LEVELS[0]["a"][m.LEVELS[0]["items"][0][1]])%4+1),{})]
 if c in ("q133","q153","q183","q193"):return [((m.decode(m.LEVELS[0]["items"][0])%4+1 if c=="q133" else 4 if c=="q153" else 2 if c=="q183" else 4),{})]
 return [(6,{})]
def valid(r):g=r.frame[-1];assert g.shape==(64,64) and 0<=int(g.min())<=int(g.max())<=15
def digest(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def runwin(c,m,plans):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[]
 for i,p in enumerate(plans):
  assert g.level_index==i
  for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
  levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":digest(r)})
 assert r.state==GameState.WIN;return{"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels}
def runloss(c,m):
 g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);p=loss(c,m)
 for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
 assert r.state==GameState.GAME_OVER,(c,r.state);return{"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in p],"terminal_frame_sha256":digest(r)}
def qualify(write=False):
 for c in CODES:
  m=load(c);p=PLANS[c](m);w=runwin(c,m,p);l=runloss(c,m)
  if write:
   d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(w,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(l,indent=2)+"\n")
  print(c,"levels",len(p),"actions",sum(map(len,p)),"qualified")
def test_batch06_plans_and_losses():qualify()
def test_batch06_fuzz():
 rng=random.Random(8606)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch06_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);a=r.frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert (a==5).mean()<.1
 assert len(sig)==10
def test_batch06_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch06-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  m=load(c);meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
