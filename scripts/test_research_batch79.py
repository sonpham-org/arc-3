"""Qualification, replay, fuzz, visual, and artifact gates for Batch 79."""
import argparse,hashlib,json
import test_research_batch77 as base
ROOT=base.ROOT
CODES=["q560","q585","q588","q602","q615","q631","q642","q661","q679","q702"]
LOSS={c:[(6,{})] for c in CODES}
def run(fn,*args):
 old_codes,old_loss=base.CODES,base.LOSS;base.CODES,base.LOSS=CODES,LOSS
 try:return fn(*args)
 finally:base.CODES,base.LOSS=old_codes,old_loss
def test_batch79_plans_and_losses():run(base.qualify)
def test_batch79_fuzz():run(base.test_batch77_fuzz)
def test_batch79_visuals():run(base.test_batch77_visuals)
def test_batch79_artifacts():
 b=json.loads((ROOT/"research"/"gpt-batch79-v1.json").read_text());assert[x["game_id"] for x in b["games"]]==CODES
 for x in b["games"]:
  c=x["game_id"];meta=json.loads((ROOT/"research"/"games"/f"{c}-v1.json").read_text());src=ROOT/meta["artifacts"]["source"]
  assert hashlib.sha256(src.read_bytes()).hexdigest()==x["source_sha256"]==meta["artifacts"]["source_sha256"]
  for key in ("thumbnail","win_recording","loss_recording"):assert (ROOT/meta["artifacts"][key]).is_file()
def test_batch79_recordings_replay_exactly():run(base.test_batch77_recordings_replay_exactly)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--write-recordings",action="store_true");run(base.qualify,p.parse_args().write_recordings)
