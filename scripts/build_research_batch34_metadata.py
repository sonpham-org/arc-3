"""Generate metadata and visual artifacts for research Batch 34."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q208":("Mirror Lanterns","observer-dependent-dynamics","physical-light-tracking-through-a-reflected-and-rotated-observer-frame",[1,2,3,6],"A violet mirror pavilion separates four physical lanterns from their apparent positions."),
"q239":("Chorus Market","social-inference","joint-inference-of-public-norm-and-private-trust-regime",[1,2,3,4,5,6],"A green market records bids while separate norm and trust indicators move."),
"q270":("Circuit Cautery","causal-intervention","timed-reversible-clamps-identify-parent-and-inversion-in-a-circuit",[1,2,3,4,5,6],"A burgundy circuit board records pulses from reversible wire clamps."),
"q301":("Color Foundry","conservation-law-induction","weighted-pigment-mass-conservation-across-mixing-and-lifo-splitting",[1,2,3,4,5,6],"A cyan foundry turns primary pigment pairs into weighted violet compounds."),
"q332":("Planetarium Keys","epistemic-resource-allocation","battery-limited-telescope-observations-under-filter-remapping",[1,2,3,4,5,6],"A magenta dome retains a nine-star map while filters rotate at recharge."),
"q363":("Clockwork Menagerie","tool-construction","ordered-creature-assembly-under-coupled-gear-phase-and-pawl-state",[1,2,3,4,5,6],"An orange workshop grows clockwork creatures from blue parts and yellow gears."),
"q394":("Hive Courier","distributed-partial-observability","ordered-comb-deposits-compress-two-private-dance-memories",[1,2,3,4,5,6],"A yellow hive links two bees through a persistent shared comb."),
"q425":("Ember Doctrine","nonstationary-rule-revision","banked-samples-span-a-heat-triggered-law-change-and-quench",[1,2,3,4,5,6],"A burgundy kiln banks old and new laws around an orange heat threshold."),
"q456":("Fossil Carousel","persistent-identity","specimen-provenance-under-independent-pose-and-plinth-transformations",[1,2,3,4,5,6],"A pink museum preserves fossil identity beneath reconstructed poses."),
"q488":("Temple Scaffold","hierarchical-goal-discovery","dependency-node-construction-with-stage-remapped-support-inputs",[1,2,3,4,5,6],"A magenta temple exposes scaffold dependencies and remapped supports.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before gathering the required state","reuses a control mapping after its latent frame changes","tracks visible tokens without the relevant invariant"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n")
  g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True)
  games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch34-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch34-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten invariant-and-evidence games across the first ten research axes, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch34-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
