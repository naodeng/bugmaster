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
    def test_assess_candidate_rejects_noncanonical_record_reference_ids(self):
        invalid_candidates = (
            candidate(candidateId="candidate-1"),
            candidate(oracleRef="oracle-1"),
            candidate(evidenceRefs=["evidence-1"]),
        )
        for invalid_candidate in invalid_candidates:
            with self.subTest(candidate=invalid_candidate):
                with self.assertRaisesRegex(
                    ValueError, "candidate-assessment-input-invalid"
                ):
                    assess_candidate(invalid_candidate, oracle(), [evidence()])

    def test_noncanonical_optional_identity_is_not_emitted(self):
        identity = candidate()["identity"]
        identity["oracleRef"] = "oracle-1"
        assessment = assess_candidate(
            candidate(identity=identity), oracle(), [evidence()]
        )

        self.assertNotIn("identity", assessment)

    def test_false_positive_check_with_noncanonical_evidence_id_is_omitted(self):
        checks = [
            {
                "check": "authorization_scope",
                "result": "unknown",
                "evidenceRefs": ["evidence-1"],
            }
        ]

        assessment = assess_candidate(
            candidate(falsePositiveChecks=checks), oracle(), [evidence()]
        )

        self.assertEqual(assessment["falsePositiveChecks"], [])
        self.assertIn("FALSE_POSITIVE_CHECK_INCONCLUSIVE", assessment["reasonCodes"])

    def test_noncanonical_counterevidence_reference_is_not_emitted(self):
        assessment = assess_candidate(
            candidate(),
            oracle(),
            [evidence()],
            {"oracleRef": "OR-001", "evidenceRefs": ["evidence-1"]},
        )

        self.assertEqual(assessment["evidenceRefs"], ["EV-001"])

    def test_duplicate_target_requires_canonical_candidate_id(self):
        duplicate = candidate(candidateId="legacy-1")
        duplicate["decision"] = "candidate"

        with self.assertRaisesRegex(ValueError, "duplicate-identity-mismatch"):
            assess_candidate(
                candidate(candidateId="CF-002"),
                oracle(),
                [evidence()],
                duplicate_of=duplicate,
            )

    def test_review_event_rejects_noncanonical_evidence_id(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])

        with self.assertRaisesRegex(ValueError, "review-event-evidence-invalid"):
            append_review_event(assessment, review_event(evidenceRefs=["EV-001\n"]))

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

    def test_caller_supplied_verifiers_cannot_auto_reject_counterevidence(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("ORACLE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])
        self.assertIn("EVIDENCE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])
        self.assertNotIn("TRUSTED_COUNTEREVIDENCE", assessment["reasonCodes"])
        self.assertNotIn("counterEvidenceRefs", assessment)

    def test_counterevidence_for_different_oracle_is_not_linked(self):
        assessment = assess_candidate(
            candidate(),
            oracle(),
            [evidence(), evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-OTHER", "evidenceRefs": ["EV-002"]},
        )

        self.assertEqual(assessment["decision"], "candidate")
        self.assertNotIn("EV-002", assessment["evidenceRefs"])

    def test_caller_supplied_verifier_callbacks_are_not_accepted(self):
        args = (
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
        )
        verifier_options = (
            {"evidence_verifier": lambda item: True},
            {"oracle_verifier": lambda item: True},
        )
        for options in verifier_options:
            with self.subTest(options=tuple(options)):
                with self.assertRaises(TypeError):
                    assess_candidate(*args, **options)

    def test_self_asserted_provenance_cannot_auto_reject_without_trusted_verifier(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_PROVENANCE_UNVERIFIED", assessment["reasonCodes"])

    def test_counterevidence_with_invalid_provenance_stays_in_review(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-002"]),
            oracle(),
            [evidence("EV-002", "satisfied", provenanceVerified=False)],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_INSUFFICIENT", assessment["reasonCodes"])

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
        )
        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("CONTRADICTORY_EVIDENCE", assessment["reasonCodes"])

    def test_conflicting_observations_in_candidate_evidence_require_review(self):
        assessment = assess_candidate(
            candidate(evidenceRefs=["EV-001", "EV-002"]),
            oracle(),
            [evidence(), evidence("EV-002", "satisfied")],
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
        for evidence_refs in ("EV-001", None):
            with self.subTest(evidence_refs=evidence_refs):
                assessment = assess_candidate(
                    candidate(falsePositiveChecks=[
                        {
                            "check": "business_exception",
                            "result": "clear",
                            "evidenceRefs": evidence_refs,
                        }
                    ]),
                    oracle(),
                    [evidence()],
                )
                self.assertEqual(assessment["falsePositiveChecks"], [])
                self.assertEqual(assessment["decision"], "needs_review")
                self.assertIn(
                    "FALSE_POSITIVE_CHECK_INCONCLUSIVE", assessment["reasonCodes"]
                )

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

    def test_duplicate_link_requires_matching_top_level_and_identity_oracle(self):
        existing = assess_candidate(candidate(), oracle(), [evidence()])
        mismatched_candidate = candidate(candidateId="CF-002", oracleRef="OR-002")
        mismatched_existing = {**existing, "oracleRef": "OR-002"}

        for incoming, duplicate in (
            (mismatched_candidate, existing),
            (candidate(candidateId="CF-003"), mismatched_existing),
        ):
            with self.subTest(
                candidateOracle=incoming["oracleRef"],
                duplicateOracle=duplicate["oracleRef"],
            ):
                with self.assertRaisesRegex(ValueError, "duplicate-identity-mismatch"):
                    assess_candidate(
                        incoming,
                        oracle(),
                        [evidence("EV-002")],
                        duplicate_of=duplicate,
                    )

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

        existing = assess_candidate(candidate(), oracle(), [evidence()])
        for decision in ([], {}):
            with self.subTest(duplicate_decision=decision):
                duplicate_of = {
                    **existing,
                    "candidateId": "CF-OLD",
                    "decision": decision,
                }
                with self.assertRaisesRegex(ValueError, "duplicate-identity-mismatch"):
                    assess_candidate(
                        candidate(candidateId="CF-002"),
                        oracle(),
                        [evidence("EV-002")],
                        duplicate_of=duplicate_of,
                    )

    def test_required_candidate_assessment_fields_are_validated(self):
        for updates in (
            {"observedSurface": None},
            {"observedSurface": ""},
            {"patternId": None},
            {"patternId": "BP-API-2"},
            {"oracleRef": ""},
            {"oracleRef": {"id": "OR-001"}},
        ):
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    assess_candidate(candidate(**updates), oracle(), [evidence()])

    def test_candidate_identity_drops_fields_not_allowed_by_the_output_schema(self):
        identity = {**candidate()["identity"], "unrecognized": "value"}

        assessment = assess_candidate(
            candidate(identity=identity), oracle(), [evidence()]
        )

        self.assertNotIn("identity", assessment)

    def test_candidate_identity_with_empty_value_is_omitted(self):
        identity = {**candidate()["identity"], "operationRef": ""}

        assessment = assess_candidate(
            candidate(identity=identity), oracle(), [evidence()]
        )

        self.assertNotIn("identity", assessment)

    def test_unhashable_evidence_level_is_treated_as_invalid_evidence(self):
        assessment = assess_candidate(
            candidate(), oracle(), [evidence(level=["E3"])]
        )

        self.assertEqual(assessment["decision"], "needs_review")
        self.assertIn("EVIDENCE_INSUFFICIENT", assessment["reasonCodes"])

    def test_candidate_review_history_must_be_valid_before_it_is_copied(self):
        assessment = assess_candidate(
            candidate(reviewEvents=[review_event()]), oracle(), [evidence()]
        )
        self.assertEqual(assessment["review"]["events"], [review_event()])

        with self.assertRaises(ValueError):
            assess_candidate(
                candidate(reviewEvents=[{"eventId": "REV-BROKEN"}]),
                oracle(),
                [evidence()],
            )

    def test_candidate_review_history_must_be_a_list(self):
        with self.assertRaisesRegex(ValueError, "candidate-review-history-invalid"):
            assess_candidate(
                candidate(reviewEvents="malformed"), oracle(), [evidence()]
            )

    def test_review_event_can_reference_counterevidence(self):
        event = review_event(evidenceRefs=["EV-002"])

        assessment = assess_candidate(
            candidate(reviewEvents=[event]),
            oracle(),
            [evidence(), evidence("EV-002", "satisfied")],
            {"oracleRef": "OR-001", "evidenceRefs": ["EV-002"]},
        )

        self.assertEqual(assessment["review"]["events"], [event])
        self.assertIn("EV-002", assessment["evidenceRefs"])

    def test_review_event_rejects_invalid_assessment_header(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        invalid_headers = (
            {"candidateId": ""},
            {"revision": 0},
            {"schemaVersion": "2.0"},
            {"decision": "confirmed"},
            {"observedSurface": ""},
            {"patternId": "BP-API-2"},
        )

        for header in invalid_headers:
            with self.subTest(header=header):
                corrupt = copy.deepcopy(assessment)
                corrupt.update(header)
                event = review_event(
                    candidateId=corrupt["candidateId"],
                    candidateRevision=corrupt["revision"],
                )
                with self.assertRaisesRegex(ValueError, "review-assessment-invalid"):
                    append_review_event(corrupt, event)

    def test_malformed_candidate_lists_are_normalized_to_empty(self):
        assessment = assess_candidate(
            candidate(evidenceRefs="EV-001", falsePositiveChecks="unknown"),
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

    def test_review_history_can_grow_across_candidate_revisions(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        first_event = review_event()
        reviewed = append_review_event(assessment, first_event)

        next_revision = candidate(
            revision=2,
            reviewEvents=reviewed["review"]["events"],
        )
        next_assessment = assess_candidate(next_revision, oracle(), [evidence()])
        second_event = review_event(eventId="REV-002", candidateRevision=2)
        updated = append_review_event(next_assessment, second_event)

        self.assertEqual(
            [event["candidateRevision"] for event in updated["review"]["events"]],
            [1, 2],
        )

    def test_historical_review_event_requires_a_positive_candidate_revision(self):
        with self.assertRaises(ValueError):
            assess_candidate(
                candidate(revision=2, reviewEvents=[review_event(candidateRevision=0)]),
                oracle(),
                [evidence()],
            )

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
        with self.assertRaises(ValueError):
            append_review_event(assessment, review_event(reviewedAt="not-a-time"))
        with self.assertRaises(ValueError):
            append_review_event(
                assessment, review_event(reviewedAt="2026-13-22T10:00:00Z")
            )

    def test_new_review_event_must_reference_the_current_candidate_revision(self):
        assessment = assess_candidate(
            candidate(revision=2), oracle(), [evidence()]
        )

        with self.assertRaises(ValueError):
            append_review_event(assessment, review_event(candidateRevision=1))

    def test_review_event_rejects_invalid_assessment_evidence_refs(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])

        for refs in (["EV-001", None], ["EV-001", "EV-001"]):
            with self.subTest(refs=refs):
                corrupt = copy.deepcopy(assessment)
                corrupt["evidenceRefs"] = refs
                with self.assertRaisesRegex(ValueError, "review-event-evidence-invalid"):
                    append_review_event(corrupt, review_event())

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
        corrupt["review"] = {"required": False, "events": "invalid"}
        with self.assertRaises(ValueError):
            append_review_event(corrupt, review_event())
        corrupt["review"] = {"required": False, "events": ["invalid-event"]}
        with self.assertRaises(ValueError):
            append_review_event(corrupt, review_event())
        corrupt["review"] = {
            "required": False,
            "events": [{"eventId": "REV-OLD", "candidateId": "CF-OTHER"}],
        }
        with self.assertRaises(ValueError):
            append_review_event(corrupt, review_event())

    def test_review_event_rejects_invalid_review_record_shape(self):
        assessment = assess_candidate(candidate(), oracle(), [evidence()])
        invalid_reviews = (
            {"events": []},
            {"required": "false", "events": []},
            {"required": False, "events": [], "source": "untrusted"},
        )

        for review in invalid_reviews:
            with self.subTest(review=review):
                corrupt = copy.deepcopy(assessment)
                corrupt["review"] = review
                with self.assertRaisesRegex(ValueError, "review-history-invalid"):
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
        with self.assertRaisesRegex(ValueError, "outcome-value-invalid"):
            score_candidate_quality([{"groundTruth": [], "decision": "candidate"}])
        with self.assertRaisesRegex(ValueError, "outcome-value-invalid"):
            score_candidate_quality([{"groundTruth": "bug", "decision": {}}])
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
