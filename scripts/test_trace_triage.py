"""Behavior checks for bounded, evidence-grounded offline triage (no network or database)."""
import json
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_triage as triage


def notes(build="abcd1234"):
    return {"gameId": "bp35", "build": build, "officialTitle": "DO NOT LEAK TITLE",
            "pageUrl": "https://arc.markbarney.net/arc3/games/bp35", "runs": [{"state": "WIN"}],
            "levels": [{"level": 1, "newRules": [{"text": "The camera scrolls.", "source": "bp35.py:10"}],
                        "observations": [{"date": "2026-10-01", "saw": "The exit moved on screen."}]},
                       {"level": 2, "newRules": [{"text": "Future secret.", "source": None}], "observations": []}],
            "observationsAnyLevel": [], "notes": "Correction: screen coordinates change."}


def packet(step=1, selection="trigger"):
    return {"game": "bp35", "build": "abcd1234", "level": 1, "path_id": "model-identity:bp35_p0:L1", "step": step,
            "trace_sha256": "1" * 64, "reference_sha256": "2" * 64, "context_complete": True, "selection": selection,
            "evidence": [{"id": "claim", "kind": "thinking", "text": "The exit must move independently."},
                         {"id": "result", "kind": "result", "text": "RIGHT changed all screen coordinates."}],
            "reference": [{"id": "note", "kind": "code_rule", "text": "The camera scrolls."}], "omissions": []}


def issue(route="human", category="contradiction"):
    return {"status": "issue", "category": category, "summary": "Screen motion may be misinterpreted.",
            "claim": {"ref": "claim", "quote": "The exit must move independently."},
            "support": {"ref": "result", "quote": "RIGHT changed all screen coordinates."},
            "reference": {"ref": "note", "quote": "The camera scrolls."},
            "alternative": "Camera movement may explain it.", "solver_knew": "unknown", "route": route,
            "human_question": "Did the solver distinguish screen and world coordinates?",
            "next_action": "Check its stored world model before selecting a recovery experiment.", "impact": "high"}


def write_run(directory, *, status="failed", completed=False, game="bp35"):
    artifacts = directory / "artifacts"
    artifacts.mkdir(exist_ok=True)
    stem = f"{game}-abcd1234_p0"
    transcript = "[SYSTEM PROMPT]\nLearn the rules from observed actions.\n[USER PROMPT]\nObserve the board.\n[THINKING]\nThe exit must move independently.\n[TOOL CALL: python]\nstep('RIGHT')\n[TOOL RESULT: python]\nRIGHT changed all screen coordinates."
    events = [{"type": "initial", "level": 1, "board": [[0] * 64 for _ in range(64)]},
              {"type": "analysis", "analysis_step": 1, "transcript": transcript},
              {"type": "action", "analysis_step": 1, "action_num": 1, "action_name": "RIGHT",
               "board_changed": True, "level_completed": completed, "board": [[1] * 64 for _ in range(64)]}]
    path = artifacts / (stem + "_events.jsonl")
    path.write_text("\n".join(json.dumps(e) for e in events))
    if status is not None:
        (artifacts / (stem + "_viewer_data.json")).write_text(json.dumps({"status": status}))
    return path


class PreparationTests(unittest.TestCase):
    def test_failed_finished_trace_is_included_without_outcome_or_titles(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = write_run(Path(tmp))
            report = triage.prepare_packets(Path(tmp), "test-model-label", notes())
            self.assertEqual(len(report["packets"]), 1)
            p = report["packets"][0]
            self.assertEqual(p["trace_sha256"], triage.file_hash(source))
            self.assertTrue(p["context_complete"])
            self.assertEqual(p["before"], ["0" * 64] * 64)
            self.assertEqual(p["after"], ["1" * 64] * 64)
            view = triage.canonical(triage.judge_view(p))
            for hidden in ("test-model-label", "DO NOT LEAK TITLE", "WIN", "Future secret", "cleared", "level_up"):
                self.assertNotIn(hidden, view)
            self.assertIn("Correction:", view)
            self.assertIn("2026-10-01", view)

    def test_unfinished_tail_is_excluded_without_explicit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_run(Path(tmp), status=None)
            self.assertEqual(triage.prepare_packets(Path(tmp), "test", notes())["packets"], [])

    def test_completed_level_can_be_prepared_from_running_play(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_run(Path(tmp), status="running", completed=True)
            self.assertEqual(len(triage.prepare_packets(Path(tmp), "test", notes())["packets"]), 1)

    def test_mismatched_build_has_visible_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_run(Path(tmp))
            result = triage.prepare_packets(Path(tmp), "test", notes("otherbuild"))
            self.assertFalse(result["packets"])
            self.assertIn("mismatched", result["errors"][0]["error"])

    def test_fences_apply_before_index_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            for game in ("as66", "ar25", "ah66", "dc22"):
                path = write_run(Path(tmp), game=game)
                path.write_text("invalid JSON must never be read")
            result = triage.prepare_packets(Path(tmp), "test", notes())
            self.assertEqual(result["counts"]["fenced"], 4)
            self.assertFalse(result["errors"])

    def test_durable_memory_is_preserved_as_solver_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = write_run(Path(tmp))
            events = [json.loads(line) for line in source.read_text().splitlines()]
            call = {"function": {"arguments": json.dumps({"code": "step('RIGHT')", "world_model": "The exit must move independently."})}}
            events[1]["transcript"] += "\n[MODEL RESPONSE META]\nraw_tool_calls: " + json.dumps([call])
            source.write_text("\n".join(json.dumps(e) for e in events))
            result = triage.prepare_packets(Path(tmp), "test", notes())
            evidence = result["packets"][0]["evidence"]
            self.assertTrue(any(e["kind"] == "memory_write" and "must move" in e["text"] for e in evidence))
            self.assertTrue(any(e["kind"] == "solver_system" for e in evidence))

    def test_focal_omission_is_explicit_and_forbids_human_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = write_run(Path(tmp))
            events = [json.loads(line) for line in source.read_text().splitlines()]
            events[1]["transcript"] = events[1]["transcript"].replace("The exit must", "x" * 5000 + "The exit must")
            source.write_text("\n".join(json.dumps(e) for e in events))
            result = triage.prepare_packets(Path(tmp), "test", notes(), max_packet_chars=12000)
            self.assertEqual(len(result["packets"]), 1)
            p = result["packets"][0]
            self.assertFalse(p["context_complete"])
            self.assertTrue(any("Focal passages omitted" in o for o in p["omissions"]))
            self.assertLessEqual(len(triage.canonical(p)), 12000)

    def test_corrupt_source_does_not_hide_another_play(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = write_run(Path(tmp))
            source.with_name("bp35-abcd1234_p1_events.jsonl").write_text("{unfinished")
            result = triage.prepare_packets(Path(tmp), "test", notes())
            self.assertEqual(len(result["packets"]), 1)
            self.assertTrue(any("incomplete event" in e["error"] for e in result["errors"]))

    def test_oversized_packet_is_reported_not_silently_clipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_run(Path(tmp))
            result = triage.prepare_packets(Path(tmp), "test", notes(), max_packet_chars=100)
            self.assertFalse(result["packets"])
            self.assertIn("budget", result["errors"][0]["error"])


class ExecutionTests(unittest.TestCase):
    def test_routing_cache_and_immutable_republication(self):
        with tempfile.TemporaryDirectory() as tmp:
            judge = lambda p: issue(category="reference_conflict")
            first = triage.execute([packet()], judge, Path(tmp))
            self.assertEqual(first["items"][0]["route"], "assistant")
            second = triage.execute([packet()], lambda p: self.fail("cached episode called judge"), Path(tmp))
            self.assertEqual(first["items"], second["items"])
            self.assertEqual(second["counts"]["cache_hits"], 1)
            changed = packet()
            changed["reference_sha256"] = "3" * 64
            third = triage.execute([changed], judge, Path(tmp))
            self.assertEqual(third["counts"]["calls"], 1)
            self.assertNotEqual(first["items"][0]["id"], third["items"][0]["id"])

    def test_invalid_quote_never_published_or_cached_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = issue()
            bad["claim"]["quote"] = "invented"
            failed = triage.execute([packet()], lambda p: bad, Path(tmp))
            self.assertFalse(failed["items"])
            self.assertEqual(len(failed["errors"]), 1)
            self.assertEqual(list(Path(tmp).glob("*.json")), [])
            retry = triage.execute([packet()], lambda p: issue(), Path(tmp))
            self.assertEqual(len(retry["items"]), 1)

    def test_budgets_reserve_one_fifth_for_untriggered_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            packets = [packet(i) for i in range(10)] + [packet(20, "audit")]
            selected = []
            result = triage.execute(packets, lambda p: selected.append(p["selection"]) or issue(), Path(tmp), max_calls=5)
            self.assertEqual(selected, ["trigger"] * 4 + ["audit"])
            self.assertEqual(result["counts"]["deferred"], 6)
            self.assertEqual(result["counts"]["audit_judged"], 1)

    def test_prepare_only_does_not_create_cache_or_call_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "absent"
            result = triage.execute([packet()], lambda p: self.fail("model called"), cache, prepare_only=True)
            self.assertEqual(len(result["packets"]), 1)
            self.assertFalse(cache.exists())

    def test_timeout_is_retryable_and_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            def timeout(_):
                raise subprocess.TimeoutExpired("codex", 1)
            result = triage.execute([packet()], timeout, Path(tmp))
            self.assertEqual(result["counts"]["calls"], 1)
            self.assertEqual(result["errors"][0]["error"], "judge timeout")
            self.assertFalse(result["items"])
            self.assertFalse(list(Path(tmp).glob("*.json")))

    def test_no_issue_is_cached_but_never_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            assessment = issue()
            assessment.update(status="no_issue", claim=None, support=None, reference=None, route="discard")
            first = triage.execute([packet()], lambda p: assessment, Path(tmp))
            second = triage.execute([packet()], lambda p: self.fail("no issue should be cached"), Path(tmp))
            self.assertFalse(first["items"])
            self.assertEqual(first["counts"]["no_issue"], 1)
            self.assertEqual(second["counts"]["cache_hits"], 1)

    def test_cache_size_limit_keeps_recent_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            for i in range(4):
                (cache / f"{i}.json").write_text("{}")
            with patch.object(triage, "MAX_CACHE_ENTRIES", 2):
                triage.trim_cache(cache)
            self.assertEqual(len(list(cache.glob("*.json"))), 2)

    def test_model_view_removes_metadata_and_codex_call_is_bounded(self):
        with patch.object(triage.subprocess, "run") as run:
            def fake(command, **kwargs):
                self.assertIn("--ignore-user-config", command)
                self.assertEqual(kwargs["timeout"], 4)
                self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
                self.assertNotIn("model-identity", kwargs["input"])
                self.assertNotIn("ARC3_PUBLISH_TOKEN", kwargs["env"])
                self.assertIn("browser_use", command)
                Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(issue()))
                return subprocess.CompletedProcess(command, 0)
            run.side_effect = fake
            self.assertEqual(triage.codex_judge(packet(), timeout=4)["status"], "issue")


class PublisherIntegrationTests(unittest.TestCase):
    def test_dry_run_and_publication_reuse_the_downloaded_run(self):
        from trace_review_publish import publish_triage
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note_file = root / "notes.json"
            note_file.write_text(json.dumps(notes()))
            args = SimpleNamespace(triage_notes=str(note_file), triage_model="gpt-6-luna",
                                   triage_max_calls=1, cache=tmp, dry_run=True, site="https://example.test")
            with patch.object(triage, "prepare_packets", return_value={"packets": [packet()], "counts": {}, "errors": []}) as prep, \
                 patch.object(triage, "codex_judge", return_value=issue()) as judge, \
                 patch.object(triage, "publish") as publish:
                report = publish_triage(args, root, "example", "machine-token")
                judge.assert_not_called()
                publish.assert_not_called()
                self.assertEqual(report["counts"]["calls"], 0)
                self.assertEqual(prep.call_args.args[:2], (root, "example"))
                args.dry_run = False
                report = publish_triage(args, root, "example", "machine-token")
                judge.assert_called_once()
                publish.assert_called_once_with(args.site, report["items"], token="machine-token")
                self.assertTrue((root / "triage-report.json").exists())


if __name__ == "__main__":
    unittest.main()
