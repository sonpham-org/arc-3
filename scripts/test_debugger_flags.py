import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ARC3-Inference"))

from debugger.flags import FLAG_SPECS, build_resume_request  # noqa: E402
from viewer.data import _resume_context_from_request_snapshot  # noqa: E402


SYSTEM = "System prompt"
USER = """Knowledge ledger carried from earlier turns:
- World model: the blue object moves.
End of carried knowledge ledger.
Inspect the newest transition in Python and distinguish gameplay change from HUD-only change.
Call `python` with compact inspection/search code and the revised required `world_model` ledger, then execute the shortest reliable valid action or batch via `action(actions)`. Stop on any terminal result.
If you use MOUSE, include integer row and col arguments."""
TOOLS = [{"type": "function", "function": {"name": "python", "parameters": {"type": "object"}}}]
CONTEXT = {
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "old turn"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": USER},
    ],
    "tools": TOOLS,
    "toolChoice": "auto",
    "boardImage": "data:image/png;base64,AA==",
}


class DebuggerFlagTests(unittest.TestCase):
    def request(self, **flags):
        payload, normalized = build_resume_request(
            model="qwen",
            context=CONTEXT,
            raw_flags=flags,
            settings={"maxTokens": 512},
        )
        return payload, normalized

    def test_registry_has_unique_ids(self) -> None:
        ids = [spec.id for spec in FLAG_SPECS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_editable_flag_changes_the_request(self) -> None:
        baseline, defaults = self.request()
        for spec in FLAG_SPECS:
            with self.subTest(flag=spec.id):
                changed, normalized = self.request(**{spec.id: not defaults[spec.id]})
                self.assertNotEqual(baseline, changed)
                self.assertEqual(normalized[spec.id], not defaults[spec.id])

    def test_memory_off_keeps_only_system_and_selected_user_turn(self) -> None:
        payload, _ = self.request(memory=False)
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "user"])
        self.assertNotIn("Knowledge ledger", str(payload["messages"][-1]["content"]))

    def test_memory_off_removes_legacy_world_model_block(self) -> None:
        context = {
            **CONTEXT,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Working world model carried from earlier turns:\nold facts\nend of world model.\nContinue."},
            ],
        }
        payload, _ = build_resume_request(model="qwen", context=context, raw_flags={"memory": False})
        self.assertNotIn("old facts", jsonish(payload["messages"]))

    def test_enabling_missing_guidance_adds_it_to_selected_turn(self) -> None:
        context = {"messages": [{"role": "user", "content": "Continue."}]}
        payload, _ = build_resume_request(model="qwen", context=context, raw_flags={})
        rendered = jsonish(payload["messages"])
        self.assertIn("distinguish gameplay change", rendered)
        self.assertIn("compact inspection/search code", rendered)
        self.assertIn("include integer row and col", rendered)

    def test_tools_and_grid_are_real_payload_switches(self) -> None:
        payload, _ = self.request(tools=False, current_grid=False)
        self.assertNotIn("tools", payload)
        self.assertNotIn("image_url", jsonish(payload["messages"]))

    def test_unknown_flags_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown debugger flag"):
            self.request(pretend_feature=True)

    def test_recent_run_sampling_defaults_are_overridable(self) -> None:
        payload, _ = build_resume_request(
            model="qwen",
            context=CONTEXT,
            raw_flags={},
            settings={"maxTokens": 2048, "temperature": 1.0, "topP": 0.95, "topK": 20},
        )
        self.assertEqual(payload["max_tokens"], 2048)
        self.assertEqual(payload["temperature"], 1.0)
        self.assertEqual(payload["top_p"], 0.95)
        self.assertEqual(payload["top_k"], 20)

        changed, _ = build_resume_request(
            model="qwen",
            context=CONTEXT,
            raw_flags={},
            settings={"maxTokens": 1024, "temperature": 0.7, "topP": 0.8, "topK": 40},
        )
        self.assertEqual(changed["max_tokens"], 1024)
        self.assertEqual(changed["temperature"], 0.7)
        self.assertEqual(changed["top_p"], 0.8)
        self.assertEqual(changed["top_k"], 40)

    def test_viewer_export_keeps_exact_context_without_embedded_image(self) -> None:
        snapshot = {
            "messages": CONTEXT["messages"][:-1]
            + [{
                "role": "user",
                "content": [
                    {"type": "text", "text": USER},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,large"}},
                ],
            }],
            "tools": TOOLS,
            "tool_choice": "auto",
        }
        exported = _resume_context_from_request_snapshot(snapshot)
        self.assertIsNotNone(exported)
        self.assertEqual(exported["source"], "exact_request")
        self.assertTrue(exported["hadCurrentGridImage"])
        self.assertTrue(exported["defaultFlags"]["current_grid"])
        self.assertTrue(exported["defaultFlags"]["mouse_guidance"])
        self.assertNotIn("data:image", jsonish(exported["messages"]))
        self.assertEqual(exported["tools"], TOOLS)


def jsonish(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
