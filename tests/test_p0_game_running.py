"""CPU-only tests for p0_run.game_running / refuse_if_game (no GPU)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from fac_tinyagent.p0_run import game_running, refuse_if_game


def _run(stdout=b"", stderr=b"", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class GameRunningTests(unittest.TestCase):
    def test_utf8_game_detected(self):
        listing = "Image Name                     PID Session Name        Session#    Mem Usage\r\n"
        listing += "r5apex_dx12.exe              1234 Console                   1  4,000 K\r\n"
        with mock.patch("subprocess.run", return_value=_run(listing.encode("utf-8"))):
            self.assertIs(game_running(), True)

    def test_utf8_no_game(self):
        listing = "Image Name                     PID Session Name        Session#    Mem Usage\r\n"
        listing += "notepad.exe                   111 Console                   1    200 K\r\n"
        with mock.patch("subprocess.run", return_value=_run(listing.encode("utf-8"))):
            self.assertIs(game_running(), False)

    def test_gbk_game_detected_when_utf8_would_fail(self):
        # Include a GBK-only character so utf-8 decoding fails, plus r5apex.
        raw = "进程名 r5apex.exe 说明：".encode("gbk") + "测试".encode("gbk")
        self.assertRaises(UnicodeDecodeError, raw.decode, "utf-8")
        with mock.patch("subprocess.run", return_value=_run(raw)):
            self.assertIs(game_running(), True)

    def test_gbk_clear_when_utf8_would_fail(self):
        raw = "进程名 notepad.exe 说明：空闲".encode("gbk")
        self.assertRaises(UnicodeDecodeError, raw.decode, "utf-8")
        with mock.patch("subprocess.run", return_value=_run(raw)):
            self.assertIs(game_running(), False)

    def test_tasklist_nonzero_is_unknown_not_clear(self):
        with mock.patch("subprocess.run", return_value=_run(b"", b"access denied", 1)):
            self.assertIsNone(game_running())

    def test_tasklist_exception_is_unknown_not_clear(self):
        with mock.patch("subprocess.run", side_effect=OSError("tasklist missing")):
            self.assertIsNone(game_running())

    def test_timeout_is_unknown(self):
        import subprocess
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("tasklist", 30)):
            self.assertIsNone(game_running())

    def test_refuse_if_game_stops_when_running(self):
        with mock.patch("fac_tinyagent.p0_run.game_running", return_value=True):
            with self.assertRaises(SystemExit) as ctx:
                refuse_if_game()
        self.assertIn("r5apex is running", str(ctx.exception))

    def test_refuse_if_game_fail_closed_on_unknown(self):
        with mock.patch("fac_tinyagent.p0_run.game_running", return_value=None):
            with self.assertRaises(SystemExit) as ctx:
                refuse_if_game()
        self.assertIn("tasklist check failed", str(ctx.exception))

    def test_refuse_if_game_allows_clear(self):
        with mock.patch("fac_tinyagent.p0_run.game_running", return_value=False):
            refuse_if_game()


class DayCountPrintTests(unittest.TestCase):
    def test_zero_is_not_rendered_as_sentinel(self):
        # The old log used `x or -1`, which turned a real 0.0 into -1.000.
        day_count = 0.0
        tool = 0.0
        rendered = "day=%.3f tool=%.3f" % (
            day_count if day_count is not None else -1,
            tool if tool is not None else -1,
        )
        self.assertEqual(rendered, "day=0.000 tool=0.000")
        self.assertNotIn("day=-1.000", rendered)


if __name__ == "__main__":
    unittest.main()
