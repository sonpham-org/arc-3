import unittest

from railway.model_backfill import (
    QWEN_FP8_REVISION,
    RADIX_REVISION,
    UNSLOTH_REVISION,
    backfill_catalog_models,
    historical_model_for_run,
)


class ModelBackfillTests(unittest.TestCase):
    def test_flash_next_families_use_radixark_pin(self) -> None:
        for run in (
            "20260827_220911_q38-flashnext-rtdv7-22",
            "20260829_083134_q38-fnv9-cap12-rep2e",
            "20260829_145255_q38-flashnext-cap14-full-r1",
            "20260830_150112_q38-f14-replay-c-v2-r2-retry1",
            "g4run-q38-f14-full-25-r2-20260829-213720",
        ):
            model = historical_model_for_run(run)
            self.assertIsNotNone(model, run)
            self.assertEqual(model["revision"], RADIX_REVISION)

    def test_pre_flash_qwen38_families_use_unsloth_pin(self) -> None:
        for run in (
            "20260820_235959_q38-cap8-ce-think-nvfp4-rtcpu-r2",
            "20260822_150829_q38-wmctx-static6-p1",
            "20260827_150332_n2x15-w1",
            "20260827_235459_q38-r6rtdv7refl-p1",
        ):
            model = historical_model_for_run(run)
            self.assertIsNotNone(model, run)
            self.assertEqual(model["revision"], UNSLOTH_REVISION)

    def test_early_qwen38_and_qwen36_runs_keep_their_actual_models(self) -> None:
        fp8 = historical_model_for_run("20260819_134223_q38-taaf-cap8-reviewedthemes-cen-p2")
        self.assertEqual(fp8["revision"], QWEN_FP8_REVISION)
        q36 = historical_model_for_run("20260810_0506_v12-ffa7gn-cap8-plan-reset-p1")
        self.assertEqual(q36["id"], "vrfai/Qwen3.6-27B-FP8")
        self.assertNotIn("revision", q36)

    def test_unknown_run_is_never_guessed(self) -> None:
        self.assertIsNone(historical_model_for_run("20260901_unknown-model-run"))

    def test_database_backfill_updates_only_verified_runs(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.statements = []

            def execute(self, statement, parameters=None) -> None:
                self.statements.append((statement, parameters))

            @staticmethod
            def fetchall():
                return [
                    ("20260829_145255_q38-flashnext-cap14-full-r1",),
                    ("20260901_unknown-model-run",),
                ]

        cursor = Cursor()
        updated, unresolved = backfill_catalog_models(cursor, lambda value: value)
        self.assertEqual(updated, 1)
        self.assertEqual(unresolved, ["20260901_unknown-model-run"])
        updates = [row for row in cursor.statements if row[1]]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][1][0]["revision"], RADIX_REVISION)


if __name__ == "__main__":
    unittest.main()
