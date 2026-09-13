import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ARC3-Inference"))

from debugger.server import SessionService, render_context  # noqa: E402


class FakeQwenClient:
    def __init__(self, *, prompt_tokens: int = 100, max_model_len: int = 512) -> None:
        self.prompt_tokens = prompt_tokens
        self.max_model_len = max_model_len

    def model_info(self):
        return {"id": "qwen-test", "max_model_len": self.max_model_len}

    def tokenize(self, _payload):
        return {"count": self.prompt_tokens, "max_model_len": self.max_model_len}


class DebuggerServerTests(unittest.TestCase):
    def body(self, *, max_tokens: int = 64):
        return {
            "context": {
                "source": "exact_request",
                "messages": [
                    {"role": "system", "content": "system"},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "turn"},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,secret"}},
                        ],
                    },
                ],
            },
            "flags": {"current_grid": False},
            "settings": {"maxTokens": max_tokens},
        }

    def test_preview_returns_read_only_context_and_exact_token_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SessionService(
                FakeQwenClient(prompt_tokens=100, max_model_len=512),
                state_root=Path(directory),
                cluster_nodes=["a108", "a424"],
            )
            preview = service.preview(self.body(max_tokens=64))
        self.assertTrue(preview["fits"])
        self.assertEqual(100, preview["promptTokens"])
        self.assertEqual(412, preview["availableOutputTokens"])
        self.assertEqual(2, preview["messageCount"])
        self.assertIn("[MESSAGE 1/2 · SYSTEM]", preview["contextText"])
        self.assertNotIn("data:image", preview["contextText"])

    def test_preview_marks_request_that_exceeds_model_window(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SessionService(
                FakeQwenClient(prompt_tokens=480, max_model_len=512),
                state_root=Path(directory),
                cluster_nodes=["a108", "a424"],
            )
            preview = service.preview(self.body(max_tokens=64))
        self.assertFalse(preview["fits"])
        self.assertEqual(32, preview["availableOutputTokens"])

    def test_context_renderer_replaces_embedded_image_bytes(self):
        text = render_context(
            {
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "look"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,secret"}},
                    ],
                }],
                "model": "qwen-test",
                "max_tokens": 64,
            }
        )
        self.assertIn("[CURRENT GRID IMAGE ATTACHED]", text)
        self.assertNotIn("base64", text)


if __name__ == "__main__":
    unittest.main()
