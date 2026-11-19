"""Process-crash checks for Session and Checkpoint atomic publication."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_WORKER = r"""
import os
import sys

from bugmaster_core.checkpoint_store import CheckpointStore
from bugmaster_core.session_store import SessionStore

root, store_kind, scenario = sys.argv[1:]
validator = lambda document: None

if store_kind == "session":
    import bugmaster_core.session_store as store_module

    store = SessionStore(root, "session-1", validator)
    store._ensure_directories()
    document = {
        "schemaVersion": "1.0",
        "sessionId": "session-1",
        "revision": 1,
        "projectRef": "project-1",
        "hostRef": "host-1",
        "environmentRef": "environment-1",
        "createdAt": "2026-11-19T00:00:00Z",
        "journalId": "journal-1",
        "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
        "approvalRefs": [],
        "checkpointRefs": [],
        "actionBudget": {},
    }
else:
    import bugmaster_core.checkpoint_store as store_module

    store = CheckpointStore(root, "session-1", validator)
    store._ensure_directories()
    document = {"sessionId": "session-1", "checkpointId": "checkpoint-1"}


def partial_write(fd, payload):
    original_write(fd, payload[: max(1, len(payload) // 2)])
    os._exit(71)


if scenario == "partial-write":
    original_write = os.write
    os.write = partial_write
elif scenario == "before-link":
    os.link = lambda source, destination: os._exit(71)
elif scenario == "after-link-before-directory-sync":
    store_module._fsync_directory = lambda directory: os._exit(71)
elif scenario == "after-directory-sync-before-cleanup":
    original_sync_directory = store_module._fsync_directory

    def sync_then_exit(directory):
        original_sync_directory(directory)
        os._exit(71)

    store_module._fsync_directory = sync_then_exit
else:
    raise AssertionError("unknown crash scenario: " + scenario)

store.create(document)
raise AssertionError("crash injection did not terminate the worker")
"""


class StoreCrashRecoveryTests(unittest.TestCase):
    def _run_crashed_worker(self, root, store_kind, scenario):
        if store_kind == "session":
            self._session_store(root)._ensure_directories()
        else:
            checkpoint_store = self._checkpoint_store(root)
            checkpoint_store._ensure_directories()
            checkpoint_store._ensure_private_directory(
                checkpoint_store._checkpoints_dir
            )
        result = subprocess.run(
            [sys.executable, "-c", _WORKER, str(root), store_kind, scenario],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 71, result.stderr)

    def _session_store(self, root):
        from bugmaster_core.session_store import SessionStore

        return SessionStore(root, "session-1", lambda document: None)

    def _checkpoint_store(self, root):
        from bugmaster_core.checkpoint_store import CheckpointStore

        return CheckpointStore(root, "session-1", lambda document: None)

    def _assert_session_not_published_and_retryable(self, root, scenario):
        self._run_crashed_worker(root, "session", scenario)
        store = self._session_store(root)
        self.assertIsNone(store.read_latest())
        self.assertEqual(store.create(_session_document())["revision"], 1)
        self.assertEqual(store.read_latest()["revision"], 1)

    def _assert_checkpoint_not_published_and_retryable(self, root, scenario):
        self._run_crashed_worker(root, "checkpoint", scenario)
        store = self._checkpoint_store(root)
        self.assertIsNone(store.read("checkpoint-1"))
        document = {"sessionId": "session-1", "checkpointId": "checkpoint-1"}
        self.assertEqual(store.create(document), document)
        self.assertEqual(store.read("checkpoint-1"), document)

    def test_partial_session_revision_write_is_not_published_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            self._assert_session_not_published_and_retryable(
                Path(directory), "partial-write"
            )

    def test_session_revision_before_link_is_not_published_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            self._assert_session_not_published_and_retryable(
                Path(directory), "before-link"
            )

    def test_session_revision_after_link_is_complete_and_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "session", "after-link-before-directory-sync"
            )
            self.assertEqual(self._session_store(root).read_latest(), _session_document())

    def test_synced_session_revision_is_readable_after_crash_before_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "session", "after-directory-sync-before-cleanup"
            )
            self.assertEqual(self._session_store(root).read_latest(), _session_document())

    def test_partial_checkpoint_write_is_not_published_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            self._assert_checkpoint_not_published_and_retryable(
                Path(directory), "partial-write"
            )

    def test_checkpoint_before_link_is_not_published_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            self._assert_checkpoint_not_published_and_retryable(
                Path(directory), "before-link"
            )

    def test_checkpoint_after_link_is_complete_and_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "checkpoint", "after-link-before-directory-sync"
            )
            self.assertEqual(
                self._checkpoint_store(root).read("checkpoint-1"),
                {"sessionId": "session-1", "checkpointId": "checkpoint-1"},
            )

    def test_synced_checkpoint_is_readable_after_crash_before_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "checkpoint", "after-directory-sync-before-cleanup"
            )
            self.assertEqual(
                self._checkpoint_store(root).read("checkpoint-1"),
                {"sessionId": "session-1", "checkpointId": "checkpoint-1"},
            )


def _session_document():
    return {
        "schemaVersion": "1.0",
        "sessionId": "session-1",
        "revision": 1,
        "projectRef": "project-1",
        "hostRef": "host-1",
        "environmentRef": "environment-1",
        "createdAt": "2026-11-19T00:00:00Z",
        "journalId": "journal-1",
        "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
        "approvalRefs": [],
        "checkpointRefs": [],
        "actionBudget": {},
    }


if __name__ == "__main__":
    unittest.main()
