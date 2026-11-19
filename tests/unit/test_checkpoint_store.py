import copy
import json
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
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

    def test_constructor_requires_nonempty_session_id_and_callable_validator(self):
        CheckpointStore, CheckpointStoreError, _ = _checkpoint_store_types(self)
        with self.assertRaises(CheckpointStoreError):
            CheckpointStore("unused", "", _accept_checkpoint)
        with self.assertRaises(CheckpointStoreError):
            CheckpointStore("unused", "session-1", None)

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
            with patch.object(Path, "mkdir", side_effect=OSError("mkdir failed")):
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
                if Path(path) == store._lock_path:
                    raise OSError("lock unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.checkpoint_store.os.open", side_effect=fail_lock_open):
                with self.assertRaises(CheckpointStoreError):
                    store.read("checkpoint-1")

            with patch(
                "bugmaster_core.checkpoint_store.os.fstat",
                return_value=type("FileStat", (), {"st_mode": stat.S_IFIFO})(),
            ):
                with self.assertRaises(CheckpointStoreError):
                    store.read("checkpoint-1")

            with patch("bugmaster_core.checkpoint_store.fcntl.flock", side_effect=OSError("lock failed")):
                with self.assertRaises(CheckpointStoreError):
                    store.read("checkpoint-1")

            real_open = os.open

            def fail_checkpoint_open(path, flags, *args, **kwargs):
                if Path(path).parent == store._checkpoints_dir:
                    raise OSError("checkpoint unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.checkpoint_store.os.open", side_effect=fail_checkpoint_open):
                with self.assertRaises(CheckpointCorruptionError):
                    store.read("checkpoint-1")

    def test_read_falls_back_when_nofollow_flag_is_unavailable(self):
        import bugmaster_core.checkpoint_store as checkpoint_store_module

        real_hasattr = hasattr

        def without_nofollow(value, name):
            if value is checkpoint_store_module.os and name == "O_NOFOLLOW":
                return False
            return real_hasattr(value, name)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            checkpoint = _valid_checkpoint()
            with patch.object(
                checkpoint_store_module,
                "hasattr",
                side_effect=without_nofollow,
                create=True,
            ):
                store.create(checkpoint)
                self.assertEqual(store.read("checkpoint-1"), checkpoint)

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
                if calls == 2:
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

            def unlink_then_fail(source, _destination):
                Path(source).unlink()
                raise OSError("link failed after removing temporary file")

            with patch("bugmaster_core.checkpoint_store.os.link", side_effect=unlink_then_fail):
                with self.assertRaises(CheckpointStoreError):
                    store.create(_valid_checkpoint())
            self.assertEqual(list(store._session_dir.glob(".checkpoint-*")), [])


if __name__ == "__main__":
    unittest.main()
