"""Qualification, replay generation, fuzzing, and artifact gates for Batch 46."""
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
import numpy as np
from arcengine import ActionInput,GameAction,GameState
ROOT=Path(__file__).resolve().parents[1]
CODES=["q220","q251","q282","q313","q344","q375","q406","q437","q468","q500"]
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def simple(m):return [[(a,{}) for a in x["plan"]]+[(6,{})] for x in m.LEVELS]
def plans_q251(m):return [[(a,{}) for a in x["before"]]+[(4,{})]+[(a,{}) for a in x["after"]]+[(5,{})]*x["rule"]+[(6,{})] for x in m.LEVELS]
def plans_q282(m):return [[(a,{}) for a in x["a"]]+[(4,{})]+[(a,{}) for a in x["b"]]+[(5,{})]*x["model"]+[(6,{})] for x in m.LEVELS]
def plans_q468(m):return [[(a,{}) for a in x["ops"]]+[(4,{})]*x["probes"]+[(5,{})]*x["ancestor"]+[(6,{})] for x in m.LEVELS]
def plans_q500(m):
 out=[]
 for x in m.LEVELS:
  cursor=helper=0;p=[];n=len(x["nodes"])
  for target in x["order"]:
   p += [(5,{})]*((target-cursor)%n);cursor=target
   need=x["nodes"][target][1]
   for i,count in enumerate(need):p += [(i+1,{})]*count
   want=x["nodes"][target][2];p += [(4,{})]*((want-helper)%3);helper=want;p.append((6,{}))
  out.append(p)
 return out
PLANS={c:simple for c in CODES};PLANS.update(q251=plans_q251,q282=plans_q282,q468=plans_q468,q500=plans_q500)
LOSS={c:[(6,{})] for c in CODES}
def valid(r):
 a=np.asarray(r.frame[-1]);assert a.shape==(64,64) and 0<=int(a.min())<=int(a.max())<=15
def dig(r):return hashlib.sha256(np.asarray(r.frame[-1],dtype=np.uint8).tobytes()).hexdigest()
def qualify(write=False):
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);levels=[];plans=PLANS[c](m)
  for i,p in enumerate(plans):
   assert g.level_index==i,(c,i,g.level_index)
   for a,d in p:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True);valid(r)
   levels.append({"level":i+1,"actions":[[a] for a,_ in p],"post_transition_frame_sha256":dig(r)})
  assert r.state==GameState.WIN,(c,r.state);win={"schema_version":1,"game_id":f"{c}-v1","expected_state":"WIN","levels":levels}
  g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for a,d in LOSS[c]:r=g.perform_action(ActionInput(id=GameAction.from_id(a),data=d),raw=True)
  assert r.state==GameState.GAME_OVER,(c,r.state);loss={"schema_version":1,"game_id":f"{c}-v1","expected_state":r.state.value,"actions":[[a] for a,_ in LOSS[c]],"terminal_frame_sha256":dig(r)}
  if write:
   d=ROOT/"research"/"recordings";d.mkdir(parents=True,exist_ok=True);(d/f"{c}-v1-win.json").write_text(json.dumps(win,indent=2)+"\n");(d/f"{c}-v1-loss.json").write_text(json.dumps(loss,indent=2)+"\n")
  print(c,"levels",len(plans),"actions",sum(map(len,plans)),"qualified")
def test_batch46_plans_and_losses():qualify()
def test_batch46_fuzz():
 rng=random.Random(464646)
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
  for _ in range(500):
   if r.state in (GameState.WIN,GameState.GAME_OVER):r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True)
   r=g.perform_action(ActionInput(id=GameAction.from_id(rng.randrange(1,7)),data={}),raw=True);valid(r)
def test_batch46_visuals():
 hashes=[];backgrounds=[]
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);a=np.asarray(r.frame[-1]);hashes.append(dig(r));backgrounds.append(int(a[0,0]));assert len(np.unique(a))>=5
 assert len(set(hashes))==10 and len(set(backgrounds))==10
def test_batch46_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch46-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for x in b["games"]:
  c=x["game_id"];meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());src=ROOT/meta["artifacts"]["source"]
  assert hashlib.sha256(src.read_bytes()).hexdigest()==x["source_sha256"]==meta["artifacts"]["source_sha256"]
  for key in ("thumbnail","win_recording","loss_recording"):assert (ROOT/meta["artifacts"][key]).is_file()
def test_batch46_recordings_replay_exactly():
 for c in CODES:
  m=load(c);g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);win=json.loads((ROOT/"research"/"recordings"/f"{c}-v1-win.json").read_text())
  for level in win["levels"]:
   for action in level["actions"]:r=g.perform_action(ActionInput(id=GameAction.from_id(action[0]),data={}),raw=True)
   assert dig(r)==level["post_transition_frame_sha256"]
  assert r.state==GameState.WIN
  g=getattr(m,c.upper())();r=g.perform_action(ActionInput(id=GameAction.RESET),raw=True);loss=json.loads((ROOT/"research"/"recordings"/f"{c}-v1-loss.json").read_text())
  for action in loss["actions"]:r=g.perform_action(ActionInput(id=GameAction.from_id(action[0]),data={}),raw=True)
  assert r.state==GameState.GAME_OVER and dig(r)==loss["terminal_frame_sha256"]
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");qualify(p.parse_args().write_recordings)
