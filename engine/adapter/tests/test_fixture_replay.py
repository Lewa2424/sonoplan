"""Fixture replay: decode pinned CI .recp when Linux SPPS is unavailable."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonoplan_adapter.fixture_replay import (  # noqa: E402
    attempt_fixture_replay,
    fixture_replay_enabled,
    resolve_fixture_replay_dir,
)

EXPECTED = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "minimal_room"
    / "expected"
)


@unittest.skipUnless(
    (EXPECTED / "Punctual receivers").is_dir(),
    "expected punctual fixtures missing",
)
class FixtureReplayTest(unittest.TestCase):
    def test_resolve_default_dir(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SONOPLAN_SPPS_FIXTURE_REPLAY_DIR", None)
            path = resolve_fixture_replay_dir()
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue((path / "Punctual receivers").is_dir())

    def test_replay_yields_confirmed_lp(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"SONOPLAN_SPPS_FIXTURE_REPLAY": "1"},
            clear=False,
        ):
            self.assertTrue(fixture_replay_enabled())
            attempt = attempt_fixture_replay(work_dir=EXPECTED)
        self.assertTrue(attempt.ok)
        self.assertTrue(attempt.work_dir)
        self.assertTrue(attempt.artifact_paths)

    def test_replay_disabled(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"SONOPLAN_SPPS_FIXTURE_REPLAY": "0"},
            clear=False,
        ):
            attempt = attempt_fixture_replay(work_dir=EXPECTED)
        self.assertFalse(attempt.ok)
        self.assertEqual(attempt.error_code, "FIXTURE_REPLAY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
