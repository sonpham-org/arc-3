"""Generate metadata and visual artifacts for research Batch 22."""
import hashlib,importlib.util,json
from PIL import Image,ImageDraw
from arcengine import ActionInput,GameAction
from build_research_batch06_metadata import ROOT,SESSION,PAL
CFG={
"q212":("Lockwater Veil","observer-dependent-dynamics","hidden-identity-updates-under-swapped-appearances",[1,2,3,6],"Barges swap appearance while attention freezes one causal identity."),
"q243":("Murmuration Pact","social-inference","parity-checked-convention-inference-with-one-misleading-response",[1,2,3,4,5],"Flocks answer offers beneath a redundant parity signal."),
"q274":("Moraine Probe","causal-intervention","budgeted-link-diagnosis-coupled-to-outer-progress",[1,2,3,4,5,6],"Stone rafts expose hidden links while local repairs change an outer token."),
"q305":("Waystation Ledger","conservation-law-induction","conserved-supply-routing-against-repetition-counter",[1,2,3,6],"Supply columns move among caravan walkers under a visible counter."),
"q336":("Backstage Survey","epistemic-resource-allocation","rotating-sightline-coverage-with-directed-influence",[1,2,3,4,5,6],"Mask sightlines accumulate signed influence across a rotating theater."),
"q367":("Catalyst Rig","tool-construction","orientation-memory-executes-a-reusable-device-when-hidden",[1,2,3,4,5,6],"Refinery components become an orientation-programmed reusable rig."),
"q398":("Asterism Delegation","distributed-partial-observability","complementary-evidence-persists-across-physical-reset",[1,2,3,5,6],"Two orbital observers reconstruct star relations before and after reset."),
"q429":("Reedbed Revision","nonstationary-rule-revision","wear-shifted-rule-coupled-to-connectivity-construction",[1,2,3,4],"Marsh construction toggles connectivity across a visible wear boundary."),
"q460":("Vault Lineage","persistent-identity","causal-identity-with-two-conserved-shared-stores",[1,2,3,4,5,6],"Echo identities traverse trails while two stores share containers."),
"q491":("Pollen Dependency","hierarchical-goal-discovery","shared-prerequisite-dag-across-visible-rule-complement",[1,2,4,5,6],"Pollen dependencies switch execution law after a visible wear cue.")}
def load(c):
 p=ROOT/"docs"/"static"/"games"/"src"/f"{c}-v1"/f"{c}.py";s=importlib.util.spec_from_file_location(c,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return p,m
def main():
 games=[];out=ROOT/"research"/"games"
 for c,(title,axis,primary,actions,sil) in CFG.items():
  p,m=load(c);h=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(ROOT).as_posix();names=[x["name"] for x in m.LEVELS]
  meta={"schema_version":1,"game_id":c,"version":"v1","internal_title":title,"public_title":None,"author_partition":"gpt","authorship":{"model_family":"OpenAI GPT-5","model_snapshot":"current Codex task model; exact deployment id not exposed to task","session_id":SESSION,"created_at":"2026-08-30T00:00:00Z","source_lineage":[f"research/gpt-ideas-v2.tsv:{c}"],"source_commit":None},"mechanics":{"primary":primary,"secondary":[axis,"cross-domain-composition"],"novelty_claim":names[-1],"closest_prior_art":["research/coverage-gap-study-v1.md","research/flash-game-mechanics-survey.md"]},"failure_modes":["commits before integrating the coupled mechanic","tracks visible appearance instead of causal state","ignores the later progression rule"],"interface":{"actions":actions,"observation":"64x64x16","deterministic":True,"seeded_stochasticity":False},"progression":[{"level":i+1,"role":["orient","discriminate","plan","compose","inhibit","synthesize"][i],"new_demand":n,"composes":list(range(1,i+1))} for i,n in enumerate(names)],"visual_identity":{"dominant_palette":[],"silhouette_grammar":sil,"spatial_grammar":sil,"motion_grammar":primary.replace("-"," "),"hud_grammar":"Persistent colored state markers expose the mechanic without text.","nearest_visual_games":[]},"evaluation":{"allowed_development_models":["deterministic-solvers","random-fuzzer","Qwen3.8 diagnostic only"],"held_out_evaluator":"anthropic","human_baseline_status":"not_started","held_out_status":"sealed"},"artifacts":{"source":rel,"metadata":f"research/games/{c}-v1.json","win_recording":f"research/recordings/{c}-v1-win.json","loss_recording":f"research/recordings/{c}-v1-loss.json","thumbnail":f"docs/static/img/games/{c}-v1.png","source_sha256":h},"status":"prototype"}
  (out/f"{c}-v1.json").write_text(json.dumps(meta,indent=2)+"\n");g=getattr(m,c.upper())();a=g.perform_action(ActionInput(id=GameAction.RESET),raw=True).frame[-1];im=Image.new("RGB",(64,64));im.putdata([PAL[int(x)] for row in a for x in row]);im.save(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png",optimize=True);games.append({"game_id":c,"title":title,"axis":axis,"levels":6,"source_sha256":h})
 path=ROOT/"research"/"gpt-batch22-v1.json";path.write_text(json.dumps({"schema_version":1,"batch_id":"gpt-batch22-v1","created_at":"2026-08-30T00:00:00Z","design":"Ten expanded-ledger games staggered across the first ten axes and new domain offsets, each with six progressive levels.","games":games},indent=2)+"\n")
 sheet=Image.new("RGB",(800,352),(242,242,246));d=ImageDraw.Draw(sheet)
 for i,c in enumerate(CFG):im=Image.open(ROOT/"docs"/"static"/"img"/"games"/f"{c}-v1.png").resize((128,128),Image.Resampling.NEAREST);x,y=(i%5)*160+16,(i//5)*176+12;sheet.paste(im,(x,y));d.text((x,y+136),c,fill=(28,28,36))
 sheet.save(ROOT/".cache"/"batch22-contact.png",optimize=True);print("10 metadata records",path)
if __name__=="__main__":main()
