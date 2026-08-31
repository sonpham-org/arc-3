"""Qualification, replay, fuzz, visual, and artifact gates for the nine-game Batch 80 boundary set."""
import argparse,hashlib,json
import test_research_batch77 as base
ROOT=base.ROOT
CODES=["q704","q708","q709","q732","q735","q764","q765","q770","q797"]
LOSS={c:[(6,{})] for c in CODES}
def run(fn,*args):
 old_codes,old_loss=base.CODES,base.LOSS;base.CODES,base.LOSS=CODES,LOSS
 try:return fn(*args)
 finally:base.CODES,base.LOSS=old_codes,old_loss
def test_batch80_plans_and_losses():run(base.qualify)
def test_batch80_fuzz():run(base.test_batch77_fuzz)
def test_batch80_visuals():
 hashes=[];backgrounds=[]
 for c in CODES:
  m=base.load(c);g=getattr(m,c.upper())();r=g.perform_action(base.ActionInput(id=base.GameAction.RESET),raw=True);a=base.np.asarray(r.frame[-1]);hashes.append(base.dig(r));backgrounds.append(int(a[0,0]));assert len(base.np.unique(a))>=5
 assert len(set(hashes))==len(CODES) and len(set(backgrounds))==len(CODES)
 prior={hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"docs"/"static"/"img"/"games").glob("q*-v1.png") if p.stem.split("-",1)[0] not in CODES}
 current=[hashlib.sha256((ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").read_bytes()).hexdigest() for c in CODES]
 assert len(set(current))==len(CODES) and not prior.intersection(current)
def test_batch80_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch80-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for x in b["games"]:
  c=x["game_id"];meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());src=ROOT/meta["artifacts"]["source"]
  assert hashlib.sha256(src.read_bytes()).hexdigest()==x["source_sha256"]==meta["artifacts"]["source_sha256"]
  for key in ("thumbnail","win_recording","loss_recording"):assert (ROOT/meta["artifacts"][key]).is_file()
def test_batch80_recordings_replay_exactly():run(base.test_batch77_recordings_replay_exactly)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");run(base.qualify,p.parse_args().write_recordings)
