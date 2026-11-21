import hashlib
import ctypes
import errno
import fcntl
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
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
    def test_acl_probe_skips_macos_api_on_other_platforms(self):
        from bugmaster_core.filesystem_security import _has_extended_acl

        with patch("bugmaster_core.filesystem_security.sys.platform", "linux"):
            self.assertFalse(_has_extended_acl(-1))

    def test_acl_probe_fails_closed_when_native_api_is_missing(self):
        from bugmaster_core.filesystem_security import _has_extended_acl

        with patch("bugmaster_core.filesystem_security.sys.platform", "darwin"):
            with patch(
                "bugmaster_core.filesystem_security.ctypes.CDLL", return_value=object()
            ):
                with self.assertRaises(OSError):
                    _has_extended_acl(-1)

    def test_acl_probe_reports_native_query_errors(self):
        from bugmaster_core.filesystem_security import _has_extended_acl

        class FailedAclQuery:
            def __call__(self, _file_descriptor):
                ctypes.set_errno(errno.EACCES)
                return None

        class FakeLibc:
            acl_get_fd = FailedAclQuery()
            acl_free = FailedAclQuery()

        with patch("bugmaster_core.filesystem_security.sys.platform", "darwin"):
            with patch(
                "bugmaster_core.filesystem_security.ctypes.CDLL",
                return_value=FakeLibc(),
            ):
                with self.assertRaises(OSError):
                    _has_extended_acl(-1)

    def test_acl_probe_uses_io_error_when_native_query_sets_no_errno(self):
        from bugmaster_core.filesystem_security import _has_extended_acl

        class FailedAclQuery:
            def __call__(self, _file_descriptor):
                ctypes.set_errno(0)
                return None

        class FakeLibc:
            acl_get_fd = FailedAclQuery()
            acl_free = FailedAclQuery()

        with patch("bugmaster_core.filesystem_security.sys.platform", "darwin"):
            with patch(
                "bugmaster_core.filesystem_security.ctypes.CDLL",
                return_value=FakeLibc(),
            ):
                with self.assertRaises(OSError) as error:
                    _has_extended_acl(-1)

        self.assertEqual(error.exception.errno, errno.EIO)

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

    def test_normalizes_the_trusted_macos_temporary_path_alias(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")

            self.assertEqual(store._resolved_root, Path(directory).resolve())

    def test_rejects_an_untrusted_system_path_alias(self):
        _, ActionJournalStoreError = _store_types(self)
        from bugmaster_core.action_journal_store import _normalize_storage_root

        alias_stat = SimpleNamespace(
            st_mode=stat.S_IFLNK | 0o777,
            st_uid=os.geteuid() + 1,
        )
        with patch.object(Path, "lstat", return_value=alias_stat):
            with patch(
                "bugmaster_core.action_journal_store.os.readlink",
                return_value="attacker-controlled-target",
            ):
                with self.assertRaises(ActionJournalStoreError):
                    _normalize_storage_root("/tmp/untrusted/store")

    def test_system_alias_probe_error_keeps_the_configured_root(self):
        from bugmaster_core.action_journal_store import _normalize_storage_root

        root = Path("/tmp/configured/store")
        with patch.object(Path, "lstat", side_effect=OSError("alias unavailable")):
            self.assertEqual(_normalize_storage_root(root), root)

    def test_non_symlink_system_path_is_not_rewritten(self):
        from bugmaster_core.action_journal_store import _normalize_storage_root

        root = Path("/tmp/configured/store")
        directory_stat = SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o755,
            st_uid=0,
        )
        with patch.object(Path, "lstat", return_value=directory_stat):
            with patch(
                "bugmaster_core.action_journal_store.os.readlink",
                return_value="private/tmp",
            ):
                self.assertEqual(_normalize_storage_root(root), root)

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
            store._ensure_directories()
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
                if target == store.path.name and kwargs.get("dir_fd") is not None:
                    raise FileNotFoundError("journal disappeared")
                return real_open(target, flags, *args, **kwargs)

            with patch(
                "bugmaster_core.action_journal.os.open",
                side_effect=disappear_during_open,
            ):
                with self.assertRaises(JournalCorruptionError):
                    store.open()

    def test_open_reports_canonical_path_inspection_errors(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize()
            real_open = os.open

            def fail_canonical_inspection(target, flags, *args, **kwargs):
                if target == store.path.name and kwargs.get("dir_fd") is not None:
                    raise PermissionError("inspection denied")
                return real_open(target, flags, *args, **kwargs)

            with patch("bugmaster_core.action_journal.os.open", fail_canonical_inspection):
                with self.assertRaises(JournalCorruptionError):
                    store.open()

    def test_initialize_reports_canonical_file_open_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store._ensure_directories()
            real_open = os.open

            def fail_canonical_open(target, flags, *args, **kwargs):
                if target == store.path.name and kwargs.get("dir_fd") is not None:
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
                if target == store.path.name and kwargs.get("dir_fd") is not None:
                    return os.dup(directory_fd)
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
                "bugmaster_core.action_journal_store._sync_directory",
                side_effect=OSError,
            ):
                with self.assertRaises(ActionJournalStoreError):
                    store.initialize()

    def test_initialize_retries_parent_sync_after_failed_root_sync(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "journal-data"
            store = ActionJournalStore(root, "session-1", "journal-1")
            parent_inode = root.parent.stat().st_ino
            synced_inodes = []
            failed_sync = False

            def fail_first_sync(directory_fd):
                nonlocal failed_sync
                synced_inodes.append(os.fstat(directory_fd).st_ino)
                if os.fstat(directory_fd).st_ino == parent_inode and not failed_sync:
                    failed_sync = True
                    raise OSError("parent directory sync failed")
                return os.fsync(directory_fd)

            with patch(
                "bugmaster_core.action_journal_store._sync_directory",
                side_effect=fail_first_sync,
            ):
                with self.assertRaises(ActionJournalStoreError):
                    store.initialize()

            self.assertTrue(root.is_dir())
            synced_inodes.clear()
            with patch(
                "bugmaster_core.action_journal_store._sync_directory",
                side_effect=lambda fd: (
                    synced_inodes.append(os.fstat(fd).st_ino), os.fsync(fd)
                )[1],
            ):
                journal = store.initialize()
                journal.close()

            self.assertIn(parent_inode, synced_inodes)

    def test_initialize_retries_parent_sync_after_failed_journal_file_sync(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store._ensure_directories()
            journal_directory_inode = store.path.parent.stat().st_ino
            failed_sync = False

            def fail_first_sync(directory_fd):
                nonlocal failed_sync
                if os.fstat(directory_fd).st_ino == journal_directory_inode and not failed_sync:
                    failed_sync = True
                    raise OSError("Journal directory sync failed")
                return os.fsync(directory_fd)

            with patch(
                "bugmaster_core.action_journal_store._sync_directory",
                side_effect=fail_first_sync,
            ):
                with self.assertRaises(ActionJournalStoreError):
                    store.initialize()

            self.assertTrue(store.path.is_file())
            synced_inodes = []
            with patch(
                "bugmaster_core.action_journal_store._sync_directory",
                side_effect=lambda fd: (
                    synced_inodes.append(os.fstat(fd).st_ino), os.fsync(fd)
                )[1],
            ):
                journal = store.initialize()
                journal.close()

            self.assertIn(journal_directory_inode, synced_inodes)

    def test_initialize_reports_storage_root_creation_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(
                Path(directory) / "uncreated" / "journal-data", "session-1", "journal-1"
            )
            real_mkdir = os.mkdir

            def fail_root_creation(name, *args, **kwargs):
                if name == store.root.name:
                    raise PermissionError("creation denied")
                return real_mkdir(name, *args, **kwargs)

            with patch("bugmaster_core.action_journal_store.os.mkdir", fail_root_creation):
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

    def test_initialize_rejects_a_symlinked_storage_root_ancestor(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            real_parent = parent / "real-parent"
            real_parent.mkdir()
            linked_parent = parent / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)

            with self.assertRaises(ActionJournalStoreError):
                ActionJournalStore(
                    linked_parent / "journal-data", "session-1", "journal-1"
                ).initialize()

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
            store._ensure_directories()
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

    def test_open_journal_keeps_using_pinned_session_directory_after_rename(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "store"
            store = ActionJournalStore(root, "session-1", "journal-1")
            journal = store.initialize()
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            outside = Path(directory) / "outside"
            outside.mkdir()
            (outside / store.path.name).write_text("", encoding="utf-8")
            moved_session = store._session_dir.with_name("session-original")
            store._session_dir.rename(moved_session)
            store._session_dir.symlink_to(outside, target_is_directory=True)

            self.assertTrue(
                journal.matches_prefix(event["sequence"], event["entryHash"])
            )

    def test_pinned_journal_rejects_directory_permissions_changed_after_open(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            os.chmod(store._session_dir, 0o777)
            try:
                with self.assertRaises(JournalCorruptionError):
                    journal.matches_prefix(0, None)
            finally:
                os.chmod(store._session_dir, 0o700)
                journal.close()

    def test_pinned_journal_wraps_directory_descriptor_duplication_errors(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournalStore(
                directory, "session-1", "journal-1"
            ).initialize()
            with patch.object(action_journal.os, "dup", side_effect=OSError):
                with self.assertRaises(JournalCorruptionError):
                    journal._open_parent()
            journal.close()

    def test_pinned_journal_closes_duplicate_when_descriptor_metadata_fails(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournalStore(
                directory, "session-1", "journal-1"
            ).initialize()
            real_dup = os.dup
            duplicated = []

            def capture_duplicate(descriptor):
                duplicate = real_dup(descriptor)
                duplicated.append(duplicate)
                return duplicate

            with patch.object(action_journal.os, "dup", new=capture_duplicate):
                with patch.object(action_journal.os, "fstat", side_effect=OSError):
                    with self.assertRaises(JournalCorruptionError):
                        journal._open_parent()

            with self.assertRaises(OSError):
                os.fstat(duplicated[0])
            journal.close()

    def test_action_journal_rejects_non_directory_pinned_descriptor(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import ActionJournal, JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-a-directory"
            path.write_text("", encoding="utf-8")
            descriptor = os.open(path, os.O_RDONLY)

            with self.assertRaises(JournalCorruptionError):
                ActionJournal(
                    Path(directory) / "journal.jsonl",
                    "session-1",
                    "journal-1",
                    require_existing=True,
                    directory_fd=descriptor,
                )

            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_store_backed_journal_does_not_recreate_a_missing_file_on_append(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.prepare("action-1", "a" * 64, 1, "R0")
            store.path.unlink()

            with self.assertRaises(JournalCorruptionError):
                journal.prepare("action-2", "b" * 64, 1, "R0")

            self.assertFalse(store.path.exists())

    def test_store_backed_append_wraps_open_errors_for_existing_journal(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            real_open = os.open

            def fail_journal_append(target, flags, *args, **kwargs):
                if (
                    target == store.path.name
                    and kwargs.get("dir_fd") is not None
                    and flags & os.O_APPEND
                ):
                    raise PermissionError("append denied")
                return real_open(target, flags, *args, **kwargs)

            with patch.object(action_journal.os, "open", new=fail_journal_append):
                with self.assertRaises(JournalCorruptionError):
                    journal.prepare("action-1", "a" * 64, 1, "R0")

    def test_pinned_journal_fails_closed_when_file_acl_query_errors(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core import action_journal

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournalStore(
                directory, "session-1", "journal-1"
            ).initialize()
            real_has_acl = action_journal._has_extended_acl

            def fail_file_acl_query(file_descriptor):
                if stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                    raise OSError("file ACL query failed")
                return real_has_acl(file_descriptor)

            try:
                with patch.object(
                    action_journal,
                    "_has_extended_acl",
                    side_effect=fail_file_acl_query,
                ):
                    with self.assertRaises(JournalCorruptionError):
                        journal.matches_prefix(0, None)
            finally:
                journal.close()

    def test_store_backed_journal_fails_closed_when_acl_query_errors(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.close()
            with patch(
                "bugmaster_core.action_journal._has_extended_acl",
                side_effect=OSError("ACL query failed"),
            ):
                with self.assertRaises(JournalCorruptionError):
                    store.open()

    def test_open_rejects_group_or_world_accessible_journal_file(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize()
            os.chmod(store.path, 0o666)

            with self.assertRaises(JournalCorruptionError):
                store.open()

            self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o666)

    def test_open_rejects_group_or_world_accessible_store_directory(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize()
            for path in (store.root, store._journals_dir, store._session_dir):
                with self.subTest(path=path):
                    os.chmod(path, 0o777)
                    with self.assertRaises(ActionJournalStoreError):
                        store.open()
                    os.chmod(path, 0o700)

    def test_open_fails_closed_when_directory_acl_query_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.close()
            with patch(
                "bugmaster_core.action_journal_store._has_extended_acl",
                side_effect=OSError("ACL query failed"),
            ):
                with self.assertRaises(ActionJournalStoreError):
                    store.open()

    def test_pinned_journal_fails_closed_when_directory_acl_query_errors(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournalStore(
                directory, "session-1", "journal-1"
            ).initialize()
            try:
                real_has_acl = __import__(
                    "bugmaster_core.action_journal", fromlist=["_has_extended_acl"]
                )._has_extended_acl

                def fail_directory_acl_query(file_descriptor):
                    if stat.S_ISDIR(os.fstat(file_descriptor).st_mode):
                        raise OSError("ACL query failed")
                    return real_has_acl(file_descriptor)

                with patch(
                    "bugmaster_core.action_journal._has_extended_acl",
                    side_effect=fail_directory_acl_query,
                ):
                    with self.assertRaises(JournalCorruptionError):
                        journal.matches_prefix(0, None)
            finally:
                journal.close()

    @unittest.skipUnless(sys.platform == "darwin", "macOS ACL enforcement only")
    def test_pinned_journal_rejects_directory_acl_added_after_open(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            try:
                subprocess.run(
                    [
                        "chmod",
                        "+a",
                        "everyone allow list,search",
                        str(store._session_dir),
                    ],
                    check=True,
                    capture_output=True,
                )
                store._session_dir.chmod(0o700)

                with self.assertRaises(JournalCorruptionError):
                    journal.matches_prefix(0, None)
            finally:
                journal.close()

    def test_open_absolute_directory_checks_filesystem_root_trust(self):
        ActionJournalStore, _ = _store_types(self)
        import bugmaster_core.action_journal_store as journal_store_module

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            root_stat = os.stat("/")
            real_check = journal_store_module._require_trusted_ancestor

            def reject_filesystem_root(directory_stat):
                if (directory_stat.st_dev, directory_stat.st_ino) == (
                    root_stat.st_dev,
                    root_stat.st_ino,
                ):
                    raise journal_store_module.ActionJournalStoreError(
                        "filesystem root trust check reached"
                    )
                return real_check(directory_stat)

            with patch.object(
                journal_store_module,
                "_require_trusted_ancestor",
                side_effect=reject_filesystem_root,
            ):
                with self.assertRaisesRegex(
                    journal_store_module.ActionJournalStoreError,
                    "filesystem root trust check reached",
                ):
                    store._open_root_directory(create=False)

    def test_initialize_does_not_recreate_a_missing_journal_for_an_existing_session(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize().close()
            SessionStore(directory, "session-1", lambda _document: None).create(
                {
                    "schemaVersion": "1.0",
                    "sessionId": "session-1",
                    "revision": 1,
                    "status": "created",
                    "projectRef": "project-1",
                    "hostRef": "codex",
                    "environmentRef": "local",
                    "createdAt": "2026-11-21T00:00:00Z",
                    "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                    "approvalRefs": [],
                    "checkpointRefs": [],
                    "actionBudget": {},
                    "journalId": "journal-1",
                }
            )
            store.path.unlink()

            with self.assertRaises(JournalCorruptionError):
                store.initialize()

            self.assertFalse(store.path.exists())

    def test_initialize_fails_closed_when_journal_storage_is_missing_for_existing_session(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize().close()
            SessionStore(directory, "session-1", lambda _document: None).create(
                {
                    "schemaVersion": "1.0",
                    "sessionId": "session-1",
                    "revision": 1,
                    "status": "created",
                    "projectRef": "project-1",
                    "hostRef": "codex",
                    "environmentRef": "local",
                    "createdAt": "2026-11-21T00:00:00Z",
                    "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                    "approvalRefs": [],
                    "checkpointRefs": [],
                    "actionBudget": {},
                    "journalId": "journal-1",
                }
            )
            store.path.unlink()
            store._session_dir.rmdir()
            store._journals_dir.rmdir()

            with self.assertRaisesRegex(
                JournalCorruptionError,
                "canonical Journal storage path is missing",
            ):
                store.initialize()

            self.assertFalse(store._journals_dir.exists())

    def test_initialize_reports_missing_path_errors_for_new_sessions(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            with patch.object(
                store,
                "_open_store_directory_at",
                side_effect=FileNotFoundError("storage path changed"),
            ):
                with self.assertRaisesRegex(
                    ActionJournalStoreError,
                    "storage path disappeared during initialization",
                ):
                    store.initialize()

    def test_initialize_serializes_journal_creation_with_session_publication(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        from bugmaster_core.session_store import SessionStore
        import bugmaster_core.session_store as session_store_module

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            session_store = SessionStore(
                directory, "session-1", lambda _document: None
            )
            session_document = {
                "schemaVersion": "1.0",
                "sessionId": "session-1",
                "revision": 1,
                "status": "created",
                "projectRef": "project-1",
                "hostRef": "codex",
                "environmentRef": "local",
                "createdAt": "2026-11-21T00:00:00Z",
                "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                "approvalRefs": [],
                "checkpointRefs": [],
                "actionBudget": {},
                "journalId": "journal-1",
            }
            journal_creation_paused = threading.Event()
            allow_journal_creation = threading.Event()
            session_lock_probe_completed = threading.Event()
            session_creation_completed = threading.Event()
            session_lock_probe_results = []
            failures = []
            real_initialize_journal_file = store._initialize_journal_file
            real_flock = session_store_module.fcntl.flock

            def pause_before_creating_journal(directory_fd):
                journal_creation_paused.set()
                if not allow_journal_creation.wait(timeout=3):
                    raise TimeoutError("Journal creation was not released")
                real_initialize_journal_file(directory_fd)

            def initialize_journal():
                try:
                    store.initialize().close()
                except BaseException as error:
                    failures.append(error)

            def create_session():
                try:
                    session_store.create(session_document)
                except BaseException as error:
                    failures.append(error)
                finally:
                    session_creation_completed.set()

            def probe_session_lock(fd, operation):
                if (
                    threading.current_thread().name == "session-publisher"
                    and operation == fcntl.LOCK_EX
                ):
                    try:
                        real_flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        session_lock_probe_results.append("blocked")
                    else:
                        session_lock_probe_results.append("available")
                        real_flock(fd, fcntl.LOCK_UN)
                    session_lock_probe_completed.set()
                return real_flock(fd, operation)

            with patch.object(
                store,
                "_initialize_journal_file",
                side_effect=pause_before_creating_journal,
            ), patch(
                "bugmaster_core.session_store.fcntl.flock",
                side_effect=probe_session_lock,
            ):
                initializer = threading.Thread(
                    target=initialize_journal, name="journal-initializer"
                )
                creator = threading.Thread(
                    target=create_session, name="session-publisher"
                )
                initializer.start()
                self.assertTrue(journal_creation_paused.wait(timeout=2))
                creator.start()
                self.assertTrue(session_lock_probe_completed.wait(timeout=2))
                self.assertEqual(session_lock_probe_results, ["blocked"])
                try:
                    self.assertFalse(session_creation_completed.is_set())
                finally:
                    allow_journal_creation.set()
                    initializer.join(timeout=3)
                    creator.join(timeout=3)

            self.assertFalse(initializer.is_alive())
            self.assertFalse(creator.is_alive())
            self.assertTrue(session_creation_completed.is_set())
            if failures:
                raise failures[0]

            store.path.unlink()
            with self.assertRaises(JournalCorruptionError):
                store.initialize()

    def test_initialize_rejects_a_hardlinked_session_lock_without_chmod(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.session_store import SessionStore, SessionStoreError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ActionJournalStore(root, "session-1", "journal-1")
            session_store = SessionStore(
                root, "session-1", lambda _document: None
            )
            store.initialize().close()
            external_file = root / "outside-session-storage"
            external_file.write_text("preserve mode", encoding="utf-8")
            os.chmod(external_file, 0o644)
            session_store._lock_path.unlink()
            os.link(external_file, session_store._lock_path)

            failure = None
            try:
                store.initialize().close()
            except SessionStoreError as error:
                failure = error

            self.assertEqual(stat.S_IMODE(external_file.stat().st_mode), 0o644)
            self.assertIsNotNone(failure)

    def test_initialize_creates_journal_when_other_session_storage_exists(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.session_store import SessionStore

        with tempfile.TemporaryDirectory() as directory:
            SessionStore(directory, "other-session", lambda _document: None).create(
                {
                    "schemaVersion": "1.0",
                    "sessionId": "other-session",
                    "revision": 1,
                    "status": "created",
                    "projectRef": "project-1",
                    "hostRef": "codex",
                    "environmentRef": "local",
                    "createdAt": "2026-11-21T00:00:00Z",
                    "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                    "approvalRefs": [],
                    "checkpointRefs": [],
                    "actionBudget": {},
                    "journalId": "other-journal",
                }
            )
            store = ActionJournalStore(directory, "new-session", "new-journal")

            journal = store.initialize()

            self.assertTrue(store.path.is_file())
            journal.close()

    def test_open_rejects_a_group_writable_ancestor(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "parent"
            parent.mkdir()
            store = ActionJournalStore(parent / "store", "session-1", "journal-1")
            store.initialize().close()
            os.chmod(parent, 0o775)

            with self.assertRaises(ActionJournalStoreError):
                store.open()

    def test_open_fails_closed_when_storage_directories_are_missing(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(
                Path(directory) / "missing", "session-1", "journal-1"
            )

            with self.assertRaises(JournalCorruptionError):
                store.open()

            self.assertFalse(store.root.exists())

    def test_directory_safety_checks_reject_invalid_ownership_and_types(self):
        from bugmaster_core.action_journal_store import ActionJournalStoreError
        from bugmaster_core.action_journal_store import (
            _require_private_directory,
            _require_trusted_ancestor,
        )

        uid = os.geteuid()
        not_a_directory = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=uid)
        wrong_owner = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=uid + 1)
        writable_ancestor = SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_uid=uid)
        safe_sticky_ancestor = SimpleNamespace(
            st_mode=stat.S_IFDIR | stat.S_ISVTX | 0o777, st_uid=0
        )

        with self.assertRaises(ActionJournalStoreError):
            _require_private_directory(-1, not_a_directory, repair=False)
        with self.assertRaises(ActionJournalStoreError):
            _require_private_directory(-1, wrong_owner, repair=False)
        with self.assertRaises(ActionJournalStoreError):
            _require_trusted_ancestor(not_a_directory)
        with self.assertRaises(ActionJournalStoreError):
            _require_trusted_ancestor(wrong_owner)
        with self.assertRaises(ActionJournalStoreError):
            _require_trusted_ancestor(writable_ancestor)
        _require_trusted_ancestor(safe_sticky_ancestor)

    def test_private_directory_repair_wraps_permission_errors(self):
        from bugmaster_core.action_journal_store import ActionJournalStoreError
        from bugmaster_core.action_journal_store import _require_private_directory

        directory_stat = SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o755,
            st_uid=os.geteuid(),
        )
        with patch(
            "bugmaster_core.action_journal_store._has_extended_acl",
            return_value=False,
        ):
            with patch(
                "bugmaster_core.action_journal_store.os.fchmod",
                side_effect=OSError("permission repair failed"),
            ):
                with self.assertRaises(ActionJournalStoreError):
                    _require_private_directory(-1, directory_stat, repair=True)

    def test_directory_relative_io_fails_closed_when_unsupported(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            with patch(
                "bugmaster_core.action_journal_store._DIRECTORY_RELATIVE_IO_SUPPORTED",
                False,
            ):
                with self.assertRaises(ActionJournalStoreError):
                    store.open()

    def test_storage_root_must_not_be_the_filesystem_root(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with self.assertRaises(ActionJournalStoreError):
            ActionJournalStore("/", "session-1", "journal-1").open()

    def test_open_reports_filesystem_root_descriptor_errors(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            real_open = os.open

            def fail_root_open(target, flags, *args, **kwargs):
                if target == "/" and kwargs.get("dir_fd") is None:
                    raise PermissionError("root descriptor denied")
                return real_open(target, flags, *args, **kwargs)

            with patch("bugmaster_core.action_journal_store.os.open", fail_root_open):
                with self.assertRaises(ActionJournalStoreError):
                    store.open()

    def test_directory_appearing_during_create_is_opened_without_recreation(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal_store import _open_absolute_directory, _open_directory_at

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            root_fd = _open_absolute_directory(store._resolved_root, create=True)
            os.mkdir("journals", mode=0o700, dir_fd=root_fd)
            real_open = os.open
            real_mkdir = os.mkdir
            first_open = True

            def report_initial_lookup_miss(name, flags, *args, **kwargs):
                nonlocal first_open
                if name == "journals" and kwargs.get("dir_fd") == root_fd and first_open:
                    first_open = False
                    raise FileNotFoundError("directory appeared after lookup")
                return real_open(name, flags, *args, **kwargs)

            def report_directory_already_exists(name, *args, **kwargs):
                if name == "journals" and kwargs.get("dir_fd") == root_fd:
                    raise FileExistsError(name)
                return real_mkdir(name, *args, **kwargs)

            try:
                with patch("bugmaster_core.action_journal_store.os.open", report_initial_lookup_miss):
                    with patch("bugmaster_core.action_journal_store.os.mkdir", report_directory_already_exists):
                        journals_fd = _open_directory_at(
                            root_fd,
                            "journals",
                            create=True,
                            private=True,
                            repair=False,
                        )
                os.close(journals_fd)
            finally:
                os.close(root_fd)

    def test_directory_creation_sync_failure_is_reported(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(
                Path(directory) / "store", "session-1", "journal-1"
            )
            from bugmaster_core.action_journal_store import _open_absolute_directory

            root_fd = _open_absolute_directory(store._resolved_root, create=True)
            os.close(root_fd)
            with patch(
                "bugmaster_core.action_journal_store._sync_directory",
                side_effect=OSError("directory sync failed"),
            ):
                with self.assertRaises(ActionJournalStoreError):
                    store._open_store_directory(create=True)

    def test_directory_open_failure_after_creation_is_reported(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)
        from bugmaster_core.action_journal_store import _open_absolute_directory, _open_directory_at

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(
                Path(directory) / "store", "session-1", "journal-1"
            )
            root_fd = _open_absolute_directory(store._resolved_root, create=True)
            real_open = os.open
            first_open = True

            def fail_after_creation(name, flags, *args, **kwargs):
                nonlocal first_open
                if name == "journals" and kwargs.get("dir_fd") == root_fd:
                    if first_open:
                        first_open = False
                        raise FileNotFoundError("directory missing")
                    raise PermissionError("directory open denied")
                return real_open(name, flags, *args, **kwargs)

            try:
                with patch("bugmaster_core.action_journal_store.os.open", fail_after_creation):
                    with self.assertRaises(ActionJournalStoreError):
                        _open_directory_at(
                            root_fd,
                            "journals",
                            create=True,
                            private=True,
                            repair=False,
                        )
            finally:
                os.close(root_fd)

    def test_open_journal_keeps_using_pinned_root_after_ancestor_replacement(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "parent"
            parent.mkdir()
            store = ActionJournalStore(parent / "store", "session-1", "journal-1")
            journal = store.initialize()
            event = journal.prepare("action-1", "a" * 64, 1, "R0")
            outside = Path(directory) / "outside"
            outside_store = ActionJournalStore(
                outside / "store", "session-1", "journal-1"
            )
            outside_store._ensure_directories()
            outside_store.path.touch()
            moved_parent = parent.with_name("parent-original")
            parent.rename(moved_parent)
            parent.symlink_to(outside, target_is_directory=True)

            self.assertTrue(
                journal.matches_prefix(event["sequence"], event["entryHash"])
            )

    def test_closed_store_backed_journal_releases_its_directory_descriptor(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalError

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournalStore(
                directory, "session-1", "journal-1"
            ).initialize()
            directory_fd = journal._directory_fd
            journal.close()

            with self.assertRaises(OSError):
                os.fstat(directory_fd)
            with self.assertRaises(JournalError):
                journal.matches_prefix(0, None)

    def test_store_backed_journal_context_manager_closes_pinned_directory(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalError

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournalStore(
                directory, "session-1", "journal-1"
            ).initialize()

            with journal as entered:
                self.assertIs(entered, journal)
            with self.assertRaises(JournalError):
                journal.__enter__()
            with self.assertRaises(JournalError):
                journal._open_parent()
            with self.assertRaises(JournalError):
                journal.prepare("action-1", "a" * 64, 1, "R0")

    def test_journal_destructor_ignores_descriptor_close_errors(self):
        ActionJournalStore, _ = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            journal = ActionJournalStore(
                directory, "session-1", "journal-1"
            ).initialize()
            directory_fd = journal._directory_fd
            real_close = os.close

            with patch("bugmaster_core.action_journal.os.close", side_effect=OSError):
                journal.__del__()

            self.assertIsNone(journal._directory_fd)
            real_close(directory_fd)

    def test_open_rejects_a_journal_owned_by_another_user(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import ActionJournal, JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store.initialize().close()
            directory_fd = store._open_store_directory(create=False)
            expected_uid = os.geteuid() + 1

            with patch(
                "bugmaster_core.action_journal.os.geteuid",
                return_value=expected_uid,
            ):
                with self.assertRaises(JournalCorruptionError):
                    ActionJournal(
                        store.path,
                        store.session_id,
                        store.journal_id,
                        require_existing=True,
                        directory_fd=directory_fd,
                    )

    def test_initialize_rejects_a_journal_owned_by_another_user(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            initialize_journal_file = store._initialize_journal_file

            def report_another_owner(directory_fd):
                fake_stat = SimpleNamespace(
                    st_mode=stat.S_IFREG | 0o600,
                    st_uid=os.geteuid() + 1,
                    st_nlink=1,
                )
                with patch(
                    "bugmaster_core.action_journal_store.os.fstat",
                    return_value=fake_stat,
                ):
                    return initialize_journal_file(directory_fd)

            with patch.object(
                store,
                "_initialize_journal_file",
                side_effect=report_another_owner,
            ):
                with self.assertRaises(JournalCorruptionError):
                    store.initialize()

    def test_initialize_rejects_a_symlinked_journal_file(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            store._ensure_directories()
            outside = Path(directory) / "outside.jsonl"
            outside.write_text("", encoding="utf-8")
            store.path.symlink_to(outside)

            with self.assertRaises(JournalCorruptionError):
                store.initialize()

            self.assertEqual(outside.read_bytes(), b"")

    def test_initialize_rejects_a_hardlinked_file_without_changing_its_mode(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "store"
            store = ActionJournalStore(root, "session-1", "journal-1")
            store._ensure_directories()
            outside_file = Path(directory) / "outside.jsonl"
            outside_file.write_text("", encoding="utf-8")
            outside_file.chmod(0o644)
            os.link(outside_file, store.path)

            with self.assertRaises(JournalCorruptionError):
                store.initialize()

            self.assertEqual(stat.S_IMODE(outside_file.stat().st_mode), 0o644)

    def test_initialize_rejects_an_exposed_existing_file_without_repairing_its_mode(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.close()
            os.chmod(store.path, 0o644)

            with self.assertRaises(JournalCorruptionError):
                store.initialize()

            self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o644)

    def test_initialize_fails_closed_when_journal_acl_query_errors(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError
        import bugmaster_core.action_journal_store as journal_store_module

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.close()
            real_has_acl = journal_store_module._has_extended_acl

            def reject_file_acl_query(file_descriptor):
                if stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                    raise OSError("ACL query failed")
                return real_has_acl(file_descriptor)

            with patch.object(
                journal_store_module,
                "_has_extended_acl",
                side_effect=reject_file_acl_query,
            ):
                with self.assertRaises(JournalCorruptionError):
                    store.initialize()

    @unittest.skipUnless(sys.platform == "darwin", "macOS ACL enforcement only")
    def test_open_rejects_a_journal_acl_that_bypasses_private_mode_bits(self):
        ActionJournalStore, _ = _store_types(self)
        from bugmaster_core.action_journal import JournalCorruptionError

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.close()
            subprocess.run(
                ["chmod", "+a", "everyone allow read", str(store.path)],
                check=True,
                capture_output=True,
            )
            store.path.chmod(0o600)

            with self.assertRaises(JournalCorruptionError):
                ActionJournalStore(directory, "session-1", "journal-1").open()
            with self.assertRaises(JournalCorruptionError):
                store.initialize()

    @unittest.skipUnless(sys.platform == "darwin", "macOS ACL enforcement only")
    def test_open_rejects_a_directory_acl_that_bypasses_private_mode_bits(self):
        ActionJournalStore, ActionJournalStoreError = _store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = ActionJournalStore(directory, "session-1", "journal-1")
            journal = store.initialize()
            journal.close()
            subprocess.run(
                [
                    "chmod",
                    "+a",
                    "everyone allow list,search",
                    str(store._session_dir),
                ],
                check=True,
                capture_output=True,
            )
            store._session_dir.chmod(0o700)

            with self.assertRaises(ActionJournalStoreError):
                ActionJournalStore(directory, "session-1", "journal-1").open()


if __name__ == "__main__":
    unittest.main()
