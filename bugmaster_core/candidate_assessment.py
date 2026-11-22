"""Deterministic screening and review history for unconfirmed candidates."""

from copy import deepcopy


_LEVELS = {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4}
_IDENTITY_FIELDS = (
    "targetRef",
    "businessObjectRef",
    "operationRef",
    "oracleRef",
    "violationSignature",
)
_REVIEW_DECISIONS = {"accept", "reject", "needs_evidence"}
_CANDIDATE_DECISIONS = {"candidate", "needs_review", "rejected", "duplicate"}
_GROUND_TRUTH = {"bug", "normal", "ambiguous"}
_FALSE_POSITIVE_CHECK_RESULTS = {"clear", "detected", "unknown"}
REASON_CODES = frozenset({
    "ORACLE_UNCONFIRMED",
    "EVIDENCE_INSUFFICIENT",
    "ENVIRONMENT_UNSTABLE",
    "FALSE_POSITIVE_CHECK_INCONCLUSIVE",
    "COUNTEREVIDENCE_MISSING",
    "EVIDENCE_PROVENANCE_UNVERIFIED",
    "ORACLE_PROVENANCE_UNVERIFIED",
    "TRUSTED_COUNTEREVIDENCE",
    "CONTRADICTORY_EVIDENCE",
    "DUPLICATE_CANDIDATE",
    "HUMAN_REVIEW_REQUIRED",
})


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _valid_oracle(candidate, oracle):
    return (
        isinstance(oracle, dict)
        and oracle.get("status") == "validated"
        and _nonempty(oracle.get("sourceRef"))
        and _nonempty(candidate.get("oracleRef"))
        and oracle.get("oracleId") == candidate.get("oracleRef")
    )


def _evidence_for(
    evidence_ref,
    evidences,
    oracle_ref,
    result=None,
    minimum_level=0,
    require_trusted=False,
    evidence_verifier=None,
):
    matches = [
        item
        for item in evidences
        if isinstance(item, dict) and item.get("evidenceId") == evidence_ref
    ]
    if len(matches) != 1:
        return None
    evidence = matches[0]
    if (
        evidence.get("source") != "tool-execution"
        or evidence.get("provenanceVerified") is not True
        or evidence.get("integrityVerified") is not True
        or evidence.get("oracleRef") != oracle_ref
        or _LEVELS.get(evidence.get("evidenceLevel"), -1) < minimum_level
        or (result is not None and evidence.get("oracleResult") != result)
    ):
        return None
    if require_trusted and (
        not callable(evidence_verifier) or evidence_verifier(evidence) is not True
    ):
        return None
    return evidence


def _matching_refs(
    refs,
    evidences,
    oracle_ref,
    result=None,
    minimum_level=0,
    require_trusted=False,
    evidence_verifier=None,
):
    return [
        ref
        for ref in dict.fromkeys(refs)
        if _nonempty(ref)
        and _evidence_for(
            ref,
            evidences,
            oracle_ref,
            result,
            minimum_level,
            require_trusted,
            evidence_verifier,
        )
        is not None
    ]


def _identity(candidate):
    identity = candidate.get("identity")
    if not isinstance(identity, dict):
        return None
    values = tuple(identity.get(field) for field in _IDENTITY_FIELDS)
    if not all(_nonempty(value) for value in values):
        return None
    return values


def _review_required(candidate):
    value = candidate.get("reviewRequired", False)
    return value if isinstance(value, bool) else True


def _normalize_false_positive_checks(checks):
    if not isinstance(checks, list):
        return []
    normalized = []
    allowed_fields = {"check", "result", "evidenceRefs"}
    for item in checks:
        if (
            not isinstance(item, dict)
            or set(item) - allowed_fields
            or not _nonempty(item.get("check"))
            or not isinstance(item.get("result"), str)
            or item.get("result") not in _FALSE_POSITIVE_CHECK_RESULTS
        ):
            continue
        evidence_refs = item.get("evidenceRefs")
        if evidence_refs is not None and (
            not isinstance(evidence_refs, list)
            or not all(_nonempty(ref) for ref in evidence_refs)
        ):
            continue
        normalized.append(deepcopy(item))
    return normalized


def _assessment_base(candidate):
    evidence_refs = candidate.get("evidenceRefs")
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    review_events = candidate.get("reviewEvents")
    if not isinstance(review_events, list):
        review_events = []
    assessment = {
        "schemaVersion": "1.0",
        "candidateId": candidate.get("candidateId"),
        "revision": candidate.get("revision"),
        "observedSurface": candidate.get("observedSurface"),
        "patternId": candidate.get("patternId"),
        "decision": "needs_review",
        "reasonCodes": [],
        "oracleRef": candidate.get("oracleRef"),
        "evidenceRefs": list(dict.fromkeys(ref for ref in evidence_refs if _nonempty(ref))),
        "falsePositiveChecks": _normalize_false_positive_checks(candidate.get("falsePositiveChecks", [])),
        "review": {
            "required": _review_required(candidate),
            "events": deepcopy(review_events),
        },
    }
    identity = candidate.get("identity")
    if _identity(candidate) is not None:
        assessment["identity"] = deepcopy(identity)
    return assessment


def assess_candidate(
    candidate,
    oracle,
    evidences,
    counter_evidence=None,
    duplicate_of=None,
    evidence_verifier=None,
    oracle_verifier=None,
):
    """Screen a candidate; rejection needs trusted Oracle and evidence verifiers."""
    if not isinstance(candidate, dict):
        raise TypeError("candidate-must-be-an-object")
    candidate_id = candidate.get("candidateId")
    revision = candidate.get("revision")
    if not _nonempty(candidate_id) or not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("candidate-identity-invalid")
    if not isinstance(evidences, list):
        evidences = []

    assessment = _assessment_base(candidate)
    if duplicate_of is not None:
        if not isinstance(duplicate_of, dict):
            raise ValueError("duplicate-reference-invalid")
        if (
            not _nonempty(duplicate_of.get("candidateId"))
            or duplicate_of.get("candidateId") == candidate_id
            or duplicate_of.get("decision") not in {"candidate", "needs_review"}
            or not isinstance(duplicate_of.get("revision"), int)
            or isinstance(duplicate_of.get("revision"), bool)
            or duplicate_of.get("revision") < 1
            or _identity(candidate) is None
            or _identity(candidate) != _identity(duplicate_of)
        ):
            raise ValueError("duplicate-identity-mismatch")
        assessment["decision"] = "duplicate"
        assessment["reasonCodes"] = ["DUPLICATE_CANDIDATE"]
        assessment["duplicateOf"] = {
            "candidateId": duplicate_of["candidateId"],
            "revision": duplicate_of["revision"],
        }
        return assessment

    reasons = assessment["reasonCodes"]
    oracle_ref = candidate.get("oracleRef")
    oracle_valid = _valid_oracle(candidate, oracle)
    if not oracle_valid:
        reasons.append("ORACLE_UNCONFIRMED")

    candidate_refs = assessment["evidenceRefs"]
    counter_refs = []
    if isinstance(counter_evidence, dict) and isinstance(counter_evidence.get("evidenceRefs"), list):
        counter_refs = [ref for ref in counter_evidence["evidenceRefs"] if _nonempty(ref)]
        assessment["evidenceRefs"] = list(dict.fromkeys(candidate_refs + counter_refs))

    valid_observation_refs = _matching_refs(candidate_refs, evidences, oracle_ref, minimum_level=3)
    violation_refs = _matching_refs(candidate_refs, evidences, oracle_ref, "violated", 3)
    raw_counter_refs = []
    valid_counter_refs = []
    trusted_oracle = False
    if (
        isinstance(counter_evidence, dict)
        and counter_evidence.get("oracleRef") == oracle_ref
        and oracle_valid
    ):
        raw_counter_refs = _matching_refs(counter_refs, evidences, oracle_ref, "satisfied", 3)
        if raw_counter_refs and callable(oracle_verifier):
            trusted_oracle = oracle_verifier(oracle) is True
        if trusted_oracle:
            valid_counter_refs = _matching_refs(
                counter_refs,
                evidences,
                oracle_ref,
                "satisfied",
                3,
                require_trusted=True,
                evidence_verifier=evidence_verifier,
            )

    if not valid_observation_refs:
        reasons.append("EVIDENCE_INSUFFICIENT")
    if candidate.get("environmentCheck") != "passed":
        reasons.append("ENVIRONMENT_UNSTABLE")

    raw_checks = candidate.get("falsePositiveChecks", [])
    checks = assessment["falsePositiveChecks"]
    check_results = []
    invalid_check_result = not isinstance(raw_checks, list) or len(checks) != len(raw_checks)
    for item in checks:
        check_results.append(item["result"])
    if "unknown" in check_results:
        reasons.append("FALSE_POSITIVE_CHECK_INCONCLUSIVE")
    if invalid_check_result:
        reasons.append("FALSE_POSITIVE_CHECK_INCONCLUSIVE")
    if "detected" in check_results and not valid_counter_refs:
        reasons.append("COUNTEREVIDENCE_MISSING")
    if raw_counter_refs and not trusted_oracle:
        reasons.append("ORACLE_PROVENANCE_UNVERIFIED")
    if raw_counter_refs and not valid_counter_refs:
        reasons.append("EVIDENCE_PROVENANCE_UNVERIFIED")
    review_required = assessment["review"]["required"]
    if review_required:
        reasons.append("HUMAN_REVIEW_REQUIRED")

    if violation_refs and valid_counter_refs:
        reasons.append("CONTRADICTORY_EVIDENCE")
    if not violation_refs and not valid_counter_refs:
        reasons.append("EVIDENCE_INSUFFICIENT")

    blocking_reasons = {
        "ORACLE_UNCONFIRMED",
        "EVIDENCE_INSUFFICIENT",
        "ENVIRONMENT_UNSTABLE",
        "FALSE_POSITIVE_CHECK_INCONCLUSIVE",
        "COUNTEREVIDENCE_MISSING",
        "EVIDENCE_PROVENANCE_UNVERIFIED",
        "ORACLE_PROVENANCE_UNVERIFIED",
        "CONTRADICTORY_EVIDENCE",
        "HUMAN_REVIEW_REQUIRED",
    }
    if any(reason in blocking_reasons for reason in reasons):
        assessment["decision"] = "needs_review"
    elif valid_counter_refs:
        assessment["decision"] = "rejected"
        reasons.append("TRUSTED_COUNTEREVIDENCE")
        assessment["counterEvidenceRefs"] = valid_counter_refs
    else:
        assessment["decision"] = "candidate"
    assessment["reasonCodes"] = list(dict.fromkeys(reasons))
    return assessment


def append_review_event(assessment, event):
    """Return a copy with an append-only review event bound to this revision."""
    if not isinstance(assessment, dict) or not isinstance(event, dict):
        raise TypeError("assessment-and-event-must-be-objects")
    revision = assessment.get("revision")
    event_revision = event.get("candidateRevision")
    if (
        event.get("candidateId") != assessment.get("candidateId")
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or not isinstance(event_revision, int)
        or isinstance(event_revision, bool)
        or event_revision != revision
        or not _nonempty(event.get("eventId"))
        or not _nonempty(event.get("reviewerId"))
        or event.get("decision") not in _REVIEW_DECISIONS
        or not _nonempty(event.get("reason"))
    ):
        raise ValueError("review-event-binding-invalid")
    evidence_refs = event.get("evidenceRefs")
    assessment_refs = assessment.get("evidenceRefs")
    if (
        not isinstance(evidence_refs, list)
        or not evidence_refs
        or not all(_nonempty(ref) for ref in evidence_refs)
        or len(set(evidence_refs)) != len(evidence_refs)
        or not isinstance(assessment_refs, list)
        or not set(evidence_refs).issubset(assessment_refs)
    ):
        raise ValueError("review-event-evidence-invalid")

    copied = deepcopy(assessment)
    review = copied.get("review")
    if not isinstance(review, dict):
        raise ValueError("review-history-invalid")
    events = review.get("events")
    if not isinstance(events, list):
        raise ValueError("review-history-invalid")
    seen_ids = set()
    for previous in events:
        if not isinstance(previous, dict):
            raise ValueError("review-history-invalid")
        previous_revision = previous.get("candidateRevision")
        previous_id = previous.get("eventId")
        previous_refs = previous.get("evidenceRefs")
        if (
            previous.get("candidateId") != copied.get("candidateId")
            or not isinstance(previous_revision, int)
            or isinstance(previous_revision, bool)
            or previous_revision != revision
            or not _nonempty(previous_id)
            or not isinstance(previous_refs, list)
            or not previous_refs
            or not all(_nonempty(ref) for ref in previous_refs)
            or len(set(previous_refs)) != len(previous_refs)
            or not set(previous_refs).issubset(assessment_refs)
        ):
            raise ValueError("review-history-invalid")
        if previous_id == event["eventId"] or previous_id in seen_ids:
            raise ValueError("review-event-id-duplicate")
        seen_ids.add(previous_id)
    events.append(deepcopy(event))
    return copied


def score_candidate_quality(outcomes):
    """Report screening precision/recall and observed human-review workload."""
    if not isinstance(outcomes, list):
        raise ValueError("outcomes-must-be-a-list")
    counts = {
        "truePositive": 0,
        "falsePositive": 0,
        "falseNegative": 0,
        "trueNegative": 0,
        "ambiguousExcluded": 0,
        "duplicatesLinked": 0,
        "humanReviewCount": 0,
        "humanReviewSeconds": 0,
        "reviewTimeRecordedCases": 0,
    }
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            raise ValueError("outcome-must-be-an-object")
        truth = outcome.get("groundTruth")
        decision = outcome.get("decision")
        if truth not in _GROUND_TRUTH or decision not in _CANDIDATE_DECISIONS:
            raise ValueError("outcome-value-invalid")
        review_required = outcome.get("humanReviewRequired", False)
        if not isinstance(review_required, bool):
            raise ValueError("human-review-required-invalid")
        review_seconds = outcome.get("reviewSeconds")
        if review_seconds is not None and (
            not isinstance(review_seconds, int)
            or isinstance(review_seconds, bool)
            or review_seconds < 0
        ):
            raise ValueError("review-seconds-invalid")
        if decision == "needs_review" or review_required:
            counts["humanReviewCount"] += 1
            if review_seconds is not None:
                counts["humanReviewSeconds"] += review_seconds
                counts["reviewTimeRecordedCases"] += 1
        if decision == "duplicate":
            counts["duplicatesLinked"] += 1
            continue
        if truth == "ambiguous":
            counts["ambiguousExcluded"] += 1
            continue
        retained = decision != "rejected"
        if truth == "bug" and retained:
            counts["truePositive"] += 1
        elif truth == "bug":
            counts["falseNegative"] += 1
        elif retained:
            counts["falsePositive"] += 1
        else:
            counts["trueNegative"] += 1

    positive_predictions = counts["truePositive"] + counts["falsePositive"]
    actual_bugs = counts["truePositive"] + counts["falseNegative"]
    actual_normal = counts["falsePositive"] + counts["trueNegative"]
    counts["precision"] = (
        counts["truePositive"] / positive_predictions if positive_predictions else None
    )
    counts["recall"] = counts["truePositive"] / actual_bugs if actual_bugs else None
    counts["falsePositiveRate"] = (
        counts["falsePositive"] / actual_normal if actual_normal else None
    )
    return counts
