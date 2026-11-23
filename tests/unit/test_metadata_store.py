import hashlib
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def candidate_document(revision=1, decision="needs_review"):
    return {
        "schemaVersion": "1.0",
        "candidateId": "CF-001",
        "revision": revision,
        "observedSurface": "api",
        "patternId": "BP-API-002",
        "oracleRef": None,
        "evidenceRefs": ["EV-001"],
        "environmentCheck": "unknown",
        "falsePositiveChecks": [],
        "reviewRequired": True,
        "candidateAssessment": {
            "schemaVersion": "1.0",
            "candidateId": "CF-001",
            "revision": revision,
            "observedSurface": "api",
            "patternId": "BP-API-002",
            "decision": decision,
            "reasonCodes": ["ORACLE_UNCONFIRMED"],
            "oracleRef": None,
            "evidenceRefs": ["EV-001"],
            "falsePositiveChecks": [],
            "review": {"required": True, "events": []},
        },
    }


def finding_document(revision=1, status="suspected"):
    return {
        "schemaVersion": "1.0",
        "findingId": "FND-001",
        "revision": revision,
        "status": status,
        "candidateRefs": [{"candidateId": "CF-001", "revision": 1}],
        "observedSurfaces": ["api"],
        "patternId": "BP-API-002",
        "oracleRef": {"oracleId": "OR-001", "revision": 1, "sha256": "a" * 64},
        "businessContext": "Order creation must be idempotent.",
        "actualBehavior": "Two orders were persisted.",
        "expectedBehavior": "Only one order should be persisted.",
        "preconditions": ["An idempotency key is supplied."],
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
        "remediation": "Inspect the transaction boundary.",
        "regressionRecommendation": "Add an idempotency regression case.",
        "recordedAt": "2026-11-23T10:00:00Z",
    }


def import_store_api(test_case):
    try:
        return importlib.import_module("bugmaster_core.metadata_store")
    except ModuleNotFoundError as error:
        test_case.fail("Candidate/Finding metadata store is not implemented: {}".format(error))


class MetadataStoreTests(unittest.TestCase):
    def setUp(self):
        self.api = import_store_api(self)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "bugmaster"
        self.candidates = self.api.CandidateStore(self.root)
        self.findings = self.api.FindingStore(self.root)

    def test_candidate_revision_can_be_created_and_read_without_aliasing(self):
        stored = self.candidates.create(candidate_document())
        stored["evidenceRefs"].append("EV-CALLER-MUTATION")

        latest = self.candidates.read_latest("CF-001")
        self.assertEqual(latest["revision"], 1)
        self.assertEqual(latest["evidenceRefs"], ["EV-001"])
        self.assertEqual(self.candidates.read_revision("CF-001", 1), latest)

    def test_candidate_append_preserves_previous_revision(self):
        self.candidates.create(candidate_document())
        updated = candidate_document(revision=2)
        updated["evidenceRefs"] = ["EV-001", "EV-002"]
        updated["candidateAssessment"]["evidenceRefs"] = ["EV-001", "EV-002"]

        self.candidates.append_revision(updated, expected_revision=1)

        self.assertEqual(self.candidates.read_latest("CF-001")["revision"], 2)
        self.assertEqual(
            self.candidates.read_revision("CF-001", 1)["evidenceRefs"], ["EV-001"]
        )

    def test_stale_candidate_revision_is_rejected(self):
        self.candidates.create(candidate_document())
        self.candidates.append_revision(candidate_document(revision=2), 1)

        with self.assertRaises(self.api.RevisionConflictError):
            self.candidates.append_revision(candidate_document(revision=2), 1)

        self.assertEqual(self.candidates.read_latest("CF-001")["revision"], 2)

    def test_candidate_cannot_change_its_stable_identity(self):
        self.candidates.create(candidate_document())
        updated = candidate_document(revision=2)
        updated["candidateAssessment"]["revision"] = 2
        updated["patternId"] = "BP-API-003"
        updated["candidateAssessment"]["patternId"] = "BP-API-003"

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.append_revision(updated, 1)

    def test_candidate_revision_and_assessment_must_match(self):
        document = candidate_document()
        document["candidateAssessment"]["revision"] = 2

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_candidate_store_rejects_noncanonical_oracle_and_evidence_ids(self):
        invalid_oracle = candidate_document()
        invalid_oracle["oracleRef"] = "oracle-001"
        invalid_oracle["candidateAssessment"]["oracleRef"] = "oracle-001"
        invalid_evidence = candidate_document()
        invalid_evidence["evidenceRefs"] = ["evidence-001"]
        invalid_evidence["candidateAssessment"]["evidenceRefs"] = ["evidence-001"]

        for document in (invalid_oracle, invalid_evidence):
            with self.subTest(document=document):
                with self.assertRaises(self.api.MetadataStoreError):
                    self.candidates.create(document)

    def test_candidate_and_finding_stores_reject_trailing_newlines_in_ids_and_digests(self):
        invalid_candidates = []

        invalid = candidate_document()
        invalid["oracleRef"] = "OR-001\n"
        invalid["candidateAssessment"]["oracleRef"] = "OR-001\n"
        invalid_candidates.append(invalid)

        invalid = candidate_document()
        invalid["evidenceRefs"] = ["EV-001\n"]
        invalid["candidateAssessment"]["evidenceRefs"] = ["EV-001\n"]
        invalid_candidates.append(invalid)

        invalid = candidate_document()
        invalid["falsePositiveChecks"] = [
            {
                "check": "authorization_scope",
                "result": "unknown",
                "evidenceRefs": ["EV-001\n"],
            }
        ]
        invalid_candidates.append(invalid)

        invalid_findings = []

        invalid = finding_document()
        invalid["candidateRefs"][0]["candidateId"] = "CF-001\n"
        invalid_findings.append(invalid)

        invalid = finding_document()
        invalid["patternId"] = "BP-API-002\n"
        invalid_findings.append(invalid)

        invalid = finding_document()
        invalid["oracleRef"]["oracleId"] = "OR-001\n"
        invalid_findings.append(invalid)

        invalid = finding_document()
        invalid["oracleRef"]["sha256"] = "a" * 64 + "\n"
        invalid_findings.append(invalid)

        invalid = finding_document()
        invalid["actionRefs"][0]["entryHash"] = "b" * 64 + "\n"
        invalid_findings.append(invalid)

        invalid = finding_document()
        invalid["evidenceRefs"][0]["evidenceId"] = "EV-001\n"
        invalid_findings.append(invalid)

        invalid = finding_document()
        invalid["evidenceRefs"][0]["sha256"] = "c" * 64 + "\n"
        invalid_findings.append(invalid)

        for document in invalid_candidates:
            with self.subTest(document=document):
                with self.assertRaises(self.api.MetadataStoreError):
                    self.candidates.create(document)

        for document in invalid_findings:
            with self.subTest(document=document):
                with self.assertRaises(self.api.MetadataStoreError):
                    self.findings.create(document)

    def test_candidate_assessment_must_reference_record_evidence(self):
        document = candidate_document()
        document["candidateAssessment"]["evidenceRefs"] = ["EV-OTHER"]

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_schema_invalid_candidate_is_not_persisted(self):
        document = candidate_document()
        document["unrecognized"] = True

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

        self.assertIsNone(self.candidates.read_latest("CF-001"))

    def test_candidate_rejection_is_blocked_without_a_trusted_host(self):
        document = candidate_document(decision="rejected")
        document["oracleRef"] = "OR-001"
        document["candidateAssessment"]["oracleRef"] = "OR-001"
        document["candidateAssessment"]["reasonCodes"] = ["TRUSTED_COUNTEREVIDENCE"]
        document["candidateAssessment"]["counterEvidenceRefs"] = ["EV-COUNTER"]
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_finding_revision_is_append_only_and_readable(self):
        self.findings.create(finding_document())
        second = finding_document(revision=2)
        second["evidenceRefs"].append(
            {"evidenceId": "EV-002", "sha256": "d" * 64, "byteLength": 21}
        )

        self.findings.append_revision(second, expected_revision=1)

        self.assertEqual(self.findings.read_latest("FND-001")["revision"], 2)
        self.assertEqual(len(self.findings.read_revision("FND-001", 1)["evidenceRefs"]), 1)

    def test_finding_evidence_ids_must_be_unique_even_with_different_fingerprints(self):
        document = finding_document()
        document["evidenceRefs"].append(
            {"evidenceId": "EV-001", "sha256": "d" * 64, "byteLength": 18}
        )

        with self.assertRaises(self.api.MetadataStoreError):
            self.findings.create(document)

    def test_finding_cannot_be_marked_confirmed_or_terminal(self):
        for status in ("confirmed", "rejected", "resolved", "reopened", "duplicate"):
            with self.subTest(status=status):
                with self.assertRaises(self.api.MetadataStoreError):
                    self.findings.create(finding_document(status=status))

    def test_duplicate_candidate_id_cannot_overwrite_history(self):
        self.candidates.create(candidate_document())

        with self.assertRaises(self.api.RevisionConflictError):
            self.candidates.create(candidate_document())

        self.assertEqual(self.candidates.read_latest("CF-001")["revision"], 1)

    def test_record_file_digest_detects_tampering(self):
        self.findings.create(finding_document())
        key = hashlib.sha256(b"FND-001").hexdigest()
        revision_path = self.root / "findings" / key / "revisions" / "00000001.json"
        document = json.loads(revision_path.read_text(encoding="utf-8"))
        document["actualBehavior"] = "changed after publication"
        revision_path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(self.api.MetadataCorruptionError):
            self.findings.read_latest("FND-001")

    def test_revision_symlink_is_rejected(self):
        self.findings.create(finding_document())
        key = hashlib.sha256(b"FND-001").hexdigest()
        revision_path = self.root / "findings" / key / "revisions" / "00000001.json"
        outside = Path(self.temporary.name) / "outside.json"
        outside.write_text(revision_path.read_text(encoding="utf-8"), encoding="utf-8")
        revision_path.unlink()
        revision_path.symlink_to(outside)

        with self.assertRaises(self.api.MetadataCorruptionError):
            self.findings.read_latest("FND-001")

    def test_permissive_storage_root_is_rejected_without_repair(self):
        self.candidates.create(candidate_document())
        self.root.chmod(0o755)

        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

        self.assertEqual(self.root.stat().st_mode & 0o777, 0o755)

    def test_create_does_not_repair_an_existing_shared_storage_root(self):
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o755)
        try:
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates.create(candidate_document())

            self.assertEqual(self.root.stat().st_mode & 0o777, 0o755)
        finally:
            self.root.chmod(0o700)

    def test_orphan_revision_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        orphan = self.root / "candidates" / key / "revisions" / "00000002.json"
        orphan.write_text(json.dumps(candidate_document(revision=2)), encoding="utf-8")

        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_symlinked_storage_root_is_rejected(self):
        outside = Path(self.temporary.name) / "outside"
        link = Path(self.temporary.name) / "root-link"
        outside.mkdir(mode=0o700)
        link.symlink_to(outside, target_is_directory=True)
        candidates = self.api.CandidateStore(link)

        with self.assertRaises(self.api.MetadataStoreError):
            candidates.create(candidate_document())

        self.assertEqual(list(outside.iterdir()), [])

    def test_hard_linked_revision_is_rejected(self):
        self.findings.create(finding_document())
        key = hashlib.sha256(b"FND-001").hexdigest()
        revision_path = self.root / "findings" / key / "revisions" / "00000001.json"
        alias = Path(self.temporary.name) / "revision-alias.json"
        os.link(revision_path, alias)

        with self.assertRaises(self.api.MetadataCorruptionError):
            self.findings.read_latest("FND-001")

    def test_missing_record_returns_none(self):
        self.assertIsNone(self.findings.read_latest("FND-MISSING"))
        self.assertIsNone(self.findings.read_revision("FND-MISSING", 1))

    def test_create_requires_revision_one(self):
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(candidate_document(revision=2))

    def test_append_rejects_invalid_expected_revision(self):
        for revision in (True, 0, 1.0):
            with self.subTest(revision=revision):
                with self.assertRaises(self.api.MetadataStoreError):
                    self.candidates.append_revision(
                        candidate_document(revision=2), revision
                    )

    def test_append_requires_next_document_revision(self):
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.append_revision(
                candidate_document(revision=1), expected_revision=1
            )

    def test_append_requires_an_existing_initial_revision(self):
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.append_revision(
                candidate_document(revision=2), expected_revision=1
            )

    def test_read_rejects_invalid_identifiers_and_revisions(self):
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.read_latest("../CF-001")
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.read_revision("CF-001", True)

    def test_read_missing_revision_returns_none(self):
        self.candidates.create(candidate_document())
        self.assertIsNone(self.candidates.read_revision("CF-001", 2))

    def test_non_object_and_non_json_candidate_documents_are_rejected(self):
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create([])
        document = candidate_document()
        document["invalidNumber"] = float("nan")
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_oversized_candidate_metadata_is_rejected(self):
        document = candidate_document()
        document["candidateAssessment"]["reasonCodes"] = ["x" * (4 * 1024 * 1024)]
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_additional_validator_must_not_accept_invalid_metadata(self):
        def reject(_document):
            raise ValueError("host policy rejected this record")

        store = self.api.CandidateStore(self.root, reject)
        with self.assertRaises(self.api.MetadataStoreError):
            store.create(candidate_document())
        self.assertIsNone(self.candidates.read_latest("CF-001"))

    def test_additional_validator_cannot_mutate_persisted_metadata(self):
        expected = finding_document()

        def mutate(document):
            document["actualBehavior"] = "changed by the extension validator"

        store = self.api.FindingStore(self.root, mutate)
        created = store.create(expected)

        self.assertEqual(created, expected)
        self.assertEqual(store.read_latest("FND-001"), expected)

    def test_candidate_and_assessment_identities_must_match(self):
        identity = {
            "targetRef": "API-ORDERS",
            "businessObjectRef": "order:17",
            "operationRef": "POST /orders",
            "oracleRef": "OR-001",
            "violationSignature": "duplicate-side-effect",
        }
        mismatched = {**identity, "violationSignature": "other-side-effect"}

        with self.subTest("different identity"):
            document = candidate_document()
            document["identity"] = identity
            document["candidateAssessment"]["identity"] = mismatched
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates.create(document)

    def test_candidate_identity_oracle_must_match_candidate_oracle_reference(self):
        identity = {
            "targetRef": "API-ORDERS",
            "businessObjectRef": "order:17",
            "operationRef": "POST /orders",
            "oracleRef": "OR-002",
            "violationSignature": "duplicate-side-effect",
        }
        document = candidate_document()
        document["identity"] = identity
        document["candidateAssessment"]["identity"] = identity.copy()

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

        with self.subTest("assessment identity without candidate identity"):
            document = candidate_document()
            document["candidateAssessment"]["identity"] = identity
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates.create(document)

        with self.subTest("candidate identity without assessment identity"):
            document = candidate_document()
            document["identity"] = identity
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates.create(document)

    def test_duplicate_candidate_cannot_reference_itself(self):
        document = candidate_document(decision="duplicate")
        identity = {
            "targetRef": "API-ORDERS",
            "businessObjectRef": "order:17",
            "operationRef": "POST /orders",
            "oracleRef": "OR-001",
            "violationSignature": "duplicate-side-effect",
        }
        document["oracleRef"] = "OR-001"
        document["identity"] = identity
        assessment = document["candidateAssessment"]
        assessment["oracleRef"] = "OR-001"
        assessment["identity"] = identity.copy()
        assessment["reasonCodes"] = ["DUPLICATE_CANDIDATE"]
        assessment["duplicateOf"] = {"candidateId": "CF-001", "revision": 1}

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_candidate_review_event_ids_must_be_unique(self):
        document = candidate_document()
        event = {
            "eventId": "REV-001",
            "candidateId": "CF-001",
            "candidateRevision": 1,
            "reviewerId": "reviewer-1",
            "decision": "needs_evidence",
            "reason": "Need more evidence.",
            "evidenceRefs": ["EV-001"],
            "reviewedAt": "2026-11-23T10:00:00Z",
        }
        document["candidateAssessment"]["review"]["events"] = [event, event.copy()]

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_candidate_review_event_evidence_must_belong_to_assessment(self):
        document = candidate_document()
        document["candidateAssessment"]["review"]["events"] = [
            {
                "eventId": "REV-001",
                "candidateId": "CF-001",
                "candidateRevision": 1,
                "reviewerId": "reviewer-1",
                "decision": "needs_evidence",
                "reason": "Need more evidence.",
                "evidenceRefs": ["EV-002"],
                "reviewedAt": "2026-11-23T10:00:00Z",
            }
        ]

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_candidate_review_event_must_bind_to_candidate_identity(self):
        document = candidate_document()
        document["candidateAssessment"]["review"]["events"] = [
            {
                "eventId": "REV-001",
                "candidateId": "CF-OTHER",
                "candidateRevision": 1,
                "reviewerId": "reviewer-1",
                "decision": "needs_evidence",
                "reason": "Need more evidence.",
                "evidenceRefs": ["EV-001"],
                "reviewedAt": "2026-11-23T10:00:00Z",
            }
        ]

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_candidate_review_event_cannot_reference_a_future_revision(self):
        document = candidate_document()
        document["candidateAssessment"]["review"]["events"] = [
            {
                "eventId": "REV-001",
                "candidateId": "CF-001",
                "candidateRevision": 2,
                "reviewerId": "reviewer-1",
                "decision": "needs_evidence",
                "reason": "Need more evidence.",
                "evidenceRefs": ["EV-001"],
                "reviewedAt": "2026-11-23T10:00:00Z",
            }
        ]

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_candidate_review_event_can_bind_to_an_existing_revision(self):
        document = candidate_document()
        document["candidateAssessment"]["review"]["events"] = [
            {
                "eventId": "REV-001",
                "candidateId": "CF-001",
                "candidateRevision": 1,
                "reviewerId": "reviewer-1",
                "decision": "needs_evidence",
                "reason": "Need more evidence.",
                "evidenceRefs": ["EV-001"],
                "reviewedAt": "2026-11-23T10:00:00Z",
            }
        ]

        self.assertEqual(self.candidates.create(document), document)

    def test_historical_review_event_evidence_must_exist_in_referenced_revision(self):
        self.candidates.create(candidate_document())
        document = candidate_document(revision=2)
        document["evidenceRefs"] = ["EV-001", "EV-002"]
        assessment = document["candidateAssessment"]
        assessment["evidenceRefs"] = ["EV-001", "EV-002"]
        assessment["review"]["events"] = [
            {
                "eventId": "REV-001",
                "candidateId": "CF-001",
                "candidateRevision": 1,
                "reviewerId": "reviewer-1",
                "decision": "needs_evidence",
                "reason": "Review references later evidence.",
                "evidenceRefs": ["EV-002"],
                "reviewedAt": "2026-11-23T10:00:00Z",
            }
        ]

        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.append_revision(document, expected_revision=1)

    def test_schema_integer_revisions_are_normalized_for_storage(self):
        first = candidate_document(revision=1.0)
        first["candidateAssessment"]["revision"] = 1.0
        created = self.candidates.create(first)

        self.assertIs(type(created["revision"]), int)
        self.assertIs(type(created["candidateAssessment"]["revision"]), int)
        self.assertIs(type(self.candidates.read_latest("CF-001")["revision"]), int)

        second = candidate_document(revision=2.0)
        second["candidateAssessment"]["revision"] = 2.0
        updated = self.candidates.append_revision(second, expected_revision=1)
        self.assertIs(type(updated["revision"]), int)

    def test_schema_integer_normalization_is_recursive_and_preserves_fractions(self):
        value = {
            "revision": 1.0,
            "nested": [2.5, {"count": 3.0, "enabled": True}],
            "label": "3.0",
        }

        normalized = self.api._normalize_schema_integers(value)

        self.assertEqual(
            normalized,
            {"revision": 1, "nested": [2.5, {"count": 3, "enabled": True}], "label": "3.0"},
        )
        self.assertIs(type(normalized["revision"]), int)

    def test_constructor_rejects_invalid_root_and_validator(self):
        with self.assertRaises(self.api.MetadataStoreError):
            self.api.CandidateStore(object())
        with self.assertRaises(self.api.MetadataStoreError):
            self.api.CandidateStore(self.root, validator=False)

    def test_contract_validator_load_failure_is_reported(self):
        with mock.patch(
            "bugmaster_core.metadata_store.Path.read_text",
            side_effect=OSError("schema file unavailable"),
        ):
            with self.assertRaises(self.api.MetadataStoreError):
                self.api.CandidateStore(self.root)

    def test_existing_storage_root_without_entity_directory_is_empty(self):
        self.root.mkdir(mode=0o700)
        store = self.api.CandidateStore(self.root)
        self.assertIsNone(store.read_latest("CF-001"))

    def test_existing_record_without_lock_file_fails_closed(self):
        key = hashlib.sha256(b"CF-001").hexdigest()
        self.root.mkdir(mode=0o700)
        (self.root / "candidates").mkdir(mode=0o700)
        (self.root / "candidates" / key).mkdir(mode=0o700)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_existing_record_without_revisions_directory_is_empty(self):
        key = hashlib.sha256(b"CF-001").hexdigest()
        entity = self.root / "candidates" / key
        self.root.mkdir(mode=0o700)
        (self.root / "candidates").mkdir(mode=0o700)
        entity.mkdir(mode=0o700)
        lock_file = entity / "metadata.lock"
        lock_file.touch(mode=0o600)
        lock_file.chmod(0o600)
        self.assertIsNone(self.candidates.read_latest("CF-001"))

    def test_lock_file_permissions_are_checked(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        lock_file = self.root / "candidates" / key / "metadata.lock"
        lock_file.chmod(0o644)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_hard_linked_lock_file_is_rejected(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        lock_file = self.root / "candidates" / key / "metadata.lock"
        os.link(lock_file, Path(self.temporary.name) / "lock-alias")
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_permissive_candidate_directory_is_rejected_without_repair(self):
        self.candidates.create(candidate_document())
        directory = self.root / "candidates"
        directory.chmod(0o755)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")
        self.assertEqual(directory.stat().st_mode & 0o777, 0o755)

    def test_permissive_revisions_directory_is_rejected_without_repair(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        directory = self.root / "candidates" / key / "revisions"
        directory.chmod(0o755)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")
        self.assertEqual(directory.stat().st_mode & 0o777, 0o755)

    def test_unexpected_record_directory_entry_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        entity = self.root / "candidates" / key
        (entity / "untracked.tmp").write_text("", encoding="utf-8")
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_invalid_revision_directory_entry_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revisions = self.root / "candidates" / key / "revisions"
        (revisions / "unexpected.tmp").write_text("", encoding="utf-8")
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_revision_with_noncanonical_filename_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revisions = self.root / "candidates" / key / "revisions"
        (revisions / "00000001.json").rename(revisions / "000000001.json")
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_directory_in_revision_slot_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revisions = self.root / "candidates" / key / "revisions"
        (revisions / "00000001.json").unlink()
        (revisions / "00000001.json").mkdir(mode=0o700)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_missing_head_with_revision_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        (self.root / "candidates" / key / "metadata.head").unlink()
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_head_symlink_and_malformed_fields_fail_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        entity = self.root / "candidates" / key
        head = entity / "metadata.head"
        original_head = json.loads(head.read_text(encoding="utf-8"))
        external_head = Path(self.temporary.name) / "head-copy.json"
        external_head.write_text(head.read_text(encoding="utf-8"), encoding="utf-8")
        head.unlink()
        head.symlink_to(external_head)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

        head.unlink()
        original_head["revision"] = True
        head.write_text(
            json.dumps(original_head, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        head.chmod(0o600)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_oversized_head_is_rejected(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        head = self.root / "candidates" / key / "metadata.head"
        head.write_bytes(b" " * 1025 + b"\n")
        head.chmod(0o600)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_oversized_revision_is_rejected(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revision = self.root / "candidates" / key / "revisions" / "00000001.json"
        revision.write_bytes(b"x" * (4 * 1024 * 1024 + 2))
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_revision_filename_and_document_identity_must_match(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revision_path = self.root / "candidates" / key / "revisions" / "00000001.json"
        document = json.loads(revision_path.read_text(encoding="utf-8"))
        document["candidateId"] = "CF-002"
        document["candidateAssessment"]["candidateId"] = "CF-002"
        revision_path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_revision_number_must_match_filename(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revision_path = self.root / "candidates" / key / "revisions" / "00000001.json"
        document = json.loads(revision_path.read_text(encoding="utf-8"))
        document["revision"] = 2
        document["candidateAssessment"]["revision"] = 2
        revision_path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_revision_sequence_must_not_skip_a_number(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revisions = self.root / "candidates" / key / "revisions"
        (revisions / "00000001.json").rename(revisions / "00000003.json")
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_metadata_head_with_missing_revisions_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        entity = self.root / "candidates" / key
        revisions = entity / "revisions"
        (revisions / "00000001.json").unlink()
        revisions.rmdir()
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_empty_revision_directory_with_head_fails_closed(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revisions = self.root / "candidates" / key / "revisions"
        (revisions / "00000001.json").unlink()
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_read_all_and_canonical_json_reject_invalid_content(self):
        with tempfile.TemporaryFile() as file_handle:
            file_handle.write(b"too long")
            file_handle.flush()
            file_handle.seek(0)
            with self.assertRaises(self.api.MetadataCorruptionError):
                self.api._RevisionedMetadataStore._read_all(
                    file_handle.fileno(), 2, "metadata"
                )
        for raw in (b"{}", b"not-json\n", b'{ "a":1 }\n'):
            with self.subTest(raw=raw):
                with self.assertRaises(self.api.MetadataCorruptionError):
                    self.api._RevisionedMetadataStore._decode_canonical_json(
                        raw, "metadata"
                    )

    def test_private_file_verification_rejects_unsafe_metadata(self):
        metadata = mock.Mock(st_mode=0o040600, st_uid=os.geteuid(), st_nlink=1)
        with mock.patch("bugmaster_core.metadata_store.os.fstat", return_value=metadata):
            with self.assertRaises(self.api.MetadataCorruptionError):
                self.api._RevisionedMetadataStore._require_private_file(
                    -1, self.api.MetadataCorruptionError, "test file"
                )

        metadata = mock.Mock(
            st_mode=0o100644,
            st_uid=os.geteuid() + 1,
            st_nlink=1,
        )
        with mock.patch("bugmaster_core.metadata_store.os.fstat", return_value=metadata):
            with self.assertRaises(self.api.MetadataCorruptionError):
                self.api._RevisionedMetadataStore._require_private_file(
                    -1, self.api.MetadataCorruptionError, "test file"
                )

        metadata.st_uid = os.geteuid()
        with mock.patch("bugmaster_core.metadata_store.os.fstat", return_value=metadata):
            with self.assertRaises(self.api.MetadataCorruptionError):
                self.api._RevisionedMetadataStore._require_private_file(
                    -1, self.api.MetadataCorruptionError, "test file"
                )

        metadata.st_mode = 0o100600
        with mock.patch("bugmaster_core.metadata_store.os.fstat", return_value=metadata):
            with mock.patch("bugmaster_core.metadata_store._has_extended_acl", return_value=True):
                with self.assertRaises(self.api.MetadataCorruptionError):
                    self.api._RevisionedMetadataStore._require_private_file(
                        -1, self.api.MetadataCorruptionError, "test file"
                    )

        with mock.patch(
            "bugmaster_core.metadata_store.os.fstat", side_effect=OSError("stat failed")
        ):
            with self.assertRaises(OSError):
                self.api._RevisionedMetadataStore._require_private_file(
                    -1, self.api.MetadataCorruptionError, "test file"
                )

        metadata.st_nlink = 2
        with mock.patch("bugmaster_core.metadata_store.os.fstat", return_value=metadata):
            with self.assertRaises(self.api.MetadataCorruptionError):
                self.api._RevisionedMetadataStore._require_private_file(
                    -1, self.api.MetadataCorruptionError, "test file"
                )

    def test_acl_inspection_failure_is_reported(self):
        metadata = mock.Mock(st_mode=0o100600, st_uid=os.geteuid(), st_nlink=1)
        with mock.patch("bugmaster_core.metadata_store.os.fstat", return_value=metadata):
            with mock.patch(
                "bugmaster_core.metadata_store._has_extended_acl",
                side_effect=OSError("ACL inspection failed"),
            ):
                with self.assertRaises(self.api.MetadataCorruptionError):
                    self.api._RevisionedMetadataStore._require_private_file(
                        -1, self.api.MetadataCorruptionError, "test file"
                    )

    def test_candidate_transition_cannot_remove_prior_evidence(self):
        self.candidates.create(candidate_document())
        updated = candidate_document(revision=2)
        updated["evidenceRefs"] = []
        updated["candidateAssessment"]["evidenceRefs"] = []
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.append_revision(updated, expected_revision=1)

    def test_candidate_review_required_flag_must_match_assessment(self):
        document = candidate_document()
        document["candidateAssessment"]["review"]["required"] = False
        with self.assertRaises(self.api.MetadataStoreError):
            self.candidates.create(document)

    def test_finding_transition_cannot_remove_prior_evidence(self):
        initial = finding_document()
        initial["evidenceRefs"].append(
            {"evidenceId": "EV-002", "sha256": "d" * 64, "byteLength": 18}
        )
        self.findings.create(initial)
        updated = finding_document(revision=2)
        updated["evidenceRefs"] = [initial["evidenceRefs"][1]]
        with self.assertRaises(self.api.MetadataStoreError):
            self.findings.append_revision(updated, expected_revision=1)

    def test_temporary_file_helpers_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            self.addCleanup(os.close, directory_fd)
            with mock.patch(
                "bugmaster_core.metadata_store.os.open",
                side_effect=FileExistsError,
            ):
                with self.assertRaises(FileExistsError):
                    self.api._create_temporary_file(directory_fd, ".metadata-test-")
        with mock.patch("bugmaster_core.metadata_store.os.write", return_value=0):
            with self.assertRaises(OSError):
                self.api._write_all(-1, b"content")

    def test_record_creation_handles_a_concurrent_lock_file_creator(self):
        real_open = os.open
        lock_open_attempts = 0

        def open_with_lock_race(path, flags, *args, **kwargs):
            nonlocal lock_open_attempts
            if path == "metadata.lock":
                lock_open_attempts += 1
                if lock_open_attempts == 1:
                    raise FileNotFoundError(path)
                if lock_open_attempts == 2:
                    descriptor = real_open(
                        path,
                        flags,
                        *args,
                        **dict(kwargs, dir_fd=kwargs["dir_fd"]),
                    )
                    os.close(descriptor)
                    raise FileExistsError(path)
            return real_open(path, flags, *args, **kwargs)

        with mock.patch(
            "bugmaster_core.metadata_store.os.open", side_effect=open_with_lock_race
        ):
            self.candidates.create(candidate_document())

        self.assertEqual(lock_open_attempts, 3)
        self.assertIsNotNone(self.candidates.read_latest("CF-001"))

    def test_lock_failure_is_reported_and_unlocks_only_after_acquire(self):
        with mock.patch(
            "bugmaster_core.metadata_store.fcntl.flock",
            side_effect=OSError("lock unavailable"),
        ):
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates.create(candidate_document())

    def test_creation_reports_directory_and_revision_open_failures(self):
        with mock.patch(
            "bugmaster_core.metadata_store._open_directory_at",
            side_effect=FileNotFoundError("directory race"),
        ):
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates.create(candidate_document())

        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revisions = self.root / "candidates" / key / "revisions"
        revisions.chmod(0o755)
        with self.assertRaises(self.api.MetadataCorruptionError):
            self.candidates.read_latest("CF-001")

    def test_revision_writer_rejects_existing_file_and_cleans_temporary_files(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        revision_dir = self.root / "candidates" / key / "revisions"
        revision_fd = os.open(revision_dir, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, revision_fd)
        storage = {"revisions_fd": revision_fd}
        with mock.patch(
            "bugmaster_core.metadata_store.os.link",
            side_effect=FileExistsError("revision exists"),
        ):
            with self.assertRaises(self.api.MetadataCorruptionError):
                self.candidates._write_revision(
                    storage, 1, self.api._canonical_bytes(candidate_document())
                )
        self.assertEqual(list(revision_dir.glob(".metadata-revision-*")), [])

        real_unlink = os.unlink

        def remove_temporary_then_fail(_file_descriptor, _payload):
            temporary = next(revision_dir.glob(".metadata-revision-*"))
            real_unlink(temporary)
            raise OSError("test write failure")

        with mock.patch(
            "bugmaster_core.metadata_store._write_all",
            side_effect=remove_temporary_then_fail,
        ):
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates._write_revision(
                    storage, 2, self.api._canonical_bytes(candidate_document(revision=2))
                )

    def test_revision_writer_reports_post_link_sync_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            revision_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            self.addCleanup(os.close, revision_fd)
            storage = {"revisions_fd": revision_fd}
            real_fsync = os.fsync
            calls = 0

            def fail_after_publication(file_descriptor):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("directory sync failed")
                return real_fsync(file_descriptor)

            with mock.patch(
                "bugmaster_core.metadata_store.os.fsync",
                side_effect=fail_after_publication,
            ):
                with self.assertRaises(self.api.MetadataStoreError):
                    self.candidates._write_revision(
                        storage, 1, self.api._canonical_bytes(candidate_document())
                    )

    def test_head_writer_cleans_up_after_replace_failure(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        entity = self.root / "candidates" / key
        entity_fd = os.open(entity, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, entity_fd)
        storage = {"entity_fd": entity_fd}
        with mock.patch(
            "bugmaster_core.metadata_store.os.replace",
            side_effect=OSError("replace failed"),
        ):
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates._write_head(
                    storage, 2, b"{}", "a" * 64
                )
        self.assertEqual(list(entity.glob(".metadata-head-*")), [])

    def test_head_writer_closes_and_cleans_if_the_temporary_file_disappears(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        entity = self.root / "candidates" / key
        entity_fd = os.open(entity, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, entity_fd)

        def remove_temporary_then_fail(_source, _target, **_kwargs):
            next(entity.glob(".metadata-head-*")).unlink()
            raise OSError("head publication failed")

        with mock.patch(
            "bugmaster_core.metadata_store.os.replace",
            side_effect=remove_temporary_then_fail,
        ):
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates._write_head(
                    {"entity_fd": entity_fd}, 2, b"{}", "a" * 64
                )

    def test_head_writer_closes_descriptor_when_mode_setting_fails(self):
        self.candidates.create(candidate_document())
        key = hashlib.sha256(b"CF-001").hexdigest()
        entity = self.root / "candidates" / key
        entity_fd = os.open(entity, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, entity_fd)
        with mock.patch(
            "bugmaster_core.metadata_store.os.fchmod",
            side_effect=OSError("chmod failed"),
        ):
            with self.assertRaises(self.api.MetadataStoreError):
                self.candidates._write_head(
                    {"entity_fd": entity_fd}, 2, b"{}", "a" * 64
                )

    def test_revision_read_error_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            self.addCleanup(os.close, directory_fd)
            storage = {"entity_fd": directory_fd, "revisions_fd": directory_fd}
            with mock.patch.object(self.candidates, "_validate_entity_entries"):
                with mock.patch.object(self.candidates, "_read_head", return_value=None):
                    with mock.patch(
                        "bugmaster_core.metadata_store.os.scandir",
                        side_effect=OSError("directory read failed"),
                    ):
                        with self.assertRaises(self.api.MetadataCorruptionError):
                            self.candidates._read_history(storage, "CF-001")

                    entry = mock.Mock(name="00000001.json")
                    entry.name = "00000001.json"
                    entry.stat.side_effect = OSError("entry stat failed")
                    scanner = mock.MagicMock()
                    scanner.__enter__.return_value = [entry]
                    with mock.patch(
                        "bugmaster_core.metadata_store.os.scandir",
                        return_value=scanner,
                    ):
                        with self.assertRaises(self.api.MetadataCorruptionError):
                            self.candidates._read_history(storage, "CF-001")

    def test_entity_directory_and_head_stat_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            self.addCleanup(os.close, directory_fd)
            storage = {"entity_fd": directory_fd, "revisions_fd": directory_fd}
            with mock.patch.object(self.candidates, "_head_exists", return_value=False):
                with mock.patch(
                    "bugmaster_core.metadata_store.os.scandir",
                    side_effect=OSError("directory read failed"),
                ):
                    with self.assertRaises(self.api.MetadataCorruptionError):
                        self.candidates._validate_entity_entries(storage)
            with mock.patch(
                "bugmaster_core.metadata_store.os.stat",
                side_effect=OSError("head stat failed"),
            ):
                with self.assertRaises(self.api.MetadataCorruptionError):
                    self.api._RevisionedMetadataStore._head_exists(storage)

            with self.assertRaises(self.api.MetadataCorruptionError):
                self.candidates._read_revision(
                    storage, "missing.json", 1, "CF-001"
                )


if __name__ == "__main__":
    unittest.main()
