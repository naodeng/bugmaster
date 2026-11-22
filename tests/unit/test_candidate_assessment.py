import copy
import unittest

from bugmaster_core.candidate_assessment import (
    append_review_event,
    assess_candidate,
    score_candidate_quality,
)


def candidate(**updates):
    value = {
        "candidateId": "CF-001",
        "revision": 1,
        "observedSurface": "api",
        "patternId": "BP-API-002",
        "oracleRef": "OR-001",
        "evidenceRefs": ["EV-001"],
        "environmentCheck": "passed",
        "falsePositiveChecks": [{"check": "business_exception", "result": "clear"}],
        "reviewRequired": False,
        "identity": {
            "targetRef": "API-ORDERS",
            "businessObjectRef": "order:17",
            "operationRef": "POST /orders",
            "oracleRef": "OR-001",
            "violationSignature": "duplicate-side-effect",
        },
    }
    value.update(updates)
    return value


def oracle(**updates):
    value = {"oracleId": "OR-001", "status": "validated", "sourceRef": "requirements.md#idempotency"}
    value.update(updates)
    return value


def evidence(evidence_id="EV-001", result="violated", level="E3", **updates):
    value = {
        "evidenceId": evidence_id,
        "source": "tool-execution",
        "provenanceVerified": True,
        "integrityVerified": True,
        "evidenceLevel": level,
        "oracleRef": "OR-001",
        "oracleResult": result,
    }
    value.update(updates)
    return value


def review_event(**updates):
    value = {
        "eventId": "REV-001",
        "candidateId": "CF-001",
        "candidateRevision": 1,
        "reviewerId": "person-17",
        "decision": "needs_evidence",
        "reason": "需要补充权威订单状态证据",
        "evidenceRefs": ["EV-001"],
        "reviewedAt": "2026-11-22T10:00:00Z",
    }
    value.update(updates)
    return value


class CandidateAssessmentTests(unittest.TestCase):
    def test_real_bug_is_retained_as_candidate_not_confirmed(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        self.assertEqual(assessment["decision"], "candidate")
        self.assertNotEqual(assessment["decision"], "confirmed")
        self.assertEqual(assessment["reasonCodes"], [])

    def test_missing_oracle_requires_review(self):
        assessment = assess_candidate(candidate(), oracle(status="pending"), [evidence()])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("ORACLE_UNCONFIRMED", assessment["reasonCodes"])

    def test_unbound_oracle_reference_requires_review(self):
        assessment = assess_candidate(candidate(oracleRef="OR-OTHER"), oracle(), [evidence()])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("ORACLE_UNCONFIRMED", assessment["reasonCodes"])

    def test_missing_or_untrusted_execution_evidence_requires_review(self):
        assessment = assess_candidate(
            candidate(), oracle(), [evidence(provenanceVerified=False)]
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_INSUFFICIENT", assessment["reasonCodes"])

    def test_evidence_below_e3_requires_review(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence(level="E2")])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_INSUFFICIENT", assessment["reasonCodes"])

    def test_unstable_environment_cannot_auto_reject(self):
        assessment = assess_candidate(
            candidate(environmentCheck="unknown"),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("ENVIRONMENT_UNSTABLE", assessment["reasonCodes"])

    def test_normal_behavior_is_rejected_only_with_valid_counterevidence(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
            evidence_verifier=lambda item: item["evidenceId"] == "EV-002",
            oracle_verifier=lambda item: item["oracleId"] == "OR-001",
        )
        self.assertEqual(assessment["decision"], "rejected")
        self.assertIn("TRUSTED_COUNTEREVIDENCE", assessment["reasonCodes"])
        self.assertEqual(assessment["counterEvidenceRefs"], ["EV-002"])

    def test_self_asserted_provenance_cannot_auto_reject_without_trusted_verifier(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])

    def test_self_asserted_validated_oracle_cannot_auto_reject(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
            evidence_verifier=lambda item: True,
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("ORACLE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])

    def test_rejected_counterevidence_fails_closed_when_verifier_denies(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
            evidence_verifier=lambda item: False,
            oracle_verifier=lambda item: True,
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])

    def test_model_opinion_cannot_reject_without_counterevidence(self):
        assessment = assess_candidate(
            candidate(modelJudgement="not_a_bug"),
            oracle(),
            [evidence(result="inconclusive")],
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertNotIn("TRUSTED_COUNTEREVIDENCE", assessment["reasonCodes"])

    def test_model_opinion_does_not_override_verified_violation(self):
        assessment = assess_candidate(
            candidate(modelJudgement="not_a_bug"), oracle(), [evidence()]
        )
        self.assertEqual(assessment["decision"], "candidate")

    def test_conflicting_valid_observations_require_review(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-001", "EV-002"]),
            oracle(),
            [evidence(), evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
            evidence_verifier=lambda item: True,
            oracle_verifier=lambda item: True,
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("CONTRADICTORY_EVIDENCE", assessment["reasonCodes"])

    def test_unknown_false_positive_check_requires_review(self):
        checks = [{"check": "business_exception", "result": "unknown"}]
        assessment = assess_candidate(candidate(falsePositiveChecks=checks), oracle(), [evidence()])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("FALSE_POSITIVE_CHECK_INCONCLUSIVE", assessment["reasonCodes"])

    def test_unrecognized_false_positive_check_result_fails_closed(self):
        checks = [{"check": "business_exception", "result": "probably_clear"}]
        assessment = assess_candidate(candidate(falsePositiveChecks=checks), oracle(), [evidence()])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("FALSE_POSITIVE_CHECK_INCONCLUSIVE", assessment["reasonCodes"])
        self.assertEqual(assessment["falsePositiveChecks"], [])

    def test_nonobject_false_positive_check_is_omitted_and_requires_review(self):
        assessment = assess_candidate(
            candidate(falsePositiveChecks=["not-a-check"]), oracle(), [evidence()]
        )
        self.assertEqual(assessment["falsePositiveChecks"], [])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("FALSE_POSITIVE_CHECK_INCONCLUSIVE", assessment["reasonCodes"])

    def test_malformed_false_positive_check_evidence_refs_are_omitted(self):
        assessment = assess_candidate(
            candidate(falsePositiveChecks=[
                {"check": "business_exception", "result": "clear", "evidenceRefs": "EV-001"}
            ]),
            oracle(),
            [evidence()],
        )
        self.assertEqual(assessment["falsePositiveChecks"], [])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("FALSE_POSITIVE_CHECK_INCONCLUSIVE", assessment["reasonCodes"])

    def test_detected_false_positive_signal_without_rebuttal_requires_review(self):
        checks = [{"check": "business_exception", "result": "detected"}]
        assessment = assess_candidate(candidate(falsePositiveChecks=checks), oracle(), [evidence()])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("COUNTEREVIDENCE_MISSING", assessment["reasonCodes"])

    def test_cross_surface_duplicate_is_linked_and_not_counted_as_second_candidate(self):
        existing = assess_candidate(candidate(), oracle(), [evidence()])
        incoming = candidate(candidateId="CF-002", observedSurface="browser")
        assessment = assess_candidate(incoming, oracle(), [evidence("EV-002")], duplicate_of=existing)
        self.assertEqual(assessment["decision"], "duplicate")
        self.assertEqual(assessment["duplicateOf"], {"candidateId": "CF-001", "revision": 1})
        self.assertIn("DUPLICATE_CANDIDATE", assessment["reasonCodes"])

    def test_duplicate_link_with_different_identity_is_rejected(self):
        existing = assess_candidate(candidate(), oracle(), [evidence()])
        incoming = candidate(candidateId="CF-002", identity={"targetRef": "OTHER"})
        with self.assertRaises(ValueError):
            assess_candidate(incoming, oracle(), [evidence("EV-002")], duplicate_of=existing)

    def test_duplicate_cannot_point_to_noncanonical_assessment(self):
        existing = assess_candidate(candidate(), oracle(), [evidence()])
        existing["decision"] = "rejected"
        with self.assertRaises(ValueError):
            assess_candidate(
                candidate(candidateId="CF-002"),
                oracle(),
                [evidence("EV-002")],
                duplicate_of=existing,
            )

    def test_invalid_candidate_and_duplicate_inputs_are_rejected(self):
        with self.assertRaises(TypeError):
            assess_candidate(None, oracle(), [])
        with self.assertRaises(ValueError):
            assess_candidate(candidate(revision=True), oracle(), [evidence()])
        with self.assertRaises(ValueError):
            assess_candidate(candidate(revision=0), oracle(), [evidence()])
        with self.assertRaises(ValueError):
            assess_candidate(candidate(), oracle(), [evidence()], duplicate_of="CF-000")
        with self.assertRaises(ValueError):
            assess_candidate(
                candidate(candidateId="CF-002", identity=None),
                oracle(),
                [evidence("EV-002")],
                duplicate_of=assess_candidate(candidate(), oracle(), [evidence()]),
            )

    def test_malformed_candidate_lists_are_normalized_to_empty(self):
        assessment = assess_candidate(
            candidate(evidenceRefs="EV-001", falsePositiveChecks="unknown", reviewEvents="bad"),
            oracle(),
            [evidence()],
        )
        self.assertEqual(assessment["evidenceRefs"], [])
        self.assertEqual(assessment["falsePositiveChecks"], [])
        self.assertEqual(assessment["review"]["events"], [])
        self.assertIn("FALSE_POSITIVE_CHECK_INCONCLUSIVE", assessment["reasonCodes"])
        self.assertEqual(len(assessment["reasonCodes"]), len(set(assessment["reasonCodes"])))

    def test_missing_evidence_collection_stays_needs_review(self):
        assessment = assess_candidate(candidate(), oracle(), None)
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_INSUFFICIENT", assessment["reasonCodes"])

    def test_incomplete_optional_deduplication_identity_is_omitted(self):
        assessment = assess_candidate(
            candidate(identity={"targetRef": "API-ORDERS"}), oracle(), [evidence()]
        )
        self.assertNotIn("identity", assessment)

    def test_policy_required_human_review_keeps_candidate_pending(self):
        assessment = assess_candidate(candidate(reviewRequired=True), oracle(), [evidence()])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("HUMAN_REVIEW_REQUIRED", assessment["reasonCodes"])

    def test_invalid_review_requirement_fails_closed(self):
        assessment = assess_candidate(candidate(reviewRequired="false"), oracle(), [evidence()])
        self.assertTrue(assessment["review"]["required"])
        self.assertEqual(assessment["decision"], "needs_review")

    def test_unsigned_human_acceptance_does_not_clear_required_review(self):
        accepted = review_event(decision="accept")
        source = candidate(reviewRequired=True, reviewEvents=[accepted])
        assessment = assess_candidate(source, oracle(), [evidence()])
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("HUMAN_REVIEW_REQUIRED", assessment["reasonCodes"])

    def test_review_event_appends_without_mutating_previous_assessment(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        previous = copy.deepcopy(assessment)
        reviewed = append_review_event(assessment, review_event())
        self.assertEqual(assessment, previous)
        self.assertEqual(len(assessment["review"]["events"]), 0)
        self.assertEqual(reviewed["review"]["events"], [review_event()])
        second_event = review_event(eventId="REV-002", decision="accept")
        twice_reviewed = append_review_event(reviewed, second_event)
        self.assertEqual(twice_reviewed["review"]["events"], [review_event(), second_event])

    def test_review_event_must_bind_candidate_revision_and_evidence(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        with self.assertRaises(ValueError):
            append_review_event(assessment, review_event(candidateRevision=2))
        with self.assertRaises(ValueError):
            append_review_event(assessment, review_event(candidateRevision=True))
        with self.assertRaises(ValueError):
            append_review_event(assessment, review_event(evidenceRefs=[]))
        with self.assertRaises(ValueError):
            append_review_event(assessment, review_event(evidenceRefs=["EV-001", "EV-001"]))
        with self.assertRaises(ValueError):
            append_review_event(assessment, review_event(reviewerId=" "))

    def test_review_event_id_cannot_overwrite_existing_feedback(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        reviewed = append_review_event(assessment, review_event())
        with self.assertRaises(ValueError):
            append_review_event(reviewed, review_event(decision="reject"))

    def test_review_event_rejects_nonobjects_and_corrupt_history(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        with self.assertRaises(TypeError):
            append_review_event(None, review_event())
        with self.assertRaises(TypeError):
            append_review_event(assessment, None)
        corrupt = copy.deepcopy(assessment)
        corrupt["review"] = "invalid"
        with self.assertRaises(ValueError):
            append_review_event(corrupt, review_event())
        corrupt["review"] = {"events": "invalid"}
        with self.assertRaises(ValueError):
            append_review_event(corrupt, review_event())
        corrupt["review"] = {"events": ["invalid-event"]}
        with self.assertRaises(ValueError):
            append_review_event(corrupt, review_event())
        corrupt["review"] = {"events": [{"eventId": "REV-OLD", "candidateId": "CF-OTHER"}]}
        with self.assertRaises(ValueError):
            append_review_event(corrupt, review_event())

    def test_candidate_quality_reports_precision_recall_and_review_cost(self):
        metrics = score_candidate_quality(
            [
                {"groundTruth": "bug", "decision": "candidate"},
                {"groundTruth": "normal", "decision": "rejected"},
                {"groundTruth": "bug", "decision": "needs_review", "reviewSeconds": 45},
                {"groundTruth": "normal", "decision": "candidate", "humanReviewRequired": True, "reviewSeconds": 30},
                {"groundTruth": "ambiguous", "decision": "needs_review", "reviewSeconds": 15},
                {"groundTruth": "bug", "decision": "duplicate"},
            ]
        )
        self.assertEqual(metrics["truePositive"], 2)
        self.assertEqual(metrics["falsePositive"], 1)
        self.assertEqual(metrics["falseNegative"], 0)
        self.assertAlmostEqual(metrics["precision"], 2 / 3)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["ambiguousExcluded"], 1)
        self.assertEqual(metrics["duplicatesLinked"], 1)
        self.assertEqual(metrics["humanReviewCount"], 3)
        self.assertEqual(metrics["humanReviewSeconds"], 90)

    def test_candidate_quality_handles_empty_denominators(self):
        metrics = score_candidate_quality([])
        self.assertIsNone(metrics["precision"])
        self.assertIsNone(metrics["recall"])
        self.assertIsNone(metrics["falsePositiveRate"])

    def test_review_time_remains_unmeasured_without_invented_duration(self):
        metrics = score_candidate_quality(
            [{"groundTruth": "bug", "decision": "needs_review"}]
        )
        self.assertEqual(metrics["humanReviewCount"], 1)
        self.assertEqual(metrics["humanReviewSeconds"], 0)
        self.assertEqual(metrics["reviewTimeRecordedCases"], 0)

    def test_duplicate_link_does_not_hide_human_review_cost(self):
        metrics = score_candidate_quality(
            [{
                "groundTruth": "bug",
                "decision": "duplicate",
                "humanReviewRequired": True,
                "reviewSeconds": 17,
            }]
        )
        self.assertEqual(metrics["duplicatesLinked"], 1)
        self.assertEqual(metrics["humanReviewCount"], 1)
        self.assertEqual(metrics["humanReviewSeconds"], 17)
        self.assertIsNone(metrics["precision"])

    def test_candidate_quality_rejects_unknown_values(self):
        with self.assertRaises(ValueError):
            score_candidate_quality(None)
        with self.assertRaises(ValueError):
            score_candidate_quality([None])
        with self.assertRaises(ValueError):
            score_candidate_quality([{"groundTruth": "unknown", "decision": "candidate"}])
        with self.assertRaises(ValueError):
            score_candidate_quality([{"groundTruth": "bug", "decision": "confirmed"}])
        with self.assertRaises(ValueError):
            score_candidate_quality([{"groundTruth": "normal", "decision": "candidate", "humanReviewRequired": "yes"}])
        with self.assertRaises(ValueError):
            score_candidate_quality([{"groundTruth": "normal", "decision": "rejected", "reviewSeconds": -1}])
        with self.assertRaises(ValueError):
            score_candidate_quality([{"groundTruth": "normal", "decision": "rejected", "reviewSeconds": True}])
        false_negative = score_candidate_quality([{"groundTruth": "bug", "decision": "rejected"}])
        self.assertEqual(false_negative["falseNegative"], 1)
        self.assertEqual(false_negative["recall"], 0.0)


if __name__ == "__main__":
    unittest.main()
