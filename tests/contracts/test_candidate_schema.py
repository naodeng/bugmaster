import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = pathlib.Path(__file__).resolve().parents[2]
CANDIDATE_SCHEMA_PATH = ROOT / "schemas" / "candidate.schema.json"
ASSESSMENT_SCHEMA_PATH = ROOT / "schemas" / "candidate-assessment.schema.json"


def candidate_document():
    assessment = {
        "schemaVersion": "1.0",
        "candidateId": "CF-001",
        "revision": 1,
        "observedSurface": "api",
        "patternId": "BP-API-002",
        "decision": "needs_review",
        "reasonCodes": ["ORACLE_UNCONFIRMED"],
        "oracleRef": None,
        "evidenceRefs": ["EV-001"],
        "falsePositiveChecks": [],
        "review": {"required": True, "events": []},
    }
    return {
        "schemaVersion": "1.0",
        "candidateId": "CF-001",
        "revision": 1,
        "observedSurface": "api",
        "patternId": "BP-API-002",
        "oracleRef": None,
        "evidenceRefs": ["EV-001"],
        "environmentCheck": "unknown",
        "falsePositiveChecks": [],
        "reviewRequired": True,
        "candidateAssessment": assessment,
    }


class CandidateSchemaTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CANDIDATE_SCHEMA_PATH.is_file(), "candidate schema is missing")
        self.assertTrue(ASSESSMENT_SCHEMA_PATH.is_file(), "assessment schema is missing")
        self.schema = json.loads(CANDIDATE_SCHEMA_PATH.read_text(encoding="utf-8"))
        assessment_schema = json.loads(
            ASSESSMENT_SCHEMA_PATH.read_text(encoding="utf-8")
        )
        registry = Registry().with_resource(
            assessment_schema["$id"], Resource.from_contents(assessment_schema)
        )
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator(
            self.schema, registry=registry, format_checker=FormatChecker()
        )

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_candidate_revision_matches_contract(self):
        self.assertEqual(list(self.validator.iter_errors(candidate_document())), [])

    def test_candidate_rejects_unknown_fields(self):
        document = candidate_document()
        document["sourceVerified"] = True
        self.assert_invalid(document)

    def test_candidate_rejects_empty_evidence_reference(self):
        document = candidate_document()
        document["evidenceRefs"] = [""]
        self.assert_invalid(document)

    def test_candidate_rejects_embedded_evidence_bytes(self):
        document = candidate_document()
        document["evidenceBlob"] = "base64-content-is-out-of-scope"
        self.assert_invalid(document)

    def test_candidate_assessment_must_match_its_own_schema(self):
        document = candidate_document()
        document["candidateAssessment"]["modelConfirmed"] = True
        self.assert_invalid(document)

    def test_candidate_rejects_boolean_revision(self):
        document = candidate_document()
        document["revision"] = True
        self.assert_invalid(document)


if __name__ == "__main__":
    unittest.main()
