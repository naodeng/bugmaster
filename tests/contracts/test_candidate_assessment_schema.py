import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from bugmaster_core.candidate_assessment import REASON_CODES, assess_candidate


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "candidate-assessment.schema.json"
NEEDS_REVIEW_PATH = ROOT / "examples" / "contracts" / "candidate-assessment-needs-review.json"
REJECTED_PATH = ROOT / "examples" / "contracts" / "candidate-assessment-rejected.json"


class CandidateAssessmentSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())
        cls.needs_review = json.loads(NEEDS_REVIEW_PATH.read_text(encoding="utf-8"))
        cls.rejected = json.loads(REJECTED_PATH.read_text(encoding="utf-8"))

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_needs_review_assessment_matches_contract(self):
        self.assertEqual(list(self.validator.iter_errors(self.needs_review)), [])

    def test_runtime_reason_codes_match_the_schema_enum(self):
        schema_codes = set(self.schema["properties"]["reasonCodes"]["items"]["enum"])
        self.assertEqual(REASON_CODES, schema_codes)

    def test_runtime_assessments_match_the_schema(self):
        candidate = {
            "candidateId": "CF-010",
            "revision": 1,
            "observedSurface": "api",
            "patternId": "BP-API-002",
            "oracleRef": "OR-001",
            "evidenceRefs": ["EV-010"],
            "environmentCheck": "passed",
            "falsePositiveChecks": [],
            "identity": {
                "targetRef": "API-ORDERS",
                "businessObjectRef": "order:17",
                "operationRef": "POST /orders",
                "oracleRef": "OR-001",
                "violationSignature": "duplicate-side-effect",
            },
        }
        oracle = {"oracleId": "OR-001", "status": "validated", "sourceRef": "req.md"}
        evidence = {
            "evidenceId": "EV-010",
            "source": "tool-execution",
            "provenanceVerified": True,
            "integrityVerified": True,
            "evidenceLevel": "E3",
            "oracleRef": "OR-001",
            "oracleResult": "violated",
        }
        assessment = assess_candidate(candidate, oracle, [evidence])
        self.assertEqual(list(self.validator.iter_errors(assessment)), [])

        extra_identity = copy.deepcopy(candidate)
        extra_identity["identity"]["unrecognized"] = "ignored"
        assessment = assess_candidate(extra_identity, oracle, [evidence])
        self.assertNotIn("identity", assessment)
        self.assertEqual(list(self.validator.iter_errors(assessment)), [])

        malformed_checks = copy.deepcopy(candidate)
        malformed_checks["falsePositiveChecks"] = ["invalid-check"]
        assessment = assess_candidate(malformed_checks, oracle, [evidence])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertEqual(assessment["falsePositiveChecks"], [])
        self.assertEqual(list(self.validator.iter_errors(assessment)), [])

        normal_evidence = dict(evidence, oracleResult="satisfied")
        assessment = assess_candidate(
            candidate,
            oracle,
            [normal_evidence],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-010"]},
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("ORACLE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])
        self.assertIn("EVIDENCE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])
        self.assertEqual(list(self.validator.iter_errors(assessment)), [])

    def test_schema_rejection_fixture_requires_counterevidence(self):
        self.assertEqual(list(self.validator.iter_errors(self.rejected)), [])

    def test_candidate_decision_cannot_be_confirmed(self):
        document = copy.deepcopy(self.needs_review)
        document["decision"] = "confirmed"
        self.assert_invalid(document)

    def test_reason_codes_are_a_closed_enum(self):
        document = copy.deepcopy(self.needs_review)
        document["reasonCodes"] = ["MODEL_SAYS_NOT_A_BUG"]
        self.assert_invalid(document)

    def test_rejection_without_counterevidence_is_invalid(self):
        document = copy.deepcopy(self.rejected)
        del document["counterEvidenceRefs"]
        self.assert_invalid(document)

    def test_rejection_without_trusted_counterevidence_reason_is_invalid(self):
        document = copy.deepcopy(self.rejected)
        document["reasonCodes"] = ["EVIDENCE_INSUFFICIENT"]
        self.assert_invalid(document)

    def test_duplicate_requires_canonical_candidate_reference(self):
        document = copy.deepcopy(self.needs_review)
        document["decision"] = "duplicate"
        document["reasonCodes"] = ["DUPLICATE_CANDIDATE"]
        document["identity"] = {
            "targetRef": "API-ORDERS",
            "businessObjectRef": "order:17",
            "operationRef": "POST /orders",
            "oracleRef": "OR-001",
            "violationSignature": "duplicate-side-effect",
        }
        self.assert_invalid(document)
        document["duplicateOf"] = {"candidateId": "CF-000", "revision": 1}
        self.assertEqual(list(self.validator.iter_errors(document)), [])

    def test_review_feedback_must_bind_revision_and_evidence(self):
        document = copy.deepcopy(self.needs_review)
        document["review"]["events"] = [
            {
                "eventId": "REV-001",
                "candidateId": "CF-001",
                "candidateRevision": 1,
                "reviewerId": "reviewer-1",
                "decision": "needs_evidence",
                "reason": "需要权威状态证据",
                "evidenceRefs": ["EV-001"],
                "reviewedAt": "2026-11-22T10:00:00Z",
            }
        ]
        self.assertEqual(list(self.validator.iter_errors(document)), [])
        del document["review"]["events"][0]["evidenceRefs"]
        self.assert_invalid(document)
        document["review"]["events"][0]["evidenceRefs"] = ["EV-001"]
        document["review"]["events"][0]["reviewedAt"] = "not-a-date"
        self.assert_invalid(document)

    def test_candidate_assessment_rejects_unrecognized_fields(self):
        document = copy.deepcopy(self.needs_review)
        document["modelConfirmed"] = True
        self.assert_invalid(document)

    def test_oracle_and_evidence_references_use_canonical_ids(self):
        invalid_documents = []
        invalid_oracle = copy.deepcopy(self.needs_review)
        invalid_oracle["oracleRef"] = "oracle-001"
        invalid_documents.append(invalid_oracle)

        invalid_evidence = copy.deepcopy(self.needs_review)
        invalid_evidence["evidenceRefs"] = ["evidence-001"]
        invalid_documents.append(invalid_evidence)

        invalid_false_positive = copy.deepcopy(self.needs_review)
        invalid_false_positive["falsePositiveChecks"] = [
            {
                "check": "authorization_scope",
                "result": "unknown",
                "evidenceRefs": ["evidence-001"],
            }
        ]
        invalid_documents.append(invalid_false_positive)

        invalid_counter_evidence = copy.deepcopy(self.rejected)
        invalid_counter_evidence["counterEvidenceRefs"] = ["evidence-001"]
        invalid_documents.append(invalid_counter_evidence)

        for document in invalid_documents:
            with self.subTest(document=document):
                self.assert_invalid(document)

    def test_nested_review_and_identity_references_use_canonical_ids(self):
        invalid_review = copy.deepcopy(self.needs_review)
        invalid_review["review"]["events"] = [
            {
                "eventId": "REV-001",
                "candidateId": "CF-001",
                "candidateRevision": 1,
                "reviewerId": "reviewer-1",
                "decision": "needs_evidence",
                "reason": "需要证据",
                "evidenceRefs": ["evidence-001"],
                "reviewedAt": "2026-11-22T10:00:00Z",
            }
        ]
        invalid_identity = copy.deepcopy(self.needs_review)
        invalid_identity["identity"] = {
            "targetRef": "API-ORDERS",
            "businessObjectRef": "order:17",
            "operationRef": "POST /orders",
            "oracleRef": "oracle-001",
            "violationSignature": "duplicate-side-effect",
        }

        for document in (invalid_review, invalid_identity):
            with self.subTest(document=document):
                self.assert_invalid(document)


if __name__ == "__main__":
    unittest.main()
