import unittest

from scripts.publish_game_versions import (
    IMPORTED_FAMILIES,
    classify_model,
    find_game_class,
    infer_author,
    model_name,
    split_commit_message,
)


CLAUDE_COMMIT = """ng01 Negative: up/down now flip gravity

Pressing up pulls the walker to the ceiling.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
"""


class AuthorTests(unittest.TestCase):
    def test_models_are_named_the_way_the_badges_show_them(self) -> None:
        self.assertEqual(model_name("Claude Fable 5.1 (spill chamber; original game by Claude Opus 5)"), "Claude Fable 5.1")
        self.assertEqual(model_name("Codex (GPT-6)"), "Codex (GPT-6)")
        self.assertEqual(model_name("Claude Opus 5 (Bubba)"), "Claude Opus 5")
        self.assertEqual(classify_model("OpenAI GPT-5"), "gpt")
        self.assertEqual(classify_model("Codex (GPT-6)"), "gpt")
        self.assertEqual(classify_model("Claude Opus 5 <noreply@anthropic.com>"), "claude")
        self.assertIsNone(classify_model("Son Pham"))

    def test_a_revision_trusts_its_commit_trailer_first(self) -> None:
        header = "# Author: Codex (GPT-6)\n"
        self.assertEqual(infer_author(CLAUDE_COMMIT, header, seed=False, focused=False),
                         {"kind": "claude", "model": "Claude Opus 5"})
        self.assertEqual(infer_author("Fix colours", header, seed=False, focused=True),
                         {"kind": "gpt", "model": "Codex (GPT-6)"})
        self.assertEqual(infer_author("Fix colours", "", seed=False, focused=True)["kind"], "unknown")

    def test_a_bulk_import_does_not_credit_its_co_author_with_the_game(self) -> None:
        bulk = "Games tab asset pipeline\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>\n"
        self.assertEqual(infer_author(bulk, "", seed=True, focused=False)["kind"], "unknown")
        self.assertEqual(infer_author(bulk, "", seed=True, focused=True)["kind"], "claude")
        metadata = {"kind": "gpt", "model": "OpenAI GPT-5"}
        self.assertEqual(infer_author(bulk, "", seed=True, focused=True, metadata=metadata), metadata)

    def test_imported_families_are_credited_to_their_source(self) -> None:
        author, name, reason = IMPORTED_FAMILIES["official"]
        self.assertEqual((author["kind"], name), ("human", "ARC Prize Foundation"))
        self.assertEqual(IMPORTED_FAMILIES["redbluepill"][0]["kind"], "other")


class CommitMessageTests(unittest.TestCase):
    def test_subject_is_the_reason_and_trailers_are_dropped(self) -> None:
        reason, details = split_commit_message(CLAUDE_COMMIT)
        self.assertEqual(reason, "ng01 Negative: up/down now flip gravity")
        self.assertEqual(details, "Pressing up pulls the walker to the ceiling.")
        reason, details = split_commit_message("Games tab: recolour hv01\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n")
        self.assertEqual((reason, details), ("recolour hv01", None))


class SourceTests(unittest.TestCase):
    def test_finds_the_arcbasegame_subclass(self) -> None:
        text = "import arcengine\nclass Helper:\n    pass\nclass G009(arcengine.ARCBaseGame):\n    pass\n"
        self.assertEqual(find_game_class(text), "G009")
        self.assertIsNone(find_game_class("def broken(:\n"))


if __name__ == "__main__":
    unittest.main()
