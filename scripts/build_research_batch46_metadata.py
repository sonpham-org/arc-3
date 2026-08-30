"""Generate metadata, thumbnails, and the contact sheet for research Batch 46."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q220":("Vault Veil","observer-dependent-dynamics","attention-frozen-dual-resource-circulation-through-pressure-seals","A pale stone vault uses maroon chambers, paired resource rails, and pressure seals."),
"q251":("Pollen Pact","social-inference","social-response-inference-complemented-after-visible-wear","A cyan alpine meadow carries pink pollen kites and two convention rails."),
"q282":("Semaphore Probe","causal-intervention","budgeted-causal-identification-across-two-miniature-relay-systems","A lavender signal yard uses orange masts, green flags, and paired test bays."),
"q313":("Impeller Ledger","conservation-law-induction","global-rotor-stock-conservation-with-redundancy-priced-sampling","A gold turbine chamber shows three dark rotors and compact wake ledgers."),
"q344":("Tessera Survey","epistemic-resource-allocation","evidence-union-gated-interruption-of-a-compressed-topology-macro","A blue mosaic stages pink, cyan, and yellow seam samples around a white latch."),
"q375":("Vivarium Rig","tool-construction","dual-effect-habitat-assembly-under-partner-specific-reciprocity","A green terrarium builds colored component stacks above fauna route bars."),
"q406":("Crossing Delegation","distributed-partial-observability","disjoint-passenger-and-dock-projections-integrated-through-controller-marks","An orange river crossing separates passenger projections, dock evidence, and marks."),
"q437":("Spectrum Revision","nonstationary-rule-revision","wear-triggered-relational-algebra-revision-across-visual-domains","A white prism gallery transfers a worn rule between packet and symbolic domains."),
"q468":("Escapement Lineage","persistent-identity","causal-ancestry-through-gear-transforms-and-fault-discriminating-probes","A charcoal clock tower combines pale gears, ancestry trails, and intervention rails."),
"q500":("Workbench Dependency","hierarchical-goal-discovery","shared-fixture-prerequisites-with-helper-identity-bound-delayed-debt","A pink mobile workshop grows black fixtures from tools, helpers, and debt tokens.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games";out.mkdir(parents=True,exist_ok=True)
 for c,(title,axis,primary,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  g=getattr(m,c.upper())();frame=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];palette=sorted({int(v) for row in frame for v in row})
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before gathering discriminating state","tracks surface tokens without conservation, causal identity, or controller provenance","ignores the revised rule, evidence cost, reciprocity, or delayed identity debt"],"interface":{"actions":[1,2,3,4,5,6],"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":palette,"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Colored evidence, conservation, wear, controller, helper, and debt rails expose state without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");im=Image.new("RGB",(64,64));im.putdata([PAL[int(v)] for row in frame for v in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch46-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch46-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten cross-axis games coupling hidden dynamics, social revision, causal testing, conservation, evidence, construction, delegation, rule transfer, identity, and delayed obligation.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 (ROOT/".cache").mkdir(exist_ok=True);sheet.save(ROOT/".cache"/"batch46-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
