"""Generate metadata, thumbnails, and the contact sheet for research Batch 45."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q219":("Reedbed Veil","observer-dependent-dynamics","attention-scheduled-local-updates-with-connectivity-changing-causeways","A cyan marsh uses reed columns, beetle salinity bands, and bright causeways."),
"q250":("Vault Pact","social-inference","hidden-offer-conventions-under-dual-conservation-and-route-rewiring","A maroon catacomb presents three stone arches, paired resource ledgers, and echo carriers."),
"q281":("Pollen Probe","causal-intervention","budgeted-causal-signatures-complemented-after-visible-wear","A green alpine meadow shows tethered pollen kites and a visible wear front."),
"q312":("Semaphore Ledger","conservation-law-induction","global-stock-conservation-across-two-policy-testing-miniatures","An orange cliff yard stacks flags, relay beams, and three conserved stock bars."),
"q343":("Impeller Survey","epistemic-resource-allocation","nonredundant-evidence-union-before-an-irreversible-route-choice","A silver turbine chamber contrasts two rotors with wake-sample ribbons."),
"q374":("Tessera Rig","tool-construction","dual-effect-component-assembly-with-state-window-macro-interruption","A pink folding mosaic builds colored component stacks around a phase latch."),
"q405":("Vivarium Delegation","distributed-partial-observability","alternating-projections-with-persistent-marks-and-reciprocal-help","A white glass terrarium separates green fauna strata and controller marks."),
"q436":("Crossing Revision","nonstationary-rule-revision","wear-triggered-ferry-recalibration-across-disjoint-controller-views","A blue river crossing uses sandy banks, a white ferry, and passenger trails."),
"q467":("Spectrum Lineage","persistent-identity","causal-ancestry-through-split-merge-and-appearance-exchange","A yellow prism gallery carries colored packets along explicit ancestry trails."),
"q499":("Monsoon Dependency","hierarchical-goal-discovery","shared-weather-prerequisites-gated-by-unequal-cycle-phase-pairs","A magenta weather garden grows cyan clouds from seed, storm, and sun resources.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games";out.mkdir(parents=True,exist_ok=True)
 for c,(title,axis,primary,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  g=getattr(m,c.upper())();frame=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];palette=sorted({int(v) for row in frame for v in row})
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before gathering discriminating state","tracks visible tokens without the conserved, causal, identity, or controller invariant","ignores the late rule, topology, reciprocity, or phase constraint"],"interface":{"actions":[1,2,3,4,5,6],"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":palette,"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Colored evidence, phase, resource, and controller rails expose state without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");im=Image.new("RGB",(64,64));im.putdata([PAL[int(v)] for row in frame for v in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch45-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch45-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten light-background cross-axis games coupling attention, inference, intervention, conservation, evidence, construction, delegation, revision, identity, and hierarchy.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 (ROOT/".cache").mkdir(exist_ok=True);sheet.save(ROOT/".cache"/"batch45-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
