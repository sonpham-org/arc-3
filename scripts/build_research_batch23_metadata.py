"""Generate metadata and visual artifacts for research Batch 23."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q521":("Pollen Frame","multi-scale-reference-frames","moving-local-controls-complemented-after-visible-wear",[1,2,3,6],"Pollen crosses moving bloom frames before controls visibly complement."),
"q552":("Semaphore Lesson","policy-learning-from-demonstration","conditional-policy-from-noisy-miniature-relay-tests",[1,2,3,4,5,6],"Flag demonstrations cross occluded beams and two miniature systems."),
"q583":("Impeller Counter","adaptive-adversary","shape-stable-opponent-tactic-and-stop-sampling-safely",[1,2,3,4,5],"Blade treatments shape a visible counter-rotating opponent tactic."),
"q614":("Tessera Grammar","compositional-communication","relay-transformed-command-chunks-with-interrupt-window",[1,2,3,4,5,6],"Grouped mosaic commands cross topology seams and a macro window."),
"q645":("Vivarium Sandbox","counterfactual-planning","fair-reset-miniature-tests-before-one-policy-commit",[1,2,3,4,5],"Two terrariums preserve balanced evidence across physical resets."),
"q676":("Crossing Analogy","structural-analogy","dock-to-passenger-structure-through-alternating-marks",[1,2,3,4,5],"Dock relations transfer to passengers through alternating controllers."),
"q707":("Spectrum Evidence","confidence-calibration","reliability-stopping-transferred-from-geometry-to-agents",[1,2,5,6],"Prism evidence and packet evidence share one weighted algebra."),
"q738":("Escapement Gradient","continuous-quantity-reasoning","fault-diagnosed-conserved-distribution-over-gear-phase",[1,2,3,4,5,6],"Weights redistribute through fault-dependent nested gear phases."),
"q769":("Monsoon Obligation","long-horizon-credit-assignment","identity-debt-repaid-after-sparse-unequal-cycle-rewards",[1,2,3,4,5],"Rain-seed obligations survive rewards at sparse storm phase pairs."),
"q800":("Workbench Rhythm","temporal-abstraction","event-chunked-interrupt-with-helper-bound-delayed-debt",[1,2,3,4,5],"Workshop tools interrupt autonomous rhythms before repaying a helper.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,sil) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before the relevant state is identified","copies surface behavior instead of the structural rule","ignores the secondary progression constraint"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":sil,"spatial_grammar":sil,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch23-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch23-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten expanded-ledger games spanning the remaining axes and final domain offsets, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch23-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
