"""Regression: exit code 0 without valid outputs must fail (ENG-009, FIX-003)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Allow running without install: python -m unittest from engine/adapter
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonoplan_adapter.contracts import OutputFileSpec
from sonoplan_adapter.validate_outputs import evaluate_run


class ExitZeroWithoutOutputsTest(unittest.TestCase):
    def test_exit_0_missing_required_output_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            result = evaluate_run(
                exit_code=0,
                work_dir=work,
                specs=(
                    OutputFileSpec(
                        relative_path="Punctual receivers/Sound level.recp",
                        required=True,
                        min_bytes=1,
                    ),
                ),
            )
            self.assertFalse(result.ok)
            self.assertIn("exit_0_without_valid_outputs", result.failure_reasons)
            self.assertTrue(
                any(r.startswith("missing_required_output:") for r in result.failure_reasons)
            )

    def test_exit_0_with_nonempty_required_output_passes_size_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            out = work / "Punctual receivers" / "Sound level.recp"
            out.parent.mkdir(parents=True)
            out.write_bytes(b"\x00\x01FAKE")  # not a real decode — size gate only
            result = evaluate_run(
                exit_code=0,
                work_dir=work,
                specs=(
                    OutputFileSpec(
                        relative_path="Punctual receivers/Sound level.recp",
                        required=True,
                        min_bytes=1,
                    ),
                ),
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.failure_reasons, [])

    def test_non_zero_exit_fails_even_if_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            out = work / "Punctual receivers" / "Sound level.recp"
            out.parent.mkdir(parents=True)
            out.write_bytes(b"\x00\x01")
            result = evaluate_run(
                exit_code=1,
                work_dir=work,
                specs=(
                    OutputFileSpec(
                        relative_path="Punctual receivers/Sound level.recp",
                        required=True,
                        min_bytes=1,
                    ),
                ),
            )
            self.assertFalse(result.ok)
            self.assertIn("spps_exit_code=1", result.failure_reasons)


class BrokenFixtureLayoutTest(unittest.TestCase):
    def test_broken_exit0_fixture_dir(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[2] / "fixtures" / "broken_exit0"
        )
        self.assertTrue(fixture.is_dir(), msg="broken_exit0 fixture missing")
        manifest = fixture / "manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        specs = tuple(
            OutputFileSpec(
                relative_path=item["path"],
                required=bool(item.get("required", True)),
                min_bytes=int(item.get("min_bytes", 1)),
            )
            for item in data["expected_outputs"]
        )
        result = evaluate_run(
            exit_code=int(data.get("simulated_exit_code", 0)),
            work_dir=fixture,
            specs=specs,
        )
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
