"""Generate metadata, thumbnails, and the contact sheet for research Batch 50."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q225":("Vivarium Veil","observer-dependent-dynamics","attention-scheduled-fauna-updates-conditioned-by-partner-favor","A gray stacked terrarium uses three horizontal strata, moving fauna, and favor rails."),
"q255":("Vivarium Pact","social-inference","hidden-colony-convention-with-reciprocity-conditioned-responses","A pink-violet vivarium court stacks fauna shelves above offer and response ribbons."),
"q285":("Vivarium Probe","causal-intervention","budgeted-causal-fauna-probes-with-reciprocal-irreversible-repair","A magenta diagnostic habitat places three fauna chambers above evidence and favor bars."),
"q293":("Ember Ledger","conservation-law-induction","conserved-vessel-stock-under-one-shared-operation-fuel","A violet kiln ledger exposes three vessel vaults, stock bars, heat, and fuel rails."),
"q323":("Ember Survey","epistemic-resource-allocation","heat-evidence-movement-and-commitment-sharing-one-fuel-reserve","A white-hot survey kiln arranges three lenses above evidence and remaining-fuel bars."),
"q353":("Ember Rig","tool-construction","dual-effect-kiln-assembly-and-repair-sharing-finite-fuel","A black kiln workshop grows colored component towers into heat-spanning rigs."),
"q383":("Ember Delegation","distributed-partial-observability","disjoint-controller-views-marks-and-handoffs-sharing-fuel","A dark-red kiln splits two broad vessel consoles with marks and a fuel rail."),
"q413":("Ember Revision","nonstationary-rule-revision","fuel-priced-recalibration-of-a-wear-revised-heat-law","A blue kiln diagnostic couples three vessel columns to wear, heat, and fuel bars."),
"q443":("Ember Lineage","persistent-identity","fuel-priced-split-merge-appearance-and-ancestry-tracking","A green kiln ancestry field traces vessel masks above selection and fuel rails."),
"q507":("Canopy Frame","multi-scale-reference-frames","moving-orchard-frame-through-a-capacity-limited-intermediate-store","A red orchard uses shade terraces, seed gliders, and a narrow framed storage rack.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games";out.mkdir(parents=True,exist_ok=True)
 for c,(title,axis,primary,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS];g=getattr(m,c.upper())();frame=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];palette=sorted({int(v) for row in frame for v in row})
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"reciprocity-fuel-and-capacity-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["spends shared fuel without preserving the required terminal operations","tracks surface appearance instead of partner state, conservation, or ancestry","ignores intermediate capacity or commits before evidence is sufficient"],"interface":{"actions":[1,2,3,4,5,6],"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":palette,"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Colored favor, evidence, fuel, wear, controller, lineage, frame, and capacity rails expose state without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");im=Image.new("RGB",(64,64));im.putdata([PAL[int(v)] for row in frame for v in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch50-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch50-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten games coupling reciprocity, shared finite fuel, and intermediate capacity to attention, convention, intervention, conservation, evidence, construction, delegation, revision, identity, and moving reference frames.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 (ROOT/".cache").mkdir(exist_ok=True);sheet.save(ROOT/".cache"/"batch50-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
