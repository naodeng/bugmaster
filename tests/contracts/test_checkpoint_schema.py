import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "checkpoint.schema.json"


class CheckpointSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCHEMA_PATH.is_file():
            raise AssertionError("the versioned Checkpoint schema is missing")
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )

    def valid_checkpoint(self):
        return {
            "schemaVersion": "1.0",
            "checkpointId": "checkpoint-1",
            "sessionId": "session-1",
            "sessionRevision": 2,
            "scopeId": "scope-1",
            "scopeRevision": 1,
            "journalSequence": 4,
            "journalHeadHash": "a" * 64,
            "createdAt": "2026-11-18T10:30:00Z",
        }

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_checkpoint_binds_session_revision_scope_and_journal_head(self):
        self.assertEqual(
            list(self.validator.iter_errors(self.valid_checkpoint())), []
        )

    def test_empty_journal_uses_zero_sequence_and_null_hash(self):
        checkpoint = self.valid_checkpoint()
        checkpoint["journalSequence"] = 0
        checkpoint["journalHeadHash"] = None
        self.assertEqual(list(self.validator.iter_errors(checkpoint)), [])

    def test_nonempty_journal_requires_a_head_hash(self):
        checkpoint = self.valid_checkpoint()
        checkpoint["journalHeadHash"] = None
        self.assert_invalid(checkpoint)

    def test_empty_journal_cannot_claim_a_head_hash(self):
        checkpoint = self.valid_checkpoint()
        checkpoint["journalSequence"] = 0
        self.assert_invalid(checkpoint)

    def test_session_revision_must_be_positive(self):
        checkpoint = self.valid_checkpoint()
        checkpoint["sessionRevision"] = 0
        self.assert_invalid(checkpoint)

    def test_journal_head_must_be_a_sha256_digest(self):
        checkpoint = self.valid_checkpoint()
        checkpoint["journalHeadHash"] = "not-a-sha256"
        self.assert_invalid(checkpoint)

    def test_created_at_must_be_a_date_time(self):
        checkpoint = self.valid_checkpoint()
        checkpoint["createdAt"] = "sometime"
        self.assert_invalid(checkpoint)

    def test_untrusted_resume_authorization_fields_are_rejected(self):
        checkpoint = self.valid_checkpoint()
        checkpoint["approved"] = True
        self.assert_invalid(checkpoint)


    def test_checkpoint_store_persists_schema_valid_document(self):
        import tempfile

        try:
            from bugmaster_core.checkpoint_store import CheckpointStore
        except ImportError:
            self.fail("CheckpointStore must persist the versioned Checkpoint contract")

        with tempfile.TemporaryDirectory() as directory:
            store = CheckpointStore(
                directory, "session-1", self.validator.validate
            )
            checkpoint = self.valid_checkpoint()
            self.assertEqual(store.create(checkpoint), checkpoint)
            self.assertEqual(store.read("checkpoint-1"), checkpoint)

    def test_checkpoint_store_rejects_schema_invalid_document_before_writing(self):
        import tempfile

        try:
            from bugmaster_core.checkpoint_store import (
                CheckpointStore,
                CheckpointStoreError,
            )
        except ImportError:
            self.fail("CheckpointStore must reject invalid Checkpoint documents")

        with tempfile.TemporaryDirectory() as directory:
            store = CheckpointStore(
                directory, "session-1", self.validator.validate
            )
            checkpoint = self.valid_checkpoint()
            checkpoint["journalHeadHash"] = None
            with self.assertRaises(CheckpointStoreError):
                store.create(checkpoint)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_checkpoint_reference_validator_accepts_schema_integer_numbers(self):
        import tempfile

        from bugmaster_core.action_journal import ActionJournal
        from bugmaster_core.checkpoint_reference_validator import (
            CheckpointReferenceValidator,
        )
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        session_schema = json.loads(
            (REPOSITORY_ROOT / "schemas" / "session.schema.json").read_text(
                encoding="utf-8"
            )
        )
        session_validator = Draft202012Validator(
            session_schema, format_checker=FormatChecker()
        )
        with tempfile.TemporaryDirectory() as directory:
            session_store = SessionStore(
                directory, "session-1", session_validator.validate
            )
            session = {
                "schemaVersion": "1.0",
                "sessionId": "session-1",
                "revision": 1,
                "status": "created",
                "projectRef": "project-local-orders",
                "hostRef": "codex",
                "environmentRef": "env-isolated-test",
                "createdAt": "2026-11-19T08:00:00Z",
                "updatedAt": "2026-11-19T08:00:00Z",
                "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                "approvalRefs": [],
                "actionBudget": {"maxActions": 20, "consumedActions": 0},
                "journalId": "session-1-journal",
                "checkpointRefs": [],
            }
            session_store.create(session)

            checkpoint = self.valid_checkpoint()
            checkpoint.update(
                {
                    "checkpointId": "checkpoint-1",
                    "sessionRevision": 1.0,
                    "scopeRevision": 1.0,
                    "journalSequence": 0.0,
                    "journalHeadHash": None,
                }
            )
            checkpoint_store = CheckpointStore(
                directory, "session-1", self.validator.validate
            )
            checkpoint_store.create(checkpoint)

            latest = dict(session)
            latest["revision"] = 2
            latest["updatedAt"] = "2026-11-19T08:01:00Z"
            latest["checkpointRefs"] = ["checkpoint-1"]
            session_store.append_revision(latest, expected_revision=1)
            journal = ActionJournal(
                Path(directory) / "journals" / "journal-1.jsonl", "session-1"
            )

            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal
            )
            self.assertEqual(validator.validate("checkpoint-1"), checkpoint)


if __name__ == "__main__":
    unittest.main()

