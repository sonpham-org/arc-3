"""Qualification and fuzz coverage for research Batch 31."""
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1];CODES=["q205","q236","q267","q298","q329","q360","q391","q422","q453","q485"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def plans_q205(m):return [[(a,{}) for a in x["plan"]]+[(6,{})] for x in m.LEVELS]
def plans_q236(m):return [[(a,{}) for a in x["need"]]+[(4,{})]*x["rule"]+[(5,{})] for x in m.LEVELS]
def plans_q267(m):
 out=[]
 for x in m.LEVELS:
  p=[]
  for i in range(0,len(x["need"]),x["cap"]):p += [(a,{}) for a in x["need"][i:i+x["cap"]]]+[(4,{})]
  out.append(p+[(5,{})]*x["model"]+[(6,{})])
 return out
def plans_q298(m):return [[(a,{}) for a in x["plan"]]+[(4,{}),(4,{}),(6,{})] for x in m.LEVELS]
def plans_q329(m):return [[y for a in x["solution"] for y in ((a,{}),(5,{}))]+[(6,{})] for x in m.LEVELS]
def plans_q360(m):
 out=[]
 for x in m.LEVELS:
  p=[];phase=[0,0]
  for module in x["modules"]:
   for a in module:
    p += [(5,{})]*((-phase[0])%x["mods"][0])+[(6,{})]*((-phase[1])%x["mods"][1]);p.append((a,{}));phase=[1%x["mods"][0],2%x["mods"][1]]
   p.append((4,{}))
  out.append(p)
 return out
def plans_q391(m):
 out=[]
 for x in m.LEVELS:
  target=x["clues"][0]^x["clues"][1];k=next(i for i in range(3) if 2*i%3==target);out.append([(1,{}),(2,{}),(1,{})]+[(3,{})]*k+[(6,{})])
 return out
def plans_q422(m):return [[(1,{})]*x["boundary"]+[(4,{}),(2,{})]+[(3,{})]*x["rule"]+[(6,{})] for x in m.LEVELS]
def plans_q453(m):
 out=[]
 for x in m.LEVELS:
  p=(0,1,2)
  for z in x["ops"]:p=m.transform(p,z)
  out.append([(a,{}) for a in x["ops"]]+[(3,{})]*p.index(x["ancestor"])+[(4,{})]*m.parity(x)+[(6,{})])
 return out
def plans_q485(m):
 out=[]
 for x in m.LEVELS:
  n=len(x["deps"]);cursor=0;p=[]
  for target in x["order"]:
   k=(cursor-target)%n;p += [(1,{})]*k;cursor=(cursor-k)%n;p.append((5,{}))
  out.append(p+[(6,{})])
 return out
PLANS={c:globals()["plans_"+c] for c in CODES};LOSS={c:[(6,{})] for c in CODES};LOSS.update({"q236":[(5,{})],"q360":[(4,{})]})
def valid(r):a=r.frame[-1];assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def qualify(write=False):
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[];plans=PLANS[c](m)
  for i,p in enumerate(plans):
   assert g.level_index==i,(c,i,g.level_index)
   for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
   levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
  assert r.state==GameState.WIN,(c,r.state);win={"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels};g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
  assert r.state==GameState.GAME_OVER,(c,r.state);loss={"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":dig(r)}
  if write:d=ROOT/"research"/"recordings";(d/f"{c}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(c,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")
def test_batch31_plans_and_losses():qualify()
def test_batch31_fuzz():
 rng=random.Random(31313)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch31_visuals():
 sig=set()
 for c in CODES:m=load(c);g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];sig.add(tuple(int(a[y,x]) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))));assert(a==5).mean()<.1
 assert len(sig)==10
def test_batch31_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch31-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for c in CODES:
  m=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());assert hashlib.sha256((ROOT/m["artifacts"]["source"]).read_bytes()).hexdigest()==m["artifacts"]["source_sha256"]
if __name__=="__main__":p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
