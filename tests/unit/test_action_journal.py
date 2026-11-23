import hashlib
import tempfile
import unittest
import copy
import json
import os
import stat
import subprocess
import sys
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
    def test_recorded_outcome_returns_validated_event_binding(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(
                path, session_id="session-1", journal_id="journal-session-1"
            )
            _prepare_and_dispatch(journal)
            event = journal.record_outcome(
                "action-1", "completed", "artifacts/result.json"
            )

            recovered = ActionJournal(
                path,
                session_id="session-1",
                journal_id="journal-session-1",
                require_existing=True,
            )
            binding = recovered.recorded_outcome("action-1")

        self.assertEqual(binding["sessionId"], "session-1")
        self.assertEqual(binding["journalId"], "journal-session-1")
        self.assertEqual(binding["actionId"], "action-1")
        self.assertEqual(binding["outcome"], "completed")
        self.assertEqual(binding["resultRef"], "artifacts/result.json")
        self.assertEqual(binding["sequence"], event["sequence"])
        self.assertEqual(binding["entryHash"], event["entryHash"])

    def test_recorded_outcome_rejects_actions_without_outcome(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(
                Path(directory) / "journal.jsonl", session_id="session-1"
            )
            journal.prepare(
                action_id="action-1",
                intent_digest="a" * 64,
                scope_revision=1,
                risk="R0",
            )

            with self.assertRaises(JournalError):
                journal.recorded_outcome("action-1")

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
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
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

    def test_checkpoint_prefix_accepts_integral_json_number_values(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            first = journal.prepare("action-1", "a" * 64, 1, "R0")

            self.assertTrue(
                _matches_prefix(self, journal, 1.0, first["entryHash"])
            )
            self.assertTrue(_matches_prefix(self, journal, 0.0, None))

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

    def test_checkpoint_prefix_rejects_duplicate_json_keys_in_later_events(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            events = [_prepared_event(), _prepared_event(sequence=2, action_id="action-2")]
            _write_hashed_events(path, events)
            journal = ActionJournal(path, "session-1")
            first_hash = events[0]["entryHash"]

            lines = path.read_text(encoding="utf-8").splitlines()
            lines[1] = lines[1].replace(
                '"eventType":"action_prepared"',
                '"eventType":"unknown","eventType":"action_prepared"',
                1,
            )
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 1, first_hash)

    def test_journal_round_trips_unicode_line_separators(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            event = journal.prepare(
                "action-1",
                "a" * 64,
                1,
                "R2",
                approval_ref="approval\u2028reference\u2029end",
            )

            reloaded = ActionJournal(path, "session-1")
            self.assertTrue(
                _matches_prefix(self, reloaded, 1, event["entryHash"])
            )

    def test_missing_journal_matches_only_the_empty_prefix(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-created" / "journal.jsonl"
            journal = ActionJournal(path, "session-1")

            self.assertTrue(_matches_prefix(self, journal, 0, None))
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            self.assertTrue(_matches_prefix(self, journal, 1, event["entryHash"]))

    def test_dangling_journal_symlink_is_not_treated_as_missing(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            path.symlink_to(Path(directory) / "missing-target.jsonl")

            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, "session-1")

    def test_symlinked_journal_is_rejected(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.jsonl"
            ActionJournal(target, "session-1").prepare(
                "action-1", "a" * 64, 1, "R0"
            )
            link = Path(directory) / "journal.jsonl"
            link.symlink_to(target)

            with self.assertRaises(JournalCorruptionError):
                ActionJournal(link, "session-1")

    def test_non_regular_journal_is_rejected(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal-directory"
            path.mkdir()

            with self.assertRaises(JournalCorruptionError):
                ActionJournal(path, "session-1")

    def test_fifo_journal_is_rejected_without_blocking(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO journal checks require POSIX")
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.fifo"
            os.mkfifo(path)
            program = (
                "from bugmaster_core.action_journal import ActionJournal; "
                "ActionJournal({!r}, 'session-1')"
            ).format(str(path))
            try:
                result = subprocess.run(
                    [sys.executable, "-c", program],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
            except subprocess.TimeoutExpired:
                self.fail("opening a FIFO journal must fail without blocking")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("JournalCorruptionError", result.stderr)

    def test_constructor_rejects_invalid_parent_paths(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_parent = root / "parent-file"
            file_parent.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(JournalError):
                ActionJournal(file_parent / "journal.jsonl", "session-1")

            directory_parent = root / "directory"
            directory_parent.mkdir()
            resolved_file = root / "resolved-file"
            resolved_file.write_text("not a directory", encoding="utf-8")
            real_resolve = Path.resolve

            def resolve_to_file(path, *args, **kwargs):
                if path == directory_parent:
                    return resolved_file
                return real_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", new=resolve_to_file):
                with self.assertRaises(JournalError):
                    ActionJournal(directory_parent / "journal.jsonl", "session-1")

    def test_constructor_wraps_parent_inspection_and_resolution_errors(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "journals"
            parent.mkdir()
            path = parent / "journal.jsonl"
            real_stat = Path.stat

            def fail_parent_stat(candidate, *args, **kwargs):
                if candidate == parent:
                    raise PermissionError("parent metadata is not readable")
                return real_stat(candidate, *args, **kwargs)

            with patch.object(Path, "stat", new=fail_parent_stat):
                with self.assertRaises(JournalError):
                    ActionJournal(path, "session-1")

            real_resolve = Path.resolve

            def fail_parent_resolve(candidate, *args, **kwargs):
                if candidate == parent:
                    raise PermissionError("parent cannot be resolved")
                return real_resolve(candidate, *args, **kwargs)

            with patch.object(Path, "resolve", new=fail_parent_resolve):
                with self.assertRaises(JournalError):
                    ActionJournal(path, "session-1")

    def test_constructor_fails_if_no_parent_component_exists(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with patch.object(Path, "stat", side_effect=FileNotFoundError):
            with self.assertRaises(JournalError):
                ActionJournal("/missing/journal.jsonl", "session-1")

    def test_require_existing_rejects_a_missing_parent_directory(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(JournalCorruptionError):
                ActionJournal(
                    Path(directory) / "missing" / "journal.jsonl",
                    "session-1",
                    require_existing=True,
                )

    def test_parent_open_and_directory_identity_failures_are_corruption(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            real_open = action_journal.os.open

            def fail_anchor_open(file, flags, *args, **kwargs):
                if file == "/":
                    raise PermissionError("root cannot be opened")
                return real_open(file, flags, *args, **kwargs)

            with patch.object(action_journal.os, "open", new=fail_anchor_open):
                with self.assertRaises(JournalCorruptionError):
                    _matches_prefix(self, journal, 0, None)

            journal._anchor_identity = (0, 0)
            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 0, None)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            journal._directory_identities[
                tuple(journal._relative_parent_parts)
            ] = (0, 0)
            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 0, None)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            journal._parent_identity = (0, 0)
            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 0, None)

    def test_parent_open_permission_error_is_corruption(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournal(Path(directory) / "journal.jsonl", "session-1")
            real_open = action_journal.os.open
            component = journal._relative_parent_parts[-1]

            def fail_parent_component(file, flags, *args, **kwargs):
                if file == component and kwargs.get("dir_fd") is not None:
                    raise PermissionError("parent cannot be opened")
                return real_open(file, flags, *args, **kwargs)

            with patch.object(
                action_journal.os, "open", new=fail_parent_component
            ):
                with self.assertRaises(JournalCorruptionError):
                    _matches_prefix(self, journal, 0, None)

    def test_path_verification_rejects_a_different_parent_descriptor(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            parent_fd = journal._open_parent()
            file_fd = os.open(path.name, os.O_RDONLY, dir_fd=parent_fd)
            other = root / "other"
            other.mkdir()
            other_fd = os.open(other, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with patch.object(journal, "_open_parent", return_value=os.dup(other_fd)):
                    with self.assertRaises(JournalCorruptionError):
                        journal._verify_journal_path(file_fd, parent_fd)
            finally:
                os.close(file_fd)
                os.close(parent_fd)
                os.close(other_fd)

    def test_parent_creation_handles_races_and_fails_closed_on_errors(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            real_mkdir = action_journal.os.mkdir
            raced = []

            def create_before_mkdir(file, mode=0o777, *, dir_fd=None):
                if file == "nested" and not raced:
                    real_mkdir(file, mode, dir_fd=dir_fd)
                    raced.append(True)
                    raise FileExistsError("another writer created the directory")
                return real_mkdir(file, mode, dir_fd=dir_fd)

            with patch.object(action_journal.os, "mkdir", new=create_before_mkdir):
                journal.prepare("action-1", "a" * 64, 1, "R0")
            self.assertTrue(path.is_file())

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            with patch.object(
                action_journal.os, "mkdir", side_effect=PermissionError("denied")
            ):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-1", "a" * 64, 1, "R0")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            real_open = action_journal.os.open
            nested_open_count = []

            def fail_open_after_create(file, flags, *args, **kwargs):
                if file == "nested" and kwargs.get("dir_fd") is not None:
                    nested_open_count.append(True)
                    if len(nested_open_count) == 2:
                        raise PermissionError("created parent cannot be opened")
                return real_open(file, flags, *args, **kwargs)

            with patch.object(action_journal.os, "open", new=fail_open_after_create):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-1", "a" * 64, 1, "R0")
            self.assertEqual(len(nested_open_count), 2)

    def test_malformed_journal_json_errors_are_wrapped_as_corruption(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        cases = (
            (
                "deeply-nested",
                lambda line: line.replace(
                    '"data":{',
                    '"data":{"nested":' + "[" * 10000 + "0" + "]" * 10000 + ",",
                    1,
                ),
                (ValueError, RecursionError),
            ),
            (
                "long-integer",
                lambda line: line.replace(
                    '"sequence":1', '"sequence":' + "9" * 5000, 1
                ),
                None,
            ),
        )

        for label, mutate, cause_types in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "journal.jsonl"
                line = json.dumps(_prepared_event(), separators=(",", ":"))
                path.write_text(mutate(line) + "\n", encoding="utf-8")

                with self.assertRaises(JournalCorruptionError) as raised:
                    ActionJournal(path, "session-1")
                if cause_types is not None:
                    self.assertIsInstance(raised.exception.__cause__, cause_types)

    def test_unencodable_journal_text_is_wrapped_as_corruption(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            event = _prepared_event()
            event["actionId"] = "\ud800"
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            with self.assertRaises(JournalCorruptionError) as raised:
                ActionJournal(path, "session-1")
            self.assertIsInstance(raised.exception.__cause__, UnicodeEncodeError)

    def test_parent_directory_disappearance_does_not_look_like_an_empty_journal(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "nested" / "journals"
            path = parent / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            path.unlink()
            parent.rmdir()
            parent.parent.rmdir()

            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 0, None)

    def test_parent_symlink_retarget_does_not_redirect_journal_reads_or_appends(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_root = root / "first"
            second_root = root / "second"
            first_parent = first_root / "journals"
            second_parent = second_root / "journals"
            first_parent.mkdir(parents=True)
            second_parent.mkdir(parents=True)
            first_path = first_parent / "journal.jsonl"
            second_path = second_parent / "journal.jsonl"
            first_event = ActionJournal(first_path, "session-1").prepare(
                "action-a", "a" * 64, 1, "R0"
            )
            ActionJournal(second_path, "session-1").prepare(
                "action-b", "b" * 64, 1, "R0"
            )
            alias = root / "current"
            alias.symlink_to(first_root, target_is_directory=True)
            journal = ActionJournal(alias / "journals" / "journal.jsonl", "session-1")

            alias.unlink()
            alias.symlink_to(second_root, target_is_directory=True)

            self.assertTrue(
                _matches_prefix(self, journal, 1, first_event["entryHash"])
            )
            journal.prepare("action-c", "c" * 64, 1, "R0")
            self.assertEqual(len(first_path.read_text(encoding="utf-8").splitlines()), 2)
            self.assertEqual(len(second_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_missing_parent_is_created_under_the_ancestor_captured_at_init(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_root = root / "first"
            second_root = root / "second"
            first_root.mkdir()
            second_root.mkdir()
            alias = root / "current"
            alias.symlink_to(first_root, target_is_directory=True)
            journal = ActionJournal(
                alias / "journals" / "journal.jsonl", "session-1"
            )

            alias.unlink()
            alias.symlink_to(second_root, target_is_directory=True)
            journal.prepare("action-1", "a" * 64, 1, "R0")

            self.assertTrue((first_root / "journals" / "journal.jsonl").is_file())
            self.assertFalse((second_root / "journals").exists())

    def test_new_parent_directory_entries_are_synced(self):
        ActionJournal, _, _ = _journal_types(self)
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "level-one" / "level-two" / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            real_fsync = action_journal.os.fsync
            directory_syncs = []

            def record_directory_sync(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode):
                    info = os.fstat(fd)
                    directory_syncs.append((info.st_dev, info.st_ino))
                return real_fsync(fd)

            with patch.object(
                action_journal.os, "fsync", side_effect=record_directory_sync
            ):
                journal.prepare("action-1", "a" * 64, 1, "R0")

            required_directories = {
                (path.parents[2].stat().st_dev, path.parents[2].stat().st_ino),
                (path.parents[1].stat().st_dev, path.parents[1].stat().st_ino),
                (path.parent.stat().st_dev, path.parent.stat().st_ino),
            }
            self.assertTrue(required_directories.issubset(set(directory_syncs)))

    def test_parent_directory_sync_failure_is_retried_before_another_append(self):
        ActionJournal, _, _ = _journal_types(self)
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            directory_syncs = []
            real_fsync = action_journal.os.fsync

            def fail_directory_sync(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode):
                    directory_syncs.append(fd)
                    raise OSError("directory entry sync failed")
                return real_fsync(fd)

            with patch.object(
                action_journal.os, "fsync", side_effect=fail_directory_sync
            ):
                with self.assertRaises(OSError):
                    journal.prepare("action-1", "a" * 64, 1, "R0")
                with self.assertRaises(OSError):
                    journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertEqual(len(directory_syncs), 2)
            self.assertFalse(path.exists())

    def test_new_instance_resyncs_parent_after_directory_creation_sync_failure(self):
        ActionJournal, _, _ = _journal_types(self)
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journals" / "journal.jsonl"
            root_stat = root.stat()
            root_identity = (root_stat.st_dev, root_stat.st_ino)
            first = ActionJournal(path, "session-1")
            real_fsync = action_journal.os.fsync
            failed = []
            synced = []

            def fail_root_once(fd):
                current = os.fstat(fd)
                identity = (current.st_dev, current.st_ino)
                if identity == root_identity and not failed:
                    failed.append(identity)
                    raise OSError("parent directory sync failed")
                if stat.S_ISDIR(current.st_mode):
                    synced.append(identity)
                return real_fsync(fd)

            with patch.object(action_journal.os, "fsync", side_effect=fail_root_once):
                with self.assertRaises(OSError):
                    first.prepare("action-1", "a" * 64, 1, "R0")
                second = ActionJournal(path, "session-1")
                second.prepare("action-1", "a" * 64, 1, "R0")

            self.assertEqual(failed, [root_identity])
            self.assertIn(root_identity, synced)

    def test_missing_journal_after_observation_fails_without_recreation(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            path.unlink()

            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 0, None)
            with self.assertRaises(JournalCorruptionError):
                journal.prepare("action-2", "b" * 64, 1, "R0")
            self.assertFalse(path.exists())

    def test_replaced_journal_file_fails_closed(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            original = Path(directory) / "journal.original"
            path.rename(original)
            path.write_bytes(b"")

            with self.assertRaises(JournalCorruptionError):
                _matches_prefix(self, journal, 0, None)

    def test_hardlinked_journal_is_rejected_before_changing_target(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            target = root / "other-file.jsonl"
            target.write_text("not a Journal\n", encoding="utf-8")
            os.chmod(target, 0o644)
            os.link(target, path)

            with self.assertRaises(JournalCorruptionError):
                journal.prepare("action-1", "a" * 64, 1, "R0")

            self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            self.assertEqual(target.read_text(encoding="utf-8"), "not a Journal\n")

    def test_read_rejects_journal_replaced_while_waiting_for_lock(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            original = root / "journal.original"
            real_flock = action_journal.fcntl.flock
            replaced = []

            def replace_before_lock(fd, operation):
                if operation == fcntl.LOCK_EX and not replaced:
                    path.rename(original)
                    path.write_text("", encoding="utf-8")
                    replaced.append(True)
                return real_flock(fd, operation)

            with patch.object(
                action_journal.fcntl, "flock", side_effect=replace_before_lock
            ):
                with self.assertRaises(JournalCorruptionError):
                    _matches_prefix(self, journal, 1, event["entryHash"])

            self.assertEqual(path.read_text(encoding="utf-8"), "")
            self.assertEqual(len(original.read_text(encoding="utf-8").splitlines()), 1)

    def test_append_rejects_journal_replaced_while_waiting_for_lock(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            original = root / "journal.original"
            real_flock = action_journal.fcntl.flock
            replaced = []

            def replace_before_lock(fd, operation):
                if operation == fcntl.LOCK_EX and not replaced:
                    path.rename(original)
                    path.write_text("", encoding="utf-8")
                    replaced.append(True)
                return real_flock(fd, operation)

            with patch.object(
                action_journal.fcntl, "flock", side_effect=replace_before_lock
            ):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertEqual(path.read_text(encoding="utf-8"), "")
            self.assertEqual(len(original.read_text(encoding="utf-8").splitlines()), 1)

    def test_hardlink_added_while_waiting_for_append_lock_is_rejected(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            alias = root / "journal-alias.jsonl"
            original_contents = path.read_text(encoding="utf-8")
            real_flock = action_journal.fcntl.flock
            linked = []

            def link_before_lock(fd, operation):
                if operation == fcntl.LOCK_EX and not linked:
                    os.link(path, alias)
                    linked.append(True)
                return real_flock(fd, operation)

            with patch.object(
                action_journal.fcntl, "flock", side_effect=link_before_lock
            ):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertEqual(path.read_text(encoding="utf-8"), original_contents)
            self.assertEqual(alias.read_text(encoding="utf-8"), original_contents)

    def test_read_rejects_journal_removed_while_waiting_for_lock(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            moved = root / "journal.moved"
            real_flock = action_journal.fcntl.flock
            removed = []

            def remove_before_lock(fd, operation):
                if operation == fcntl.LOCK_EX and not removed:
                    path.rename(moved)
                    removed.append(True)
                return real_flock(fd, operation)

            with patch.object(
                action_journal.fcntl, "flock", side_effect=remove_before_lock
            ):
                with self.assertRaises(JournalCorruptionError):
                    _matches_prefix(self, journal, 1, event["entryHash"])

            self.assertEqual(len(moved.read_text(encoding="utf-8").splitlines()), 1)

    def test_read_rejects_symlink_inserted_while_waiting_for_lock(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            original = root / "journal.original"
            real_flock = action_journal.fcntl.flock
            linked = []

            def insert_symlink_before_lock(fd, operation):
                if operation == fcntl.LOCK_EX and not linked:
                    path.rename(original)
                    path.symlink_to(original)
                    linked.append(True)
                return real_flock(fd, operation)

            with patch.object(
                action_journal.fcntl, "flock", side_effect=insert_symlink_before_lock
            ):
                with self.assertRaises(JournalCorruptionError):
                    _matches_prefix(self, journal, 1, event["entryHash"])

            self.assertTrue(path.is_symlink())

    def test_read_rejects_parent_replaced_while_waiting_for_lock(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "journal-dir"
            parent.mkdir()
            path = parent / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            moved = root / "journal-dir.moved"
            real_flock = action_journal.fcntl.flock
            replaced = []

            def replace_parent_before_lock(fd, operation):
                if operation == fcntl.LOCK_EX and not replaced:
                    parent.rename(moved)
                    parent.mkdir()
                    replaced.append(True)
                return real_flock(fd, operation)

            with patch.object(
                action_journal.fcntl, "flock", side_effect=replace_parent_before_lock
            ):
                with self.assertRaises(JournalCorruptionError):
                    _matches_prefix(self, journal, 1, event["entryHash"])

            self.assertFalse(path.exists())
            self.assertEqual(
                len((moved / "journal.jsonl").read_text(encoding="utf-8").splitlines()),
                1,
            )

    def test_append_rejects_parent_replaced_while_waiting_for_lock(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "journal-dir"
            parent.mkdir()
            path = parent / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            moved = root / "journal-dir.moved"
            real_flock = action_journal.fcntl.flock
            replaced = []

            def replace_parent_before_lock(fd, operation):
                if operation == fcntl.LOCK_EX and not replaced:
                    parent.rename(moved)
                    parent.mkdir()
                    replaced.append(True)
                return real_flock(fd, operation)

            with patch.object(
                action_journal.fcntl, "flock", side_effect=replace_parent_before_lock
            ):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertFalse(path.exists())
            self.assertEqual(
                len((moved / "journal.jsonl").read_text(encoding="utf-8").splitlines()),
                1,
            )

    def test_append_handles_existing_file_and_wraps_open_errors(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            path.write_text("", encoding="utf-8")
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            self.assertEqual(event["sequence"], 1)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            real_open = action_journal.os.open

            def fail_create_open(file, flags, *args, **kwargs):
                if (
                    file == path.name
                    and flags & os.O_CREAT
                    and flags & os.O_EXCL
                ):
                    raise PermissionError("journal cannot be created")
                return real_open(file, flags, *args, **kwargs)

            with patch.object(action_journal.os, "open", new=fail_create_open):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-1", "a" * 64, 1, "R0")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            real_open = action_journal.os.open

            def fail_existing_open(file, flags, *args, **kwargs):
                if file == path.name and kwargs.get("dir_fd") is not None:
                    raise PermissionError("journal cannot be reopened")
                return real_open(file, flags, *args, **kwargs)

            with patch.object(action_journal.os, "open", new=fail_existing_open):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-2", "b" * 64, 1, "R0")

    def test_read_descriptor_closes_when_unlock_fails(self):
        ActionJournal, _, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            real_open = action_journal.os.open
            real_close = action_journal.os.close
            real_flock = action_journal.fcntl.flock
            file_fds = []
            closed_fds = []

            def track_open(file, flags, *args, **kwargs):
                fd = real_open(file, flags, *args, **kwargs)
                if kwargs.get("dir_fd") is not None:
                    file_fds.append(fd)
                return fd

            def track_close(fd):
                closed_fds.append(fd)
                return real_close(fd)

            def fail_unlock(fd, operation):
                if operation == fcntl.LOCK_UN:
                    raise OSError("unlock failed")
                return real_flock(fd, operation)

            with patch.object(action_journal.os, "open", side_effect=track_open):
                with patch.object(action_journal.os, "close", side_effect=track_close):
                    with patch.object(
                        action_journal.fcntl, "flock", side_effect=fail_unlock
                    ):
                        with self.assertRaises(OSError):
                            journal._load_current()

            self.assertTrue(file_fds)
            self.assertIn(file_fds[-1], closed_fds)

    def test_append_descriptor_closes_when_unlock_fails(self):
        ActionJournal, _, _ = _journal_types(self)
        import fcntl
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            journal.prepare("action-1", "a" * 64, 1, "R0")
            real_open = action_journal.os.open
            real_close = action_journal.os.close
            real_flock = action_journal.fcntl.flock
            file_fds = []
            closed_fds = []

            def track_open(file, flags, *args, **kwargs):
                fd = real_open(file, flags, *args, **kwargs)
                if kwargs.get("dir_fd") is not None:
                    file_fds.append(fd)
                return fd

            def track_close(fd):
                closed_fds.append(fd)
                return real_close(fd)

            def fail_unlock(fd, operation):
                if operation == fcntl.LOCK_UN:
                    raise OSError("unlock failed")
                return real_flock(fd, operation)

            with patch.object(action_journal.os, "open", side_effect=track_open):
                with patch.object(action_journal.os, "close", side_effect=track_close):
                    with patch.object(
                        action_journal.fcntl, "flock", side_effect=fail_unlock
                    ):
                        with self.assertRaises(OSError):
                            journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertTrue(file_fds)
            self.assertIn(file_fds[-1], closed_fds)

    def test_append_rejects_a_journal_symlink_before_changing_its_target(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "journal.jsonl"
            journal = ActionJournal(path, "session-1")
            target = root / "other-file.jsonl"
            target.write_text("not a Journal\n", encoding="utf-8")
            os.chmod(target, 0o644)
            path.symlink_to(target)

            with self.assertRaises(JournalCorruptionError):
                journal.prepare("action-1", "a" * 64, 1, "R0")

            self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            self.assertEqual(target.read_text(encoding="utf-8"), "not a Journal\n")

    def test_rejects_duplicate_journal_id_in_later_event_before_prefix_read(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            events = [
                _prepared_event(sequence=1, action_id="action-1"),
                _prepared_event(sequence=2, action_id="action-2"),
            ]
            _write_hashed_events(path, events)
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[1] = lines[1].replace(
                '"journalId":"journal-session-1"',
                '"journalId":"other-journal","journalId":"journal-session-1"',
                1,
            )
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.chmod(path, 0o600)

            with self.assertRaisesRegex(JournalCorruptionError, "invalid JSON"):
                ActionJournal(
                    path, session_id="session-1", journal_id="journal-session-1"
                ).matches_prefix(1, events[0]["entryHash"])

    def test_rejects_a_legacy_v1_journal_without_mutating_its_file(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            legacy_event = _prepared_event()
            legacy_event["schemaVersion"] = "1.0"
            legacy_event.pop("journalId")
            _write_hashed_events(path, [legacy_event])
            os.chmod(path, 0o600)
            original = path.read_bytes()
            original_mode = stat.S_IMODE(path.stat().st_mode)

            with self.assertRaises(JournalCorruptionError):
                ActionJournal(
                    path, session_id="session-1", journal_id="journal-session-1"
                )

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), original_mode)

    def test_rejects_appending_to_a_late_appearing_v1_journal_without_mutation(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(
                path, session_id="session-1", journal_id="journal-session-1"
            )
            legacy_event = _prepared_event()
            legacy_event["schemaVersion"] = "1.0"
            legacy_event.pop("journalId")
            _write_hashed_events(path, [legacy_event])
            os.chmod(path, 0o644)
            original = path.read_bytes()
            original_mode = stat.S_IMODE(path.stat().st_mode)

            with self.assertRaises(JournalCorruptionError):
                journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), original_mode)

    def test_rejects_an_unencodable_journal_id_before_file_creation(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            with self.assertRaisesRegex(JournalError, "UTF-8"):
                ActionJournal(path, "session-1", journal_id="\ud800")
            self.assertFalse(path.exists())

    def test_rejects_an_unencodable_session_id_before_file_creation(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            with self.assertRaisesRegex(JournalError, "UTF-8"):
                ActionJournal(
                    path, "\ud800", journal_id="journal-valid"
                )
            self.assertFalse(path.exists())

    def test_explicit_journal_identity_is_read_only_and_survives_reopen(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = ActionJournal(
                path, session_id="session-1", journal_id="journal-explicit"
            )
            event = journal.prepare("action-1", "a" * 64, 1, "R0")

            with self.assertRaises(AttributeError):
                journal.journal_id = "journal-replaced"

            reopened = ActionJournal(
                path, session_id="session-1", journal_id="journal-explicit"
            )
            self.assertEqual(reopened.journal_id, "journal-explicit")
            self.assertTrue(reopened.matches_prefix(1, event["entryHash"]))

    def test_unicode_journal_identity_survives_event_write_and_reopen(self):
        ActionJournal, _, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal_id = "journal\u2028\u0085identity"
            journal = ActionJournal(
                path, session_id="session-1", journal_id=journal_id
            )
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            reopened = ActionJournal(
                path, session_id="session-1", journal_id=journal_id
            )

            self.assertEqual(event["journalId"], journal_id)
            self.assertEqual(reopened.journal_id, journal_id)
            self.assertTrue(reopened.matches_prefix(1, event["entryHash"]))

    def test_rejects_an_empty_explicit_journal_id_before_file_creation(self):
        ActionJournal, _, JournalError = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            with self.assertRaisesRegex(JournalError, "non-empty"):
                ActionJournal(path, "session-1", journal_id="")
            self.assertFalse(path.exists())

    def test_rejects_a_valid_event_bound_to_a_different_journal_id(self):
        ActionJournal, JournalCorruptionError, _ = _journal_types(self)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            event = _prepared_event()
            event["journalId"] = "journal-actual"
            _write_hashed_events(path, [event])
            os.chmod(path, 0o600)

            with self.assertRaisesRegex(JournalCorruptionError, "ID does not match"):
                ActionJournal(
                    path, session_id="session-1", journal_id="journal-reader"
                )


if __name__ == "__main__":
    unittest.main()
