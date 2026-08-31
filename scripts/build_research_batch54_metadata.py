"""Generate metadata, thumbnails, and the contact sheet for research Batch 54."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q229":("Monsoon Veil","observer-dependent-dynamics","attention-scheduled-rain-dynamics-under-two-unequal-weather-cycles","A white weather garden uses three cloud wells, moving rain seeds, and two phase rails."),
"q259":("Monsoon Pact","social-inference","hidden-offer-convention-committed-only-at-a-joint-weather-phase","A silver weather court stacks rain chambers above response, choice, and storm-cycle bands."),
"q289":("Monsoon Probe","causal-intervention","causal-weather-diagnosis-before-an-aligned-irreversible-repair","A gray storm laboratory places three cloud chambers above evidence and repair bands."),
"q319":("Monsoon Ledger","conservation-law-induction","conserved-rain-stock-transferred-under-two-unequal-storm-cycles","A charcoal reservoir ledger exposes three rain stocks and paired phase rails."),
"q349":("Monsoon Survey","epistemic-resource-allocation","budgeted-weather-evidence-collected-before-a-sparse-joint-cycle-policy","A red weather survey arranges three lenses above evidence and route rails."),
"q379":("Monsoon Rig","tool-construction","reusable-rain-instrument-assembly-under-dual-cycle-activation-windows","A black weather workshop grows colored parts beneath three storm cells."),
"q409":("Monsoon Delegation","distributed-partial-observability","two-reader-mark-integration-at-a-sparse-shared-weather-phase","A magenta forecast garden splits two observation windows above persistent marks."),
"q417":("Canopy Revision","nonstationary-rule-revision","wear-revised-orchard-law-through-a-capacity-limited-intermediate-store","A pink terraced orchard moves seed records through narrow shade and storage bins."),
"q447":("Canopy Lineage","persistent-identity","split-merge-ancestry-through-a-capacity-limited-orchard-store","An orange orchard traces seed lineage across a narrow two-pane store."),
"q529":("Monsoon Frame","multi-scale-reference-frames","moving-local-rain-controls-aligned-with-two-global-weather-cycles","A blue weather frame composes two rain shuttles with rotation, translation, and phase rails.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games";out.mkdir(parents=True,exist_ok=True)
 for c,(title,axis,primary,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS];g=getattr(m,c.upper())();frame=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];palette=sorted({int(v) for row in frame for v in row})
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"unequal-cycle-and-capacity-bottleneck-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["acts on elapsed time instead of tracking both visible phases","fills the intermediate store in a globally valid but locally deadlocking order","collapses the primary inference task into surface color matching"],"interface":{"actions":[1,2,3,4,5,6],"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":palette,"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Colored weather, phase, evidence, store, wear, lineage, frame, and commitment rails expose state without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");im=Image.new("RGB",(64,64));im.putdata([PAL[int(v)] for row in frame for v in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch54-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch54-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten games contrasting sparse two-cycle weather windows across seven capability axes with capacity-limited orchard revision and identity, then composing local and global weather frames.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 (ROOT/".cache").mkdir(exist_ok=True);sheet.save(ROOT/".cache"/"batch54-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
