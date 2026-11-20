import os
import tempfile
import unittest

from bugmaster_core.checkpoint_store import (
    CheckpointCorruptionError,
    CheckpointStore,
)


class CheckpointStoreSecurityTests(unittest.TestCase):
    def test_read_rejects_checkpoint_directory_with_insecure_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CheckpointStore(directory, "session-1", lambda _document: None)
            checkpoint = {
                "schemaVersion": "1.0",
                "checkpointId": "checkpoint-1",
                "sessionId": "session-1",
                "sessionRevision": 2,
                "scopeId": "scope-1",
                "scopeRevision": 1,
                "journalSequence": 4,
                "journalHeadHash": "a" * 64,
                "createdAt": "2026-11-19T08:00:00Z",
            }
            store.create(checkpoint)
            os.chmod(store._session_dir / "checkpoints", 0o755)

            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")


if __name__ == "__main__":
    unittest.main()
