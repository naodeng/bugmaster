import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from bugmaster_core.action_journal import ActionJournal
from bugmaster_core.provenance import (
    ProvenanceError,
    canonical_record_sha256,
    verify_provenance,
)


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(document):
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _sha256(payload)


class ProvenanceBindingTests(unittest.TestCase):
    def setUp(self):
        self.source_bytes = b"The order response must not expose another customer's data."
        self.artifact_bytes = b'{"orderId":"order-1","ownerId":"user-1"}'
        self.oracle = {
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
                "sha256": _sha256(self.source_bytes),
                "byteLength": len(self.source_bytes),
            },
            "recordedAt": "2026-11-23T10:00:00Z",
        }
        self.evidence = {
            "schemaVersion": "1.0",
            "evidenceId": "EV-ORDER-001",
            "evidenceLevel": "E3",
            "capturedAt": "2026-11-23T10:01:00Z",
            "artifact": {
                "reference": "artifacts/response.json",
                "mediaType": "application/json",
                "sha256": _sha256(self.artifact_bytes),
                "byteLength": len(self.artifact_bytes),
            },
            "oracleRef": {
                "oracleId": self.oracle["oracleId"],
                "revision": self.oracle["revision"],
                "sha256": _canonical_sha256(self.oracle),
            },
            "journalRef": {
                "sessionId": "session-1",
                "journalId": "journal-session-1",
                "actionId": "action-1",
                "outcome": "completed",
                "resultRef": "artifacts/response.json",
                "sequence": 3,
                "entryHash": "0" * 64,
            },
        }

    def _journal(self, directory):
        journal = ActionJournal(
            Path(directory) / "journal.jsonl",
            session_id="session-1",
            journal_id="journal-session-1",
        )
        journal.prepare(
            action_id="action-1",
            intent_digest="a" * 64,
            scope_revision=1,
            risk="R0",
        )
        journal.mark_dispatched("action-1", intent_digest="a" * 64)
        outcome_event = journal.record_outcome(
            "action-1", "completed", "artifacts/response.json"
        )
        self.evidence["journalRef"]["entryHash"] = outcome_event["entryHash"]
        return journal

    def _assert_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_matching_artifacts_oracle_and_journal_remain_untrusted(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)

            result = verify_provenance(
                self.oracle,
                self.evidence,
                self.source_bytes,
                self.artifact_bytes,
                journal,
            )

        self.assertEqual(result.artifact_integrity, "matched")
        self.assertEqual(result.oracle_binding, "matched")
        self.assertEqual(result.journal_binding, "matched")
        self.assertEqual(result.source_authenticity, "unverified")
        self.assertEqual(result.finding_gate, "blocked")

    def test_integral_json_numbers_follow_schema_integer_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.oracle["revision"] = 1.0
            self.oracle["source"]["byteLength"] = float(
                self.oracle["source"]["byteLength"]
            )
            self.evidence["artifact"]["byteLength"] = float(
                self.evidence["artifact"]["byteLength"]
            )
            self.evidence["oracleRef"]["revision"] = 1.0
            self.evidence["oracleRef"]["sha256"] = canonical_record_sha256(
                self.oracle
            )
            self.evidence["journalRef"]["sequence"] = 3.0

            result = verify_provenance(
                self.oracle,
                self.evidence,
                self.source_bytes,
                self.artifact_bytes,
                journal,
            )

        self.assertEqual(result.finding_gate, "blocked")

    def test_boolean_is_not_accepted_as_an_integer_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.oracle["revision"] = True
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_custom_float_subclass_is_not_accepted_as_an_integer_revision(self):
        class ForgedFloat(float):
            def is_integer(self):
                return True

            def __int__(self):
                return 1

        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.oracle["revision"] = ForgedFloat(1.5)
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_custom_string_subclass_cannot_forge_oracle_schema_version(self):
        class ForgedString(str):
            def __eq__(self, _other):
                return True

            def __ne__(self, _other):
                return False

            __hash__ = str.__hash__

        self.oracle["schemaVersion"] = ForgedString("9.0")
        self._assert_provenance_rejected()

    def test_custom_string_subclass_cannot_forge_evidence_level(self):
        class ForgedString(str):
            def __eq__(self, _other):
                return True

            __hash__ = str.__hash__

        self.evidence["evidenceLevel"] = ForgedString("E9")
        self._assert_provenance_rejected()

    def test_custom_string_subclass_cannot_forge_journal_outcome(self):
        class ForgedString(str):
            def __eq__(self, _other):
                return True

            __hash__ = str.__hash__

        self.evidence["journalRef"]["outcome"] = ForgedString("unknown")
        self._assert_provenance_rejected()

    def test_instance_override_cannot_bypass_journal_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            forged_binding = journal.recorded_outcome("action-1")
            forged_binding["entryHash"] = "f" * 64
            self.evidence["journalRef"]["entryHash"] = forged_binding["entryHash"]
            journal.recorded_outcome = lambda _action_id: forged_binding

            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_instance_override_of_journal_loader_cannot_forge_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            forged_binding = journal.recorded_outcome("action-1")
            forged_binding["entryHash"] = "f" * 64
            self.evidence["journalRef"]["entryHash"] = forged_binding["entryHash"]
            forged_event = {
                "actionId": "action-1",
                "eventType": "action_outcome",
                "data": {
                    "outcome": forged_binding["outcome"],
                    "resultRef": forged_binding["resultRef"],
                },
                "sequence": forged_binding["sequence"],
                "entryHash": forged_binding["entryHash"],
            }
            journal._load_current = lambda: ([forged_event], {})

            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_mismatched_oracle_source_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes + b" altered",
                    self.artifact_bytes,
                    journal,
                )

    def test_source_digest_mismatch_is_distinct_from_byte_length_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    b"x" * len(self.source_bytes),
                    self.artifact_bytes,
                    journal,
                )

    def test_mismatched_evidence_artifact_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes + b" altered",
                    journal,
                )

    def test_artifact_byte_length_mismatch_fails_before_hash_match(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["artifact"]["byteLength"] += 1
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_artifact_digest_mismatch_is_distinct_from_byte_length_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["artifact"]["sha256"] = "0" * 64
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_oracle_revision_digest_must_match_exact_record(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["oracleRef"]["revision"] = 2
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_oracle_identifier_must_follow_the_stable_format(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.oracle["oracleId"] = "oracle-1"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_malformed_oracle_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.oracle["recordedAt"] = "2026-02-30T10:00:00Z"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_timestamp_with_invalid_format_is_rejected(self):
        self.oracle["recordedAt"] = "not-a-timestamp"
        self._assert_provenance_rejected()

    def test_unsupported_oracle_schema_version_is_rejected(self):
        self.oracle["schemaVersion"] = "9.0"
        self._assert_provenance_rejected()

    def test_unsupported_evidence_schema_version_is_rejected(self):
        self.evidence["schemaVersion"] = "9.0"
        self._assert_provenance_rejected()

    def test_journal_outcome_must_be_a_supported_terminal_value(self):
        self.evidence["journalRef"]["outcome"] = "unknown"
        self._assert_provenance_rejected()

    def test_malformed_source_digest_is_rejected(self):
        self.oracle["source"]["sha256"] = "not-a-sha256-digest"
        self._assert_provenance_rejected()

    def test_journal_result_reference_must_match_recorded_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["journalRef"]["resultRef"] = "artifacts/other.json"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_self_asserted_provenance_flags_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["provenanceVerified"] = True
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_evidence_identifier_and_level_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["evidenceId"] = "evidence-1"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_unrecognized_evidence_level_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["evidenceLevel"] = "E5"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_journal_identity_must_match_the_evidence_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.evidence["journalRef"]["journalId"] = "journal-other"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_corrupt_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            with open(journal.path, "ab") as stream:
                stream.write(b"{}\n")
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_canonical_record_digest_rejects_non_json_values(self):
        with self.assertRaises(ProvenanceError):
            canonical_record_sha256({"value": object()})
        with self.assertRaises(ProvenanceError):
            canonical_record_sha256([])

    def test_non_byte_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    bytearray(self.source_bytes),
                    self.artifact_bytes,
                    journal,
                )

    def test_malformed_unicode_text_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.oracle["statement"] = "\ud800"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_unicode_whitespace_only_text_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = self._journal(directory)
            self.oracle["statement"] = "\u0085"
            with self.assertRaises(ProvenanceError):
                verify_provenance(
                    self.oracle,
                    self.evidence,
                    self.source_bytes,
                    self.artifact_bytes,
                    journal,
                )

    def test_a_mock_or_subclassed_journal_is_not_an_accepted_verifier(self):
        class JournalLookalike:
            session_id = "session-1"
            journal_id = "journal-session-1"

            def recorded_outcome(self, _action_id):
                return {}

        with self.assertRaises(ProvenanceError):
            verify_provenance(
                self.oracle,
                self.evidence,
                self.source_bytes,
                self.artifact_bytes,
                JournalLookalike(),
            )


if __name__ == "__main__":
    unittest.main()
