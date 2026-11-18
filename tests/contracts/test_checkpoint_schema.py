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


if __name__ == "__main__":
    unittest.main()
