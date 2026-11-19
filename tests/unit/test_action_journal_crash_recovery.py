"""Process-crash checks for conservative Action Journal recovery."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_WORKER = r"""
import os
import sys

from bugmaster_core.action_journal import ActionJournal

path, scenario = sys.argv[1:]
journal = ActionJournal(path, session_id="session-1", journal_id="journal-1")
digest = "a" * 64


def prepare():
    journal.prepare("action-1", digest, 1, "R0")


def dispatch():
    prepare()
    journal.mark_dispatched("action-1", digest)


def exit_after_write(*, partial=False):
    original_write = os.write

    def write_then_exit(fd, payload):
        if partial:
            original_write(fd, payload[: max(1, len(payload) // 2)])
        else:
            original_write(fd, payload)
        os._exit(71)

    os.write = write_then_exit


def exit_after_fsync():
    original_fsync = os.fsync

    def fsync_then_exit(fd):
        original_fsync(fd)
        os._exit(71)

    os.fsync = fsync_then_exit


if scenario == "partial-prepared":
    exit_after_write(partial=True)
    prepare()
elif scenario == "prepared-before-fsync":
    exit_after_write()
    prepare()
elif scenario == "prepared-after-fsync":
    exit_after_fsync()
    prepare()
elif scenario == "partial-dispatched":
    prepare()
    exit_after_write(partial=True)
    journal.mark_dispatched("action-1", digest)
elif scenario == "dispatched-after-fsync":
    prepare()
    exit_after_fsync()
    journal.mark_dispatched("action-1", digest)
elif scenario == "partial-outcome":
    dispatch()
    exit_after_write(partial=True)
    journal.record_outcome("action-1", "completed", "result-1")
elif scenario == "unknown-outcome":
    dispatch()
    journal.record_outcome("action-1", "outcome_unknown")
    os._exit(71)
elif scenario == "reconciliation-claim":
    dispatch()
    journal.record_reconciliation_claim(
        "action-1",
        "not_executed",
        observation_ref="observation-1",
        observer_ref="observer-1",
        basis="authoritative-read-only",
    )
    os._exit(71)
elif scenario == "completed-outcome":
    dispatch()
    exit_after_fsync()
    journal.record_outcome("action-1", "completed", "result-1")
elif scenario == "enumeration":
    journal.prepare("action-terminal", digest, 1, "R0")
    journal.mark_dispatched("action-terminal", digest)
    journal.record_outcome("action-terminal", "completed", "result-terminal")
    for action_id in ("action-z", "action-a", "action-m"):
        journal.prepare(action_id, digest, 1, "R0")
    os._exit(71)
else:
    raise AssertionError("unknown crash scenario: " + scenario)

raise AssertionError("crash injection did not terminate the worker")
"""


class ActionJournalCrashRecoveryTests(unittest.TestCase):
    def _run_crashed_worker(self, root, scenario):
        journal_path = root / "journal.jsonl"
        journal_path.write_bytes(b"")
        journal_path.chmod(0o600)
        result = subprocess.run(
            [sys.executable, "-c", _WORKER, str(journal_path), scenario],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 71, result.stderr)
        return journal_path

    def _assert_needs_reconciliation(self, journal_path):
        from bugmaster_core.action_journal import ActionJournal, JournalError

        recovered = ActionJournal(
            journal_path, session_id="session-1", journal_id="journal-1"
        )
        self.assertEqual(recovered.recovery_status("action-1"), "needs_reconciliation")
        with self.assertRaises(JournalError):
            recovered.mark_dispatched("action-1", intent_digest="a" * 64)

    def _assert_corruption_fails_closed(self, journal_path):
        from bugmaster_core.action_journal import ActionJournal, JournalCorruptionError

        with self.assertRaises(JournalCorruptionError):
            ActionJournal(
                journal_path, session_id="session-1", journal_id="journal-1"
            )

    def test_crash_during_prepared_event_write_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "partial-prepared"
            )
            self._assert_corruption_fails_closed(journal_path)

    def test_crash_after_prepared_write_before_fsync_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "prepared-before-fsync"
            )
            self._assert_needs_reconciliation(journal_path)

    def test_crash_after_prepared_fsync_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "prepared-after-fsync"
            )
            self._assert_needs_reconciliation(journal_path)

    def test_crash_during_dispatched_event_write_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "partial-dispatched"
            )
            self._assert_corruption_fails_closed(journal_path)

    def test_crash_after_dispatch_marker_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "dispatched-after-fsync"
            )
            self._assert_needs_reconciliation(journal_path)

    def test_crash_during_outcome_write_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "partial-outcome"
            )
            self._assert_corruption_fails_closed(journal_path)

    def test_unknown_outcome_survives_process_crash_as_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "unknown-outcome"
            )
            self._assert_needs_reconciliation(journal_path)

    def test_reconciliation_claim_does_not_unlock_after_process_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "reconciliation-claim"
            )
            self._assert_needs_reconciliation(journal_path)

    def test_recovery_enumerates_every_unresolved_id_in_journal_order(self):
        from bugmaster_core.action_journal import ActionJournal

        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "enumeration"
            )
            recovered = ActionJournal(
                journal_path, session_id="session-1", journal_id="journal-1"
            )
            self.assertEqual(
                recovered.actions_needing_reconciliation(),
                ("action-z", "action-a", "action-m"),
            )

    def test_terminal_action_is_not_listed_for_reconciliation(self):
        from bugmaster_core.action_journal import ActionJournal

        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "completed-outcome"
            )
            recovered = ActionJournal(
                journal_path, session_id="session-1", journal_id="journal-1"
            )
            self.assertEqual(recovered.actions_needing_reconciliation(), ())

    def test_completed_outcome_survives_process_crash_as_terminal(self):
        from bugmaster_core.action_journal import ActionJournal

        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "completed-outcome"
            )
            recovered = ActionJournal(
                journal_path, session_id="session-1", journal_id="journal-1"
            )
            self.assertEqual(recovered.recovery_status("action-1"), "terminal")


if __name__ == "__main__":
    unittest.main()
