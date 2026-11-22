import copy
import fcntl
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _checkpoint_store_types(test_case):
    try:
        from bugmaster_core.checkpoint_store import (
            CheckpointCorruptionError,
            CheckpointStore,
            CheckpointStoreError,
        )
    except ImportError:
        test_case.fail("Checkpoints must be durably stored as immutable local records")
    return CheckpointStore, CheckpointStoreError, CheckpointCorruptionError


def _accept_checkpoint(_document):
    return None


def _valid_checkpoint():
    return {
        "schemaVersion": "1.0",
        "checkpointId": "checkpoint-1",
        "sessionId": "session-1",
        "sessionRevision": 2,
        "scopeId": "scope-1",
        "scopeRevision": 1,
        "journalSequence": 4,
        "journalHeadHash": "a" * 64,
        "createdAt": "2026-11-19T08:00:00Z",
    }


class CheckpointStoreTests(unittest.TestCase):
    def make_store(self, root, session_id="session-1", validator=_accept_checkpoint):
        CheckpointStore, _, _ = _checkpoint_store_types(self)
        return CheckpointStore(root, session_id, validator)

    def test_create_and_read_checkpoint_returns_independent_data(self):
        CheckpointStore, _, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = CheckpointStore(directory, "session-1", _accept_checkpoint)
            checkpoint = _valid_checkpoint()
            stored = store.create(checkpoint)
            checkpoint["scopeRevision"] = 99

            self.assertEqual(stored["scopeRevision"], 1)
            self.assertEqual(store.read("checkpoint-1")["scopeRevision"], 1)
            self.assertEqual(store.read("missing-checkpoint"), None)

    def test_checkpoint_id_is_immutable(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            original = _valid_checkpoint()
            store.create(original)
            replacement = copy.deepcopy(original)
            replacement["scopeRevision"] = 2

            with self.assertRaises(CheckpointStoreError):
                store.create(replacement)
            self.assertEqual(store.read("checkpoint-1"), original)

    def test_checkpoint_must_match_the_store_session(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            checkpoint = _valid_checkpoint()
            checkpoint["sessionId"] = "other-session"

            with self.assertRaises(CheckpointStoreError):
                store.create(checkpoint)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_checkpoint_validator_rejection_happens_before_storage_creation(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)

        def reject(_document):
            raise ValueError("checkpoint schema failed")

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory, validator=reject)
            with self.assertRaises(CheckpointStoreError):
                store.create(_valid_checkpoint())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_oversized_document_is_rejected_before_json_normalization(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            oversized = _valid_checkpoint()
            oversized["extension"] = "x" * (4 * 1024 * 1024 + 1)

            with patch("bugmaster_core.checkpoint_store.json.loads") as loads:
                with self.assertRaises(CheckpointStoreError):
                    store.create(oversized)
                loads.assert_not_called()

    def test_constructor_requires_nonempty_session_id_and_callable_validator(self):
        CheckpointStore, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with self.assertRaises(CheckpointStoreError):
            CheckpointStore("unused", "", _accept_checkpoint)
        with self.assertRaises(CheckpointStoreError):
            CheckpointStore("unused", "session-1", None)

    def test_constructor_wraps_checkpoint_root_resolution_failures(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with patch.object(Path, "resolve", side_effect=OSError("resolve failed")):
            with self.assertRaises(CheckpointStoreError):
                self.make_store("unused")

    def test_constructor_wraps_session_store_root_resolution_failures(self):
        from bugmaster_core.session_store import SessionStoreError

        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with patch(
            "bugmaster_core.checkpoint_store.SessionStore",
            side_effect=SessionStoreError("root changed during resolution"),
        ):
            with self.assertRaises(CheckpointStoreError):
                self.make_store("unused")

    def test_constructor_wraps_root_permission_errors(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with patch(
            "bugmaster_core.checkpoint_store.SessionStore",
            side_effect=PermissionError("root is not searchable"),
        ):
            with self.assertRaises(CheckpointStoreError):
                self.make_store("unsearchable/store")

    def test_create_wraps_deep_document_serialization_errors(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            document = _valid_checkpoint()
            nested = document
            for _ in range(10000):
                nested["nested"] = {}
                nested = nested["nested"]

            with self.assertRaises(CheckpointStoreError):
                store.create(document)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_create_wraps_json_normalization_errors(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with patch(
                "bugmaster_core.checkpoint_store.json.loads",
                side_effect=ValueError("normalization failed"),
            ):
                with self.assertRaises(CheckpointStoreError):
                    store.create(_valid_checkpoint())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_terminal_parent_component_matches_session_store_root_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "store"
            original_store = self.make_store(root)
            original = _valid_checkpoint()
            original_store.create(original)
            store = self.make_store(root / "missing" / "..")

            self.assertEqual(store.read("checkpoint-1"), original)
            second = copy.deepcopy(original)
            second["checkpointId"] = "checkpoint-2"
            self.assertEqual(store.create(second), second)
            self.assertEqual(original_store.read("checkpoint-2"), second)
            self.assertFalse((root / "missing").exists())

    def test_checkpoint_files_are_private_on_posix(self):
        CheckpointStore, _, _ = _checkpoint_store_types(self)
        if os.name != "posix":
            self.skipTest("POSIX file permission contract")
        with tempfile.TemporaryDirectory() as directory:
            store = CheckpointStore(directory, "session-1", _accept_checkpoint)
            store.create(_valid_checkpoint())
            checkpoint_path = next(Path(directory).rglob("*.json"))
            self.assertEqual(checkpoint_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(checkpoint_path.parent.stat().st_mode & 0o777, 0o700)

    def test_read_rejects_checkpoint_directory_with_insecure_permissions(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        if os.name != "posix":
            self.skipTest("POSIX directory permission contract")
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            os.chmod(store._session_dir / "checkpoints", 0o755)

            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

    def test_read_rejects_checkpoint_directory_with_owner_only_nondefault_mode(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        if os.name != "posix":
            self.skipTest("POSIX directory permission contract")
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            os.chmod(store._checkpoints_dir, 0o500)

            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

            self.assertEqual(
                stat.S_IMODE(store._checkpoints_dir.stat().st_mode), 0o500
            )

    def test_concurrent_duplicate_writers_cannot_replace_checkpoint(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            first_store = self.make_store(directory)
            second_store = self.make_store(directory)
            barrier = threading.Barrier(2)
            outcomes = []

            def create(store, scope_revision):
                checkpoint = _valid_checkpoint()
                checkpoint["scopeRevision"] = scope_revision
                barrier.wait()
                try:
                    store.create(checkpoint)
                    outcomes.append(("created", scope_revision))
                except CheckpointStoreError:
                    outcomes.append(("rejected", scope_revision))

            writers = [
                threading.Thread(target=create, args=(first_store, 1)),
                threading.Thread(target=create, args=(second_store, 2)),
            ]
            for writer in writers:
                writer.start()
            for writer in writers:
                writer.join()

            self.assertEqual(sorted(outcome for outcome, _ in outcomes), ["created", "rejected"])
            self.assertIn(first_store.read("checkpoint-1")["scopeRevision"], (1, 2))

    def test_read_fails_closed_when_checkpoint_directory_is_dangling_symlink(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root / "store")
            store._ensure_directories()
            store._lock_path.touch(mode=0o600)
            store._checkpoints_dir.symlink_to(
                root / "missing-checkpoints", target_is_directory=True
            )

            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

    def test_read_fails_closed_when_checkpoint_file_is_malformed(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            checkpoint_path = next(Path(directory).rglob("*.json"))
            checkpoint_path.write_bytes(b"not-json\n")

            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")


    def test_rejects_non_utf8_session_and_checkpoint_ids(self):
        CheckpointStore, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with self.assertRaises(CheckpointStoreError):
            CheckpointStore("unused", "\ud800", _accept_checkpoint)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with self.assertRaises(CheckpointStoreError):
                store.read("\ud800")

    def test_rejects_invalid_document_shapes_and_json_values_before_storage(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        invalid_documents = [None]
        empty_id = _valid_checkpoint()
        empty_id["checkpointId"] = ""
        invalid_documents.append(empty_id)
        non_json = _valid_checkpoint()
        non_json["extension"] = object()
        invalid_documents.append(non_json)
        oversized = _valid_checkpoint()
        oversized["extension"] = "x" * (4 * 1024 * 1024 + 1)
        invalid_documents.append(oversized)

        for index, document in enumerate(invalid_documents):
            with self.subTest(document=index), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(CheckpointStoreError):
                    self.make_store(directory).create(document)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_read_missing_session_returns_none_without_creating_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-created"
            store = self.make_store(root)

            self.assertIsNone(store.read("checkpoint-1"))
            with self.assertRaises(_checkpoint_store_types(self)[1]):
                store.read("")
            self.assertFalse(root.exists())

            root.mkdir()
            self.assertIsNone(store.read("checkpoint-1"))
            store._sessions_dir.mkdir(mode=0o700)
            self.assertIsNone(store.read("checkpoint-1"))

    def test_read_returns_none_when_checkpoint_directory_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._ensure_directories()
            store._lock_path.touch(mode=0o600)

            self.assertIsNone(store.read("checkpoint-1"))

    def test_read_rejects_checkpoint_directory_acl_without_repair(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            checkpoint_directory = store._checkpoints_dir
            checkpoint_inode = checkpoint_directory.stat().st_ino

            def report_checkpoint_directory_acl(fd):
                return os.fstat(fd).st_ino == checkpoint_inode

            with patch(
                "bugmaster_core.session_store._has_extended_acl",
                side_effect=report_checkpoint_directory_acl,
            ), self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

            self.assertEqual(
                stat.S_IMODE(checkpoint_directory.stat().st_mode), 0o700
            )

    def test_read_rejects_checkpoint_directory_with_another_owner(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            checkpoint_inode = store._checkpoints_dir.stat().st_ino
            real_fstat = os.fstat

            def report_another_checkpoint_directory_owner(fd):
                metadata = real_fstat(fd)
                if metadata.st_ino == checkpoint_inode:
                    return SimpleNamespace(
                        st_mode=metadata.st_mode,
                        st_uid=metadata.st_uid + 1,
                    )
                return metadata

            with patch(
                "bugmaster_core.session_store.os.fstat",
                side_effect=report_another_checkpoint_directory_owner,
            ), self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

            self.assertEqual(
                stat.S_IMODE(store._checkpoints_dir.stat().st_mode), 0o700
            )

    def test_read_rejects_checkpoint_file_acl_without_repair(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            checkpoint = _valid_checkpoint()
            store.create(checkpoint)
            checkpoint_path = (
                store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            )
            checkpoint_inode = checkpoint_path.stat().st_ino

            def report_checkpoint_file_acl(fd):
                return os.fstat(fd).st_ino == checkpoint_inode

            with patch(
                "bugmaster_core.session_store._has_extended_acl",
                side_effect=report_checkpoint_file_acl,
            ), self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

            self.assertEqual(stat.S_IMODE(checkpoint_path.stat().st_mode), 0o600)

    def test_read_rejects_checkpoint_file_owned_by_another_user(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            checkpoint_path = (
                store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            )
            checkpoint_inode = checkpoint_path.stat().st_ino
            original_fstat = os.fstat

            def report_foreign_owner(fd):
                metadata = original_fstat(fd)
                if metadata.st_ino != checkpoint_inode:
                    return metadata
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_uid=os.geteuid() + 1,
                    st_nlink=metadata.st_nlink,
                    st_size=metadata.st_size,
                )

            with patch(
                "bugmaster_core.session_store.os.fstat",
                side_effect=report_foreign_owner,
            ), self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

    def test_read_rejects_checkpoint_file_hard_link_without_repair(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            store.create(_valid_checkpoint())
            checkpoint_path = (
                store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            )
            external_file = root / "outside-checkpoint"
            os.link(checkpoint_path, external_file)

            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

            self.assertEqual(stat.S_IMODE(external_file.stat().st_mode), 0o600)

    def test_read_accepts_checkpoint_file_linked_to_its_crash_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            checkpoint = store.create(_valid_checkpoint())
            checkpoint_path = (
                store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            )
            temporary_link = store._session_dir / (".checkpoint-" + "a" * 32)
            os.link(checkpoint_path, temporary_link)

            self.assertEqual(store.read("checkpoint-1"), checkpoint)

    def test_first_publication_sync_failure_preserves_temporary_link(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            session_store = store._session_store
            session_store.create(
                {
                    "schemaVersion": "1.0",
                    "sessionId": "session-1",
                    "revision": 1,
                    "status": "created",
                    "projectRef": "project-local-orders",
                    "hostRef": "codex",
                    "environmentRef": "env-isolated-test",
                    "createdAt": "2026-11-19T08:00:00Z",
                    "updatedAt": "2026-11-19T08:00:00Z",
                    "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                    "approvalRefs": [],
                    "actionBudget": {"maxActions": 20, "consumedActions": 0},
                    "journalId": "journal-session-1",
                    "checkpointRefs": [],
                }
            )
            store._checkpoints_dir.mkdir(mode=0o700)
            checkpoints_inode = store._checkpoints_dir.stat().st_ino
            original_fsync = os.fsync

            def fail_checkpoints_directory_sync(fd):
                if os.fstat(fd).st_ino == checkpoints_inode:
                    raise OSError("Checkpoint directory sync unavailable")
                return original_fsync(fd)

            with patch(
                "bugmaster_core.session_store.os.fsync",
                side_effect=fail_checkpoints_directory_sync,
            ), self.assertRaises(CheckpointStoreError):
                store.create(_valid_checkpoint())

            checkpoint_path = (
                store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            )
            temporary_links = list(store._session_dir.glob(".checkpoint-*"))
            self.assertEqual(len(temporary_links), 1)
            self.assertEqual(temporary_links[0].stat().st_ino, checkpoint_path.stat().st_ino)

            session_store.append_revision(
                {
                    "schemaVersion": "1.0",
                    "sessionId": "session-1",
                    "revision": 2,
                    "status": "created",
                    "projectRef": "project-local-orders",
                    "hostRef": "codex",
                    "environmentRef": "env-isolated-test",
                    "createdAt": "2026-11-19T08:00:00Z",
                    "updatedAt": "2026-11-19T08:01:00Z",
                    "scopeHistory": [{"scopeId": "scope-1", "revision": 1}],
                    "approvalRefs": [],
                    "actionBudget": {"maxActions": 20, "consumedActions": 0},
                    "journalId": "journal-session-1",
                    "checkpointRefs": [],
                },
                expected_revision=1,
            )

            self.assertEqual(list(store._session_dir.glob(".checkpoint-*")), [])
            self.assertEqual(store.read("checkpoint-1"), _valid_checkpoint())

    def test_read_wraps_storage_directory_inspection_failures(self):
        import bugmaster_core.checkpoint_store as checkpoint_store_module

        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            real_open = os.open

            def fail_sessions_open(path, flags, *args, **kwargs):
                if path == "sessions":
                    raise PermissionError("inspect failed")
                return real_open(path, flags, *args, **kwargs)

            with patch.object(checkpoint_store_module.os, "open", side_effect=fail_sessions_open):
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

    def test_ensure_directories_maps_session_store_errors(self):
        from bugmaster_core.session_store import SessionCorruptionError, SessionStoreError

        _, CheckpointStoreError, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with patch.object(
                store._session_store,
                "_ensure_directories",
                side_effect=SessionCorruptionError("corrupt"),
            ):
                with self.assertRaises(CheckpointCorruptionError):
                    store._ensure_directories()

            with patch.object(
                store._session_store,
                "_ensure_directories",
                side_effect=SessionStoreError("unavailable"),
            ):
                with self.assertRaises(CheckpointStoreError):
                    store._ensure_directories()

    def test_read_wraps_checkpoint_stat_and_open_races(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            filename = store._checkpoint_filename("checkpoint-1")
            real_stat = os.stat

            def fail_checkpoint_stat(path, *args, **kwargs):
                if path == filename:
                    raise PermissionError("cannot inspect record")
                return real_stat(path, *args, **kwargs)

            with patch(
                "bugmaster_core.checkpoint_store.os.stat",
                side_effect=fail_checkpoint_stat,
            ):
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

            real_open = os.open

            def remove_checkpoint_before_open(path, flags, *args, **kwargs):
                if path == filename:
                    os.unlink(path, dir_fd=kwargs["dir_fd"])
                    raise FileNotFoundError(path)
                return real_open(path, flags, *args, **kwargs)

            with patch(
                "bugmaster_core.checkpoint_store.os.open",
                side_effect=remove_checkpoint_before_open,
            ):
                self.assertIsNone(store.read("checkpoint-1"))

    def test_read_returns_none_if_storage_appears_after_missing_check(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory) / "store")
            writer = self.make_store(Path(directory) / "store")
            document = _valid_checkpoint()
            original_locked = store._locked

            @contextmanager
            def create_after_missing_check(**kwargs):
                with original_locked(**kwargs) as storage:
                    if not kwargs.get("create_directories", True) and storage is None:
                        writer.create(document)
                    yield storage

            with patch.object(store, "_locked", create_after_missing_check):
                self.assertIsNone(store.read("checkpoint-1"))
            self.assertEqual(writer.read("checkpoint-1"), document)

    def test_read_rejects_a_symlinked_parent_storage_directory(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            actual = self.make_store(base / "actual")
            actual.create(_valid_checkpoint())
            linked = self.make_store(base / "linked")
            linked.root.mkdir()
            linked._sessions_dir.symlink_to(actual._sessions_dir, target_is_directory=True)

            with self.assertRaises(CheckpointCorruptionError):
                linked.read("checkpoint-1")

    def test_store_pins_a_symlinked_ancestor_when_it_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            original_store = self.make_store(base / "original" / "data")
            redirected_store = self.make_store(base / "redirected" / "data")
            original = _valid_checkpoint()
            redirected = copy.deepcopy(original)
            redirected["scopeRevision"] = 2
            original_store.create(original)
            redirected_store.create(redirected)

            alias = base / "alias"
            alias.symlink_to(base / "original", target_is_directory=True)
            store = self.make_store(alias / "data")
            self.assertEqual(store.read("checkpoint-1"), original)

            alias.unlink()
            alias.symlink_to(base / "redirected", target_is_directory=True)

            self.assertEqual(store.read("checkpoint-1"), original)
            second = copy.deepcopy(original)
            second["checkpointId"] = "checkpoint-2"
            self.assertEqual(store.create(second), second)
            self.assertEqual(original_store.read("checkpoint-2"), second)
            self.assertIsNone(redirected_store.read("checkpoint-2"))

    def test_read_uses_the_locked_session_directory_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            original_store = self.make_store(base / "original")
            redirected_store = self.make_store(base / "redirected")
            original = _valid_checkpoint()
            redirected = copy.deepcopy(original)
            redirected["scopeRevision"] = 2
            original_store.create(original)
            redirected_store.create(redirected)
            session_path = original_store._session_dir
            moved_session = base / "moved-session"
            real_flock = fcntl.flock
            replaced = False

            def lock_then_replace_directory(fd, operation):
                nonlocal replaced
                real_flock(fd, operation)
                if operation == fcntl.LOCK_SH and not replaced:
                    session_path.rename(moved_session)
                    session_path.symlink_to(
                        redirected_store._session_dir, target_is_directory=True
                    )
                    replaced = True

            with patch(
                "bugmaster_core.session_store.fcntl.flock",
                side_effect=lock_then_replace_directory,
            ):
                self.assertEqual(original_store.read("checkpoint-1"), original)
            self.assertTrue(replaced)

    def test_create_does_not_recreate_a_missing_lock_for_persisted_checkpoints(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            store._lock_path.unlink()
            second = _valid_checkpoint()
            second["checkpointId"] = "checkpoint-2"

            with self.assertRaises(CheckpointCorruptionError):
                store.create(second)
            self.assertFalse(store._lock_path.exists())
            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-2")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipes are required")
    def test_read_rejects_fifo_session_lock_without_blocking(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._ensure_directories()
            os.mkfifo(store._lock_path, 0o600)
            script = (
                "import sys\n"
                "from bugmaster_core.checkpoint_store import CheckpointStore, CheckpointStoreError\n"
                "store = CheckpointStore(sys.argv[1], 'session-1', lambda _: None)\n"
                "try:\n"
                "    store.read('checkpoint-1')\n"
                "except CheckpointStoreError:\n"
                "    pass\n"
                "else:\n"
                "    raise SystemExit('FIFO lock was accepted')\n"
            )

            try:
                result = subprocess.run(
                    [sys.executable, "-c", script, directory],
                    cwd=Path(__file__).resolve().parents[2],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
            except subprocess.TimeoutExpired:
                self.fail("reading a Checkpoint with a FIFO lock must not block")

            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipes are required")
    def test_read_does_not_block_if_checkpoint_changes_to_fifo_before_open(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            checkpoint_path = store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            script = (
                "import os, sys\n"
                "from pathlib import Path\n"
                "from bugmaster_core.checkpoint_store import CheckpointCorruptionError, CheckpointStore\n"
                "real_open = os.open\n"
                "target = Path(sys.argv[2])\n"
                "state = {'replaced': False}\n"
                "def replace_with_fifo(path, flags, *args, **kwargs):\n"
                "    if not state['replaced'] and Path(path).name == target.name:\n"
                "        os.unlink(target)\n"
                "        os.mkfifo(target, 0o600)\n"
                "        state['replaced'] = True\n"
                "    return real_open(path, flags, *args, **kwargs)\n"
                "os.open = replace_with_fifo\n"
                "store = CheckpointStore(sys.argv[1], 'session-1', lambda _: None)\n"
                "try:\n"
                "    store.read('checkpoint-1')\n"
                "except CheckpointCorruptionError:\n"
                "    pass\n"
                "else:\n"
                "    raise SystemExit('FIFO Checkpoint was accepted')\n"
            )

            try:
                result = subprocess.run(
                    [sys.executable, "-c", script, directory, str(checkpoint_path)],
                    cwd=Path(__file__).resolve().parents[2],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
            except subprocess.TimeoutExpired:
                self.fail("opening a replaced FIFO Checkpoint must not block")

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_read_only_reader_does_not_require_write_permission_on_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            os.chmod(store._lock_path, 0o400)

            self.assertEqual(store.read("checkpoint-1"), _valid_checkpoint())
            self.assertEqual(stat.S_IMODE(store._lock_path.stat().st_mode), 0o400)

    def test_relative_root_is_fixed_when_the_store_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            original_cwd = Path.cwd()
            first = base / "first"
            second = base / "second"
            first.mkdir()
            second.mkdir()
            try:
                os.chdir(first)
                store = self.make_store("checkpoint-data")
                os.chdir(second)
                store.create(_valid_checkpoint())
            finally:
                os.chdir(original_cwd)

            self.assertTrue((first / "checkpoint-data" / "sessions").is_dir())
            self.assertFalse((second / "checkpoint-data").exists())

    def test_read_rejects_invalid_checkpoint_storage_entries(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root / "not-a-directory")
            store._ensure_directories()
            store._lock_path.touch(mode=0o600)
            store._checkpoints_dir.write_text("file", encoding="utf-8")
            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            store._ensure_directories()
            store._lock_path.touch(mode=0o600)
            store._checkpoints_dir.mkdir(mode=0o700)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            checkpoint_path = store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            checkpoint_path.symlink_to(target)
            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._ensure_directories()
            store._lock_path.touch(mode=0o600)
            store._checkpoints_dir.mkdir(mode=0o700)
            (store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")).mkdir()
            with self.assertRaises(CheckpointCorruptionError):
                store.read("checkpoint-1")

    def test_checkpoint_root_and_session_storage_paths_are_restricted(self):
        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            link = root / "linked-root"
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(CheckpointStoreError):
                self.make_store(link).create(_valid_checkpoint())

            file_root = root / "file-root"
            file_root.write_text("file", encoding="utf-8")
            with self.assertRaises(CheckpointStoreError):
                self.make_store(file_root).create(_valid_checkpoint())

            blocked_root = root / "blocked-root"
            blocked_root.mkdir()
            (blocked_root / "sessions").write_text("file", encoding="utf-8")
            with self.assertRaises(CheckpointStoreError):
                self.make_store(blocked_root).create(_valid_checkpoint())

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            import bugmaster_core.session_store as session_store_module

            real_open = os.open

            def fail_sessions_open(path, flags, *args, **kwargs):
                if path == "sessions" and "dir_fd" in kwargs:
                    raise OSError("mkdir failed")
                return real_open(path, flags, *args, **kwargs)

            with patch.object(
                session_store_module.os, "open", side_effect=fail_sessions_open
            ):
                with self.assertRaises(CheckpointStoreError):
                    store.create(_valid_checkpoint())

    def test_store_does_not_change_caller_owned_root_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o750)
            self.make_store(directory).create(_valid_checkpoint())

            self.assertEqual(Path(directory).stat().st_mode & 0o777, 0o750)

    def test_read_rejects_malformed_checkpoint_file_variants(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        corruptions = [
            (lambda path: os.chmod(path, 0o644), None),
            (lambda path: path.write_bytes(b"x" * (4 * 1024 * 1024 + 2)), 0o600),
            (lambda path: path.write_bytes(b"{}"), None),
            (lambda path: path.write_bytes(b"\xff\n"), None),
            (lambda path: path.write_text(json.dumps(_valid_checkpoint()) + "\n", encoding="utf-8"), None),
            (lambda path: path.write_bytes(b'{"value":' + b"9" * 5000 + b"}\n"), None),
            (lambda path: path.write_bytes(b"[" * 10000 + b"0" + b"]" * 10000 + b"\n"), None),
        ]
        for index, (corrupt, mode) in enumerate(corruptions):
            with self.subTest(corruption=index), tempfile.TemporaryDirectory() as directory:
                store = self.make_store(directory)
                store.create(_valid_checkpoint())
                checkpoint_path = next(store._checkpoints_dir.glob("*.json"))
                corrupt(checkpoint_path)
                if mode is not None:
                    os.chmod(checkpoint_path, mode)
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

    def test_read_limits_bytes_when_checkpoint_grows_after_fstat(self):
        _, _, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            real_read = os.read
            remaining = 4 * 1024 * 1024 + 2

            def growing_checkpoint_read(fd, size):
                nonlocal remaining
                if stat.S_ISREG(os.fstat(fd).st_mode):
                    chunk_size = min(size, remaining)
                    remaining -= chunk_size
                    return b"x" * chunk_size
                return real_read(fd, size)

            with patch("bugmaster_core.checkpoint_store.os.read", side_effect=growing_checkpoint_read):
                with self.assertRaisesRegex(CheckpointCorruptionError, "too large"):
                    store.read("checkpoint-1")

        for field, value in (("checkpointId", "checkpoint-2"), ("sessionId", "other-session")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                store = self.make_store(directory)
                store.create(_valid_checkpoint())
                checkpoint_path = next(store._checkpoints_dir.glob("*.json"))
                invalid = _valid_checkpoint()
                invalid[field] = value
                checkpoint_path.write_text(
                    json.dumps(invalid, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

    def test_lock_and_checkpoint_file_open_failures_are_wrapped(self):
        import bugmaster_core.checkpoint_store as checkpoint_store_module

        _, CheckpointStoreError, CheckpointCorruptionError = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_checkpoint())
            real_open = os.open

            def fail_lock_open(path, flags, *args, **kwargs):
                if path == "session.lock":
                    raise OSError("lock unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.checkpoint_store.os.open", side_effect=fail_lock_open):
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

            checkpoint_path = (
                store._checkpoints_dir / store._checkpoint_filename("checkpoint-1")
            )
            checkpoint_inode = checkpoint_path.stat().st_ino
            real_fstat = os.fstat

            def report_checkpoint_as_fifo(file_descriptor):
                metadata = real_fstat(file_descriptor)
                if metadata.st_ino == checkpoint_inode:
                    return SimpleNamespace(st_mode=stat.S_IFIFO)
                return metadata

            with patch(
                "bugmaster_core.checkpoint_store.os.fstat",
                side_effect=report_checkpoint_as_fifo,
            ):
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

            with patch("bugmaster_core.session_store.fcntl.flock", side_effect=OSError("lock failed")):
                with self.assertRaises(CheckpointStoreError):
                    store.read("checkpoint-1")

            real_open = os.open

            def fail_checkpoint_open(path, flags, *args, **kwargs):
                if path == store._checkpoint_filename("checkpoint-1"):
                    raise OSError("checkpoint unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.checkpoint_store.os.open", side_effect=fail_checkpoint_open):
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

    def test_storage_fails_closed_when_nofollow_flag_is_unavailable(self):
        import bugmaster_core.checkpoint_store as checkpoint_store_module

        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        real_hasattr = hasattr

        def without_nofollow(value, name):
            if value is checkpoint_store_module.os and name == "O_NOFOLLOW":
                return False
            return real_hasattr(value, name)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with patch.object(
                checkpoint_store_module,
                "hasattr",
                side_effect=without_nofollow,
                create=True,
            ):
                with self.assertRaises(CheckpointStoreError):
                    store.create(_valid_checkpoint())

    def test_write_failures_clean_up_checkpoint_temporary_files(self):
        import bugmaster_core.checkpoint_store as checkpoint_store_module

        _, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            real_fchmod = os.fchmod
            calls = 0

            def fail_checkpoint_mode(fd, mode):
                nonlocal calls
                calls += 1
                if calls == 5:
                    raise OSError("cannot secure Checkpoint")
                return real_fchmod(fd, mode)

            with patch("bugmaster_core.checkpoint_store.os.fchmod", side_effect=fail_checkpoint_mode):
                with self.assertRaises(CheckpointStoreError):
                    store.create(_valid_checkpoint())
            self.assertEqual(list(store._session_dir.glob(".checkpoint-*")), [])

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with patch("bugmaster_core.checkpoint_store.os.write", return_value=0):
                with self.assertRaises(CheckpointStoreError):
                    store.create(_valid_checkpoint())
            self.assertEqual(list(store._session_dir.glob(".checkpoint-*")), [])

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)

            def unlink_then_fail(source, _destination, *, src_dir_fd=None, **_kwargs):
                os.unlink(source, dir_fd=src_dir_fd)
                raise OSError("link failed after removing temporary file")

            with patch("bugmaster_core.checkpoint_store.os.link", side_effect=unlink_then_fail):
                with self.assertRaises(CheckpointStoreError):
                    store.create(_valid_checkpoint())
            self.assertEqual(list(store._session_dir.glob(".checkpoint-*")), [])


if __name__ == "__main__":
    unittest.main()
