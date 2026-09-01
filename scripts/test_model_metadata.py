import json
import tempfile
import unittest
from pathlib import Path

from scripts.model_metadata import (
    ModelMetadataError,
    extract_model_metadata,
    validate_model_metadata,
)


MODEL_ID = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
REVISION = "7b719225242aacd3dbd3f9407468c2ee9a9d2594"


class ModelMetadataTests(unittest.TestCase):
    def test_extracts_and_cross_checks_launch_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / "LAUNCH_STATE.json").write_text(
                json.dumps({"model": {"id": MODEL_ID, "revision": REVISION}}),
                encoding="utf-8",
            )
            (run / "model-info.json").write_text(
                json.dumps(
                    {
                        "model_id": MODEL_ID,
                        "revision": REVISION,
                        "quantization": "NVFP4",
                    }
                ),
                encoding="utf-8",
            )
            model = extract_model_metadata(run)
            self.assertEqual(model["display"], f"{MODEL_ID}@7b719225")
            self.assertEqual(model["quantization"], "NVFP4")
            self.assertEqual(
                {row["file"] for row in model["evidence"]},
                {"LAUNCH_STATE.json", "model-info.json"},
            )
            self.assertTrue(all(len(row["sha256"]) == 64 for row in model["evidence"]))

    def test_rejects_disagreement_between_launch_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / "LAUNCH_STATE.json").write_text(
                json.dumps({"model": {"id": MODEL_ID, "revision": REVISION}}),
                encoding="utf-8",
            )
            (run / "model-info.json").write_text(
                json.dumps({"model_id": "Qwen/Other", "revision": REVISION}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ModelMetadataError, "disagree"):
                extract_model_metadata(run)

    def test_rejects_missing_or_unpinned_model_for_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ModelMetadataError, "refusing an unlabelled upload"):
                extract_model_metadata(Path(temp))
        with self.assertRaisesRegex(ModelMetadataError, "40-character"):
            validate_model_metadata({"id": MODEL_ID, "revision": "7b719225"})


if __name__ == "__main__":
    unittest.main()
