"""Generate metadata and visual artifacts for research Batch 33."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q207":("Shadow Orchard","observer-dependent-dynamics","observer-relative-shadow-tracking-under-sun-dependent-hidden-motion",[1,2,3,6],"A green orchard stages red fruit, angular shadows, and a moving yellow sun."),
"q238":("Signal Banquet","social-inference","ordered-invitation-transcripts-identify-a-hidden-etiquette",[1,2,3,4,5,6],"An orange banquet table turns guest order into a visible social transcript."),
"q269":("Mycelium Override","causal-intervention","temporal-nutrient-pulses-discriminate-network-parent-and-polarity",[1,2,3,4,5,6],"A pink fungal bed records delayed effects from staged nutrient interventions."),
"q300":("Aquifer Tithe","conservation-law-induction","weighted-water-conservation-across-pumping-evaporation-and-condensation",[1,2,3,4,5,6],"A blue aquifer carries water into violet vapor and back without losing mass."),
"q331":("Lantern Census","epistemic-resource-allocation","persistent-census-evidence-under-base-triggered-sensor-remapping",[1,2,3,4,5,6],"A red street grid retains surveyed blocks while lantern orientation changes."),
"q362":("Kitewright","tool-construction","ordered-component-stitching-under-coupled-wind-and-tension",[1,2,3,4,5,6],"A cyan field exposes yellow kite components, wind, and string tension."),
"q393":("Submarine Chorus","distributed-partial-observability","ordered-acoustic-compression-over-two-local-tone-memories",[1,2,3,4,5,6],"A blue ocean separates two orange submarines and their shared sonar chorus."),
"q424":("Bloom Calendar","nonstationary-rule-revision","season-triggered-rule-revision-with-explicit-evidence-archiving",[1,2,3,4,5,6],"A green garden archives old and new flowering laws across seasons."),
"q455":("Puppet Provenance","persistent-identity","lineage-tracking-under-independent-costume-and-position-transformations",[1,2,3,4,5,6],"A burgundy stage preserves puppet strings beneath rotating costumes."),
"q487":("Archive Staircase","hierarchical-goal-discovery","ordered-subgoal-sequences-under-a-stage-shifting-glyph-dictionary",[1,2,3,4,5,6],"An orange archive climbs sealed steps while its glyph dictionary shifts.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before gathering the required state","replays a prior level after its mapping changes","tracks appearance rather than the latent causal or identity variable"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n")
  g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True)
  games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch33-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch33-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten colorful stage-and-landscape games across the first ten research axes, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch33-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
