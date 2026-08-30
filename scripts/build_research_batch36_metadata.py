"""Generate metadata and visual artifacts for research Batch 36."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q210":("Aurora Parallax","observer-dependent-dynamics","physical-aurora-band-tracking-through-a-polar-view-frame",[1,2,3,6],"A blue sky separates three luminous aurora bands from a polar observation marker."),
"q241":("Festival Oaths","social-inference","role-and-mood-inference-from-path-dependent-public-replies",[1,2,3,4,5,6],"An orange festival records replies whose meaning changes with the questioning path."),
"q272":("Geode Resonance","causal-intervention","ordered-crystal-strikes-reveal-parent-polarity-and-hysteresis",[1,2,3,4,5,6],"A pink cavern records echoes from crystals with persistent causal memory."),
"q303":("Loom Dye Ledger","conservation-law-induction","weighted-dye-conservation-through-lifo-braiding-and-unbraiding",[1,2,3,4,5,6],"A cyan loom turns primary dyes into weighted braids without losing material."),
"q334":("Meteor Survey","epistemic-resource-allocation","charge-limited-spectrum-passes-under-orbital-filter-remapping",[1,2,3,4,5,6],"A burgundy sky preserves a nine-cell meteor survey while spectra rotate."),
"q365":("Orchestra Workshop","tool-construction","instrument-assembly-with-component-dependent-beat-and-mute-transitions",[1,2,3,4,5,6],"An orange stage grows instruments from parts under beat and mute constraints."),
"q396":("Coral Signal","distributed-partial-observability","destructive-directional-relays-between-two-partial-reef-observers",[1,2,3,4,5,6],"A cyan reef makes local memories vanish when their signals enter the shared channel."),
"q427":("Eclipse Law","nonstationary-rule-revision","observation-advances-the-eclipse-boundary-being-inferred",[1,2,3,4,5,6],"A green plain banks laws while every observation advances the eclipse."),
"q458":("Caravan Seals","persistent-identity","ownership-tracking-under-independent-cargo-and-seal-transformations",[1,2,3,4,5,6],"A burgundy camp separates persistent ownership from changing crate seals."),
"q490":("Cavern Charter","hierarchical-goal-discovery","dependency-chamber-construction-with-stage-remapped-keystones",[1,2,3,4,5,6],"A pink cavern exposes nested chambers and remapped structural keystones.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,silhouette) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before gathering the required state","ignores path-dependent or destructive state transitions","tracks visible tokens without the relevant invariant"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":silhouette,"spatial_grammar":silhouette,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1]
  im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch36-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch36-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten path-dependent and state-destructive games across the first ten research axes, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):
  im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch36-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
