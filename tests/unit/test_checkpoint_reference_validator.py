import shutil
import tempfile
import unittest
from pathlib import Path


def _reference_types(test_case):
    try:
        from bugmaster_core.checkpoint_reference_validator import (
            CheckpointReferenceError,
            CheckpointReferenceValidator,
        )
    except ImportError as error:
        test_case.fail(
            "checkpoint references need real local-store validation: {}".format(
                error
            )
        )
    return CheckpointReferenceError, CheckpointReferenceValidator


def _accept_document(_document):
    return None


def _journal_store_type(test_case):
    try:
        from bugmaster_core.action_journal_store import ActionJournalStore
    except ImportError as error:
        test_case.fail(
            "Checkpoint validation needs a stable-ID Journal store: {}".format(
                error
            )
        )
    return ActionJournalStore


def _valid_session(session_id="session-1", journal_id="journal-session-1"):
    return {
        "schemaVersion": "1.0",
        "sessionId": session_id,
        "revision": 1,
        "status": "created",
        "projectRef": "project-1",
        "hostRef": "codex",
        "environmentRef": "local",
        "createdAt": "2026-11-19T00:00:00Z",
        "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
        "approvalRefs": [],
        "checkpointRefs": [],
        "actionBudget": {},
        "journalId": journal_id,
    }


def _valid_checkpoint(**changes):
    checkpoint = {
        "schemaVersion": "1.0",
        "checkpointId": "checkpoint-1",
        "sessionId": "session-1",
        "sessionRevision": 1,
        "scopeId": "scope-1",
        "scopeRevision": 1,
        "journalSequence": 0,
        "journalHeadHash": None,
        "createdAt": "2026-11-19T00:00:00Z",
    }
    checkpoint.update(changes)
    return checkpoint


class CheckpointReferenceValidatorTests(unittest.TestCase):
    def make_context(
        self,
        root,
        session_id="session-1",
        session_root=None,
        journal_id="journal-session-1",
    ):
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        root = Path(root)
        session_root = Path(session_root) if session_root else root
        session_store = SessionStore(
            session_root, session_id, _accept_document
        )
        checkpoint_store = CheckpointStore(
            root, session_id, _accept_document
        )
        journal_store = ActionJournalStore(root, session_id, "journal-session-1")
        journal = journal_store.initialize()
        session_store.create(_valid_session(session_id, journal_id))
        return checkpoint_store, session_store, journal_store, journal

    @staticmethod
    def register_checkpoint(checkpoint_store, session_store, checkpoint):
        checkpoint_store.create(checkpoint)
        previous = session_store.read_latest()
        current = dict(previous)
        current["revision"] += 1
        current["checkpointRefs"] = previous["checkpointRefs"] + [
            checkpoint["checkpointId"]
        ]
        session_store.append_revision(
            current, expected_revision=previous["revision"]
        )

    @staticmethod
    def append_session_revision(session_store, **changes):
        previous = session_store.read_latest()
        current = dict(previous)
        current["revision"] += 1
        current.update(changes)
        return session_store.append_revision(
            current, expected_revision=previous["revision"]
        )

    def test_validates_checkpoint_session_scope_and_journal_prefix(self):
        _, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(
                directory
            )
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            checkpoint = _valid_checkpoint(
                journalSequence=event["sequence"],
                journalHeadHash=event["entryHash"],
            )
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            self.assertEqual(validator.validate("checkpoint-1"), checkpoint)

    def test_accepts_an_empty_journal_prefix(self):
        _, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(
                directory
            )
            checkpoint = _valid_checkpoint()
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            self.assertEqual(validator.validate("checkpoint-1"), checkpoint)

    def test_rejects_a_checkpoint_that_is_not_persisted(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(
                directory
            )
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("missing-checkpoint")

    def test_rejects_a_checkpoint_with_a_missing_session_revision(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(
                directory
            )
            checkpoint = _valid_checkpoint(sessionRevision=3)
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_a_scope_reference_absent_from_the_anchored_revision(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(
                directory
            )
            checkpoint = _valid_checkpoint(scopeId="scope-2")
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_requires_latest_session_revision_to_reference_the_checkpoint(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(
                directory
            )
            checkpoint_store.create(_valid_checkpoint())
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_session_history_disappearing_during_reference_validation(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(
                directory
            )
            self.register_checkpoint(
                checkpoint_store, session_store, _valid_checkpoint()
            )
            read_revision = session_store.read_revision

            def remove_session_after_read(revision):
                result = read_revision(revision)
                shutil.rmtree(session_store._session_dir)
                return result

            session_store.read_revision = remove_session_after_read
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            try:
                validator.validate("checkpoint-1")
            except Exception as error:
                self.assertIsInstance(error, CheckpointReferenceError)
            else:
                self.fail("missing Session history must reject the Checkpoint")

    def test_rejects_a_checkpoint_with_a_mismatched_journal_prefix(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(
                directory
            )
            journal.prepare("action-1", "a" * 64, 1, "R0")
            checkpoint = _valid_checkpoint(
                journalSequence=1, journalHeadHash="b" * 64
            )
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_validator_ignores_a_caller_selected_noncanonical_journal_file(self):
        _, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal import ActionJournal
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore
        ActionJournalStore = _journal_store_type(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_store = SessionStore(root, "session-1", _accept_document)
            checkpoint_store = CheckpointStore(root, "session-1", _accept_document)
            session_store.create(_valid_session())

            # A matching ID at a caller-selected path must be ignored.
            supplied_elsewhere = ActionJournal(
                root / "caller-selected.jsonl", "session-1", "journal-session-1"
            )
            event = supplied_elsewhere.prepare("action-1", "a" * 64, 1, "R0")
            checkpoint = _valid_checkpoint(
                journalSequence=event["sequence"],
                journalHeadHash=event["entryHash"],
            )
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)

            store = ActionJournalStore(root, "session-1", "journal-session-1")
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, store
            )

            with self.assertRaises(JournalCorruptionError):
                validator.validate("checkpoint-1")

    def test_rejects_a_caller_selected_action_journal_instance(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal import ActionJournal

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, _, _ = self.make_context(directory)
            caller_selected = ActionJournal(
                Path(directory) / "caller-selected.jsonl",
                "session-1",
                "journal-session-1",
            )

            with self.assertRaises(CheckpointReferenceError):
                CheckpointReferenceValidator(
                    checkpoint_store, session_store, caller_selected
                )

    def test_rejects_storage_components_for_different_sessions(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, _, _ = self.make_context(directory)
            ActionJournalStore = _journal_store_type(self)
            other_journal_store = ActionJournalStore(
                directory, "session-2", "journal-session-2"
            )

            with self.assertRaises(CheckpointReferenceError):
                CheckpointReferenceValidator(
                    checkpoint_store, session_store, other_journal_store
                )

    def test_rejects_session_journal_id_that_differs_from_the_bound_journal(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(
                directory, journal_id="journal-wrong"
            )
            checkpoint = _valid_checkpoint()
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_session_and_checkpoint_stores_with_different_roots(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        ActionJournalStore = _journal_store_type(self)
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint_store = CheckpointStore(
                root / "checkpoints", "session-1", _accept_document
            )
            session_store = SessionStore(
                root / "sessions", "session-1", _accept_document
            )
            journal_store = ActionJournalStore(
                root, "session-1", "journal-session-1"
            )

            with self.assertRaises(CheckpointReferenceError):
                CheckpointReferenceValidator(
                    checkpoint_store, session_store, journal_store
                )

    def test_accepts_checkpoint_anchored_before_later_scope_history(self):
        _, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(
                directory
            )
            checkpoint = _valid_checkpoint()
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            self.append_session_revision(
                session_store,
                scopeHistory=[
                    {"scopeId": "scope-1", "revision": 1},
                    {"scopeId": "scope-1", "revision": 2},
                ],
            )
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            self.assertEqual(validator.validate("checkpoint-1"), checkpoint)

    def test_propagates_corrupt_journal_instead_of_accepting_checkpoint(self):
        _, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(
                directory
            )
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            checkpoint = _valid_checkpoint(
                journalSequence=event["sequence"],
                journalHeadHash=event["entryHash"],
            )
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            with journal.path.open("ab") as stream:
                stream.write(b"{broken-json}\n")
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(JournalCorruptionError):
                validator.validate("checkpoint-1")


if __name__ == "__main__":
    unittest.main()
