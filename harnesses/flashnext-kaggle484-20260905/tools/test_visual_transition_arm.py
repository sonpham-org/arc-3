from __future__ import annotations

import ast
import math
import os
from pathlib import Path
import unittest


os.environ.setdefault("LOCAL_ANALYZER_MODEL_ID", "test-model")
os.environ.setdefault("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:9/v1")
os.environ.setdefault("MULTIMODAL_CONTEXT", "current_grid")
os.environ.setdefault("MULTIMODAL_UPSCALE", "4")

from inference.agent import prompts, tool_agent
from inference.agent.runtime_state import Frame


def _load_sampling_helper():
    solver_path = (
        Path(__file__).parent
        / "candidate-visual-transitions-r1"
        / "src"
        / "ARC3-Inference"
        / "inference"
        / "framework"
        / "solver.py"
    )
    module = ast.parse(solver_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_sample_evenly", "_visual_transition_sample_indices"}
    }
    namespace = {"math": math}
    selected = ast.Module(
        body=[functions["_sample_evenly"], functions["_visual_transition_sample_indices"]],
        type_ignores=[],
    )
    exec(compile(selected, str(solver_path), "exec"), namespace)
    return namespace["_visual_transition_sample_indices"]


_visual_transition_sample_indices = _load_sampling_helper()


class VisualTransitionSamplingTests(unittest.TestCase):
    def test_log2_sampling_spans_complete_timeline(self) -> None:
        expected = {
            1: (0, []),
            2: (2, [0, 1]),
            4: (2, [0, 3]),
            8: (3, [0, 4, 7]),
            16: (4, [0, 5, 10, 15]),
            32: (5, [0, 8, 16, 23, 31]),
            64: (6, [0, 13, 25, 38, 50, 63]),
            128: (7, [0, 21, 42, 64, 85, 106, 127]),
            256: (8, [0, 36, 73, 109, 146, 182, 219, 255]),
        }
        for total_frames, value in expected.items():
            with self.subTest(total_frames=total_frames):
                self.assertEqual(
                    _visual_transition_sample_indices(total_frames), value
                )

    def test_visual_parts_are_ordered_and_labeled(self) -> None:
        grid0 = [[0, 1], [2, 3]]
        grid1 = [[1, 1], [2, 3]]
        grid2 = [[1, 1], [3, 3]]
        parts, summary = tool_agent._build_visual_transition_parts(
            [
                {
                    "action_num": 17,
                    "action": "LEFT",
                    "animation_frame_count": 8,
                    "animation_changed_frame_count": 6,
                    "view": {
                        "before_frame": {
                            "grid": grid0,
                            "step": 16,
                            "level": 2,
                            "index": -1,
                        },
                        "keyframes": [
                            {
                                "grid": grid0,
                                "step": 17,
                                "level": 2,
                                "index": 0,
                            },
                            {
                                "grid": grid1,
                                "step": 17,
                                "level": 2,
                                "index": 4,
                            },
                            {
                                "grid": grid2,
                                "step": 17,
                                "level": 2,
                                "index": 7,
                            },
                        ],
                    },
                }
            ]
        )
        self.assertEqual(len([part for part in parts if part["type"] == "image_url"]), 3)
        self.assertIn("action 17 (LEFT)", parts[0]["text"])
        self.assertIn("positions 0, 4, 7", parts[0]["text"])
        self.assertEqual(parts[1]["text"], "Transition 1, returned frame 1 of 8:")
        self.assertEqual(parts[3]["text"], "Transition 1, returned frame 5 of 8:")
        self.assertEqual(parts[5]["text"], "Transition 1, returned frame 8 of 8:")
        for part in parts:
            if part["type"] == "image_url":
                self.assertTrue(
                    part["image_url"]["url"].startswith("data:image/png;base64,")
                )
        self.assertIn("action 17 LEFT", summary)

    def test_metadata_only_parts_contain_no_images(self) -> None:
        parts, summary = tool_agent._build_visual_transition_parts(
            [
                {
                    "action_num": 4,
                    "action": "RIGHT",
                    "animation_frame_count": 8,
                    "animation_changed_frame_count": 5,
                    "view": {
                        "before_frame": {"grid": [[0]], "index": -1},
                        "keyframes": [
                            {"grid": [[0]], "index": 0},
                            {"grid": [[1]], "index": 3},
                            {"grid": [[2]], "index": 7},
                        ],
                    },
                }
            ],
            include_images=False,
        )
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["type"], "text")
        self.assertIn("returned 8 frames", parts[0]["text"])
        self.assertIn("positions: 0, 3, 7", parts[0]["text"])
        self.assertIn("metadata only", summary)

    def test_pending_transition_precedes_next_prompt_and_current_grid(self) -> None:
        agent = tool_agent.ToolAgent()
        agent._pending_visual_transition_parts = [
            {"type": "text", "text": "queued transition"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,AAAA"},
            },
        ]
        current = Frame(grid=((0, 1), (2, 3)), step=18, level=2)
        message = agent._build_user_message("Choose the next action.", current)
        self.assertEqual(message["role"], "user")
        content = message["content"]
        self.assertEqual(content[0]["text"], "queued transition")
        self.assertIn("Choose the next action", content[2]["text"])
        self.assertEqual(content[-1]["type"], "image_url")

    def test_transition_base64_is_estimated_as_visual_tokens_only(self) -> None:
        agent = tool_agent.ToolAgent()
        large_url = "data:image/png;base64," + ("A" * 12000)
        current_only = [
            {"role": "system", "content": "system"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Current grid image:"},
                    {"type": "image_url", "image_url": {"url": large_url}},
                ],
            },
        ]
        with_transition = [
            {"role": "system", "content": "system"},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Chronological visual transition after action 2 (LEFT).",
                    },
                    {"type": "image_url", "image_url": {"url": large_url}},
                    {"type": "text", "text": "Current grid image:"},
                    {"type": "image_url", "image_url": {"url": large_url}},
                ],
            },
        ]
        current_estimate = agent._estimate_request_input_tokens(current_only)
        transition_estimate = agent._estimate_request_input_tokens(with_transition)
        self.assertGreater(transition_estimate, current_estimate)
        self.assertLess(transition_estimate - current_estimate, 200)

    def test_legacy_animation_tools_are_not_advertised(self) -> None:
        combined = prompts.STRUCTURED_RUNTIME_STATE_ADDENDUM + prompts.PYTHON_ADDENDUM
        self.assertNotIn("last_animation.region", combined)
        self.assertNotIn("ASCII frames are pasted", combined)
        self.assertIn("chronological", combined)


if __name__ == "__main__":
    unittest.main()
