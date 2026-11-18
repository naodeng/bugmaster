import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from bugmaster_core.action_journal import ActionJournal


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class JournalSchemaTests(unittest.TestCase):
    def _load_schema(self):
        schema_path = REPOSITORY_ROOT / "schemas" / "event.schema.json"
        if not schema_path.is_file():
            self.fail("the versioned Action Journal event schema is missing")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return schema

    def _real_events(self, path):
        journal = ActionJournal(path, session_id="session-1")
        journal.prepare(
            action_id="action-1",
            intent_digest="a" * 64,
            scope_revision=1,
            risk="R0",
        )
        journal.mark_dispatched("action-1", intent_digest="a" * 64)
        journal.record_outcome(
            "action-1", "completed", result_ref="tool-result-1"
        )
        journal.prepare(
            action_id="action-2",
            intent_digest="b" * 64,
            scope_revision=1,
            risk="R2",
            approval_ref="approval-2",
        )
        journal.mark_dispatched("action-2", intent_digest="b" * 64)
        journal.record_outcome("action-2", "outcome_unknown")
        journal.reconcile(
            "action-2",
            outcome="not_executed",
            observation_ref="read-only-state-2",
            observer_ref="operator-1",
            basis="authoritative-read-only",
        )
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def test_actual_journal_events_validate_against_versioned_contract(self):
        schema = self._load_schema()
        validator = Draft202012Validator(schema, format_checker=FormatChecker())

        with tempfile.TemporaryDirectory() as directory:
            events = self._real_events(Path(directory) / "journal.jsonl")
            self.assertEqual(
                [event["eventType"] for event in events],
                [
                    "action_prepared",
                    "action_dispatched",
                    "action_outcome",
                    "action_prepared",
                    "action_dispatched",
                    "action_outcome",
                    "action_reconciled",
                ],
            )
            for event in events:
                with self.subTest(eventType=event["eventType"]):
                    validator.validate(event)

    def test_r2_preparation_event_cannot_omit_approval_reference(self):
        schema = self._load_schema()
        validator = Draft202012Validator(schema, format_checker=FormatChecker())

        with tempfile.TemporaryDirectory() as directory:
            event = self._real_events(Path(directory) / "journal.jsonl")[3]
            event["data"]["approvalRef"] = None
            self.assertFalse(validator.is_valid(event))


if __name__ == "__main__":
    unittest.main()
