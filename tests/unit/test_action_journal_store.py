import hashlib
import tempfile
import unittest
from pathlib import Path


def _store_types(test_case):
    try:
        from bugmaster_core.action_journal_store import (
            ActionJournalStore,
            ActionJournalStoreError,
        )
    except ImportError as error:
        test_case.fail(
            "ActionJournal files must resolve from stable identities: {}".format(
                error
            )
        )
    return ActionJournalStore, ActionJournalStoreError


class ActionJournalStoreTests(unittest.TestCase):
    def test_resolves_a_stable_path_from_session_and_journal_ids(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = ActionJournalStore(root, "session-1", "journal-1")
            second = ActionJournalStore(root, "session-1", "journal-1")
            session_key = hashlib.sha256(b"session-1").hexdigest()
            journal_key = hashlib.sha256(b"journal-1").hexdigest()

            expected = root / "journals" / session_key / (journal_key + ".jsonl")
            self.assertEqual(first.path, expected)
            self.assertEqual(second.path, expected)

    def test_separates_paths_by_session_and_journal_identity(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                ActionJournalStore(root, "session-1", "journal-1").path,
                ActionJournalStore(root, "session-2", "journal-1").path,
                ActionJournalStore(root, "session-1", "journal-2").path,
            }

            self.assertEqual(len(paths), 3)

    def test_identity_and_root_cannot_change_after_path_resolution(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            for name, value in (
                ("root", Path(directory) / "other"),
                ("session_id", "session-2"),
                ("journal_id", "journal-2"),
            ):
                with self.subTest(name=name):
                    with self.assertRaises(AttributeError):
                        setattr(store, name, value)

    def test_open_uses_the_canonical_path_and_reloads_the_same_prefix(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ActionJournalStore(root, "session-1", "journal-1")
            journal = store.open()
            event = journal.prepare("action-1", "a" * 64, 1, "R0")

            reopened = ActionJournalStore(root, "session-1", "journal-1").open()
            self.assertEqual(journal.path, store.path)
            self.assertEqual(reopened.journal_id, "journal-1")
            self.assertTrue(
                reopened.matches_prefix(event["sequence"], event["entryHash"])
            )

    def test_rejects_a_symlinked_journal_directory(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            (root / "journals").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ActionJournalStoreError):
                ActionJournalStore(root, "session-1", "journal-1").open()

    def test_rejects_a_symlinked_storage_root(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            outside = parent / "outside"
            outside.mkdir()
            root = parent / "linked-root"
            root.symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ActionJournalStoreError):
                ActionJournalStore(root, "session-1", "journal-1").open()

    def test_reports_an_unusable_storage_root(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "regular-file"
            root.write_text("not a directory", encoding="utf-8")

            with self.assertRaises(ActionJournalStoreError):
                ActionJournalStore(root / "child", "session-1", "journal-1").open()

    def test_rejects_a_symlinked_journal_file(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ActionJournalStore(root, "session-1", "journal-1")
            store.open()
            outside = root / "outside.jsonl"
            outside.write_text("", encoding="utf-8")
            store.path.symlink_to(outside)

            from bugmaster_core.action_journal import JournalCorruptionError

            with self.assertRaises(JournalCorruptionError):
                ActionJournalStore(root, "session-1", "journal-1").open()

    def test_rejects_a_directory_at_the_journal_file_path(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ActionJournalStore(root, "session-1", "journal-1")
            store.path.parent.mkdir(parents=True)
            store.path.mkdir()

            from bugmaster_core.action_journal import JournalCorruptionError

            with self.assertRaises(JournalCorruptionError):
                store.open()

    def test_rejects_empty_or_invalid_utf8_identity(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for session_id, journal_id in (
                ("", "journal-1"),
                ("session-1", " "),
                ("\ud800", "journal-1"),
            ):
                with self.subTest(session_id=session_id, journal_id=journal_id):
                    with self.assertRaises(ActionJournalStoreError):
                        ActionJournalStore(root, session_id, journal_id)


if __name__ == "__main__":
    unittest.main()
