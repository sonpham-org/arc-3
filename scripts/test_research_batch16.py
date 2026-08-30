"""Qualification and recordings for research Batch 16."""
from itertools import combinations
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q107","q116","q126","q136","q146","q156","q166","q176","q186","q196"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def cyc(cur,target,n,left,right):
 r=(target-cur)%n;l=(cur-target)%n;return ([(right,{})]*r,target) if r<=l else ([(left,{})]*l,target)
def plans_q107(m):return [[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q116(m):
 out=[]
 for l in m.LEVELS:
  t=l["rules"][l["target"]];best=None
  for size in range(1,l["limit"]+1):
   for bits in combinations(range(l["examples"]),size):
    if all(i==l["target"] or any(((t>>b)&1)!=((v>>b)&1) for b in bits) for i,v in enumerate(l["rules"])):best=bits;break
   if best is not None:break
  assert best is not None;p=[];cur=0
  for b in best:z,cur=cyc(cur,b,l["examples"],1,2);p+=z+[(5,{})]
  z,_=cyc(0,l["target"],len(l["rules"]),3,4);out.append(p+z+[(6,{})])
 return out
def plans_q126(m):return [[(a,{}) for a in l["target"]]+[(1,{})] for l in m.LEVELS]
def plans_q136(m):
 return [[(a,{}) for t in l["target"] for a in m.survivor_code(t,l["drop"])] for l in m.LEVELS]
def plans_q146(m):return [[x for b in l["path"] for x in ((5,{}),(b+1,{}))]+[(6,{})] for l in m.LEVELS]
def plans_q156(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,g in enumerate(l["gates"]):
   p.append((m.evaluate(g)+1,{}))
   if i<len(l["gates"])-1:p.append((4,{}))
  out.append(p+[(6,{})])
 return out
def plans_q166(m):
 out=[]
 for l in m.LEVELS:
  p=[]
  for i,a in enumerate(l["route"]):
   if i==l["checkpoint"]:p.append((5,{}))
   p.append((a,{}))
  out.append(p+[(6,{})])
 return out
def plans_q176(m):return [[(a,{}) for a in l["plan"]]+[(6,{})] for l in m.LEVELS]
def plans_q186(m):return [[(a,{}) for a in l["target"]]+[(5,{})]*l["delay"] for l in m.LEVELS]
def plans_q196(m):return [[x for a in l["events"] for x in ((a,{}),(5,{}))] for l in m.LEVELS]
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS["q126"]=[(2,{}),(1,{})];LOSS["q136"]=[(3,{})];LOSS["q186"]=[(2,{}),(5,{})];LOSS["q196"]=[(2,{}),(5,{})]
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
def test_batch16_plans_and_losses():qualify()
def test_batch16_fuzz():
 rng=random.Random(16161)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch16_visuals():
 sig=set()
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch16_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch16-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/meta["artifacts"]["source"]).read_bytes()).hexdigest()==meta["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
