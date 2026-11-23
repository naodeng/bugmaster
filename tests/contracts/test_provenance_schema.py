import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]


class OracleEvidenceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle_schema = json.loads(
            (ROOT / "schemas" / "oracle.schema.json").read_text(encoding="utf-8")
        )
        cls.evidence_schema = json.loads(
            (ROOT / "schemas" / "evidence.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(cls.oracle_schema)
        Draft202012Validator.check_schema(cls.evidence_schema)
        cls.oracle_validator = Draft202012Validator(
            cls.oracle_schema, format_checker=FormatChecker()
        )
        cls.evidence_validator = Draft202012Validator(
            cls.evidence_schema, format_checker=FormatChecker()
        )
        cls.oracle = {
            "schemaVersion": "1.0",
            "oracleId": "OR-ORDER-001",
            "revision": 1,
            "statement": "The response is scoped to the authenticated owner.",
            "appliesTo": {
                "targetRef": "target:orders-api",
                "featureRef": "api-0123456789abcdef",
            },
            "source": {
                "reference": "requirements/orders.md#owner-scope",
                "sha256": "a" * 64,
                "byteLength": 57,
            },
            "recordedAt": "2026-11-23T10:00:00Z",
        }
        cls.evidence = {
            "schemaVersion": "1.0",
            "evidenceId": "EV-ORDER-001",
            "evidenceLevel": "E3",
            "capturedAt": "2026-11-23T10:01:00Z",
            "artifact": {
                "reference": "artifacts/response.json",
                "mediaType": "application/json",
                "sha256": "b" * 64,
                "byteLength": 40,
            },
            "oracleRef": {
                "oracleId": "OR-ORDER-001",
                "revision": 1,
                "sha256": "c" * 64,
            },
            "journalRef": {
                "sessionId": "session-1",
                "journalId": "journal-session-1",
                "actionId": "action-1",
                "outcome": "completed",
                "resultRef": "artifacts/response.json",
                "sequence": 3,
                "entryHash": "d" * 64,
            },
        }

    def test_versioned_oracle_source_fingerprint_is_structurally_valid(self):
        self.assertEqual(list(self.oracle_validator.iter_errors(self.oracle)), [])

    def test_action_evidence_binding_is_structurally_valid(self):
        self.assertEqual(list(self.evidence_validator.iter_errors(self.evidence)), [])

    def test_oracle_rejects_self_asserted_authenticity_flag(self):
        document = copy.deepcopy(self.oracle)
        document["sourceVerified"] = True
        self.assertNotEqual(list(self.oracle_validator.iter_errors(document)), [])

    def test_oracle_rejects_whitespace_only_statement(self):
        document = copy.deepcopy(self.oracle)
        document["statement"] = "   "
        self.assertNotEqual(list(self.oracle_validator.iter_errors(document)), [])

    def test_oracle_rejects_python_unicode_whitespace_only_statement(self):
        document = copy.deepcopy(self.oracle)
        document["statement"] = "\u0085"
        self.assertNotEqual(list(self.oracle_validator.iter_errors(document)), [])

    def test_evidence_rejects_self_asserted_provenance_flag(self):
        document = copy.deepcopy(self.evidence)
        document["provenanceVerified"] = True
        self.assertNotEqual(list(self.evidence_validator.iter_errors(document)), [])

    def test_evidence_requires_a_terminal_recorded_journal_outcome(self):
        document = copy.deepcopy(self.evidence)
        document["journalRef"]["outcome"] = "outcome_unknown"
        self.assertNotEqual(list(self.evidence_validator.iter_errors(document)), [])

    def test_evidence_rejects_whitespace_only_result_reference(self):
        document = copy.deepcopy(self.evidence)
        document["journalRef"]["resultRef"] = "   "
        self.assertNotEqual(list(self.evidence_validator.iter_errors(document)), [])

    def test_evidence_rejects_python_unicode_whitespace_only_result_reference(self):
        document = copy.deepcopy(self.evidence)
        document["journalRef"]["resultRef"] = "\u0085"
        self.assertNotEqual(list(self.evidence_validator.iter_errors(document)), [])


if __name__ == "__main__":
    unittest.main()
