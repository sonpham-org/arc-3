"""
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Guards on datasets/splits/public25-train-test-split.json -- the 18/7 partition
of the live ARC-3 public builds used for the Qwen3.8-27B SFT/RL experiment. Asserts the
split is a complete, non-overlapping partition of exactly the 25 game ids the Kaggle duck
harness pins in ARC3-Inference/inference/framework/kaggle.py, that no game carrying
labelled decision-step records is in the held-out set, that both halves span easy and
hard, that the modality quota holds, and that the generator is reproducible. The
harness-id guard is the load-bearing one: it fires when the official lineup changes,
which silently invalidates any measurement taken across this split.
SRP/DRY check: Pass -- no existing test covers datasets/splits/; reads the committed
artifact and the harness source rather than duplicating the difficulty formula.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLIT_PATH = ROOT / "datasets" / "splits" / "public25-train-test-split.json"
KAGGLE_PY = ROOT / "ARC3-Inference" / "inference" / "framework" / "kaggle.py"
EPISODES = ROOT / "datasets" / "decision-steps" / "v0" / "episodes"


def load_split():
    return json.loads(SPLIT_PATH.read_text())


def harness_game_ids():
    src = KAGGLE_PY.read_text()
    block = re.search(r"DUCK_HARNESS_PUBLIC_GAME_IDS.*?\((.*?)\)", src, re.S).group(1)
    return set(re.findall(r'"([a-z0-9]{4}-[0-9a-f]+)"', block))


class SplitShapeTests(unittest.TestCase):
    def setUp(self):
        self.split = load_split()
        self.train = self.split["train"]["games"]
        self.test = self.split["test"]["games"]

    def test_sizes_are_eighteen_and_seven(self):
        self.assertEqual(len(self.train), 18, "Son's directive is 18 training games")
        self.assertEqual(len(self.test), 7, "Son's directive is 7 test games")

    def test_partition_is_disjoint_and_complete(self):
        overlap = set(self.train) & set(self.test)
        self.assertEqual(overlap, set(), f"a game is in both halves: {overlap}")
        self.assertEqual(
            set(self.train) | set(self.test),
            set(self.split["games"]),
            "the two halves must cover every game the file describes",
        )

    def test_covers_exactly_the_harness_pinned_lineup(self):
        pinned = harness_game_ids()
        described = {v["game_id"] for v in self.split["games"].values()}
        self.assertEqual(
            described,
            pinned,
            "the split no longer covers exactly the 25 builds the duck harness runs; "
            "the official lineup changed, so re-snapshot current-builds.json and "
            "regenerate the split rather than editing this assertion",
        )


class NoLeakageTests(unittest.TestCase):
    def setUp(self):
        self.split = load_split()

    def test_no_labelled_corpus_game_is_held_out(self):
        corpus = {p.name[:4] for p in EPISODES.glob("*.jsonl")}
        self.assertTrue(corpus, "expected labelled episodes on disk to guard against")
        leaked = corpus & set(self.split["test"]["games"])
        self.assertEqual(
            leaked,
            set(),
            f"{sorted(leaked)} have labelled decision-step records AND sit in the "
            "held-out set; that corpus is SFT teacher data, so the test measurement "
            "would be contaminated before a step is trained",
        )

    def test_training_only_list_matches_what_is_on_disk(self):
        corpus = sorted({p.name[:4] for p in EPISODES.glob("*.jsonl")})
        self.assertEqual(
            self.split["_provenance"]["training_only_games"],
            corpus,
            "the recorded training-only list has drifted from the episodes directory; "
            "the corpus grew and the split was not regenerated",
        )


class StratificationTests(unittest.TestCase):
    def setUp(self):
        self.split = load_split()
        self.games = self.split["games"]

    def test_both_halves_span_easy_and_hard(self):
        for half in ("train", "test"):
            terciles = {self.games[g]["difficulty_tercile"] for g in self.split[half]["games"]}
            self.assertIn("easy", terciles, f"{half} has no easy game")
            self.assertIn("hard", terciles, f"{half} has no hard game")

    def test_test_set_modality_quota(self):
        counts = self.split["test"]["summary"]["modality_counts"]
        self.assertEqual(
            counts,
            {"click": 2, "keyboard": 1, "keyboard_click": 4},
            "the held-out set no longer mirrors the lineup's input modalities; a "
            "measured gain would be confounded with interface transfer",
        )

    def test_mean_difficulty_of_the_halves_agrees(self):
        gap = abs(
            self.split["train"]["summary"]["difficulty_z_mean"]
            - self.split["test"]["summary"]["difficulty_z_mean"]
        )
        self.assertLess(gap, 0.10, f"halves differ in mean difficulty by {gap}")

    def test_difficulty_ranks_are_a_permutation(self):
        ranks = sorted(v["difficulty_rank"] for v in self.games.values())
        self.assertEqual(ranks, list(range(1, len(self.games) + 1)))


class ReproducibilityTests(unittest.TestCase):
    def test_regenerating_reproduces_the_committed_split(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "make_train_test_split.py"), str(ROOT)],
            capture_output=True,
            text=True,
            check=True,
        )
        regenerated = json.loads(proc.stdout)
        committed = load_split()
        self.assertEqual(
            regenerated["train"]["games"], committed["train"]["games"], "train half drifted"
        )
        self.assertEqual(
            regenerated["test"]["games"], committed["test"]["games"], "test half drifted"
        )
        self.assertEqual(
            regenerated, committed, "the generator no longer reproduces the committed file"
        )


if __name__ == "__main__":
    unittest.main()
