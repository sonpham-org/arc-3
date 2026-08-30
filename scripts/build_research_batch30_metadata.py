"""Generate metadata and visual artifacts for research Batch 30."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q505":("Alloy Frame","multi-scale-reference-frames","billet-motion-composed-with-translating-rotating-force-lanes",[1,2,3,6],"Billets cross a foundry ring under moving force-frame controls."),
"q536":("Palimpsest Lesson","policy-learning-from-demonstration","conditional-policy-learning-separated-from-a-visible-failed-twin",[1,2,3,4,5,6],"Archive demonstrations mix context, no-op marks, and a near-miss trace."),
"q567":("Canopy Counter","adaptive-adversary","capacity-chunked-opponent-shaping-before-a-counter",[1,2,3,4,5],"Orchard tactics must be buffered and flushed without deadlock."),
"q598":("Breakwater Grammar","compositional-communication","grouped-relay-language-with-a-dormant-first-command",[1,2,3,4,5,6],"Harbor commands compose relay transforms while their first symbol changes commitment."),
"q629":("Strata Sandbox","counterfactual-planning","reversible-miniature-quarry-tests-with-persistent-evidence",[1,2,3,4,5],"Quarry simulations reset physical progress while preserving tested branches."),
"q660":("Spore Analogy","structural-analogy","relational-transfer-while-two-autonomous-colony-clocks-advance",[1,2,3,4,5],"Humidity transformations transfer to spores across unequal visible schedules."),
"q691":("Tapestry Evidence","confidence-calibration","weighted-safe-stopping-after-evidence-rewires-adjacency",[1,2,6],"Loom evidence changes cursor adjacency before a safe claim."),
"q722":("Lockwater Gradient","continuous-quantity-reasoning","conserved-barge-flow-with-causal-identity-exchange",[1,2,3,4,6],"Canal quantities remain conserved across a required carrier swap."),
"q753":("Murmuration Obligation","long-horizon-credit-assignment","delayed-identity-debt-guarded-by-redundant-parity",[1,2,3,4,5],"Flock debt survives rewards and one misleading wind-wake signal."),
"q784":("Moraine Rhythm","temporal-abstraction","macro-time-glacier-alignment-coupled-to-an-outer-token",[2,3,4,5,6],"Stone-raft rhythms align crevasse clocks while writing an outer token.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before resolving the hidden state","optimizes one mechanic while violating the coupled constraint","tracks surface appearance instead of causal structure"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch30-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch30-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten diagonal-domain games across the second ten research axes, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch30-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
