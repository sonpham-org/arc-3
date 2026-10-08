"""Regression coverage for separated competitions, observed history, and publishing."""
import contextlib
import copy
from datetime import datetime, timezone
import gzip
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import leaderboard_config as config
import leaderboard_snapshot as snapshot
import leaderboard_push_explainer as pusher


class LeaderboardPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"LEADERBOARD_DATA_DIR": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def select(self, competition):
        os.environ["LEADERBOARD_COMPETITION"] = competition
        importlib.reload(config)
        importlib.reload(snapshot)
        importlib.reload(pusher)

    def rows(self):
        rows = [[i, f"ordinary-{i}", f"Team {i}", "2026-10-07", 100 - i / 10, 1, "member"]
                for i in range(1, 603)]
        rows[600][1] = snapshot.OUR_TEAM_ID
        return rows

    def collect(self, rows, day=7):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, day, 23, tzinfo=timezone.utc)
        with patch.object(snapshot, "fetch_rows", return_value=copy.deepcopy(rows)), \
                patch.object(snapshot, "datetime", Clock), contextlib.redirect_stdout(io.StringIO()):
            snapshot.main()
        return json.loads((snapshot.OUT / "latest.json").read_text())

    def test_first_day_unknown_then_previous_day_observation(self):
        self.select(config.ARC2)
        rows = self.rows()
        first = self.collect(rows)
        self.assertTrue(all(r[7:] == [None, None] for r in first["rows"]))
        rows[0][4] += 1
        same_day = self.collect(rows)
        self.assertEqual(same_day["rows"][0][7:], [None, None])
        tomorrow = self.collect(rows, day=8)
        self.assertEqual(tomorrow["rows"][0][7:], [1, rows[0][4]])
        after_gap = self.collect(rows, day=10)
        self.assertEqual(after_gap["rows"][0][7:], [None, None])

    def test_competitions_do_not_share_history_or_payloads(self):
        self.select(config.ARC3)
        arc3 = self.collect(self.rows())
        saved = (self.root / "latest.json").read_bytes()
        self.select(config.ARC2)
        arc2 = self.collect(self.rows())
        self.assertEqual(snapshot.OUT, self.root / "arc-2")
        self.assertEqual((self.root / "latest.json").read_bytes(), saved)
        self.assertNotEqual(arc3["ourTeamId"], arc2["ourTeamId"])
        self.assertEqual(arc2["pinnedTeamIds"], ["17023174", "15605185"])
        requests = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{}'
        def capture(req, **kwargs):
            requests.append(json.loads(gzip.decompress(req.data)))
            return Response()
        with patch.object(pusher, "token", return_value="test-only"), \
                patch.object(pusher.urllib.request, "urlopen", side_effect=capture), \
                contextlib.redirect_stdout(io.StringIO()):
            pusher.main()
        self.assertEqual(requests[0]["competition"], config.ARC2)
        self.assertEqual(requests[0]["documents"]["latest"], arc2)
        self.assertNotIn(arc3["ourTeamId"], requests[0]["documents"]["history"]["trails"])
        (snapshot.OUT / "latest.json").write_bytes(saved)
        with self.assertRaisesRegex(ValueError, "another competition"):
            self.collect(self.rows())
        with patch.object(pusher, "token", return_value="test-only"), \
                patch.object(pusher.urllib.request, "urlopen") as send:
            with self.assertRaisesRegex(ValueError, "another competition"):
                pusher.main()
            send.assert_not_called()

    def test_featured_below_cutoffs_keeps_changes_and_rank_history(self):
        self.select(config.ARC2)
        rows = self.rows()
        self.collect(rows)
        self.collect(rows)
        hist = json.loads((snapshot.OUT / "history.json").read_text())
        self.assertEqual(len(hist["trails"][snapshot.OUR_TEAM_ID]["pts"]), 1)
        self.assertNotIn("ordinary-602", hist["trails"])
        rows[600][4] += 1
        rows[601][4] += 1
        self.collect(rows)
        events = json.loads((snapshot.OUT / "events.json").read_text())
        self.assertEqual([e["id"] for e in events], [snapshot.OUR_TEAM_ID])
        rows[599], rows[600] = rows[600], rows[599]
        rows[599][0], rows[600][0] = 600, 601
        self.collect(rows)
        hist = json.loads((snapshot.OUT / "history.json").read_text())
        self.assertEqual(hist["trails"][snapshot.OUR_TEAM_ID]["pts"][-1][2], 600)
        self.assertEqual(len(json.loads((snapshot.OUT / "events.json").read_text())), 1)

    def test_legacy_arc3_history_and_first_seen_featured_team(self):
        self.select(config.ARC3)
        rows = self.rows()
        old = self.collect(rows)
        del old["competition"]
        (snapshot.OUT / "latest.json").write_text(json.dumps(old))
        featured = "16021367"
        rows[601][1] = featured
        self.collect(rows)
        hist = json.loads((snapshot.OUT / "history.json").read_text())
        self.assertEqual(len(hist["snaps"]), 2)
        self.assertEqual(hist["trails"][featured]["pts"][-1][2], 602)
        events = json.loads((snapshot.OUT / "events.json").read_text())
        self.assertEqual(events[-1]["id"], featured)
        self.assertIsNone(events[-1]["from"])
        self.select(config.ARC2)
        with self.assertRaisesRegex(ValueError, "another competition"):
            config.check_competition(old)

    def test_arc3_failure_does_not_block_arc2_publish(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        mock_bin = self.root / "bin"
        mock_bin.mkdir()
        source = Path(__file__).with_name("leaderboard_publish.sh").read_text()
        source = source.replace('export PATH="/Users/macmini/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"',
                                f'export PATH="{mock_bin}:/usr/bin:/bin"')
        job = scripts / "leaderboard_publish.sh"
        job.write_text(source)
        for name, content in {
            "git": "#!/bin/bash\nexit 0\n",
            "python3.13": '#!/bin/bash\necho "$LEADERBOARD_COMPETITION $1" >> "$TEST_LOG"\n'
                          '[[ "$LEADERBOARD_COMPETITION" == *-3 && "$1" == *snapshot.py ]] && exit 1\nexit 0\n',
        }.items():
            path = mock_bin / name
            path.write_text(content)
            path.chmod(0o755)
        log = self.root / "calls.txt"
        result = subprocess.run(["bash", str(job)], env={**os.environ, "TEST_LOG": str(log)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text().splitlines(), [
            f"{config.ARC3} scripts/leaderboard_snapshot.py",
            f"{config.ARC2} scripts/leaderboard_snapshot.py",
            f"{config.ARC2} scripts/leaderboard_push_explainer.py",
        ])


if __name__ == "__main__":
    unittest.main()
