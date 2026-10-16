"""SPPS environment gates (no binary launch required on Windows)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonoplan_adapter.env import (  # noqa: E402
    CODE_SPPS_BIN_MISSING,
    CODE_SPPS_NOT_LINUX,
    check_spps_environment,
    fixture_inputs_ready,
    probe_elf_magic,
)


class SppsEnvTest(unittest.TestCase):
    def test_non_linux_fails_clearly(self) -> None:
        with mock.patch("sonoplan_adapter.env.is_linux_host", return_value=False):
            with mock.patch.dict("os.environ", {"SPPS_BIN": "/tmp/spps"}, clear=False):
                status = check_spps_environment()
        self.assertFalse(status.ok)
        self.assertEqual(status.code, CODE_SPPS_NOT_LINUX)

    def test_linux_without_bin_fails(self) -> None:
        with mock.patch("sonoplan_adapter.env.is_linux_host", return_value=True):
            with mock.patch.dict("os.environ", {"SPPS_BIN": ""}, clear=False):
                status = check_spps_environment(spps_bin=None)
        self.assertFalse(status.ok)
        self.assertEqual(status.code, CODE_SPPS_BIN_MISSING)

    def test_elf_magic_and_fixture_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            elf = work / "spps"
            elf.write_bytes(b"\x7fELF" + b"\x00" * 8)
            self.assertTrue(probe_elf_magic(elf))
            self.assertFalse(fixture_inputs_ready(work, ("config.xml",)))
            (work / "config.xml").write_text("<spps/>", encoding="utf-8")
            self.assertTrue(fixture_inputs_ready(work, ("config.xml",)))


if __name__ == "__main__":
    unittest.main()
