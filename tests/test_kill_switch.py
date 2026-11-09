import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_trading import kill_switch as ks
from paper_trading.kill_switch import KillSwitch, KillSwitchError
from scripts import kill_switch as cli


class KillSwitchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "HALT"

    def test_absent_sentinel_is_not_engaged(self):
        self.assertFalse(KillSwitch(self.path).engaged())

    def test_engage_is_idempotent_and_logged(self):
        switch = KillSwitch(self.path)
        first = switch.engage("manual", actor="ken")
        again = switch.engage("other reason", actor="someone")
        self.assertTrue(first["engaged"])
        self.assertEqual(again["reason"], "manual")
        self.assertEqual([e["event"] for e in switch.history()], ["engage"])

    def test_halt_survives_restart(self):
        KillSwitch(self.path).engage("loss", actor="risk_gate")
        fresh = KillSwitch(self.path)
        self.assertEqual(fresh.status()["actor"], "risk_gate")

    def test_unreadable_or_malformed_sentinel_fails_closed(self):
        self.path.write_text("not json")
        self.assertEqual(KillSwitch(self.path).status()["reason"], "malformed_sentinel")
        self.path.write_text("[1]")
        self.assertTrue(KillSwitch(self.path).engaged())
        self.path.unlink()
        self.path.mkdir()  # reading a directory raises OSError
        self.assertEqual(KillSwitch(self.path).status()["reason"], "unreadable_sentinel")

    def test_release_requires_actor_and_note(self):
        switch = KillSwitch(self.path)
        switch.engage("loss")
        for actor, note in [("", "ok"), ("ken", " ")]:
            with self.assertRaises(KillSwitchError):
                switch.release(actor, note)
        self.assertTrue(switch.engaged())
        with self.assertRaises(KillSwitchError):
            KillSwitch(Path(self.tmp.name) / "other").release("ken", "note")

    def test_release_is_journaled_before_removal(self):
        switch = KillSwitch(self.path)
        switch.engage("loss")
        switch.release("ken", "reviewed fills")
        self.assertFalse(switch.engaged())
        events = switch.history()
        self.assertEqual([e["event"] for e in events], ["engage", "release"])
        self.assertEqual(events[1]["actor"], "ken")

    def test_crash_after_journal_before_unlink_stays_engaged(self):
        switch = KillSwitch(self.path)
        switch.engage("loss")
        with mock.patch.object(Path, "unlink", side_effect=OSError("crash")):
            with self.assertRaises(OSError):
                switch.release("ken", "note")
        self.assertTrue(KillSwitch(self.path).engaged())

    def test_unreadable_log_blocks_release(self):
        switch = KillSwitch(self.path)
        switch.engage("loss")
        switch.log_path.write_text("garbage")
        with self.assertRaises(KillSwitchError):
            switch.release("ken", "note")
        self.assertTrue(switch.engaged())

    def test_cli_engage_status_release(self):
        def run(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(["--path", str(self.path), *argv])
            return code, out.getvalue()
        self.assertEqual(run("status")[0], 0)
        self.assertEqual(run("engage", "--reason", "manual")[0], 0)
        code, text = run("status")
        self.assertEqual(code, 1)
        self.assertTrue(json.loads(text)["engaged"])
        self.assertEqual(run("release", "--actor", "ken", "--note", "ok")[0], 0)
        self.assertEqual(run("status")[0], 0)

    def test_default_path_does_not_live_inside_tracked_sources(self):
        self.assertIn(".local", ks.DEFAULT_PATH.parts)


if __name__ == "__main__":
    unittest.main()
