"""Process-crash checks for Session and Checkpoint atomic publication."""

import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path


_WORKER = r"""
import os
import sys
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from bugmaster_core.checkpoint_store import CheckpointStore
from bugmaster_core.session_store import SessionStore

root, store_kind, scenario = sys.argv[1:]
schema_name = "session" if store_kind == "session" else "checkpoint"
schema_path = Path.cwd() / "schemas" / (schema_name + ".schema.json")
schema = json.loads(schema_path.read_text(encoding="utf-8"))
validator = Draft202012Validator(schema, format_checker=FormatChecker()).validate

if store_kind == "session":
    import bugmaster_core.session_store as store_module

    store = SessionStore(root, "session-1", validator)
    store._ensure_directories()
    document = {
        "schemaVersion": "1.0",
        "sessionId": "session-1",
        "revision": 1,
        "status": "created",
        "projectRef": "project-1",
        "hostRef": "host-1",
        "environmentRef": "environment-1",
        "createdAt": "2026-11-19T00:00:00Z",
        "updatedAt": "2026-11-19T00:00:00Z",
        "journalId": "journal-1",
        "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
        "approvalRefs": [],
        "checkpointRefs": [],
        "actionBudget": {"maxActions": 0, "consumedActions": 0},
    }
else:
    import bugmaster_core.checkpoint_store as store_module

    store = CheckpointStore(root, "session-1", validator)
    store._ensure_directories()
    document = {
        "schemaVersion": "1.0",
        "checkpointId": "checkpoint-1",
        "sessionId": "session-1",
        "sessionRevision": 1,
        "scopeId": "scope-1",
        "scopeRevision": 1,
        "journalSequence": 0,
        "journalHeadHash": None,
        "createdAt": "2026-11-19T00:00:00Z",
    }


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
elif scenario == "after-head-directory-sync":
    original_sync_directory = store_module._fsync_directory
    sync_count = 0

    def sync_then_exit_after_head(directory):
        global sync_count
        sync_count += 1
        original_sync_directory(directory)
        if sync_count == 3:
            os._exit(71)

    store_module._fsync_directory = sync_then_exit_after_head
else:
    raise AssertionError("unknown crash scenario: " + scenario)

store.create(document)
raise AssertionError("crash injection did not terminate the worker")
"""


class StoreCrashRecoveryTests(unittest.TestCase):
    def test_crash_documents_satisfy_the_versioned_storage_schemas(self):
        session_validator = _schema_validator("session")
        checkpoint_validator = _schema_validator("checkpoint")

        self.assertIsNone(session_validator(_session_document()))
        self.assertIsNone(checkpoint_validator(_checkpoint_document()))

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

        return SessionStore(root, "session-1", _schema_validator("session"))

    def _checkpoint_store(self, root):
        from bugmaster_core.checkpoint_store import CheckpointStore

        return CheckpointStore(root, "session-1", _schema_validator("checkpoint"))

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
        document = _checkpoint_document()
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

    def test_session_revision_without_committed_head_fails_closed_after_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "session", "after-link-before-directory-sync"
            )
            from bugmaster_core.session_store import SessionCorruptionError

            with self.assertRaisesRegex(SessionCorruptionError, "head is missing"):
                self._session_store(root).read_latest()

    def test_session_revision_without_committed_head_fails_closed_after_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "session", "after-directory-sync-before-cleanup"
            )
            from bugmaster_core.session_store import SessionCorruptionError

            with self.assertRaisesRegex(SessionCorruptionError, "head is missing"):
                self._session_store(root).read_latest()

    def test_session_revision_with_committed_head_is_readable_after_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(root, "session", "after-head-directory-sync")
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
                _checkpoint_document(),
            )

    def test_synced_checkpoint_is_readable_after_crash_before_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._run_crashed_worker(
                root, "checkpoint", "after-directory-sync-before-cleanup"
            )
            self.assertEqual(
                self._checkpoint_store(root).read("checkpoint-1"),
                _checkpoint_document(),
            )


def _session_document():
    return {
        "schemaVersion": "1.0",
        "sessionId": "session-1",
        "revision": 1,
        "status": "created",
        "projectRef": "project-1",
        "hostRef": "host-1",
        "environmentRef": "environment-1",
        "createdAt": "2026-11-19T00:00:00Z",
        "updatedAt": "2026-11-19T00:00:00Z",
        "journalId": "journal-1",
        "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
        "approvalRefs": [],
        "checkpointRefs": [],
        "actionBudget": {"maxActions": 0, "consumedActions": 0},
    }


def _checkpoint_document():
    return {
        "schemaVersion": "1.0",
        "checkpointId": "checkpoint-1",
        "sessionId": "session-1",
        "sessionRevision": 1,
        "scopeId": "scope-1",
        "scopeRevision": 1,
        "journalSequence": 0,
        "journalHeadHash": None,
        "createdAt": "2026-11-19T00:00:00Z",
    }


def _schema_validator(name):
    from jsonschema import Draft202012Validator, FormatChecker

    schema_path = Path(__file__).resolve().parents[2] / "schemas" / (name + ".schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker()).validate


if __name__ == "__main__":
    unittest.main()
