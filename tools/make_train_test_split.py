"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Deterministically partition the 25 live ARC-3 public builds into an 18-game
training set and a 7-game held-out test set for the Qwen3.8-27B SFT/RL experiment
(Son Pham directive, 15-Sep-2026). Stratifies on TWO axes simultaneously: input
modality (the `tags` field: click / keyboard / keyboard_click) and a human-derived
difficulty score. Reads only committed manifests -- current-builds.json for level
counts and per-level baselines, human-leaderboards.json for what the ten fastest
human winners actually spent, published-replays.json for human win rate where the
blog row sits on a build that is still live. Exhaustively enumerates every candidate
test set meeting the modality quota and picks the one that best matches the training
set's difficulty distribution; no randomness, no seed, same input -> same split.
SRP/DRY check: Pass -- no existing splitter in this repo (`ls tools/`, `grep -ril
split datasets/`); reuses the committed manifests rather than re-fetching the API.
"""
import json, statistics, itertools, sys, pathlib

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
DS = ROOT / "datasets" / "decision-steps"

builds = json.load(open(DS / "current-builds.json"))["builds"]
lbs = {l["leaderboard_id"]: l for l in json.load(open(DS / "human-leaderboards.json"))["leaderboards"]}
blog = json.load(open(DS / "published-replays.json"))["replays"]

# Any game that already has labelled decision-step records is TRAINING-ONLY. Those
# records are the one corpus actually built for SFT teacher data, so letting their
# game sit in the held-out set contaminates the test set on day one. Derived from
# what is on disk, not hardcoded, so it tracks the corpus as it grows.
EPISODES = DS / "v0" / "episodes"
corpus_games = sorted({p.name[:4] for p in EPISODES.glob("*.jsonl")}) if EPISODES.is_dir() else []

live_ids = {b["game_id"] for b in builds}
blog_live = {}
for r in blog:
    if r["game_id"] in live_ids:
        blog_live.setdefault(r["game_id"][:4], []).append(r)

games = {}
for b in builds:
    gid = b["game_id"][:4]
    base = b["baseline_actions"]
    tags = b.get("tags") or []
    # ft09 carries no tags; its recording declares [1,2,3,4,6] -> both modalities.
    modality = tags[0] if tags else "keyboard_click"
    lb = lbs.get(gid)
    lb_actions = [r["actions"] for r in lb["rows"]] if lb else []
    rows = blog_live.get(gid, [])
    games[gid] = {
        "game_id": b["game_id"],
        "title": b.get("title"),
        "modality": modality,
        "tags_raw": tags,
        "n_levels": len(base),
        "baseline_total_actions": sum(base),
        "leaderboard_median_actions": statistics.median(lb_actions) if lb_actions else None,
        "leaderboard_best_actions": min(lb_actions) if lb_actions else None,
        "leaderboard_rows": len(lb_actions),
        "blog_live_rows": len(rows),
        "blog_live_win_rate": (sum(r["state"] == "WIN" for r in rows) / len(rows)) if rows else None,
    }

def z(vals):
    m, s = statistics.mean(vals), statistics.pstdev(vals)
    return [(v - m) / s if s else 0.0 for v in vals]

order = sorted(games)
# Three difficulty components, all "bigger = harder", equally weighted.
#  - baseline_total_actions: how long the designer expects the game to take. Under a
#    hard 108K generated-token/game cap this is the dominant cost axis.
#  - n_levels: more levels = more independent chances to stall.
#  - leaderboard_median_actions: what the ten fastest human WINNERS actually spent.
comp = {
    "baseline_total_actions": z([games[g]["baseline_total_actions"] for g in order]),
    "n_levels": z([float(games[g]["n_levels"]) for g in order]),
    "leaderboard_median_actions": z([float(games[g]["leaderboard_median_actions"]) for g in order]),
}
for i, g in enumerate(order):
    games[g]["difficulty_components_z"] = {k: round(v[i], 4) for k, v in comp.items()}
    games[g]["difficulty_z"] = round(sum(v[i] for v in comp.values()) / len(comp), 4)

ranked = sorted(order, key=lambda g: games[g]["difficulty_z"])
# Terciles over 25 -> 8 easy / 9 medium / 8 hard.
for i, g in enumerate(ranked):
    games[g]["difficulty_rank"] = i + 1
    games[g]["difficulty_tercile"] = "easy" if i < 8 else ("medium" if i < 17 else "hard")

by_mod = {}
for g in order:
    games[g]["has_labelled_corpus_records"] = g in corpus_games
    games[g]["test_eligible"] = g not in corpus_games
    by_mod.setdefault(games[g]["modality"], []).append(g)
eligible = {m: [g for g in gs if games[g]["test_eligible"]] for m, gs in by_mod.items()}
# Proportional 7-of-25 test quota: 13 kc -> 4, 7 click -> 2, 4 keyboard -> 1.
QUOTA = {"keyboard_click": 4, "click": 2, "keyboard": 1}
assert sum(QUOTA.values()) == 7
for m, n in QUOTA.items():
    assert len(eligible[m]) >= n, (m, len(eligible.get(m, [])))

all_z = [games[g]["difficulty_z"] for g in order]
GLOBAL_MEAN, GLOBAL_SD = statistics.mean(all_z), statistics.pstdev(all_z)
# Target tercile counts in a 7-game test set, proportional to 8/9/8 over 25.
TARGET_TERCILE = {"easy": 2, "medium": 3, "hard": 2}

def cost(test):
    tz = [games[g]["difficulty_z"] for g in test]
    trz = [games[g]["difficulty_z"] for g in order if g not in test]
    counts = {"easy": 0, "medium": 0, "hard": 0}
    for g in test:
        counts[games[g]["difficulty_tercile"]] += 1
    tercile_err = sum(abs(counts[k] - TARGET_TERCILE[k]) for k in counts)
    return (
        tercile_err,                                             # hard constraint first
        round(abs(statistics.mean(tz) - statistics.mean(trz)), 6),  # same average difficulty
        round(abs(statistics.pstdev(tz) - GLOBAL_SD), 6),           # same spread, not clustered
        tuple(sorted(test)),                                        # deterministic tie-break
    )

best, best_cost, evaluated = None, None, 0
for kc in itertools.combinations(sorted(eligible["keyboard_click"]), QUOTA["keyboard_click"]):
    for cl in itertools.combinations(sorted(eligible["click"]), QUOTA["click"]):
        for kb in itertools.combinations(sorted(eligible["keyboard"]), QUOTA["keyboard"]):
            test = set(kc) | set(cl) | set(kb)
            evaluated += 1
            c = cost(test)
            if best_cost is None or c < best_cost:
                best, best_cost = sorted(test), c

test_games = best
train_games = [g for g in order if g not in set(best)]
assert len(train_games) == 18 and len(test_games) == 7

def summarize(names):
    zs = [games[g]["difficulty_z"] for g in names]
    mods, terc = {}, {}
    for g in names:
        mods[games[g]["modality"]] = mods.get(games[g]["modality"], 0) + 1
        terc[games[g]["difficulty_tercile"]] = terc.get(games[g]["difficulty_tercile"], 0) + 1
    return {
        "count": len(names),
        "modality_counts": dict(sorted(mods.items())),
        "difficulty_tercile_counts": dict(sorted(terc.items())),
        "difficulty_z_mean": round(statistics.mean(zs), 4),
        "difficulty_z_sd": round(statistics.pstdev(zs), 4),
        "difficulty_z_min": round(min(zs), 4),
        "difficulty_z_max": round(max(zs), 4),
        "baseline_total_actions_sum": sum(games[g]["baseline_total_actions"] for g in names),
    }

out = {
    "_provenance": {
        "what": "An 18-game training / 7-game held-out test partition of the 25 live ARC-3 public builds, for the Qwen3.8-27B SFT then RL experiment.",
        "why": "Son Pham directive 15-Sep-2026: 'separate 25 games into 2 groups, 18 for training and 7 for testing. Make sure to roughly stratify it so that there are easy and hard games in both.' Improvement is only meaningful if measured on games never trained on, and only interpretable if the two groups are comparable.",
        "how": "Difficulty is the mean of three z-scored, human-derived signals (baseline_total_actions, n_levels, leaderboard_median_actions), split into terciles. Every test set meeting the proportional modality quota (4 keyboard_click / 2 click / 1 keyboard) was enumerated exhaustively and scored on tercile match, then difficulty-mean gap, then spread; ties break on sorted game id. No RNG, no seed.",
        "generated_by": "tools/make_train_test_split.py",
        "inputs": ["datasets/decision-steps/current-builds.json", "datasets/decision-steps/human-leaderboards.json", "datasets/decision-steps/published-replays.json"],
        "candidate_test_sets_evaluated": evaluated,
        "training_only_games": corpus_games,
        "training_only_reason": "These games already have labelled decision-step records in datasets/decision-steps/v0/episodes/. That corpus is teacher data for SFT, so its games are forced into training; an unconstrained split put all three in the test set, which would have contaminated the held-out measurement before a single step was trained.",
        "caveats": [
            "Difficulty here is HUMAN difficulty. Nothing in this repo measures per-game agent difficulty -- ARC3-Inference/runs is empty -- so the model's own ordering may differ. RE-CHECK AFTER THE BASELINE: if the base 27B scores zero on all 7 test games, the test set cannot show improvement no matter what training does, and the split must be redrawn against measured base scores.",
            "ft09 carries no tags in current-builds.json. It is treated as keyboard_click because its recording declares available_actions [1,2,3,4,6]. That is an assignment, not a published label.",
            "blog_live_win_rate is present for only the minority of games whose blog rows sit on a build that is still live; it is reported per game but is NOT an input to the difficulty score, precisely because it is missing for most games.",
            "Leaderboard rows are all wins at score 100, so they measure the cost of a successful human run, not the probability of one.",
            "as66-821a4dcad9c2 is deliberately absent: it is not in the live 25. It is therefore a free never-trained-on generalisation probe, and 15 recordings for it are already on disk.",
            "All seeds, attempts, teacher traces and branch states from a game belong to that game's split. Do not let a training game's trace appear in a test rollout.",
            "The Boss's own human recordings cover 11 of the 25 games, several of which are in the test set. Those are legitimate held-out material ONLY if they are never used as teacher traces. If human-demonstration SFT is later extended beyond the labelled corpus, re-run this splitter with those games added to training_only and re-baseline."
        ],
    },
    "train": {"summary": summarize(train_games), "games": train_games},
    "test": {"summary": summarize(test_games), "games": test_games},
    "games": {g: games[g] for g in order},
}
print(json.dumps(out, indent=2))
