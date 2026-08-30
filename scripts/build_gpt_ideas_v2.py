"""Build the consolidated 800-concept GPT ledger and its deterministic audit."""
from __future__ import annotations
import csv,hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/"research"/"gpt-ideas-v1.tsv";ANTH=ROOT/"research"/"anthropic-build-ideas-v1.tsv"
OUT=ROOT/"research"/"gpt-ideas-v2.tsv";AUDIT=ROOT/"research"/"gpt-ideas-v2.audit.json"
DOMAINS=[
 ("Aurora","polar observatory","crystal motes","sweeping light curtains"),("Tide","tidal basin","shell carriers","reversing currents"),
 ("Ember","ceramic kiln","clay vessels","stored heat bands"),("Honeycomb","layered apiary","nectar couriers","hexagonal scent fields"),
 ("Alloy","magnetic foundry","metal billets","alternating force lanes"),("Palimpsest","sliding archive","memory tiles","overwritten shelf traces"),
 ("Canopy","terraced orchard","seed gliders","seasonal shade bands"),("Breakwater","modular harbor","cargo skiffs","tide-gated channels"),
 ("Strata","deep quarry","ore crawlers","load-bearing fault lines"),("Spore","glass greenhouse","spore colonies","humidity gradients"),
 ("Tapestry","kinetic loom","thread shuttles","crossing tension fields"),("Lockwater","stepped canal","barge tokens","coupled water levels"),
 ("Murmuration","open aviary","flock markers","collective wind wakes"),("Moraine","moving glacier","stone rafts","crevasse flow bands"),
 ("Waystation","desert caravan","supply walkers","shifting dune corridors"),("Backstage","rotating theater","mask actors","scene-dependent sightlines"),
 ("Catalyst","chemical refinery","reactant beads","temperature-gated pipes"),("Asterism","orbital chart","star nodes","precessing relation lines"),
 ("Reedbed","flooded marsh","reed beetles","salinity fronts"),("Vault","branching catacomb","echo carriers","pressure-sealed passages"),
 ("Pollen","alpine meadow","pollen kites","directional bloom waves"),("Semaphore","cliff signal yard","flag agents","occluded relay beams"),
 ("Impeller","turbine chamber","blade riders","counter-rotating wakes"),("Tessera","folding mosaic","colored tesserae","topology-changing seams"),
 ("Vivarium","stacked terrarium","microfauna","temperature strata"),("Crossing","river ferry","passenger tokens","capacity-limited docks"),
 ("Spectrum","prism gallery","light packets","wavelength-splitting panes"),("Escapement","clock tower","weight tokens","nested gear phases"),
 ("Monsoon","weather garden","rain seeds","delayed storm cells"),("Workbench","mobile workshop","tool sprites","reconfigurable fixtures")]
VARIANTS=[
 ("hysteresis","Returning the control to an earlier setting does not restore the earlier state, so the plan must model a visible hysteresis loop."),
 ("irreversible-commitment","One operation is irreversible and must be delayed until the preceding evidence excludes every unsafe branch."),
 ("shared-budget","Observation, movement, and repair consume the same finite resource, turning information gathering into a direct planning tradeoff."),
 ("two-timescale","Local state updates every action while the enclosing state updates only after a completed local cycle, requiring two clocks."),
 ("moving-reference","The relevant relation is expressed in a frame that translates and rotates between decisions rather than in screen coordinates."),
 ("negative-demonstration","A visible failed example shares most of the successful sequence and isolates the single causal distinction that matters."),
 ("capacity-bottleneck","A narrow intermediate store imposes a hard capacity, so a valid global transfer can still deadlock through bad ordering."),
 ("delayed-credit","The consequence of the first intervention remains dormant across two solved subgoals before changing the terminal affordance."),
 ("reversible-probe","A probe can be undone physically but its observation persists, separating reversible world state from irreversible knowledge."),
 ("asynchronous-agents","Two autonomous actors update on different visible schedules, and useful coordination occurs only at sparse shared events."),
 ("topology-rewrite","Completing an intermediate pattern rewires which locations are adjacent, so the later plan operates on a new graph."),
 ("identity-exchange","Two entities exchange appearance and position while retaining causal identity, making trail history necessary for assignment."),
 ("parity-check","A redundant parity relation detects one misleading observation and must be satisfied before the final action is accepted."),
 ("nested-subgoal","Solving a local enclosure changes one token in an outer dependency puzzle, coupling inner completion order to the terminal goal."),
 ("adaptive-counter","A visible opponent state updates from the last two player policies and punishes repetition with a predictable counter."),
 ("continuous-accumulation","Small discrete actions accumulate a continuous-looking quantity whose threshold and direction both matter."),
 ("observation-write","Looking at a component writes its current orientation into memory; hiding it later executes the stored orientation."),
 ("evidence-preserving-reset","A single reset erases physical progress while preserving acquired evidence, enforcing separate experiment and execution phases."),
 ("dual-effect-tool","Every constructed component changes both function and connectivity, so a locally useful tool can obstruct the global route."),
 ("coupled-conservation","Two quantities are independently conserved but share containers, requiring simultaneous bookkeeping rather than one scalar total."),
 ("visible-rule-boundary","A wear cue announces a change point after which the learned rule becomes its complement instead of merely gaining difficulty."),
 ("parallel-sandboxes","Two miniature systems accept different tests before exactly one learned policy is committed to the larger irreversible system."),
 ("value-of-information-stop","Further samples remain available but become costly once no possible result can change the best supported decision."),
 ("interruptible-macro","A repeated autonomous routine can be compressed, but one state-defined window requires interrupting the macro before its last action."),
 ("reciprocal-partner","A partner remembers whether recent help was fair and changes a later policy according to a short, inferable reciprocity rule."),
 ("complementary-observers","Separate controllers see disjoint attributes and must leave persistent nonverbal evidence before control alternates."),
 ("cross-domain-transfer","The same relational algebra is demonstrated first with geometry and later with agents whose surface features share nothing."),
 ("diagnostic-intervention","Several faults explain passive observations, but one carefully chosen intervention produces mutually exclusive outcomes."),
 ("phase-synchrony","Two cycles have unequal periods and the useful action exists only at a phase pair rather than at a fixed elapsed time."),
 ("identity-bound-obligation","A temporary benefit creates a delayed obligation attached to the helper's identity rather than to the transferred object.")]
assert len(VARIANTS)==len(DOMAINS)==30
AXES=[
 ("observer-dependent-dynamics","Veil","In the {arena}, {actors} update under {field}: exposing one region freezes its local transition while occluding it releases a domain-specific change, so the player must schedule attention across coupled regions."),
 ("social-inference","Pact","Within the {arena}, several {actors} respond to recent offers using a stable but hidden convention grounded by {field}; low-cost interactions reveal whether the group rewards fairness, recency, or reciprocity before a joint commitment."),
 ("causal-intervention","Probe","The {arena} contains apparently adjacent {actors} connected through hidden parts of {field}; a small intervention budget must distinguish direct transmission, shared cause, and coincidence before one irreversible repair."),
 ("conservation-law-induction","Ledger","Across the {arena}, transformations reshape {actors} through {field} while preserving one latent quantity; the goal distribution can be reached only by tracking transfers globally rather than matching local appearance."),
 ("epistemic-resource-allocation","Survey","Disposable observations in the {arena} reveal bounded slices of {field} around selected {actors}; the player must choose measurements whose union answers a later route question before the evidence budget expires."),
 ("tool-construction","Rig","Short components in the {arena} can redirect, join, or support {actors} moving through {field}; later levels require building one reusable device whose geometry has two interacting functional effects."),
 ("distributed-partial-observability","Delegation","Two controllers in the {arena} receive complementary projections of {actors} and {field}; alternating control and leaving persistent nonverbal marks are required to integrate the remote evidence into one action."),
 ("nonstationary-rule-revision","Revision","A visible wear state in the {arena} causes the rule governing {actors} and {field} to change at a learnable boundary; sparse recalibration must identify whether the new law is inverted, rotated, or delayed."),
 ("persistent-identity","Lineage","The {actors} in the {arena} repeatedly split, merge, and exchange appearances along {field}; only their causal trails preserve identity when a later gate requests a particular ancestor rather than a current look."),
 ("hierarchical-goal-discovery","Dependency","A terminal request in the {arena} expands into nested prerequisites involving {actors} and {field}; completing stable lower patterns unlocks new operations, and shared subgoals must be reused across branches."),
 ("multi-scale-reference-frames","Frame","Local motion of {actors} inside the {arena} composes with translation and rotation of {field}; edge exchanges depend on global alignment even though every control is expressed in a moving local frame."),
 ("policy-learning-from-demonstration","Lesson","Demonstrations in the {arena} show {actors} acting through {field}, but include a context switch and one causally ineffective gesture; the player must infer the intended conditional policy rather than clone the visible sequence."),
 ("adaptive-adversary","Counter","An opponent in the {arena} selects among three tactics from the player's recent treatment of {actors} and {field}; its update is legible, so success requires deliberately shaping the opponent state before exploiting a counter."),
 ("compositional-communication","Grammar","Messages in the {arena} encode operations on {actors} using both grouping and spatial relations in {field}; relays apply local transforms, making later commands require composition rather than symbol lookup."),
 ("counterfactual-planning","Sandbox","Two miniature copies of the {arena} can test different interventions on {actors} under {field}; evidence persists but simulated progress does not, and only one policy may be committed to the irreversible main system."),
 ("structural-analogy","Analogy","A rule first demonstrated as a transformation of {field} in the {arena} reappears as an interaction among {actors}; surface colors and positions change while the conserved relational structure remains exact."),
 ("confidence-calibration","Evidence","Physical evidence from {field} accumulates around candidate explanations for {actors} in the {arena}; observations have unequal reliability, and stopping is rewarded once no remaining sample can change the best supported action."),
 ("continuous-quantity-reasoning","Gradient","Discrete controls reshape a continuous-looking distribution of {actors} over {field} in the {arena}; capacity, phase, and conserved total jointly determine whether accumulated influence crosses the target threshold."),
 ("long-horizon-credit-assignment","Obligation","An early choice involving {actors} in the {arena} writes a delayed consequence into {field}; intervening rewards obscure the link, while the final obligation remains attached to causal identity rather than the borrowed object."),
 ("temporal-abstraction","Rhythm","The {actors} in the {arena} follow an autonomous rhythm expressed by events in {field}; useful control depends on chunking repeated routines, scaling intervals, and interrupting at state-defined windows instead of counting frames.")]
def read_tsv(path):
 with path.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f,delimiter="\t"))
def main():
 old=read_tsv(OLD);anth=read_tsv(ANTH);assert len(old)==200 and len(anth)==200
 rows=[dict(r) for r in old];next_id=201
 for axis,suffix,template in AXES:
  for (label,arena,actors,field),(variant,twist) in zip(DOMAINS,VARIANTS):
   concept=template.format(arena=arena,actors=actors,field=field)+" "+twist
   rows.append({"id":f"q{next_id:03d}","internal_title":f"{label} {suffix}","primary_axis":axis,"concept":concept})
   next_id+=1
 assert next_id==801 and len(rows)==800
 ids=[r["id"] for r in rows];titles=[r["internal_title"] for r in rows];concepts=[r["concept"] for r in rows]
 assert len(set(ids))==len(ids) and len(set(titles))==len(titles) and len(set(concepts))==len(concepts)
 assert rows[:200]==old;counts=Counter(r["primary_axis"] for r in rows);assert set(counts.values())=={40}
 with OUT.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=["id","internal_title","primary_axis","concept"],delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(rows)
 payload=OUT.read_bytes();audit={"schema_version":1,"source_ledger":"research/gpt-ideas-v1.tsv","source_sha256":hashlib.sha256(OLD.read_bytes()).hexdigest(),"output_ledger":"research/gpt-ideas-v2.tsv","output_sha256":hashlib.sha256(payload).hexdigest(),"gpt_concepts":len(rows),"anthropic_build_briefs":len(anth),"combined_design_inventory":len(rows)+len(anth),"new_id_range":["q201","q800"],"new_concepts":600,"domain_families":len(DOMAINS),"structural_variants":[v[0] for v in VARIANTS],"per_axis":dict(sorted(counts.items())),"invariants":{"legacy_rows_preserved":True,"ids_unique":True,"titles_unique":True,"concepts_unique":True,"forty_concepts_per_axis":True,"thirty_structural_variants_per_axis":True}}
 AUDIT.write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8");print(f"{len(rows)} GPT + {len(anth)} Anthropic = {len(rows)+len(anth)} concepts");print(AUDIT)
if __name__=="__main__":main()
