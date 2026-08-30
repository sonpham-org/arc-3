"""Generate metadata and visual artifacts for research Batch 26."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q202":("Tide Veil","observer-dependent-dynamics","attention-scheduled-updates-under-reversing-coupled-currents",[1,2,6],"Two tidal pools alternate frozen and hidden carrier updates."),
"q233":("Ember Pact","social-inference","resource-priced-probing-of-a-stable-hidden-group-convention",[1,2,3,4,5],"Ceramic vessels answer offers through convention-specific stored heat bands."),
"q264":("Honeycomb Probe","causal-intervention","budgeted-transmission-diagnosis-across-nested-local-and-outer-clocks",[1,2,3,5],"Apiary probes separate direct transmission, shared cause, and coincidence."),
"q295":("Alloy Ledger","conservation-law-induction","conserved-routing-under-translating-rotating-local-controls",[1,2,3,4,6],"Foundry billets redistribute globally while controls rotate through local lanes."),
"q326":("Palimpsest Survey","epistemic-resource-allocation","bounded-set-cover-observation-of-overwritten-traces",[1,2,3,4,5],"Archive measurements expose selected unions of overwritten shelf evidence."),
"q357":("Canopy Rig","tool-construction","capacity-bounded-assembly-of-multi-effect-reusable-modules",[1,2,3,4,6],"Orchard components become ordered glider modules through a narrow store."),
"q388":("Breakwater Delegation","distributed-partial-observability","alternating-complementary-views-integrated-by-persistent-marks",[1,2,3,4,5,6],"Harbor controllers merge complementary skiff evidence across persistent marks."),
"q419":("Strata Revision","nonstationary-rule-revision","wear-boundary-recalibration-with-knowledge-persisting-after-undo",[1,3,4,5,6],"Quarry probes are physically reversed while their rule evidence remains."),
"q450":("Spore Lineage","persistent-identity","ancestry-tracking-through-appearance-exchange-and-unequal-clocks",[1,2,3,6],"Greenhouse colonies exchange places while causal trails preserve ancestry."),
"q482":("Lockwater Dependency","hierarchical-goal-discovery","identity-conditioned-prerequisites-with-mid-solve-adjacency-rewrite",[1,2,3,5,6],"Canal prerequisites share locks after identity exchange and route rewiring.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games";out.mkdir(parents=True,exist_ok=True)
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before resolving the hidden state","optimizes one mechanic while violating the coupled constraint","tracks surface appearance instead of causal structure"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch26-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch26-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten expanded-ledger games across the first ten research axes at fresh domain offsets, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch26-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
