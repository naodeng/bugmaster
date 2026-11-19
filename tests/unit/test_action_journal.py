import hashlib
import tempfile
import unittest
import copy
import json
import os
import stat
from pathlib import Path
from unittest.mock import patch


def _journal_types(test_case):
    try:
        from bugmaster_core.action_journal import (
            ActionJournal,
            JournalCorruptionError,
            JournalError,
        )
    except ImportError:
        test_case.fail(
            "the action journal must persist write-ahead events and enforce safe resume"
        )
    return ActionJournal, JournalCorruptionError, JournalError


def _prepare_and_dispatch(journal, action_id="action-1", digest="a" * 64):
    journal.prepare(
        action_id=action_id,
        intent_digest=digest,
        scope_revision=1,
        risk="R2",
        approval_ref="approval-{}".format(action_id),
    )
    journal.mark_dispatched(action_id, intent_digest=digest)


def _event(event_type, sequence, data, action_id="action-1"):
    return {
        "schemaVersion": "1.1",
        "sessionId": "session-1",
        "journalId": "journal-session-1",
        "sequence": sequence,
        "eventType": event_type,
        "actionId": action_id,
        "recordedAt": "2026-11-18T00:00:00Z",
        "data": data,
        "previousHash": None,
        "entryHash": "0" * 64,
    }


def _prepared_event(sequence=1, action_id="action-1", data=None):
    return _event(
        "action_prepared",
        sequence,
        data
        or {
            "intentDigest": "a" * 64,
            "scopeRevision": 1,
            "risk": "R0",
            "approvalRef": None,
        },
        action_id=action_id,
    )


def _write_hashed_events(path, events):
    previous_hash = None
    lines = []
    for event in events:
        event["previousHash"] = previous_hash
        unhashed = dict(event)
        del unhashed["entryHash"]
        canonical = json.dumps(
            unhashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        event["entryHash"] = hashlib.sha256(canonical).hexdigest()
        lines.append(
            json.dumps(event, sort_keys=True, separators=(",", ":"))
        )
        previous_hash = event["entryHash"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _matches_prefix(test_case, journal, sequence, head_hash):
    matcher = getattr(journal, "matches_prefix", None)
    test_case.assertTrue(
        callable(matcher),
        "ActionJournal must verify a checkpoint's sequence/hash prefix",
    )
    return matcher(sequence, head_hash)


class ActionJournalRecoveryTests(unittest.TestCase):
    def test_restart_blocks_replaying_an_action_with_unknown_result(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal_path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(journal_path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R2",
                approval_ref="approval-1",
            )
            journal.mark_dispatched("action-1", intent_digest="a" * 64)

            recovered = ActionJournal(journal_path, session_id="session-1")
            self.assertEqual(
                recovered.recovery_status("action-1"), "needs_reconciliation"
            )
            with self.assertRaises(JournalError):
                recovered.mark_dispatched("action-1", intent_digest="a" * 64)

    def test_prepared_intent_without_dispatch_marker_is_not_assumed_unexecuted(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            recovered = ActionJournal(path, session_id="session-1")
            self.assertEqual(
                recovered.recovery_status("action-1"), "needs_reconciliation"
            )
            with self.assertRaises(JournalError):
                recovered.mark_dispatched("action-1", intent_digest="a" * 64)

    def test_prepared_intent_is_persisted_before_dispatch_marker(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(first["eventType"], "action_prepared")
            self.assertEqual(first["sequence"], 1)

            journal.mark_dispatched("action-1", intent_digest="a" * 64)
            events = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [event["eventType"] for event in events],
                ["action_prepared", "action_dispatched"],
            )
            self.assertEqual([event["sequence"] for event in events], [1, 2])

    def test_r2_action_requires_action_approval_reference(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            with self.assertRaises(JournalError):
                journal.prepare(
                    action_id="action-1",
                    intent_digest="a" * 64,
                    scope_revision=1,
                    risk="R2",
                )

    def test_action_id_cannot_be_reused(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            with self.assertRaises(JournalError):
                journal.prepare(
                    action_id="action-1",
                    intent_digest="b" * 64,
                    scope_revision=1,
                    risk="R0",
                )

    def test_dispatch_requires_the_prepared_intent_digest(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            with self.assertRaises(JournalError):
                journal.mark_dispatched("action-1", intent_digest="b" * 64)

    def test_dispatch_rejects_malformed_digest_without_consuming_intent(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            with self.assertRaises(JournalError):
                journal.mark_dispatched("action-1", intent_digest="bad")
            journal.mark_dispatched("action-1", intent_digest="a" * 64)

    def test_unhashable_action_identifiers_are_rejected_as_journal_errors(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(
                Path(directory) / "journal.jsonl", session_id="session-1"
            )
            for operation in (
                lambda: journal.mark_dispatched([], intent_digest="a" * 64),
                lambda: journal.record_outcome([], "completed", "result-1"),
                lambda: journal.record_reconciliation_claim(
                    [],
                    outcome="completed",
                    observation_ref="state-1",
                    observer_ref="operator-1",
                    basis="authoritative-read-only",
                ),
                lambda: journal.recovery_status([]),
            ):
                with self.subTest(operation=operation):
                    with self.assertRaises(JournalError):
                        operation()

    def test_invalid_preparation_metadata_is_rejected_before_file_creation(self):
        ActionJournal, _, JournalError = _journal_types(self)
        invalid_inputs = (
            {"action_id": "  "},
            {"intent_digest": "not-a-digest"},
            {"scope_revision": True},
            {"scope_revision": 0},
            {"risk": "R3"},
            {"risk": "R9"},
            {"approval_ref": "  "},
        )

        for change in invalid_inputs:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "journal.jsonl"
                journal = ActionJournal(path, session_id="session-1")
                values = {
                    "action_id": "action-1",
                    "intent_digest": "a" * 64,
                    "scope_revision": 1,
                    "risk": "R0",
                    "approval_ref": None,
                }
                values.update(change)
                with self.assertRaises(JournalError):
                    journal.prepare(**values)
                self.assertFalse(path.exists())

    def test_r3_preparation_is_rejected(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            with self.assertRaises(JournalError):
                journal.prepare(
                    action_id="action-1",
                    intent_digest="a" * 64,
                    scope_revision=1,
                    risk="R3",
                )

    def test_invalid_outcomes_and_reconciliation_claims_are_rejected(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            _prepare_and_dispatch(journal)
            with self.assertRaises(JournalError):
                journal.record_outcome("action-1", "maybe")
            with self.assertRaises(JournalError):
                journal.record_outcome("action-1", "completed", result_ref=" ")
            with self.assertRaises(JournalError):
                journal.record_reconciliation_claim(
                    "action-1",
                    outcome="maybe",
                    observation_ref="state-1",
                    observer_ref="operator-1",
                    basis="authoritative-read-only",
                )
            with self.assertRaises(JournalError):
                journal.record_reconciliation_claim(
                    "action-1",
                    outcome="completed",
                    observation_ref="state-1",
                    observer_ref=" ",
                    basis="authoritative-read-only",
                )
            with self.assertRaises(JournalError):
                journal.record_reconciliation_claim(
                    "action-1",
                    outcome="completed",
                    observation_ref="state-1",
                    observer_ref="operator-1",
                    basis="agent-assertion",
                )

    def test_empty_journal_is_readable_and_unknown_action_has_no_recovery_state(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            path.touch()
            journal = ActionJournal(path, session_id="session-1")
            with self.assertRaises(JournalError):
                journal.recovery_status("missing-action")

    def test_malformed_journal_bytes_fail_closed(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        invalid_bytes = (b"\xff\n", b"\n", b"not-json\n")

        for raw in invalid_bytes:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "journal.jsonl"
                path.write_bytes(raw)
                with self.assertRaises(JournalCorruptionError):
                    ActionJournal(path, session_id="session-1")

    def test_malformed_event_envelope_fails_closed(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        mutations = (
            ("schema-version", lambda event: event.update(schemaVersion="2.0")),
            ("sequence", lambda event: event.update(sequence=0)),
            ("identity", lambda event: event.update(actionId=" ")),
            ("timestamp-empty", lambda event: event.update(recordedAt="")),
            ("timestamp-format", lambda event: event.update(recordedAt="not-a-time")),
            ("timestamp-naive", lambda event: event.update(recordedAt="2026-11-18T00:00:00")),
            ("timestamp-calendar", lambda event: event.update(recordedAt="2026-13-18T00:00:00Z")),
            ("data-type", lambda event: event.update(data=[])),
        )

        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "journal.jsonl"
                event = _prepared_event()
                mutate(event)
                _write_hashed_events(path, [event])
                with self.assertRaises(JournalCorruptionError):
                    ActionJournal(path, session_id="session-1")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            event = _prepared_event()
            _write_hashed_events(path, [event])
            event["previousHash"] = "f" * 64
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, session_id="session-1")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            event = _prepared_event()
            event["entryHash"] = "x" * 64
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, session_id="session-1")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            event = _prepared_event()
            event.pop("recordedAt")
            _write_hashed_events(path, [event])
            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, session_id="session-1")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            event = _prepared_event()
            _write_hashed_events(path, [event])
            event["data"]["risk"] = "R1"
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, session_id="session-1")

    def test_journal_session_identity_must_match(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            _write_hashed_events(path, [_prepared_event()])
            with self.assertRaises(JournalError):
                ActionJournal(path, session_id="other-session")

    def test_prepared_event_fields_and_risk_are_checked_after_hash_verification(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        invalid_data = (
            {"intentDigest": "a" * 64, "scopeRevision": 1, "risk": "R0"},
            {"intentDigest": "x", "scopeRevision": 1, "risk": "R0", "approvalRef": None},
            {"intentDigest": "a" * 64, "scopeRevision": True, "risk": "R0", "approvalRef": None},
            {"intentDigest": "a" * 64, "scopeRevision": 0, "risk": "R0", "approvalRef": None},
            {"intentDigest": "a" * 64, "scopeRevision": 1, "risk": "R3", "approvalRef": None},
            {"intentDigest": "a" * 64, "scopeRevision": 1, "risk": "R0", "approvalRef": " "},
            {"intentDigest": "a" * 64, "scopeRevision": 1, "risk": "R2", "approvalRef": None},
        )

        for data in invalid_data:
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "journal.jsonl"
                _write_hashed_events(path, [_prepared_event(data=data)])
                with self.assertRaises(JournalCorruptionError):
                    ActionJournal(path, session_id="session-1")

    def test_invalid_event_transitions_are_rejected_even_with_recalculated_hashes(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        valid_prepared = _prepared_event()

        def dispatched(data=None, sequence=2):
            return _event(
                "action_dispatched",
                sequence,
                data or {"intentDigest": "a" * 64},
            )

        def outcome(data, sequence=2):
            return _event("action_outcome", sequence, data)

        def reconciled(data, sequence=2):
            return _event("action_reconciliation_claimed", sequence, data)

        cases = (
            (
                "unprepared-dispatch",
                [_event("action_dispatched", 1, {"intentDigest": "a" * 64})],
            ),
            (
                "duplicate-prepared",
                [copy.deepcopy(valid_prepared), _prepared_event(sequence=2)],
            ),
            (
                "unknown-event",
                [copy.deepcopy(valid_prepared), _event("unknown", 2, {})],
            ),
            (
                "dispatch-fields",
                [
                    copy.deepcopy(valid_prepared),
                    dispatched({"intentDigest": "a" * 64, "extra": True}),
                ],
            ),
            (
                "dispatch-digest",
                [copy.deepcopy(valid_prepared), dispatched({"intentDigest": ["a"]})],
            ),
            (
                "dispatch-mismatch",
                [copy.deepcopy(valid_prepared), dispatched({"intentDigest": "b" * 64})],
            ),
            (
                "dispatch-twice",
                [copy.deepcopy(valid_prepared), dispatched(), dispatched(sequence=3)],
            ),
            (
                "outcome-before-dispatch",
                [
                    copy.deepcopy(valid_prepared),
                    outcome({"outcome": "completed", "resultRef": "result-1"}),
                ],
            ),
            (
                "outcome-fields",
                [
                    copy.deepcopy(valid_prepared),
                    dispatched(),
                    outcome(
                        {"outcome": "outcome_unknown", "resultRef": None, "extra": True},
                        sequence=3,
                    ),
                ],
            ),
            (
                "outcome-value",
                [
                    copy.deepcopy(valid_prepared),
                    dispatched(),
                    outcome({"outcome": "maybe", "resultRef": None}, sequence=3),
                ],
            ),
            (
                "outcome-ref",
                [
                    copy.deepcopy(valid_prepared),
                    dispatched(),
                    outcome(
                        {"outcome": "outcome_unknown", "resultRef": " "}, sequence=3
                    ),
                ],
            ),
            (
                "known-outcome-missing-ref",
                [
                    copy.deepcopy(valid_prepared),
                    dispatched(),
                    outcome({"outcome": "completed", "resultRef": None}, sequence=3),
                ],
            ),
            (
                "reconcile-fields",
                [
                    copy.deepcopy(valid_prepared),
                    reconciled({"outcome": "not_executed"}),
                ],
            ),
            (
                "reconcile-value",
                [
                    copy.deepcopy(valid_prepared),
                    reconciled(
                        {
                            "outcome": "maybe",
                            "observationRef": "state-1",
                            "observerRef": "operator-1",
                            "basis": "authoritative-read-only",
                        }
                    ),
                ],
            ),
            (
                "reconcile-observer",
                [
                    copy.deepcopy(valid_prepared),
                    reconciled(
                        {
                            "outcome": "not_executed",
                            "observationRef": "state-1",
                            "observerRef": " ",
                            "basis": "authoritative-read-only",
                        }
                    ),
                ],
            ),
            (
                "reconcile-basis",
                [
                    copy.deepcopy(valid_prepared),
                    reconciled(
                        {
                            "outcome": "not_executed",
                            "observationRef": "state-1",
                            "observerRef": "operator-1",
                            "basis": "agent-assertion",
                        }
                    ),
                ],
            ),
            (
                "terminal-reconcile",
                [
                    copy.deepcopy(valid_prepared),
                    dispatched(),
                    outcome({"outcome": "completed", "resultRef": "result-1"}, sequence=3),
                    reconciled(
                        {
                            "outcome": "not_executed",
                            "observationRef": "state-1",
                            "observerRef": "operator-1",
                            "basis": "authoritative-read-only",
                        },
                        sequence=4,
                    ),
                ],
            ),
        )

        for label, events in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "journal.jsonl"
                _write_hashed_events(path, events)
                with self.assertRaises(JournalCorruptionError):
                    ActionJournal(path, session_id="session-1")

    def test_zero_progress_write_is_reported_as_an_io_error(self):
        from unittest.mock import patch

        from bugmaster_core.action_journal import _write_all

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bytes"
            fd = os.open(str(path), os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                with patch("bugmaster_core.action_journal.os.write", return_value=0):
                    with self.assertRaises(OSError):
                        _write_all(fd, b"x")
            finally:
                os.close(fd)

    def test_unknown_result_requires_read_only_reconciliation_and_new_action(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            _prepare_and_dispatch(journal)
            journal.record_outcome("action-1", "outcome_unknown")

            recovered = ActionJournal(path, session_id="session-1")
            self.assertEqual(
                recovered.recovery_status("action-1"), "needs_reconciliation"
            )
            with self.assertRaises(JournalError):
                recovered.record_reconciliation_claim(
                    "action-1",
                    outcome="not_executed",
                    observation_ref="",
                    observer_ref="operator-1",
                    basis="authoritative-read-only",
                )

            record_claim = getattr(recovered, "record_reconciliation_claim", None)
            self.assertTrue(callable(record_claim), "unverified reconciliation must be recorded as a claim")
            record_claim(
                "action-1",
                outcome="not_executed",
                observation_ref="read-only-order-state-1",
                observer_ref="operator-1",
                basis="authoritative-read-only",
            )
            self.assertEqual(
                recovered.recovery_status("action-1"), "needs_reconciliation"
            )
            with self.assertRaises(JournalError):
                recovered.mark_dispatched("action-1", intent_digest="a" * 64)

            recovered.prepare(
                action_id="action-2",
                intent_digest="b" * 64,
                scope_revision=1,
                risk="R2",
                approval_ref="approval-action-2",
            )
            with self.assertRaises(JournalError):
                recovered.mark_dispatched("action-2", intent_digest="b" * 64)

    def test_completed_action_has_terminal_recovery_state(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            _prepare_and_dispatch(journal)
            journal.record_outcome(
                "action-1", "completed", result_ref="tool-result-1"
            )
            recovered = ActionJournal(path, session_id="session-1")
            self.assertEqual(recovered.recovery_status("action-1"), "terminal")

    def test_failed_read_only_action_is_terminal_but_claim_stays_blocked(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            journal.mark_dispatched("action-1", intent_digest="a" * 64)
            journal.record_outcome("action-1", "failed", result_ref="tool-error-1")
            journal.prepare(
                action_id="action-2",
                intent_digest="b" * 64,
                scope_revision=1,
                risk="R0",
            )
            journal.mark_dispatched("action-2", intent_digest="b" * 64)
            journal.record_reconciliation_claim(
                "action-2",
                outcome="completed",
                observation_ref="read-only-state-2",
                observer_ref="operator-1",
                basis="authoritative-read-only",
            )

            recovered = ActionJournal(path, session_id="session-1")
            self.assertEqual(recovered.recovery_status("action-1"), "terminal")
            self.assertEqual(
                recovered.recovery_status("action-2"), "needs_reconciliation"
            )

    def test_failed_mutating_action_requires_reconciliation_before_next_dispatch(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            _prepare_and_dispatch(journal)
            journal.record_outcome("action-1", "failed", result_ref="http-500-1")

            recovered = ActionJournal(path, session_id="session-1")
            self.assertEqual(
                recovered.recovery_status("action-1"), "needs_reconciliation"
            )
            recovered.prepare(
                action_id="action-2",
                intent_digest="b" * 64,
                scope_revision=1,
                risk="R2",
                approval_ref="approval-action-2",
            )
            with self.assertRaises(JournalError):
                recovered.mark_dispatched("action-2", intent_digest="b" * 64)

    def test_restarted_session_cannot_turn_a_missing_result_into_a_completion_claim(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            _prepare_and_dispatch(journal)
            recovered = ActionJournal(path, session_id="session-1")

            with self.assertRaises(JournalError):
                recovered.record_outcome(
                    "action-1", "completed", result_ref="unverified-claim"
                )
            self.assertEqual(
                recovered.recovery_status("action-1"), "needs_reconciliation"
            )

    def test_modified_event_is_rejected_by_hash_chain(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R2",
                approval_ref="approval-action-1",
            )
            event = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(event["entryHash"]), 64)
            event["data"]["approvalRef"] = "approval-replaced"
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, session_id="session-1")

    def test_truncated_final_event_fails_closed_without_rewriting_file(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            with path.open("ab") as stream:
                stream.write(b'{"partial":')
            before = path.read_bytes()

            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, session_id="session-1")
            self.assertEqual(path.read_bytes(), before)

    def test_completed_result_requires_a_tool_result_reference(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            _prepare_and_dispatch(journal)
            with self.assertRaises(JournalError):
                journal.record_outcome("action-1", "completed")

    def test_journal_file_is_private_on_posix(self):
        ActionJournal, _, _ = _journal_types(self)
        if os.name != "posix":
            self.skipTest("POSIX file mode is not available on this host")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_session_mismatch_is_rejected(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, session_id="session-1")
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )
            with self.assertRaises(JournalError):
                ActionJournal(path, session_id="session-2")

    def test_empty_session_id_is_rejected(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(JournalError):
                ActionJournal(Path(directory) / "journal.jsonl", " ")

    def test_checkpoint_prefix_matches_a_persisted_hash_chain_head(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            first = journal.prepare("action-1", "a" * 64, 1, "R0")
            journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertTrue(
                _matches_prefix(self, journal, 1, first["entryHash"])
            )

    def test_checkpoint_prefix_accepts_a_valid_empty_anchor(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            self.assertTrue(_matches_prefix(self, journal, 0, None))
            journal.prepare("action-1", "a" * 64, 1, "R0")
            self.assertTrue(_matches_prefix(self, journal, 0, None))

    def test_checkpoint_prefix_rejects_a_mismatched_anchor(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            first = journal.prepare("action-1", "a" * 64, 1, "R0")

            for sequence, head_hash in (
                (1, "b" * 64),
                (2, first["entryHash"]),
                (1, None),
                (1, "not-a-sha256"),
                (0, "a" * 64),
            ):
                with self.subTest(sequence=sequence, head_hash=head_hash):
                    self.assertFalse(
                        _matches_prefix(self, journal, sequence, head_hash)
                    )

    def test_checkpoint_prefix_rejects_malformed_sequences(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            for sequence in (True, -1, 1.5, "1"):
                with self.subTest(sequence=sequence):
                    with self.assertRaises(JournalError):
                        _matches_prefix(self, journal, sequence, None)

    def test_checkpoint_prefix_fails_closed_when_the_journal_is_corrupt(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            first = journal.prepare("action-1", "a" * 64, 1, "R0")
            with path.open("ab") as stream:
                stream.write(b"{broken-json}\n")

            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 1, first["entryHash"])

    def test_journal_events_bind_the_configured_journal_id_and_schema_version(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            try:
                journal = ActionJournal(
                    Path(directory) / "journal.jsonl",
                    session_id="session-1",
                    journal_id="journal-primary",
                )
            except TypeError as error:
                self.fail("ActionJournal must accept a stable journal ID: {}".format(error))
            event = journal.prepare("action-1", "a" * 64, 1, "R0")

            self.assertEqual(event.get("journalId"), "journal-primary")
            self.assertEqual(event.get("schemaVersion"), "1.1")

    def test_journal_identity_cannot_be_changed_after_construction(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            try:
                journal = ActionJournal(
                    Path(directory) / "journal.jsonl",
                    session_id="session-1",
                    journal_id="journal-primary",
                )
            except TypeError as error:
                self.fail("ActionJournal must accept a stable journal ID: {}".format(error))

            with self.assertRaises(AttributeError):
                journal.journal_id = "journal-secondary"
            self.assertEqual(journal.journal_id, "journal-primary")

    def test_journal_rejects_events_bound_to_a_different_journal_id(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            try:
                journal = ActionJournal(
                    path,
                    session_id="session-1",
                    journal_id="journal-primary",
                )
            except TypeError as error:
                self.fail("ActionJournal must accept a stable journal ID: {}".format(error))
            journal.prepare("action-1", "a" * 64, 1, "R0")

            try:
                ActionJournal(
                    path,
                    session_id="session-1",
                    journal_id="journal-secondary",
                )
            except JournalCorruptionError:
                pass
            except TypeError as error:
                self.fail("ActionJournal must validate the persisted journal ID: {}".format(error))
            else:
                self.fail("a different Journal ID must not load this event log")

    def test_journal_id_may_contain_unicode_line_separator_characters(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal_id = "journal\u2028\u0085identity"
            journal = ActionJournal(
                path, session_id="session-1", journal_id=journal_id
            )
            first = journal.prepare("action-1", "a" * 64, 1, "R0")

            reopened = ActionJournal(
                path, session_id="session-1", journal_id=journal_id
            )

            self.assertEqual(
                reopened.recovery_status("action-1"), "needs_reconciliation"
            )
            self.assertTrue(reopened.matches_prefix(1, first["entryHash"]))

    def test_read_rejects_a_fifo_without_blocking(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            os.mkfifo(path)
            real_open = os.open

            def open_nonblocking_fifo(target, flags, *args, **kwargs):
                if Path(target) == path:
                    self.assertTrue(flags & os.O_NONBLOCK)
                return real_open(target, flags, *args, **kwargs)

            with patch("bugmaster_core.action_journal.os.open", side_effect=open_nonblocking_fifo):
                with self.assertRaises(JournalCorruptionError):
                    ActionJournal(path, "session-1")

    def test_append_rejects_a_fifo_before_changing_its_mode_or_writing(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            os.mkfifo(path)
            fifo_mode = stat.S_IMODE(path.stat().st_mode)
            real_open = os.open

            def open_nonblocking_fifo(target, flags, *args, **kwargs):
                if Path(target) == path:
                    self.assertTrue(flags & os.O_NONBLOCK)
                return real_open(target, flags, *args, **kwargs)

            with patch("bugmaster_core.action_journal.os.open", side_effect=open_nonblocking_fifo):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-1", "a" * 64, 1, "R0")
            self.assertTrue(stat.S_ISFIFO(path.lstat().st_mode))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), fifo_mode)

    def test_journal_rejects_an_empty_explicit_journal_id(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            try:
                ActionJournal(
                    Path(directory) / "journal.jsonl",
                    session_id="session-1",
                    journal_id=" ",
                )
            except JournalError:
                pass
            except TypeError as error:
                self.fail("ActionJournal must validate an explicit Journal ID: {}".format(error))
            else:
                self.fail("an empty Journal ID must be rejected")


if __name__ == "__main__":
    unittest.main()
