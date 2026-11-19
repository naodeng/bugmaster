import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "session.schema.json"


class SessionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCHEMA_PATH.is_file():
            raise AssertionError("the versioned Session schema is missing")
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )

    def valid_session(self):
        return {
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
            "approvalRefs": [
                {
                    "approvalId": "approval-1",
                    "scopeId": "scope-1",
                    "scopeRevision": 1,
                }
            ],
            "actionBudget": {
                "maxActions": 20,
                "consumedActions": 0,
            },
            "journalId": "session-1-journal",
            "checkpointRefs": [],
        }

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_session_records_scope_approval_budget_and_recovery_references(self):
        self.assertEqual(list(self.validator.iter_errors(self.valid_session())), [])

    def test_initial_session_can_have_no_approvals_or_checkpoints(self):
        session = self.valid_session()
        session["approvalRefs"] = []
        session["checkpointRefs"] = []
        session["actionBudget"] = {"maxActions": 0, "consumedActions": 0}
        self.assertEqual(list(self.validator.iter_errors(session)), [])

    def test_session_revision_must_be_positive(self):
        session = self.valid_session()
        session["revision"] = 0
        self.assert_invalid(session)

    def test_session_status_must_use_the_canonical_lifecycle(self):
        session = self.valid_session()
        session["status"] = "approved"
        self.assert_invalid(session)

    def test_scope_history_requires_positive_scope_revisions(self):
        session = self.valid_session()
        session["scopeHistory"][0]["revision"] = 0
        self.assert_invalid(session)

    def test_approval_reference_must_bind_a_scope_revision(self):
        session = self.valid_session()
        del session["approvalRefs"][0]["scopeRevision"]
        self.assert_invalid(session)

    def test_action_budget_counters_cannot_be_negative(self):
        session = self.valid_session()
        session["actionBudget"]["consumedActions"] = -1
        self.assert_invalid(session)

    def test_timestamps_must_be_rfc3339_date_times(self):
        session = self.valid_session()
        session["updatedAt"] = "later"
        self.assert_invalid(session)

    def test_session_cannot_assert_approval_or_authorization(self):
        session = copy.deepcopy(self.valid_session())
        session["approvedByModel"] = True
        self.assert_invalid(session)


if __name__ == "__main__":
    unittest.main()
