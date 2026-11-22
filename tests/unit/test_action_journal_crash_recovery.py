"""Process-crash checks for conservative Action Journal recovery."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_WORKER = r"""
import os
import stat
import sys

from bugmaster_core.action_journal import ActionJournal
from bugmaster_core.action_journal_store import ActionJournalStore

storage_path, scenario, storage_mode = sys.argv[1:]
if storage_mode == "store-backed":
    journal = ActionJournalStore(
        storage_path, "session-1", "journal-1"
    ).open()
else:
    journal = ActionJournal(
        storage_path, session_id="session-1", journal_id="journal-1"
    )
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
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
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
elif scenario == "failed-risk-enumeration":
    for action_id, risk in (("action-risk-zero", "R0"), ("action-risk-one", "R1")):
        journal.prepare(action_id, digest, 1, risk)
        journal.mark_dispatched(action_id, digest)
        journal.record_outcome(action_id, "failed", "failure-ref")
    os._exit(71)
else:
    raise AssertionError("unknown crash scenario: " + scenario)

raise AssertionError("crash injection did not terminate the worker")
"""


class ActionJournalCrashRecoveryTests(unittest.TestCase):
    def _run_crashed_worker(self, root, scenario, *, store_backed=False):
        worker_storage_path = root
        if store_backed:
            from bugmaster_core.action_journal_store import ActionJournalStore
            from bugmaster_core.session_store import SessionStore

            store = ActionJournalStore(root, "session-1", "journal-1")
            store.initialize().close()
            SessionStore(root, "session-1", lambda _document: None).create(
                {
                    "schemaVersion": "1.0",
                    "sessionId": "session-1",
                    "revision": 1,
                    "status": "created",
                    "projectRef": "project-1",
                    "hostRef": "codex",
                    "environmentRef": "local",
                    "createdAt": "2026-11-21T00:00:00Z",
                    "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                    "approvalRefs": [],
                    "checkpointRefs": [],
                    "actionBudget": {},
                    "journalId": "journal-1",
                }
            )
            journal_path = store.path
        else:
            journal_path = root / "journal.jsonl"
            journal_path.write_bytes(b"")
            journal_path.chmod(0o600)
            worker_storage_path = journal_path
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                _WORKER,
                str(worker_storage_path),
                scenario,
                "store-backed" if store_backed else "path-based",
            ],
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

    def test_enumeration_of_an_empty_journal_returns_no_actions(self):
        from bugmaster_core.action_journal import ActionJournal

        with tempfile.TemporaryDirectory() as directory:
            journal_path = Path(directory) / "journal.jsonl"
            journal_path.write_bytes(b"")
            journal_path.chmod(0o600)
            recovered = ActionJournal(
                journal_path, session_id="session-1", journal_id="journal-1"
            )
            self.assertEqual(recovered.actions_needing_reconciliation(), ())

    def test_store_backed_crash_requires_reconciliation(self):
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.action_journal import JournalError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "dispatched-after-fsync", store_backed=True
            )
            recovered = ActionJournalStore(
                root, "session-1", "journal-1"
            ).open()
            self.assertEqual(
                recovered.actions_needing_reconciliation(), ("action-1",)
            )
            with self.assertRaises(JournalError):
                recovered.mark_dispatched("action-1", intent_digest="a" * 64)
            recovered.close()

    def test_failed_nonzero_risk_action_is_listed_for_reconciliation(self):
        from bugmaster_core.action_journal import ActionJournal

        with tempfile.TemporaryDirectory() as directory:
            journal_path = self._run_crashed_worker(
                Path(directory), "failed-risk-enumeration"
            )
            recovered = ActionJournal(
                journal_path, session_id="session-1", journal_id="journal-1"
            )
            self.assertEqual(
                recovered.actions_needing_reconciliation(), ("action-risk-one",)
            )
            self.assertEqual(
                recovered.recovery_status("action-risk-zero"), "terminal"
            )
            self.assertEqual(
                recovered.recovery_status("action-risk-one"),
                "needs_reconciliation",
            )

    def test_enumeration_fails_closed_when_journal_is_missing(self):
        from bugmaster_core.action_journal import ActionJournal, JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            recovered = ActionJournal(
                Path(directory) / "missing.jsonl",
                session_id="session-1",
                journal_id="journal-1",
            )
            with self.assertRaises(JournalCorruptionError):
                recovered.actions_needing_reconciliation()

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
