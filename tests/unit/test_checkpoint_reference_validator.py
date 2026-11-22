import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _reference_types(test_case):
    try:
        from bugmaster_core.checkpoint_reference_validator import (
            CheckpointReferenceError,
            CheckpointReferenceValidator,
        )
    except ImportError as error:
        test_case.fail(
            "checkpoint references must be validated across the real local stores: {}".format(
                error
            )
        )
    return CheckpointReferenceError, CheckpointReferenceValidator


def _accept_document(_document):
    return None


def _valid_session(session_id="session-1", journal_id="journal-1"):
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
        self, root, session_id="session-1", session_root=None, journal_id="journal-1"
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
        journal_store = ActionJournalStore(root, session_id, journal_id)
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
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
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

    def test_validates_journal_from_the_pinned_session_root_snapshot(self):
        _, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "store"
            checkpoint_store, session_store, journal_store, journal = self.make_context(root)
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            checkpoint = _valid_checkpoint(
                journalSequence=event["sequence"],
                journalHeadHash=event["entryHash"],
            )
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )
            replacement_root = Path(directory) / "replacement"
            replacement_root.mkdir(mode=0o700)
            moved_root = Path(directory) / "store-pinned"
            original_read = session_store._read_revisions_locked
            root_replaced = False

            def replace_root_after_snapshot(
                storage, *, recover_pending=False, requested_revision=None
            ):
                nonlocal root_replaced
                history = original_read(
                    storage,
                    recover_pending=recover_pending,
                    requested_revision=requested_revision,
                )
                if not root_replaced:
                    root.rename(moved_root)
                    replacement_root.rename(root)
                    root_replaced = True
                return history

            with patch.object(
                session_store,
                "_read_revisions_locked",
                side_effect=replace_root_after_snapshot,
            ):
                self.assertEqual(validator.validate("checkpoint-1"), checkpoint)

    def test_validator_rejects_a_group_writable_storage_ancestor(self):
        from bugmaster_core.action_journal_store import ActionJournalStoreError

        _, CheckpointReferenceValidator = _reference_types(self)
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "parent"
            parent.mkdir(mode=0o700)
            root = parent / "store"
            checkpoint_store, session_store, journal_store, _ = self.make_context(root)
            checkpoint = _valid_checkpoint()
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )
            parent.chmod(0o775)

            try:
                with self.assertRaises(ActionJournalStoreError):
                    validator.validate("checkpoint-1")
            finally:
                parent.chmod(0o700)

    @unittest.skipUnless(__import__("sys").platform == "darwin", "macOS ACL enforcement only")
    def test_validator_rejects_an_ancestor_acl_added_after_store_initialization(self):
        import subprocess

        _, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStoreError

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "parent"
            parent.mkdir(mode=0o700)
            root = parent / "store"
            checkpoint_store, session_store, journal_store, _ = self.make_context(root)
            checkpoint = _valid_checkpoint()
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )
            subprocess.run(
                ["chmod", "+a", "everyone allow list,search", str(parent)],
                check=True,
                capture_output=True,
            )
            parent.chmod(0o700)

            try:
                with self.assertRaises(ActionJournalStoreError):
                    validator.validate("checkpoint-1")
            finally:
                parent.chmod(0o700)

    def test_validator_reports_a_missing_storage_root(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing-root"
            checkpoint_store = CheckpointStore(root, "session-1", _accept_document)
            session_store = SessionStore(root, "session-1", _accept_document)
            journal_store = ActionJournalStore(root, "session-1", "journal-1")
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaisesRegex(CheckpointReferenceError, "root is missing"):
                validator.validate("checkpoint-1")

    def test_accepts_an_empty_journal_prefix(self):
        _, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
            checkpoint = _valid_checkpoint()
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            self.assertEqual(validator.validate("checkpoint-1"), checkpoint)

    def test_rejects_a_checkpoint_that_is_not_persisted(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("missing-checkpoint")

    def test_validator_ignores_a_caller_selected_noncanonical_journal_file(self):
        _, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal import ActionJournal, JournalCorruptionError
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_store = SessionStore(root, "session-1", _accept_document)
            checkpoint_store = CheckpointStore(root, "session-1", _accept_document)
            session_store.create(_valid_session())

            supplied_elsewhere = ActionJournal(
                root / "caller-selected.jsonl", "session-1", "journal-1"
            )
            event = supplied_elsewhere.prepare("action-1", "a" * 64, 1, "R0")
            checkpoint = _valid_checkpoint(
                journalSequence=event["sequence"],
                journalHeadHash=event["entryHash"],
            )
            self.register_checkpoint(checkpoint_store, session_store, checkpoint)

            journal_store = ActionJournalStore(root, "session-1", "journal-1")
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(JournalCorruptionError):
                validator.validate("checkpoint-1")

    def test_rejects_a_caller_selected_action_journal_instance(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal import ActionJournal
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint_store = CheckpointStore(root, "session-1", _accept_document)
            session_store = SessionStore(root, "session-1", _accept_document)
            caller_selected = ActionJournal(
                root / "caller-selected.jsonl", "session-1", "journal-1"
            )

            with self.assertRaises(CheckpointReferenceError):
                CheckpointReferenceValidator(
                    checkpoint_store, session_store, caller_selected
                )

    def test_rejects_checkpoint_when_session_storage_is_absent(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint_store = CheckpointStore(
                root, "session-1", _accept_document
            )
            session_store = SessionStore(
                root, "session-1", _accept_document
            )
            journal_store = ActionJournalStore(root, "session-1", "journal-1")
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_invalid_checkpoint_ids_before_storage_access(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate(" ")

    def test_rejects_non_integer_checkpoint_session_revisions(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        for revision in (1.5, True, 0):
            with self.subTest(revision=revision):
                with tempfile.TemporaryDirectory() as directory:
                    checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
                    checkpoint = _valid_checkpoint(sessionRevision=revision)
                    self.register_checkpoint(
                        checkpoint_store, session_store, checkpoint
                    )
                    validator = CheckpointReferenceValidator(
                        checkpoint_store, session_store, journal_store
                    )

                    with self.assertRaises(CheckpointReferenceError):
                        validator.validate("checkpoint-1")

    def test_accepts_schema_integral_float_session_revision(self):
        _, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
            checkpoint = _valid_checkpoint(sessionRevision=1.0)
            self.register_checkpoint(
                checkpoint_store, session_store, checkpoint
            )
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            self.assertEqual(validator.validate("checkpoint-1"), checkpoint)

    def test_rejects_a_checkpoint_with_a_missing_session_revision(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
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
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
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
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
            checkpoint_store.create(_valid_checkpoint())
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_checkpoint_when_session_history_is_missing(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_store = SessionStore(
                root, "session-1", _accept_document
            )
            checkpoint_store = CheckpointStore(
                root, "session-1", _accept_document
            )
            journal_store = ActionJournalStore(root, "session-1", "journal-1")
            checkpoint_store.create(_valid_checkpoint())
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_references_mixed_from_different_session_snapshots(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "active"
            alternate_root = Path(directory) / "alternate"
            root.mkdir()
            alternate_root.mkdir()
            session_store = SessionStore(root, "session-1", _accept_document)
            checkpoint_store = CheckpointStore(
                root, "session-1", _accept_document
            )
            alternate_session_store = SessionStore(
                alternate_root, "session-1", _accept_document
            )
            alternate_checkpoint_store = CheckpointStore(
                alternate_root, "session-1", _accept_document
            )
            journal_store = ActionJournalStore(root, "session-1", "journal-1")
            journal = journal_store.initialize()
            alternate_journal_store = ActionJournalStore(
                alternate_root, "session-1", "journal-1"
            )
            alternate_journal = alternate_journal_store.initialize()
            session_store.create(_valid_session())
            alternate_session_store.create(_valid_session())

            event = journal.prepare("action-a", "a" * 64, 1, "R0")
            checkpoint = _valid_checkpoint(
                journalSequence=event["sequence"],
                journalHeadHash=event["entryHash"],
            )
            checkpoint_store.create(checkpoint)

            alternate_event = alternate_journal.prepare(
                "action-b", "b" * 64, 1, "R0"
            )
            alternate_checkpoint = _valid_checkpoint(
                journalSequence=alternate_event["sequence"],
                journalHeadHash=alternate_event["entryHash"],
            )
            alternate_checkpoint_store.create(alternate_checkpoint)
            alternate_latest = dict(alternate_session_store.read_latest())
            alternate_latest["revision"] = 2
            alternate_latest["checkpointRefs"] = ["checkpoint-1"]
            alternate_session_store.append_revision(
                alternate_latest, expected_revision=1
            )

            self.assertNotEqual(
                checkpoint["journalHeadHash"],
                alternate_checkpoint["journalHeadHash"],
            )
            session_dir = session_store._session_dir
            backup_dir = root / "session-a-backup"
            alternate_session_dir = alternate_session_store._session_dir
            original_read_checkpoint = checkpoint_store._read_checkpoint_file
            swapped = []

            def replace_storage_after_checkpoint_read(*args, **kwargs):
                result = original_read_checkpoint(*args, **kwargs)
                if not swapped:
                    session_dir.rename(backup_dir)
                    alternate_session_dir.rename(session_dir)
                    swapped.append(True)
                return result

            checkpoint_store._read_checkpoint_file = (
                replace_storage_after_checkpoint_read
            )
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_a_checkpoint_with_a_mismatched_journal_prefix(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
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

    def test_rejects_storage_components_for_different_sessions(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(directory)
            from bugmaster_core.action_journal_store import ActionJournalStore

            other_journal = ActionJournalStore(
                directory, "session-2", "journal-session-2"
            )

            with self.assertRaises(CheckpointReferenceError):
                CheckpointReferenceValidator(
                    checkpoint_store, session_store, other_journal
                )

    def test_rejects_journal_id_that_differs_from_the_latest_session(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStore

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, _ = self.make_context(directory)
            self.register_checkpoint(
                checkpoint_store, session_store, _valid_checkpoint()
            )
            wrong_journal = ActionJournalStore(
                directory, "session-1", "journal-other"
            )
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, wrong_journal
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_rejects_journal_id_from_a_replaced_session_snapshot(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStore
        from bugmaster_core.checkpoint_store import CheckpointStore
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "active"
            alternate_root = Path(directory) / "alternate"
            root.mkdir()
            alternate_root.mkdir()
            session_store = SessionStore(root, "session-1", _accept_document)
            checkpoint_store = CheckpointStore(
                root, "session-1", _accept_document
            )
            alternate_session_store = SessionStore(
                alternate_root, "session-1", _accept_document
            )
            journal_store = ActionJournalStore(root, "session-1", "journal-b")
            alternate_journal = journal_store.initialize()
            session_store.create(_valid_session(journal_id="journal-a"))
            alternate_session_store.create(
                _valid_session(journal_id="journal-b")
            )
            event = alternate_journal.prepare(
                "action-b", "b" * 64, 1, "R0"
            )
            checkpoint = _valid_checkpoint(
                journalSequence=event["sequence"],
                journalHeadHash=event["entryHash"],
            )
            checkpoint_store.create(checkpoint)
            alternate_latest = dict(alternate_session_store.read_latest())
            alternate_latest["revision"] = 2
            alternate_latest["checkpointRefs"] = ["checkpoint-1"]
            alternate_session_store.append_revision(
                alternate_latest, expected_revision=1
            )

            session_dir = session_store._session_dir
            backup_dir = root / "session-a-backup"
            alternate_session_dir = alternate_session_store._session_dir
            original_read_checkpoint = checkpoint_store._read_checkpoint_file
            swapped = []

            def replace_storage_after_checkpoint_read(*args, **kwargs):
                result = original_read_checkpoint(*args, **kwargs)
                if not swapped:
                    session_dir.rename(backup_dir)
                    alternate_session_dir.rename(session_dir)
                    swapped.append(True)
                return result

            checkpoint_store._read_checkpoint_file = (
                replace_storage_after_checkpoint_read
            )
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )

            with self.assertRaises(CheckpointReferenceError):
                validator.validate("checkpoint-1")

    def test_requires_checkpoint_safe_open_flags_from_validator_entry(self):
        _, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.checkpoint_store import CheckpointStoreError

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
            self.register_checkpoint(
                checkpoint_store, session_store, _valid_checkpoint()
            )
            validator = CheckpointReferenceValidator(
                checkpoint_store, session_store, journal_store
            )
            original_nonblock = os.O_NONBLOCK
            del os.O_NONBLOCK
            try:
                with self.assertRaises(CheckpointStoreError):
                    validator.validate("checkpoint-1")
            finally:
                os.O_NONBLOCK = original_nonblock

    def test_rejects_session_and_checkpoint_stores_with_different_roots(self):
        CheckpointReferenceError, CheckpointReferenceValidator = _reference_types(self)
        from bugmaster_core.action_journal_store import ActionJournalStore
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
                root / "journals", "session-1", "journal-1"
            )

            with self.assertRaises(CheckpointReferenceError):
                CheckpointReferenceValidator(
                    checkpoint_store, session_store, journal_store
                )

    def test_accepts_checkpoint_anchored_before_later_scope_history(self):
        _, CheckpointReferenceValidator = _reference_types(self)

        with tempfile.TemporaryDirectory() as directory:
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
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
            checkpoint_store, session_store, journal_store, journal = self.make_context(directory)
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

