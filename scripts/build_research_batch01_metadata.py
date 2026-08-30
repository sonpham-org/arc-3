"""Generate metadata, thumbnails, and the batch manifest for research Batch 01."""

from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw
from arcengine import ActionInput, GameAction

ROOT = Path(__file__).resolve().parents[1]
SESSION = "01a02a2e-aaf5-7e90-a559-46437ace2edb"

CONFIG = {
    "q002": {"title": "Afterimage Mill", "axis": "observer-dependent-dynamics", "primary": "observation-written-hidden-programs", "secondary": ["occlusion-as-execution", "multi-device-programming", "phase-routing"], "failures": ["treats observation as passive", "forgets hidden orientation", "cannot isolate coupled devices"], "palette": [0, 3, 4, 8, 9, 10, 11, 12, 13, 14], "silhouette": "Bronze shutter boxes, cyan payload gems, directional mill vanes, and riveted walls against a burgundy factory surround.", "spatial": "A compact industrial floor with devices mounted at the perimeter and payloads moving through its interior.", "motion": "Visible mills accept a direction; shuttered mills execute their remembered direction on explicit pulses.", "hud": "Six discrete brass rivets show remaining action capacity.", "progress": ["Write one direction and hide one mill.", "Transfer the rule to a vertical route.", "Reopen and reprogram at a corner.", "Give two mills different hidden programs.", "Use an automatic turn plate.", "Freeze completed mills while a third consumes a remembered turn."]},
    "q011": {"title": "Courtesy Lines", "axis": "social-inference", "primary": "stable-yielding-preference", "secondary": ["comparison-by-interaction", "encounter-scheduling", "local-rule-reversal"], "failures": ["sorts by appearance", "fails to infer transitive preference", "repeats harmful encounters"], "palette": [0, 1, 2, 6, 8, 9, 10, 11, 12, 14], "silhouette": "Asymmetric pedestrians with horns, side-arms, and different body profiles.", "spatial": "A sunny cyan plaza with a pale crossing, yellow curbs, encounter pads, and ordered bays above it.", "motion": "Only the chosen adjacent pair negotiates; one stable personality yields.", "hud": "Small curb stones encode the remaining encounter budget.", "progress": ["Observe one yielding encounter.", "Order three walkers through pairwise meetings.", "Recover a stable hierarchy across four shapes.", "Recognize a visibly reversed crossing.", "Use a roundabout to move encounters between lanes.", "Compose six preferences, two reversed lanes, and queue rotation."]},
    "q021": {"title": "Switchboard Diagnosis", "axis": "causal-intervention", "primary": "budgeted-hidden-wiring-diagnosis", "secondary": ["xor-causality", "intervention-selection", "commitment-under-uncertainty"], "failures": ["tests every lever independently", "confuses correlation with wiring", "commits before distinguishing graphs"], "palette": [0, 1, 3, 4, 8, 9, 11, 12, 15], "silhouette": "Block levers, inset lamps, interrupted wire traces, and a commit rail.", "spatial": "A pale diagnostic console set into a saturated violet control room, with two opposed banks separated by unreadable wiring.", "motion": "Lever interventions toggle an unknown subset of lamps; commitment is terminal.", "hud": "Lit cyan fuses show the remaining intervention budget.", "progress": ["Identify one direct wire.", "Separate two independent channels.", "Diagnose a shared XOR output.", "Choose interventions across three crossed channels.", "Reason from a live nonzero panel.", "Reach a four-lamp target through a dense overlapping graph."]},
    "q031": {"title": "Split Vessel", "axis": "conservation-law-induction", "primary": "conserved-quantity-transformation", "secondary": ["operator-induction", "exact-distribution", "hierarchical-splitting"], "failures": ["ignores conserved total", "uses visual height approximately", "applies machines in the wrong order"], "palette": [0, 1, 3, 8, 9, 10, 12, 14], "silhouette": "Tall blue-glass vessels, continuous cyan liquid columns, pipe-jaw machines, and green target menisci.", "spatial": "A bright white laboratory bench with quantities above a row of unlabeled machines.", "motion": "Machines split, pour, balance, or rotate the same conserved material.", "hud": "A row of small orange machine-energy capsules.", "progress": ["Infer an equal splitter.", "Route a split share into a third cup.", "Compose two unit pours.", "Add a cyclic vessel turntable.", "Build a four-way hierarchy using equalization and splits.", "Ignore decoy operators while producing an exact four-vessel distribution."]},
    "q041": {"title": "Keyhole Budget", "axis": "epistemic-resource-allocation", "primary": "priced-spatial-observation", "secondary": ["hidden-route-planning", "irreversible-navigation", "information-selection"], "failures": ["reveals locally instead of strategically", "moves into unobserved space", "forgets a revealed route"], "palette": [3, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "silhouette": "Square apertures, an inset violet explorer, hollow destination, latches, and crumbling pink slabs.", "spatial": "An amber keyhole field where purchased windows cut through burgundy uncertainty into cyan floor.", "motion": "Clicking reveals a bounded window; movement into unrevealed or blocked space is terminal.", "hud": "A sparse row of yellow aperture tokens and short violet step pips.", "progress": ["Reveal one straight corridor.", "Spend views to reject a dead fork.", "Cover a bent route with overlapping apertures.", "Find a latch before crossing its door.", "Plan forward across floors that collapse behind the explorer.", "Compose scarce views, a key-door dependency, and irreversible terrain."]},
    "q051": {"title": "Scaffold", "axis": "tool-construction", "primary": "load-bearing-graph-construction", "secondary": ["material-strength", "multi-path-capacity", "finite-parts"], "failures": ["builds connectivity without capacity", "wastes strong struts", "misses independent load paths"], "palette": [0, 5, 8, 9, 10, 11, 12, 13, 14], "silhouette": "Hollow black anchor pins joined by white reeds or orange heavy beams over a blue chasm.", "spatial": "Freeform geometric construction suspended in blue against a yellow sky rather than a filled tile grid.", "motion": "Clicked candidate struts become a graph; a test load flows through its independent paths.", "hud": "Material sample and remaining loose struts flank the construction.", "progress": ["Connect one light span.", "Build two independent routes for a doubled load.", "Switch to heavy material for one high-capacity route.", "Recognize bracing opportunities in a larger frame.", "Reject attractive false anchors under a tight stock budget.", "Synthesize three independent paths across a multi-tier scaffold."]},
    "q061": {"title": "Split Couriers", "axis": "distributed-partial-observability", "primary": "cross-agent-hazard-observation", "secondary": ["attention-switching", "cross-room-memory", "remote-latch-coordination"], "failures": ["acts on the local picture alone", "confuses which clue belongs to which room", "opens one side before enabling the other"], "palette": [0, 1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 14], "silhouette": "Paired blue and magenta couriers separated by a bright central seam.", "spatial": "Two simultaneous miniature rooms on distinct cyan and pink halves; each carries ghost marks for the other room's hazards.", "motion": "Only one courier moves at a time and later pressure plates unlock the remote room.", "hud": "Alternating courier-color dashes show the shared action budget.", "progress": ["Use one room's ghost mark to protect the other courier.", "Integrate crossed warnings around walls.", "Alternate control through two hazard fields.", "Let one courier open the other's gate.", "Coordinate two remote latches.", "Compose cross-room hazards, switches, gates, and control switching."]},
    "q071": {"title": "Season Shift", "axis": "nonstationary-rule-revision", "primary": "visible-phase-conditioned-terrain", "secondary": ["change-point-detection", "wait-as-action", "irreversible-traversal"], "failures": ["persists with the first terrain rule", "ignores the phase clock", "crosses a one-use tile too early"], "palette": [0, 1, 3, 9, 10, 11, 12, 13, 14, 15], "silhouette": "Warm yellow beds, cold blue beds, violet change crystals, and brittle cyan floor.", "spatial": "Narrow pale botanical routes cut through a saturated green meadow beneath a large season bar.", "motion": "The visible phase alternates passability; change stones reverse the learned mapping.", "hud": "A full-width warm-or-cold phase bar counts to the next shift.", "progress": ["Cross terrain during its open season.", "Wait deliberately for the opposite season.", "Traverse alternating terrain classes.", "Revise the mapping after a visible climate stone.", "Plan without retreat across collapsing floor.", "Compose phase timing, rule reversal, and irreversible tiles."]},
    "q081": {"title": "Shell Identity", "axis": "persistent-identity", "primary": "identity-under-independent-transformations", "secondary": ["permutation-tracking", "appearance-decoupling", "adjacent-reordering"], "failures": ["tracks shell color instead of identity", "merges position and appearance swaps", "loses identity through long permutations"], "palette": [1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15], "silhouette": "Tall jewel shells with briefly visible cores over identity-specific sockets.", "spatial": "A vivid pink gallery above a pale row of destination plinths.", "motion": "Scripted events exchange bodies or appearances independently; later repair is adjacent-only.", "hud": "A sequence of violet shuffle tablets records how many transformations remain.", "progress": ["Track one body exchange.", "Separate an appearance exchange from identity motion.", "Compose three transformations across four shells.", "Repair the permutation using adjacent exchanges only.", "Track five shells through position and color decoys.", "Synthesize six identities, six independent events, and constrained reordering."]},
    "q091": {"title": "Workshop Orders", "axis": "hierarchical-goal-discovery", "primary": "latent-subassembly-dependencies", "secondary": ["order-sensitive-composition", "reusable-fixtures", "visual-interface-matching"], "failures": ["combines parts greedily", "fails to reuse a fixture", "cannot infer a multi-level dependency tree"], "palette": [1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], "silhouette": "Tiny multicolor component glyphs, reusable charcoal fixtures, and a central press jaw.", "spatial": "Loose modules sit on a pale workshop bench inside a saturated magenta studio.", "motion": "Two selected parts combine only when their interfaces form an allowed subassembly; fixtures persist.", "hud": "Fixture-colored work tokens indicate remaining assembly effort.", "progress": ["Join one compatible pair.", "Infer a two-level dependency order.", "Build two subassemblies in parallel before the final merge.", "Use one persistent fixture across several joins.", "Infer a nonlocal nested order among five parts.", "Compose six parts through two reusable fixtures and five dependent joins."]},
}

PALETTE = [
    (255, 255, 255), (204, 204, 204), (153, 153, 153), (102, 102, 102),
    (51, 51, 51), (0, 0, 0), (229, 58, 163), (255, 123, 204),
    (249, 60, 49), (30, 147, 255), (136, 216, 241), (255, 220, 0),
    (255, 133, 27), (146, 18, 49), (79, 204, 48), (163, 86, 214),
]

ACTIONS = {"q061": [1, 2, 3, 4, 5], "q071": [1, 2, 3, 4, 5], "q081": [5, 6], "q091": [5, 6]}


def load_levels(code):
    path = ROOT / "docs" / "static" / "games" / "src" / f"{code}-v1" / f"{code}.py"
    spec = importlib.util.spec_from_file_location(f"{code}_metadata", path); module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
    return module.LEVELS


def render_thumbnail(code):
    path = ROOT / "docs" / "static" / "games" / "src" / f"{code}-v1" / f"{code}.py"
    spec = importlib.util.spec_from_file_location(f"{code}_thumbnail", path); module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
    game = getattr(module, code.upper())(); result = game.perform_action(ActionInput(id=GameAction.RESET), raw=True); grid = result.frame[-1]
    image = Image.new("RGB", (64, 64)); image.putdata([PALETTE[int(value)] for row in grid for value in row])
    out = ROOT / "docs" / "static" / "img" / "games" / f"{code}-v1.png"; out.parent.mkdir(parents=True, exist_ok=True); image.save(out, optimize=True)
    return image


def render_contact_sheet(codes):
    scale, cell_w, cell_h = 2, 160, 176
    sheet = Image.new("RGB", (cell_w * 5, cell_h * 2), (242, 242, 246)); draw = ImageDraw.Draw(sheet)
    for index, code in enumerate(codes):
        thumb = Image.open(ROOT / "docs" / "static" / "img" / "games" / f"{code}-v1.png").convert("RGB").resize((64 * scale, 64 * scale), Image.Resampling.NEAREST)
        x, y = (index % 5) * cell_w + 16, (index // 5) * cell_h + 12
        sheet.paste(thumb, (x, y)); draw.text((x, y + 136), code, fill=(28, 28, 36))
    out = ROOT / ".cache" / "batch01-contact.png"; out.parent.mkdir(parents=True, exist_ok=True); sheet.save(out, optimize=True)


def main():
    out_dir = ROOT / "research" / "games"; out_dir.mkdir(parents=True, exist_ok=True); batch = []
    roles = ["orient", "discriminate", "plan", "compose", "inhibit", "synthesize"]
    for code, cfg in CONFIG.items():
        source_rel = f"docs/static/games/src/{code}-v1/{code}.py"; source = ROOT / source_rel; digest = hashlib.sha256(source.read_bytes()).hexdigest(); levels = load_levels(code)
        metadata = {
            "schema_version": 1, "game_id": code, "version": "v1", "internal_title": cfg["title"], "public_title": None, "author_partition": "gpt",
            "authorship": {"model_family": "OpenAI GPT-5", "model_snapshot": "current Codex task model; exact deployment id not exposed to task", "session_id": SESSION, "created_at": "2026-08-30T00:00:00Z", "source_lineage": [f"research/gpt-ideas-v1.tsv:{code}"], "source_commit": None},
            "mechanics": {"primary": cfg["primary"], "secondary": cfg["secondary"], "novelty_claim": cfg["progress"][-1], "closest_prior_art": ["research/coverage-gap-study-v1.md", "research/flash-game-mechanics-survey.md"]},
            "failure_modes": cfg["failures"], "interface": {"actions": ACTIONS.get(code, [1, 2, 3, 4, 5, 6]), "observation": "64x64x16", "deterministic": True, "seeded_stochasticity": False},
            "progression": [{"level": i + 1, "role": roles[i], "new_demand": demand, "composes": list(range(1, i + 1))} for i, demand in enumerate(cfg["progress"])],
            "visual_identity": {"dominant_palette": cfg["palette"], "silhouette_grammar": cfg["silhouette"], "spatial_grammar": cfg["spatial"], "motion_grammar": cfg["motion"], "hud_grammar": cfg["hud"], "nearest_visual_games": []},
            "evaluation": {"allowed_development_models": ["deterministic-solvers", "random-fuzzer", "Qwen3.8 diagnostic only"], "held_out_evaluator": "anthropic", "human_baseline_status": "not_started", "held_out_status": "sealed"},
            "artifacts": {"source": source_rel, "metadata": f"research/games/{code}-v1.json", "win_recording": f"research/recordings/{code}-v1-win.json", "loss_recording": f"research/recordings/{code}-v1-loss.json", "thumbnail": f"docs/static/img/games/{code}-v1.png", "source_sha256": digest},
            "status": "prototype",
        }
        (out_dir / f"{code}-v1.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        render_thumbnail(code)
        batch.append({"game_id": code, "title": cfg["title"], "axis": cfg["axis"], "levels": len(levels), "source_sha256": digest})
    manifest = {"schema_version": 1, "batch_id": "gpt-batch01-v1", "created_at": "2026-08-30T00:00:00Z", "design": "Ten cross-mechanic games; each has six causal-progression levels and a distinct visual grammar.", "games": batch}
    path = ROOT / "research" / "gpt-batch01-v1.json"; path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    render_contact_sheet(CONFIG)
    print(f"{len(batch)} metadata records -> {out_dir}"); print(path)


if __name__ == "__main__": main()
