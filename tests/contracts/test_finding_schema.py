import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "finding.schema.json"


def finding_document():
    return {
        "schemaVersion": "1.0",
        "findingId": "FND-001",
        "revision": 1,
        "status": "suspected",
        "candidateRefs": [{"candidateId": "CF-001", "revision": 1}],
        "observedSurfaces": ["api"],
        "patternId": "BP-API-002",
        "oracleRef": {
            "oracleId": "OR-001",
            "revision": 2,
            "sha256": "a" * 64,
        },
        "businessContext": "Order creation must be idempotent.",
        "actualBehavior": "Two orders were persisted.",
        "expectedBehavior": "Only one order should be persisted.",
        "preconditions": ["The request uses an existing idempotency key."],
        "actionRefs": [
            {
                "sessionId": "SESSION-001",
                "journalId": "JOURNAL-001",
                "actionId": "ACTION-001",
                "sequence": 3,
                "entryHash": "b" * 64,
            }
        ],
        "evidenceRefs": [
            {"evidenceId": "EV-001", "sha256": "c" * 64, "byteLength": 17}
        ],
        "severity": None,
        "confidence": None,
        "attribution": {"layer": "unknown", "validationLevel": "E3"},
        "limitations": ["Source authenticity is unverified."],
        "remediation": "Investigate the order creation transaction.",
        "regressionRecommendation": "Add an idempotency regression case.",
        "recordedAt": "2026-11-23T10:00:00Z",
    }


class FindingSchemaTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCHEMA_PATH.is_file(), "finding schema is missing")
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator(
            self.schema, format_checker=FormatChecker()
        )

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_suspected_finding_matches_contract(self):
        self.assertEqual(list(self.validator.iter_errors(finding_document())), [])

    def test_finding_rejects_unknown_fields(self):
        document = finding_document()
        document["modelConfirmed"] = True
        self.assert_invalid(document)

    def test_finding_rejects_unknown_status(self):
        document = finding_document()
        document["status"] = "model_confirmed"
        self.assert_invalid(document)

    def test_finding_evidence_reference_requires_digest_and_length(self):
        document = finding_document()
        document["evidenceRefs"] = [{"evidenceId": "EV-001"}]
        self.assert_invalid(document)

    def test_finding_rejects_embedded_evidence_bytes(self):
        document = finding_document()
        document["evidenceRefs"][0]["data"] = "base64-content-is-out-of-scope"
        self.assert_invalid(document)

    def test_finding_rejects_boolean_revision(self):
        document = finding_document()
        document["revision"] = True
        self.assert_invalid(document)

    def test_finding_rejects_malformed_timestamp(self):
        document = finding_document()
        document["recordedAt"] = "not-a-date"
        self.assert_invalid(document)

    def test_identifier_and_digest_patterns_reject_trailing_newlines(self):
        invalid_documents = []

        invalid = finding_document()
        invalid["findingId"] = "FND-001\n"
        invalid_documents.append(invalid)

        invalid = finding_document()
        invalid["candidateRefs"][0]["candidateId"] = "CF-001\n"
        invalid_documents.append(invalid)

        invalid = finding_document()
        invalid["patternId"] = "BP-API-002\n"
        invalid_documents.append(invalid)

        invalid = finding_document()
        invalid["oracleRef"]["oracleId"] = "OR-001\n"
        invalid_documents.append(invalid)

        invalid = finding_document()
        invalid["oracleRef"]["sha256"] = "a" * 64 + "\n"
        invalid_documents.append(invalid)

        invalid = finding_document()
        invalid["actionRefs"][0]["entryHash"] = "b" * 64 + "\n"
        invalid_documents.append(invalid)

        invalid = finding_document()
        invalid["evidenceRefs"][0]["evidenceId"] = "EV-001\n"
        invalid_documents.append(invalid)

        invalid = finding_document()
        invalid["evidenceRefs"][0]["sha256"] = "c" * 64 + "\n"
        invalid_documents.append(invalid)

        for document in invalid_documents:
            with self.subTest(document=document):
                self.assert_invalid(document)


if __name__ == "__main__":
    unittest.main()
