"""Generate metadata and visual artifacts for research Batch 42."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q216":("Backstage Veil","observer-dependent-dynamics","attention-frozen-scenes-with-signed-threshold-accumulation",[1,2,3,4,5,6],"A pink theater combines focused scenes, hidden actor motion, and a signed meter."),
"q247":("Catalyst Pact","social-inference","latent-convention-offers-that-store-later-executed-orientations",[1,2,3,4,5,6],"An orange refinery separates offered beads from stored pipe orientations."),
"q278":("Asterism Probe","causal-intervention","evidence-preserving-reset-between-causal-experiment-and-repair",[1,2,3,4,5,6],"A dark orbital chart preserves luminous evidence across a physical reset."),
"q309":("Reedbed Ledger","conservation-law-induction","globally-conserved-salinity-with-transfer-rewired-connectivity",[1,2,3,4,5,6],"A green marsh moves conserved salt while every transfer rewires the route."),
"q340":("Vault Survey","epistemic-resource-allocation","bounded-echo-union-under-two-shared-conserved-quantities",[1,2,3,4,5,6],"A burgundy vault tracks echo evidence, remaining mass, and accumulated charge."),
"q371":("Pollen Rig","tool-construction","self-modifying-assembly-across-a-visible-complement-rule-change",[1,2,3,4,5,6],"A green meadow grows hardware across a visible wear-triggered rule complement."),
"q402":("Semaphore Delegation","distributed-partial-observability","alternating-destructive-relays-before-one-irreversible-policy",[1,2,3,4,5,6],"An orange cliff yard alternates controller marks as local flags vanish."),
"q433":("Impeller Revision","nonstationary-rule-revision","sparse-two-sample-recalibration-under-growing-sample-cost",[1,2,3,4,5,6],"A magenta turbine exposes wear, banked laws, and exact sample cost."),
"q464":("Tessera Lineage","persistent-identity","ancestor-tracking-with-state-window-macro-interruption",[1,2,3,4,5,6],"A pink mosaic preserves ancestry trails across folds and seam windows."),
"q496":("Crossing Dependency","hierarchical-goal-discovery","shared-prerequisite-construction-from-alternating-partial-controllers",[1,2,3,4,5,6],"A blue ferry stacks dependent docks above controller-specific evidence.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before gathering the required state","ignores reset-persistent, controller, wear, or identity state","tracks visible tokens without the relevant invariant"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1]
  im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch42-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch42-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten compound games across the first ten research axes, each with six progressive levels and a coupled secondary mechanic.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch42-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
