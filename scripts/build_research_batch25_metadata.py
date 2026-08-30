"""Generate metadata and visual artifacts for research Batch 25."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q501":("Aurora Frame","multi-scale-reference-frames","local-motion-composed-with-translating-rotating-hysteretic-frames",[1,2,3,6],"Polar motes cross a translating aurora frame whose trail retains motion history."),
"q532":("Tide Lesson","policy-learning-from-demonstration","conditional-policy-learning-with-irrelevant-demonstration-gestures",[1,2,3,4,5,6],"Tidal demonstrations mix contextual policy evidence with visible no-op gestures."),
"q563":("Ember Counter","adaptive-adversary","recent-action-opponent-shaping-under-a-shared-resource-budget",[1,2,3,4],"Kiln treatments shape a reactive rival before a budgeted counterstroke."),
"q594":("Honeycomb Grammar","compositional-communication","grouped-relay-language-under-nested-local-and-outer-clocks",[1,2,3,4,5],"Apiary relays transform grouped nectar commands as two clocks advance."),
"q625":("Alloy Sandbox","counterfactual-planning","persistent-miniature-evidence-under-resetting-moving-reference-frames",[1,2,3,4,5],"Foundry sandboxes reset their physical state while causal evidence persists."),
"q656":("Palimpsest Analogy","structural-analogy","relation-transfer-between-transformed-archives-with-a-visible-near-miss",[1,2,3,4],"Scraped folios transfer one route structure while displaying a false analogy."),
"q687":("Canopy Evidence","confidence-calibration","bounded-weighted-evidence-with-provably-safe-early-stopping",[1,2,3,5,6],"Weighted orchard samples must be flushed and stopped only at a safe margin."),
"q718":("Breakwater Gradient","continuous-quantity-reasoning","conserved-distribution-routing-with-a-dormant-early-intervention",[1,2,3,4,5,6],"Harbor quantities remain conserved while an early sluice shifts a later phase."),
"q749":("Strata Obligation","long-horizon-credit-assignment","identity-bound-obligation-surviving-physical-causal-undo",[1,2,3,4,5],"A borrowed quarry tool creates a debt remembered after the shaft is undone."),
"q780":("Spore Rhythm","temporal-abstraction","dual-autonomous-clocks-aligned-through-interruptible-macro-time",[3,4,5,6],"Greenhouse cycles combine local ticks with required three-beat macro bursts.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games";out.mkdir(parents=True,exist_ok=True)
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before resolving the hidden state","optimizes one mechanic while violating the coupled constraint","tracks surface appearance instead of causal structure"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch25-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch25-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten expanded-ledger games covering the next ten research axes, each with six progressive levels and a distinct visual environment.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch25-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
