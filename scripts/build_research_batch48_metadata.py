"""Generate metadata, thumbnails, and the contact sheet for research Batch 48."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q223":("Impeller Veil","observer-dependent-dynamics","focus-controlled-hidden-rotor-updates-with-redundancy-priced-wake-samples","A cobalt impeller chamber uses three dark rotors, bright blades, and sample-cost rails."),
"q231":("Aurora Pact","social-inference","hidden-offer-convention-under-visible-hysteretic-curtain-control","A violet aurora court uses pale curtains, suspended motes, and response ribbons."),
"q261":("Aurora Probe","causal-intervention","causal-ray-model-identification-under-hysteretic-control-sweeps","A rust-red ray chamber places luminous curtains above three intervention pylons."),
"q291":("Aurora Ledger","conservation-law-induction","conserved-crystal-transfer-through-hysteretic-stock-rotation","A deep-red crystal ledger exposes three conserved bins and paired direction rails."),
"q321":("Aurora Survey","epistemic-resource-allocation","bounded-distinct-sampling-across-hysteretic-observation-frames","A teal lens gallery divides three instruments beneath an amber curtain."),
"q351":("Aurora Rig","tool-construction","component-built-dual-effect-rigs-coupled-to-hysteretic-routing","A white aurora workshop grows colored part towers into horizontal crystal rigs."),
"q381":("Aurora Delegation","distributed-partial-observability","alternating-controller-marks-integrated-through-hysteretic-state","A purple delegation chamber stacks two partial views under a bright curtain."),
"q411":("Aurora Revision","nonstationary-rule-revision","wear-triggered-crystal-law-revision-with-delayed-hysteretic-calibration","A pink clockwork gallery couples crystal columns to wear, delay, and control rails."),
"q441":("Aurora Lineage","persistent-identity","split-merge-appearance-ancestry-through-hysteretic-reversal","A blue ancestry garden traces colored crystals through split and merge histories."),
"q503":("Ember Frame","multi-scale-reference-frames","finite-shared-fuel-across-local-motion-frame-transform-and-observation","A magenta kiln composes three heated vessels with frame, fuel, and evidence bands.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games";out.mkdir(parents=True,exist_ok=True)
 for c,(title,axis,primary,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS];g=getattr(m,c.upper())();frame=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];palette=sorted({int(v) for row in frame for v in row})
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"hysteresis-and-resource-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before gathering discriminating state","tracks visible appearance without hidden state or provenance","ignores redundancy cost, hysteresis, wear, ancestry, or shared resource depletion"],"interface":{"actions":[1,2,3,4,5,6],"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":palette,"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Colored evidence, cost, control, direction, wear, ancestry, and resource rails expose state without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");im=Image.new("RGB",(64,64));im.putdata([PAL[int(v)] for row in frame for v in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch48-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch48-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten games composing attention, convention, intervention, conservation, evidence, construction, delegation, revision, identity, and moving reference frames with hysteresis or finite shared resources.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 (ROOT/".cache").mkdir(exist_ok=True);sheet.save(ROOT/".cache"/"batch48-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
