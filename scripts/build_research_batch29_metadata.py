"""Generate metadata and visual artifacts for research Batch 29."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q204":("Honeycomb Veil","observer-dependent-dynamics","attention-scheduling-that-advances-nested-scent-clocks",[1,2,6],"Apiary focus freezes one courier while every observation advances two clocks."),
"q235":("Alloy Pact","social-inference","hidden-convention-inference-in-a-rotating-force-frame",[1,2,3,5],"Foundry offers reveal social rules through alternating measurement lanes."),
"q266":("Palimpsest Probe","causal-intervention","budgeted-causal-diagnosis-against-a-visible-near-miss",[1,2,3,4,5],"Archive probes distinguish direct, common, and coincident traces from a failed twin."),
"q297":("Canopy Ledger","conservation-law-induction","conserved-seed-routing-through-a-capacity-limited-store",[1,2,3,6],"Orchard mass moves globally through a narrow intermediate seed buffer."),
"q328":("Breakwater Survey","epistemic-resource-allocation","set-cover-sensing-with-a-dormant-first-observation",[1,2,3,4,5,6],"Harbor measurements cover channel evidence while the first sample changes a later gate."),
"q359":("Strata Rig","tool-construction","multi-effect-tool-assembly-with-reversible-physical-probing",[1,2,3,4,5,6],"Quarry modules are tested then physically undone without erasing knowledge."),
"q390":("Spore Delegation","distributed-partial-observability","complementary-mark-integration-at-sparse-dual-clock-events",[1,2,3,4,5,6],"Greenhouse controllers can mark their partial views only at shared events."),
"q421":("Tapestry Revision","nonstationary-rule-revision","wear-boundary-recalibration-after-an-adjacency-rewrite",[1,2,3,4,6],"Loom wear rewrites traversal before a sparse rule probe becomes valid."),
"q452":("Lockwater Lineage","persistent-identity","barge-ancestry-tracking-through-visible-carrier-exchange",[1,2,3,6],"Canal wake trails preserve causal barge identity across swaps."),
"q484":("Moraine Dependency","hierarchical-goal-discovery","order-sensitive-nested-prerequisites-coupled-to-an-outer-token",[1,2,5,6],"Glacier enclosure order writes a token used by the terminal dependency puzzle.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before resolving the hidden state","optimizes one mechanic while violating the coupled constraint","tracks surface appearance instead of causal structure"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch29-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch29-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten diagonal-domain games across the first ten research axes, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch29-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
