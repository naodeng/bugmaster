import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
            store.initialize()
            self.assertTrue(store.path.is_file())
            journal = store.initialize()
            event = journal.prepare("action-1", "a" * 64, 1, "R0")

            reopened = ActionJournalStore(root, "session-1", "journal-1").open()
            self.assertEqual(journal.path, store.path)
            self.assertEqual(reopened.journal_id, "journal-1")
            self.assertTrue(
                reopened.matches_prefix(event["sequence"], event["entryHash"])
            )

    def test_relative_root_is_fixed_when_the_store_is_constructed(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = base / "first"
            second = base / "second"
            first.mkdir()
            second.mkdir()
            original_cwd = Path.cwd()
            try:
                os.chdir(first)
                store = ActionJournalStore("journal-data", "session-1", "journal-1")
                expected_root = Path.cwd() / "journal-data"
                os.chdir(second)
                store.initialize()
            finally:
                os.chdir(original_cwd)

            self.assertEqual(store.root, expected_root)
            self.assertTrue(store.path.is_file())
            self.assertFalse((second / "journal-data").exists())

    def test_open_does_not_create_or_change_storage_paths(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.prepare("action-1", "a" * 64, 1, "R0")
            os.chmod(store._journals_dir, 0o500)
            os.chmod(store._session_dir, 0o500)

            reopened = store.open()

            self.assertEqual(reopened.recovery_status("action-1"), "needs_reconciliation")
            self.assertEqual(stat.S_IMODE(store._journals_dir.stat().st_mode), 0o500)
            self.assertEqual(stat.S_IMODE(store._session_dir.stat().st_mode), 0o500)

    def test_open_fails_closed_when_the_canonical_journal_is_missing(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import ActionJournal, JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ActionJournalStore(root, "session-1", "journal-1")
            store.path.parent.mkdir(parents=True)
            legacy_path = root / "legacy-journal.jsonl"
            legacy = ActionJournal(
                legacy_path, "session-1", journal_id="journal-1"
            )
            legacy.prepare("action-1", "a" * 64, 1, "R0")
            legacy_bytes = legacy_path.read_bytes()

            with self.assertRaises(JournalCorruptionError):
                store.open()

            self.assertFalse(store.path.exists())
            self.assertEqual(legacy_path.read_bytes(), legacy_bytes)

    def test_open_fails_closed_if_the_canonical_journal_disappears(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize()
            real_open = os.open

            def disappear_during_open(target, flags, *args, **kwargs):
                if Path(target) == store.path:
                    raise FileNotFoundError("journal disappeared")
                return real_open(target, flags, *args, **kwargs)

            with patch(
                "bugmaster_core.action_journal.os.open",
                side_effect=disappear_during_open,
            ):
                with self.assertRaises(JournalCorruptionError):
                    store.open()

    def test_open_reports_canonical_path_inspection_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize()
            real_lstat = Path.lstat

            def fail_canonical_inspection(path, *args, **kwargs):
                if path == store.path:
                    raise PermissionError("inspection denied")
                return real_lstat(path, *args, **kwargs)

            with patch.object(Path, "lstat", fail_canonical_inspection):
                with self.assertRaises(ActionJournalStoreError):
                    store.open()

    def test_initialize_reports_canonical_file_open_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store._ensure_directories()
            real_open = os.open

            def fail_canonical_open(target, flags, *args, **kwargs):
                if Path(target) == store.path:
                    raise PermissionError("creation denied")
                return real_open(target, flags, *args, **kwargs)

            with patch("bugmaster_core.action_journal_store.os.open", fail_canonical_open):
                with self.assertRaises(ActionJournalStoreError):
                    store.initialize()

    def test_initialize_rejects_a_non_regular_file_descriptor(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store._ensure_directories()
            directory_fd = os.open(directory, os.O_RDONLY)
            real_open = os.open

            def return_directory_for_canonical_path(target, flags, *args, **kwargs):
                if Path(target) == store.path:
                    return directory_fd
                return real_open(target, flags, *args, **kwargs)

            with patch(
                "bugmaster_core.action_journal_store.os.open",
                return_directory_for_canonical_path,
            ):
                with self.assertRaises(JournalCorruptionError):
                    store.initialize()

    def test_initialize_reports_file_sync_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store._ensure_directories()
            with patch("bugmaster_core.action_journal_store.os.fsync", side_effect=OSError):
                with self.assertRaises(ActionJournalStoreError):
                    store.initialize()

    def test_initialize_reports_directory_sync_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store._ensure_directories()
            with patch(
                "bugmaster_core.action_journal_store._fsync_directory",
                side_effect=OSError,
            ):
                with self.assertRaises(ActionJournalStoreError):
                    store.initialize()

    def test_initialize_reports_storage_root_creation_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(
                Path(directory) / "uncreated" / "journal-data", "session-1", "journal-1"
            )
            real_mkdir = Path.mkdir

            def fail_root_creation(path, *args, **kwargs):
                if path == store.root:
                    raise PermissionError("creation denied")
                return real_mkdir(path, *args, **kwargs)

            with patch.object(Path, "mkdir", fail_root_creation):
                with self.assertRaises(ActionJournalStoreError):
                    store.initialize()

    def test_initialize_rejects_a_symlinked_storage_root(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            outside = parent / "outside"
            outside.mkdir()
            root = parent / "linked-root"
            root.symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ActionJournalStoreError):
                ActionJournalStore(root, "session-1", "journal-1").initialize()

    def test_initialize_rejects_a_symlinked_journal_directory(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            (root / "journals").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(ActionJournalStoreError):
                ActionJournalStore(root, "session-1", "journal-1").initialize()

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
            store.initialize()
            store.path.unlink()
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
