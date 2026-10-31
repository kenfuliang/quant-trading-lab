"""Coordinator infrastructure only: fresh synthetic subprocesses, no strategy runs."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from research.research_controller import WriterBusy
from research.rsi_coordinator import (
    ROOT, RSIError, RSIProgram, freeze_program, incremental_preflight_case, synthetic_case,
)


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "program"

    def tearDown(self):
        self.temp.cleanup()

    def spec(self, *, cycles=None, max_launches=4, wall_seconds=30):
        if cycles is None:
            cycles = [self.cycle("c1", [synthetic_case("a", payload={"case": "a"}), synthetic_case("b", payload={"case": "b"})])]
        return freeze_program(self.directory, program_id="test-program", cycles=cycles,
                              bounds={"max_launches": max_launches, "max_financial_slots": 0, "wall_seconds": wall_seconds})

    @staticmethod
    def cycle(cid, cases):
        return {"cycle_id": cid, "parent_identities": {}, "criteria": {"objective": "verify synthetic output contract"}, "cases": cases}

    def test_real_synthetic_process_sealed_before_audit_and_cache_resume(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._audit
            audit_statuses = []
            def inspect(key, case):
                self.assertTrue((self.directory / "cases" / key / "stdout.txt").exists())
                self.assertTrue((self.directory / "cases" / key / "stderr.txt").exists())
                self.assertTrue((self.directory / "cases" / key / "artifacts/partial.txt").exists())
                audit_statuses.append(program.state["attempts"][key]["status"])
                return original(key, case)
            with patch.object(program, "_audit", side_effect=inspect):
                result = program.execute("c1", "a")
            self.assertEqual(audit_statuses[0], "captured")
            self.assertEqual(result["status"], "completed")
            self.assertFalse(result["cached"])
            self.assertEqual(result["financial_slots"], 0)
            self.assertIn("research/rsi_coordinator.py", result["code_hashes"])
            self.assertIn("-I", result["argv"])
            self.assertIn("artifacts/result.json", result["artifact_hashes"])
            self.assertEqual(program.usage()["launch_reservations"], 1)
            self.assertEqual(program.usage()["launches_observed"], 1)
            self.assertEqual(program.usage()["financial_slots_reserved"], 0)
        log_before = (self.directory / "execution.jsonl").read_bytes()
        with RSIProgram(self.directory, spec=spec) as program:
            with patch.object(program, "_run_process", side_effect=AssertionError("No relaunch")):
                reused = program.execute("c1", "a")
            self.assertTrue(reused["cached"])
            self.assertEqual(program.controller_state["attempts"]["attempt-0001"]["status"], "completed")
        self.assertEqual((self.directory / "execution.jsonl").read_bytes(), log_before)

    def test_aggregate_budget_survives_cycle_rename_and_resume(self):
        cycles = [self.cycle("c1", [synthetic_case("a", payload={"n": 1})]), self.cycle("c2", [synthetic_case("b", payload={"n": 2})])]
        spec = self.spec(cycles=cycles, max_launches=1)
        with RSIProgram(self.directory, spec=spec) as program:
            program.execute("c1", "a")
        with RSIProgram(self.directory, spec=spec) as program:
            with self.assertRaisesRegex(RSIError, "Aggregate launch"):
                program.execute("c2", "b")
            with self.assertRaisesRegex(RSIError, "not registered"):
                program.execute("new-cycle", "a")
        changed = copy.deepcopy(spec); changed["bounds"]["max_launches"] = 5
        with self.assertRaisesRegex(RSIError, "changed"):
            RSIProgram(self.directory, spec=changed)

    def test_failure_consumes_slot_logs_streams_and_preserves_partial(self):
        spec = self.spec(cycles=[self.cycle("c1", [synthetic_case("a", behavior="fail")])], max_launches=1)
        with RSIProgram(self.directory, spec=spec) as program:
            result = program.execute("c1", "a")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["returncode"], 7)
            self.assertIn("artifacts/partial.txt", result["artifact_hashes"])
            self.assertEqual((self.directory / "cases/c1/a/stdout.txt").read_text(), "synthetic stdout\n")
            self.assertEqual((self.directory / "cases/c1/a/stderr.txt").read_text(), "synthetic stderr\n")
            self.assertEqual(program.usage()["launch_reservations"], 1)
            self.assertEqual(program.controller_state["resolved_questions"], [])
            self.assertTrue(program.execute("c1", "a")["cached"])

    def test_timeout_preserves_TimeoutExpired_streams_and_partial_artifacts(self):
        spec = self.spec(cycles=[self.cycle("c1", [synthetic_case("a", sleep_seconds=1, timeout_seconds=.1)])])
        with RSIProgram(self.directory, spec=spec) as program:
            result = program.execute("c1", "a")
            self.assertEqual(result["status"], "timed_out")
            self.assertIn("artifacts/partial.txt", result["artifact_hashes"])
            self.assertIn("synthetic stdout", (self.directory / "cases/c1/a/stdout.txt").read_text())
            self.assertIn("synthetic stderr", (self.directory / "cases/c1/a/stderr.txt").read_text())
            self.assertEqual(program.usage()["launch_reservations"], 1)

    def test_timeout_exception_with_bytes_retains_both_streams(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            with patch.object(program, "_run_process", side_effect=subprocess.TimeoutExpired(["fixture"], 1, output=b"before timeout", stderr=b"error before timeout")):
                result = program.execute("c1", "a")
            self.assertEqual(result["status"], "timed_out")
            self.assertEqual((self.directory / "cases/c1/a/stdout.txt").read_bytes(), b"before timeout")
            self.assertEqual((self.directory / "cases/c1/a/stderr.txt").read_bytes(), b"error before timeout")

    def test_aggregate_deadline_is_not_reset_on_resume(self):
        spec = self.spec(wall_seconds=.05)
        with RSIProgram(self.directory, spec=spec) as program:
            original_deadline = program.state["deadline_epoch"]
        time.sleep(.06)
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertEqual(program.state["deadline_epoch"], original_deadline)
            with self.assertRaisesRegex(RSIError, "deadline"):
                program.execute("c1", "a")
            self.assertEqual(program.usage()["launch_reservations"], 0)

    def test_deadline_expiring_during_reservation_does_not_launch(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._append
            def expire(kind, payload):
                result = original(kind, payload)
                if kind == "launch_intent":
                    program._opening_remaining = 0
                return result
            with patch.object(program, "_append", side_effect=expire), patch("research.rsi_coordinator.subprocess.Popen", side_effect=AssertionError("Expired program must not launch")):
                result = program.execute("c1", "a")
            self.assertEqual(result["status"], "interrupted_before_launch")
            self.assertEqual(program.usage()["launch_reservations"], 1)
            self.assertEqual(program.usage()["launches_observed"], 0)

    def test_concurrent_writer_is_rejected_in_second_process(self):
        spec = self.spec()
        path = Path(self.temp.name) / "spec.json"; path.write_text(json.dumps(spec))
        code = "import json,sys; from research.rsi_coordinator import RSIProgram; from research.research_controller import WriterBusy\ntry: RSIProgram(sys.argv[1],spec=json.load(open(sys.argv[2])))\nexcept WriterBusy: print('writer-busy');sys.exit(0)\nsys.exit(3)"
        with RSIProgram(self.directory, spec=spec):
            child = subprocess.run([sys.executable, "-c", code, str(self.directory), str(path)], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(child.stdout.strip(), "writer-busy")

    def test_before_launch_interruption_consumes_reservation_never_relaunches(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            with patch.object(program, "_logical_reserve", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    program.execute("c1", "a")
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertEqual(program.state["attempts"]["c1/a"]["status"], "interrupted_before_launch")
            self.assertEqual(program.usage()["launch_reservations"], 1)
            self.assertEqual(program.usage()["launches_observed"], 0)
            with patch.object(program, "_run_process", side_effect=AssertionError("No retry")):
                self.assertTrue(program.execute("c1", "a")["cached"])
            self.assertEqual(program.execute("c1", "b")["status"], "completed")

    def test_interrupted_launch_intent_blocks_entire_program(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._append
            def crash(kind, payload):
                original(kind, payload)
                if kind == "launch_intent":
                    raise KeyboardInterrupt
            with patch.object(program, "_append", side_effect=crash):
                with self.assertRaises(KeyboardInterrupt):
                    program.execute("c1", "a")
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertEqual(program.state["attempts"]["c1/a"]["status"], "ambiguous")
            self.assertEqual(program.usage()["launch_reservations"], 1)
            with self.assertRaisesRegex(RSIError, "Ambiguous"):
                program.execute("c1", "b")

    def test_after_launch_interruption_saves_streams_and_stops(self):
        spec = self.spec()
        interrupted = KeyboardInterrupt(); interrupted.rsi_stdout = b"partial stdout"; interrupted.rsi_stderr = b"partial stderr"
        with RSIProgram(self.directory, spec=spec) as program:
            with patch.object(program, "_run_process", side_effect=interrupted):
                with self.assertRaises(KeyboardInterrupt):
                    program.execute("c1", "a")
            self.assertEqual(program.state["attempts"]["c1/a"]["status"], "interrupted_after_launch")
            self.assertEqual((self.directory / "cases/c1/a/stdout.txt").read_bytes(), b"partial stdout")
            with self.assertRaisesRegex(RSIError, "interrupted_after_launch"):
                program.execute("c1", "b")

    def test_crash_after_process_output_before_capture_is_ambiguous(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._append
            def crash(kind, payload):
                if kind == "captured":
                    raise KeyboardInterrupt
                return original(kind, payload)
            with patch.object(program, "_append", side_effect=crash):
                with self.assertRaises(KeyboardInterrupt):
                    program.execute("c1", "a")
        self.assertTrue((self.directory / "cases/c1/a/stdout.txt").exists())
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertEqual(program.state["attempts"]["c1/a"]["status"], "ambiguous")
            self.assertEqual(program.usage()["launches_observed"], 1)

    def test_capture_survives_interruption_before_audit_reconciles_once(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            with patch.object(program, "_finalize_captured", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    program.execute("c1", "a")
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertEqual(program.state["attempts"]["c1/a"]["status"], "completed")
            self.assertTrue(program.execute("c1", "a")["cached"])
            self.assertEqual(len(program.controller_state["attempts"]), 1)

    def test_integrity_stop_is_atomic_with_terminal_outcome(self):
        spec = self.spec(cycles=[self.cycle("c1", [synthetic_case("a", behavior="missing"), synthetic_case("b")])])
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._append
            def crash(kind, payload):
                result = original(kind, payload)
                if kind == "finalized":
                    raise KeyboardInterrupt
                return result
            with patch.object(program, "_append", side_effect=crash):
                with self.assertRaises(KeyboardInterrupt):
                    program.execute("c1", "a")
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertIn("integrity_failed", program.state["stopped_reason"])
            with self.assertRaisesRegex(RSIError, "integrity_failed"):
                program.execute("c1", "b")

    def test_missing_expected_output_fails_closed_and_no_resolution(self):
        spec = self.spec(cycles=[self.cycle("c1", [synthetic_case("a", behavior="missing"), synthetic_case("b")])])
        with RSIProgram(self.directory, spec=spec) as program:
            result = program.execute("c1", "a")
            self.assertEqual(result["status"], "integrity_failed")
            self.assertIn("stdout.txt", result["artifact_hashes"])
            self.assertEqual(program.controller_state["resolved_questions"], [])
            with self.assertRaisesRegex(RSIError, "integrity_failed"):
                program.execute("c1", "b")

    def test_tampered_output_rejected_on_execute_and_reopen(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            program.execute("c1", "a")
            (self.directory / "cases/c1/a/artifacts/result.json").write_text("{}")
            with self.assertRaisesRegex(RSIError, "tampered"):
                program.execute("c1", "a")
        with self.assertRaisesRegex(RSIError, "tampered"):
            RSIProgram(self.directory, spec=spec)

    def test_tamper_after_audit_cannot_record_completed_controller_outcome(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._record_controller
            def tamper(key):
                (self.directory / "cases" / key / "artifacts/result.json").write_text("{}")
                return original(key)
            with patch.object(program, "_record_controller", side_effect=tamper):
                with self.assertRaisesRegex(RSIError, "tampered"):
                    program.execute("c1", "a")
            self.assertEqual(program.controller_state["attempts"]["attempt-0001"]["status"], "reserved")
            self.assertEqual(program.controller_state["resolved_questions"], [])

    def test_missing_or_added_output_and_symlink_rejected(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            program.execute("c1", "a")
            extra = self.directory / "cases/c1/a/extra"; extra.write_text("extra")
            with self.assertRaisesRegex(RSIError, "tampered"):
                program.execute("c1", "a")
            extra.unlink(); extra.symlink_to("stdout.txt")
            with self.assertRaisesRegex(RSIError, "Symlink"):
                program.execute("c1", "a")
            extra.unlink(); (self.directory / "cases/c1/a/stdout.txt").unlink()
            with self.assertRaisesRegex(RSIError, "tampered"):
                program.execute("c1", "a")

    def test_duplicate_observation_renamed_under_new_cycle_is_rejected(self):
        case = synthetic_case("a", payload={"identical": True})
        spec = self.spec(cycles=[self.cycle("c1", [case]), self.cycle("c2", [case])])
        with RSIProgram(self.directory, spec=spec) as program:
            program.execute("c1", "a")
            with self.assertRaisesRegex(RSIError, "duplicate"):
                program.execute("c2", "a")
            self.assertEqual(program.usage()["launch_reservations"], 1)

    def test_arbitrary_command_financial_count_and_financial_adapter_rejected(self):
        for extra in ({"argv": ["sh", "-c", "echo nope"]}, {"financial_slots": 0}):
            case = synthetic_case("a"); case.update(extra)
            with self.assertRaisesRegex(RSIError, "arbitrary argv"):
                self.spec(cycles=[self.cycle("c1", [case])])
        case = synthetic_case("a"); case["adapter"] = "financial_runner"
        with self.assertRaisesRegex(RSIError, "financial execution unsupported"):
            self.spec(cycles=[self.cycle("c1", [case])])

    def test_exact_command_and_code_identity_cannot_be_overridden(self):
        spec = self.spec()
        for mutate in (lambda p: p["cycles"][0]["cases"][0]["argv"].append("--execute"),
                       lambda p: p["code_hashes"].update({"research/rsi_coordinator.py": "0" * 64}),
                       lambda p: p["cycles"][0]["cases"][0].update(financial_slots=8)):
            changed = copy.deepcopy(spec); mutate(changed)
            with self.assertRaisesRegex(RSIError, "changed"):
                RSIProgram(self.directory, spec=changed)

    def test_mutating_open_program_spec_cannot_change_frozen_timeout(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            program.spec["cycles"][0]["cases"][0]["timeout_seconds"] += 10
            with self.assertRaisesRegex(RSIError, "changed after immutable"):
                program.execute("c1", "a")
            self.assertEqual(program.usage()["launch_reservations"], 0)

    def test_code_input_drift_after_process_gets_no_completion_credit(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._run_process
            def mutate(key, argv, timeout):
                result = original(key, argv, timeout)
                program.spec["cycles"][0]["criteria"]["objective"] = "changed after process"
                return result
            with patch.object(program, "_run_process", side_effect=mutate):
                with self.assertRaisesRegex(RSIError, "changed after immutable"):
                    program.execute("c1", "a")
            self.assertEqual(program.state["attempts"]["c1/a"]["status"], "integrity_failed")
            self.assertEqual(program.controller_state["resolved_questions"], [])

    def test_launch_error_consumes_attempt_and_retains_error(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            with patch("research.rsi_coordinator.subprocess.Popen", side_effect=OSError("fixture exec unavailable")):
                result = program.execute("c1", "a")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(program.usage()["launch_reservations"], 1)
            self.assertIn("fixture exec unavailable", (self.directory / "cases/c1/a/stderr.txt").read_text())

    def test_post_Popen_journal_failure_terminates_child_group(self):
        from unittest.mock import Mock
        spec = self.spec()
        child = Mock(pid=12345)
        child.communicate.return_value = (b"captured before journal error", b"partial error")
        with RSIProgram(self.directory, spec=spec) as program:
            original = program._append
            def fail_launched(kind, payload):
                if kind == "launched":
                    raise OSError("fixture journal unavailable")
                return original(kind, payload)
            with patch.object(program, "_append", side_effect=fail_launched), patch("research.rsi_coordinator.subprocess.Popen", return_value=child), patch("research.rsi_coordinator.os.killpg") as kill:
                with self.assertRaisesRegex(OSError, "journal unavailable"):
                    program.execute("c1", "a")
            kill.assert_called_once()
            self.assertEqual(kill.call_args.args[0], child.pid)
            child.communicate.assert_called_once()
            self.assertEqual(program.state["attempts"]["c1/a"]["status"], "interrupted_after_launch")
            self.assertEqual(program.usage()["launches_observed"], 1)
            self.assertEqual((self.directory / "cases/c1/a/stdout.txt").read_bytes(), b"captured before journal error")

    def test_symlink_output_ancestor_is_rejected_before_reservation(self):
        spec = self.spec()
        outside = Path(self.temp.name) / "outside"; outside.mkdir()
        with RSIProgram(self.directory, spec=spec) as program:
            (self.directory / "cases").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(RSIError, "Symlink"):
                program.execute("c1", "a")
            self.assertEqual(program.usage()["launch_reservations"], 0)

    def test_partial_hashchain_or_changed_snapshot_rejected(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec):
            pass
        snapshot = self.directory / "execution-state.json"; saved = json.loads(snapshot.read_text())
        saved["state"]["deadline_epoch"] += 500; snapshot.write_text(json.dumps(saved))
        with self.assertRaisesRegex(RSIError, "snapshot differs"):
            RSIProgram(self.directory, spec=spec)
        snapshot.unlink()
        with (self.directory / "execution.jsonl").open("ab") as stream:
            stream.write(b"{")
        with self.assertRaisesRegex(RSIError, "Partial execution"):
            RSIProgram(self.directory, spec=spec)

    def test_active_writer_detects_execution_log_tamper_before_second_launch(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            program.execute("c1", "a")
            with (self.directory / "execution.jsonl").open("ab") as stream:
                stream.write(b"corruption\n")
            with self.assertRaisesRegex(RSIError, "Execution journal changed"):
                program.execute("c1", "b")
            self.assertEqual(program.usage()["launch_reservations"], 1)

    def test_active_writer_detects_controller_log_tamper_before_cache(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            program.execute("c1", "a")
            with (self.directory / "controller/events.jsonl").open("ab") as stream:
                stream.write(b"corruption\n")
            with self.assertRaisesRegex(RSIError, "Controller journal changed"):
                program.execute("c1", "a")

    def test_missing_snapshot_is_reconstructed_without_budget_reset(self):
        spec = self.spec()
        with RSIProgram(self.directory, spec=spec) as program:
            program.execute("c1", "a")
        (self.directory / "execution-state.json").unlink()
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertEqual(program.usage()["launch_reservations"], 1)
            self.assertTrue(program.execute("c1", "a")["cached"])

    def test_preflight_adapter_is_exact_read_only_no_financial_options(self):
        case = incremental_preflight_case("saved")
        # A mock replaces the process, so this unit test does not inspect market data.
        with patch("research.rsi_coordinator._saved_preflight_inputs", return_value={}):
            spec = self.spec(cycles=[self.cycle("c1", [case])])
            argv = spec["cycles"][0]["cases"][0]["argv"]
            self.assertEqual(argv, [sys.executable, "-m", "research.incremental_sizing"])
            with RSIProgram(self.directory, spec=spec) as program:
                result_process = subprocess.CompletedProcess(argv, 0, b"Preflight passed; zero financial attempts\n", b"")
                with patch.object(program, "_run_process", return_value=result_process):
                    result = program.execute("c1", "saved")
                self.assertEqual(result["status"], "completed")
                self.assertFalse(result["audit"]["financial_execution_verified"])
                self.assertEqual(program.usage()["financial_slots_reserved"], 0)
        case["parameters"] = {"execute": True}
        with self.assertRaisesRegex(RSIError, "no options"):
            self.spec(cycles=[self.cycle("c1", [case])])

    def test_cycle_contract_budget_and_artifacts_are_enforced(self):
        from tests.test_rsi_contracts import valid_cycle
        from research.rsi_coordinator import digest
        contract = valid_cycle()
        contract.update(program_id="test-program", cycle_id="c1")
        contract["artifacts"] = [{"path": "requirements.txt", "sha256": digest(ROOT / "requirements.txt")}]
        cycle = self.cycle("c1", [synthetic_case("a")])
        cycle.update(contract=contract, criteria=contract["criteria"])
        spec = self.spec(cycles=[cycle])
        self.assertIn(str(ROOT / "requirements.txt"), spec["cycles"][0]["parent_identities"])
        with RSIProgram(self.directory, spec=spec) as program:
            self.assertEqual(program.execute("c1", "a")["status"], "completed")
        cycle["cases"].append(synthetic_case("b"))
        with self.assertRaisesRegex(RSIError, "exceed cycle contract budget"):
            self.spec(cycles=[cycle])
        cycle["cases"].pop()
        with self.assertRaisesRegex(RSIError, "exceed cycle contract budget"):
            self.spec(cycles=[cycle], wall_seconds=31)
        cycle["contract"]["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash|changed|SHA|identity"):
            self.spec(cycles=[cycle])


if __name__ == "__main__":
    unittest.main()
