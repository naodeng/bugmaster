import copy
import fcntl
import gc
import json
import os
import stat
import tempfile
import threading
import tracemalloc
import unittest
from pathlib import Path
from unittest.mock import patch

def _session_store_types(test_case):
    try:
        from bugmaster_core.session_store import (
            SessionCorruptionError,
            SessionStore,
            SessionStoreError,
        )
    except ImportError:
        test_case.fail(
            "Session revisions must be stored immutably and read back fail-closed"
        )
    return SessionStore, SessionStoreError, SessionCorruptionError


def _accept_session(_document):
    return None


def _valid_session():
    return {
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
        "approvalRefs": [
            {
                "approvalId": "approval-1",
                "scopeId": "scope-1",
                "scopeRevision": 1,
            }
        ],
        "actionBudget": {"maxActions": 20, "consumedActions": 0},
        "journalId": "journal-session-1",
        "checkpointRefs": ["checkpoint-1"],
    }


def _next_revision(document, **changes):
    result = copy.deepcopy(document)
    result["revision"] += 1
    result["updatedAt"] = "2026-11-19T08:01:00Z"
    result.update(changes)
    return result


class SessionStoreTests(unittest.TestCase):
    def make_store(self, root, session_id="session-1"):
        SessionStore, _, _ = _session_store_types(self)
        return SessionStore(root, session_id, _accept_session)

    def test_create_persists_revision_one_and_returns_independent_data(self):
        SessionStore, _, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(directory, "session-1", _accept_session)
            document = _valid_session()
            returned = store.create(document)
            document["status"] = "failed"

            self.assertEqual(returned["revision"], 1)
            self.assertEqual(store.read_revision(1)["status"], "created")
            self.assertEqual(store.read_latest()["sessionId"], "session-1")

    def test_long_session_id_keeps_the_persisted_head_readable(self):
        session_id = "s" * 1000
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory), session_id)
            first = _valid_session()
            first["sessionId"] = session_id
            first["journalId"] = "journal-long-session-id"

            store.create(first)

            self.assertEqual(store.read_latest(), first)
            second = _next_revision(first, status="ready")
            store.append_revision(second, expected_revision=1)
            self.assertEqual(store.read_latest(), second)

    def test_create_recovers_initial_revision_after_head_publication_failure(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()

            with patch.object(
                store,
                "_write_head_locked",
                side_effect=SessionStoreError("head publication failed"),
            ):
                with self.assertRaises(SessionStoreError):
                    store.create(first)

            self.assertEqual(store.create(first), first)
            self.assertEqual(store.read_latest(), first)

    def test_create_does_not_publish_a_different_interrupted_initial_revision(self):
        import bugmaster_core.session_store as module

        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            with patch.object(
                store,
                "_write_head_locked",
                side_effect=SessionStoreError("head publication failed"),
            ), self.assertRaises(SessionStoreError):
                store.create(first)

            different = copy.deepcopy(first)
            different["actionBudget"]["consumedActions"] = 1
            (store._revisions_dir / "00000001.json").write_bytes(
                module._canonical_bytes(different) + b"\n"
            )

            with self.assertRaisesRegex(
                SessionStoreError, "differs from create request"
            ):
                store.create(first)

            self.assertFalse(store._head_path.exists())

    def test_initial_recovery_syncs_revision_directory_before_publishing_head(self):
        import bugmaster_core.session_store as module

        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._ensure_directories()
            store._lock_path.touch(mode=0o600)
            first = _valid_session()
            revisions_stat = store._revisions_dir.stat()
            real_fsync_directory = module._fsync_directory_fd

            def fail_revision_fsync(directory_fd):
                current_stat = os.fstat(directory_fd)
                if (
                    current_stat.st_dev == revisions_stat.st_dev
                    and current_stat.st_ino == revisions_stat.st_ino
                ):
                    raise OSError("revision directory sync failed")
                return real_fsync_directory(directory_fd)

            with patch(
                "bugmaster_core.session_store._fsync_directory_fd",
                side_effect=fail_revision_fsync,
            ), self.assertRaises(SessionStoreError):
                store.create(first)

            events = []
            real_replace = os.replace

            def record_revision_fsync(directory_fd):
                current_stat = os.fstat(directory_fd)
                if (
                    current_stat.st_dev == revisions_stat.st_dev
                    and current_stat.st_ino == revisions_stat.st_ino
                ):
                    events.append("revision-directory-fsync")
                return real_fsync_directory(directory_fd)

            def record_head_replace(source, destination, **kwargs):
                if destination == "session.head":
                    events.append("head-replace")
                return real_replace(source, destination, **kwargs)

            with patch(
                "bugmaster_core.session_store._fsync_directory_fd",
                side_effect=record_revision_fsync,
            ), patch(
                "bugmaster_core.session_store.os.replace",
                side_effect=record_head_replace,
            ):
                self.assertEqual(store.create(first), first)

            self.assertIn("revision-directory-fsync", events)
            self.assertLess(
                events.index("revision-directory-fsync"),
                events.index("head-replace"),
            )

    def test_append_keeps_previous_revision_immutable(self):
        _, _, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(first, status="ready")

            stored = store.append_revision(second, expected_revision=1)

            self.assertEqual(stored["revision"], 2)
            self.assertEqual(store.read_revision(1), first)
            self.assertEqual(store.read_latest(), second)

    def test_create_rejects_a_second_initial_revision(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            with self.assertRaises(SessionStoreError):
                store.create(_valid_session())

    def test_stale_expected_revision_cannot_replace_latest(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            store.append_revision(
                _next_revision(first, status="ready"), expected_revision=1
            )

            with self.assertRaises(SessionStoreError):
                store.append_revision(
                    _next_revision(first, status="paused"), expected_revision=1
                )
            self.assertEqual(store.read_latest()["status"], "ready")

    def test_validator_rejection_happens_before_creating_storage(self):
        _, SessionStoreError, _ = _session_store_types(self)

        def reject(_document):
            raise ValueError("session contract failed")

        with tempfile.TemporaryDirectory() as directory:
            SessionStore, _, _ = _session_store_types(self)
            store = SessionStore(directory, "session-1", reject)

            with self.assertRaises(SessionStoreError):
                store.create(_valid_session())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_session_store_requires_a_callable_validator(self):
        SessionStore, SessionStoreError, _ = _session_store_types(self)
        with self.assertRaises(SessionStoreError):
            SessionStore("unused", "session-1", None)

    def test_session_document_must_match_the_store_identity(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            invalid = _valid_session()
            invalid["sessionId"] = "different-session"

            with self.assertRaises(SessionStoreError):
                store.create(invalid)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_session_revision_rejects_boolean_and_nonpositive_values(self):
        _, SessionStoreError, _ = _session_store_types(self)
        for revision in (True, 0, -1, "1"):
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as directory:
                store = self.make_store(directory)
                invalid = _valid_session()
                invalid["revision"] = revision
                with self.assertRaises(SessionStoreError):
                    store.create(invalid)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_session_identity_and_journal_binding_are_immutable(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(first, journalId="other-journal")

            with self.assertRaises(SessionStoreError):
                store.append_revision(second, expected_revision=1)
            self.assertEqual(store.read_latest(), first)

    def test_scope_history_rejects_duplicate_and_backward_revisions(self):
        _, SessionStoreError, _ = _session_store_types(self)
        duplicate = _valid_session()
        duplicate["approvalRefs"] = []
        duplicate["scopeHistory"] = [
            {"scopeId": "scope-1", "revision": 1},
            {"scopeId": "scope-1", "revision": 1},
        ]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SessionStoreError):
                self.make_store(directory).create(duplicate)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            first["approvalRefs"] = []
            first["scopeHistory"] = [{"scopeId": "scope-1", "revision": 2}]
            store.create(first)
            backwards = _next_revision(
                first,
                scopeHistory=first["scopeHistory"]
                + [{"scopeId": "scope-1", "revision": 1}],
            )
            with self.assertRaises(SessionStoreError):
                store.append_revision(backwards, expected_revision=1)

    def test_scope_revision_history_cannot_be_removed_or_reordered(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(
                first,
                scopeHistory=[{"scopeId": "different-scope", "revision": 1}],
            )

            with self.assertRaises(SessionStoreError):
                store.append_revision(second, expected_revision=1)

    def test_approval_references_cannot_be_removed(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(first, approvalRefs=[])

            with self.assertRaises(SessionStoreError):
                store.append_revision(second, expected_revision=1)

    def test_checkpoint_references_cannot_be_removed(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(first, checkpointRefs=[])

            with self.assertRaises(SessionStoreError):
                store.append_revision(second, expected_revision=1)

    def test_consumed_action_budget_cannot_decrease(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            first["actionBudget"]["consumedActions"] = 2
            store.create(first)
            second = _next_revision(
                first,
                actionBudget={"maxActions": 20, "consumedActions": 1},
            )

            with self.assertRaises(SessionStoreError):
                store.append_revision(second, expected_revision=1)

    def test_read_fails_closed_when_a_persisted_revision_is_invalid(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            revision_path = next(Path(directory).rglob("*.json"))
            stored = json.loads(revision_path.read_text(encoding="utf-8"))
            stored["status"] = "not-a-session-state"
            revision_path.write_text(json.dumps(stored), encoding="utf-8")

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_read_fails_closed_when_revision_sequence_has_a_gap(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            store.append_revision(
                _next_revision(first, status="ready"), expected_revision=1
            )
            revision_one = next(
                path
                for path in Path(directory).rglob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["revision"] == 1
            )
            revision_one.unlink()

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_read_fails_closed_when_persisted_history_breaks_immutable_identity(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            store.append_revision(
                _next_revision(first, status="ready"), expected_revision=1
            )
            revision_one = next(
                path
                for path in Path(directory).rglob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["revision"] == 1
            )
            corrupted = json.loads(revision_one.read_text(encoding="utf-8"))
            corrupted["journalId"] = "substituted-journal"
            revision_one.write_text(
                json.dumps(corrupted, sort_keys=True, separators=(",", ":")) + chr(10),
                encoding="utf-8",
            )

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_read_rejects_an_oversized_head_before_reading_its_contents(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            store._head_path.write_bytes(b"x" * (4 * 1024 * 1024 + 1025))

            with self.assertRaisesRegex(SessionCorruptionError, "head is too large"):
                store.read_latest()

    @unittest.skipUnless(os.name == "posix", "POSIX file permission contract")
    def test_session_revision_files_are_private_on_posix(self):
        SessionStore, _, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(directory, "session-1", _accept_session)
            store.create(_valid_session())
            revision_path = next(Path(directory).rglob("*.json"))
            self.assertEqual(revision_path.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX file permission contract")
    def test_store_does_not_change_caller_owned_root_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o750)
            store = self.make_store(directory)
            store.create(_valid_session())

            self.assertEqual(Path(directory).stat().st_mode & 0o777, 0o750)

    def test_concurrent_writers_cannot_both_append_the_same_revision(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            first_store = self.make_store(directory)
            second_store = self.make_store(directory)
            first = _valid_session()
            first_store.create(first)
            barrier = threading.Barrier(2)
            outcomes = []

            def append(store, status):
                barrier.wait()
                try:
                    result = store.append_revision(
                        _next_revision(first, status=status), expected_revision=1
                    )
                    outcomes.append(("success", result["revision"]))
                except SessionStoreError:
                    outcomes.append(("rejected", None))

            threads = [
                threading.Thread(target=append, args=(first_store, "ready")),
                threading.Thread(target=append, args=(second_store, "paused")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertCountEqual(
                outcomes, [("success", 2), ("rejected", None)]
            )
            self.assertEqual(first_store.read_latest()["revision"], 2)

    def test_budget_ceiling_cannot_increase_without_scope_revision(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(
                first,
                actionBudget={"maxActions": 30, "consumedActions": 0},
            )

            with self.assertRaises(SessionStoreError):
                store.append_revision(second, expected_revision=1)

    def test_budget_ceiling_can_change_only_with_new_scope_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(
                first,
                scopeHistory=first["scopeHistory"]
                + [{"scopeId": "scope-2", "revision": 1}],
                actionBudget={"maxActions": 30, "consumedActions": 0},
            )

            self.assertEqual(
                store.append_revision(second, expected_revision=1), second
            )


    def test_rejects_invalid_session_document_shapes_and_json_values(self):
        _, SessionStoreError, _ = _session_store_types(self)
        invalid_documents = [None]
        invalid_mutations = [
            lambda document: document.update(scopeHistory=[]),
            lambda document: document.update(scopeHistory="scope"),
            lambda document: document.update(approvalRefs=None),
            lambda document: document.update(checkpointRefs=None),
            lambda document: document.update(actionBudget=[]),
            lambda document: document.update(scopeHistory=[None]),
            lambda document: document.update(scopeHistory=[{"scopeId": "", "revision": 1}]),
            lambda document: document.update(approvalRefs=[None]),
            lambda document: document.update(approvalRefs=[{"approvalId": "missing"}]),
            lambda document: document.update(checkpointRefs=[""]),
            lambda document: document.update(journalId=""),
            lambda document: document.update(actionBudget={"maxActions": 10}),
            lambda document: document.update(actionBudget={"maxActions": True, "consumedActions": 0}),
            lambda document: document.update(actionBudget={"maxActions": 10, "consumedActions": 11}),
            lambda document: document.update(extension=object()),
            lambda document: document.update(extension="x" * (4 * 1024 * 1024 + 1)),
        ]
        for mutation in invalid_mutations:
            document = _valid_session()
            mutation(document)
            invalid_documents.append(document)

        for index, document in enumerate(invalid_documents):
            with self.subTest(document=index), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(SessionStoreError):
                    self.make_store(directory).create(document)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_create_and_append_require_sequential_revisions(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            invalid_initial = _valid_session()
            invalid_initial["revision"] = 2
            with self.assertRaises(SessionStoreError):
                store.create(invalid_initial)

            first = _valid_session()
            store.create(first)
            with self.assertRaises(SessionStoreError):
                store.append_revision(_next_revision(first, revision=3), expected_revision=1)
            for expected in (True, 0, -1, "1"):
                with self.subTest(expected=expected), self.assertRaises(SessionStoreError):
                    store.append_revision(_next_revision(first), expected_revision=expected)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with self.assertRaises(SessionStoreError):
                store.append_revision(_next_revision(_valid_session()), expected_revision=1)

    def test_constructor_rejects_empty_and_non_utf8_session_ids(self):
        SessionStore, SessionStoreError, _ = _session_store_types(self)
        for session_id in ("", "   "):
            with self.subTest(session_id=session_id), self.assertRaises(SessionStoreError):
                SessionStore("unused", session_id, _accept_session)
        with self.assertRaises(SessionStoreError):
            SessionStore("unused", "\ud800", _accept_session)

    def test_read_revision_rejects_nonpositive_and_noninteger_values(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            for revision in (True, 0, -1, "1"):
                with self.subTest(revision=revision), self.assertRaises(SessionStoreError):
                    store.read_revision(revision)

    def test_reading_early_revision_keeps_memory_bounded_for_long_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            current = _valid_session()
            current["padding"] = "x" * (1024 * 1024)
            store.create(current)
            for _ in range(19):
                current = _next_revision(current, status="ready")
                store.append_revision(
                    current, expected_revision=current["revision"] - 1
                )
            del current
            gc.collect()

            tracemalloc.start()
            try:
                revision = store.read_revision(1)
                _, peak_bytes = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

            self.assertEqual(revision["revision"], 1)
            self.assertLess(peak_bytes, 16 * 1024 * 1024)

    def test_new_budget_counter_starts_at_zero_with_new_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            first["actionBudget"] = {}
            store.create(first)
            second = _next_revision(
                first,
                scopeHistory=first["scopeHistory"]
                + [{"scopeId": "scope-2", "revision": 1}],
                actionBudget={"maxActions": 10, "consumedActions": 0},
            )

            self.assertEqual(store.append_revision(second, expected_revision=1), second)
            self.assertEqual(store.read_latest(), second)

    def test_storage_falls_back_when_nofollow_open_flag_is_unavailable(self):
        import bugmaster_core.session_store as session_store_module

        real_hasattr = hasattr

        def without_nofollow(value, name):
            if value is session_store_module.os and name == "O_NOFOLLOW":
                return False
            return real_hasattr(value, name)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            document = _valid_session()
            with patch.object(
                session_store_module,
                "hasattr",
                side_effect=without_nofollow,
                create=True,
            ):
                store.create(document)
                self.assertEqual(store.read_latest(), document)

    def test_new_budget_counter_requires_new_scope_and_starts_at_zero(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            first["actionBudget"] = {}
            store.create(first)
            without_new_scope = _next_revision(
                first, actionBudget={"maxActions": 10, "consumedActions": 0}
            )
            with self.assertRaises(SessionStoreError):
                store.append_revision(without_new_scope, expected_revision=1)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            first["actionBudget"] = {}
            store.create(first)
            nonzero_new_counter = _next_revision(
                first,
                scopeHistory=first["scopeHistory"] + [{"scopeId": "scope-2", "revision": 1}],
                actionBudget={"maxActions": 10, "consumedActions": 1},
            )
            with self.assertRaises(SessionStoreError):
                store.append_revision(nonzero_new_counter, expected_revision=1)

    def test_missing_store_and_revision_reads_return_none(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory) / "not-created")
            self.assertIsNone(store.read_latest())
            self.assertIsNone(store.read_revision(1))
            store.create(_valid_session())
            self.assertIsNone(store.read_revision(2))

    def test_read_latest_fails_closed_when_the_latest_revision_is_missing(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            second = _next_revision(first, status="ready")
            store.append_revision(second, expected_revision=1)
            (store._revisions_dir / "00000002.json").unlink()

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_append_cannot_reuse_a_missing_revision_and_reset_its_budget(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            consumed = _next_revision(
                first,
                status="ready",
                actionBudget={"maxActions": 20, "consumedActions": 5},
            )
            store.append_revision(consumed, expected_revision=1)
            (store._revisions_dir / "00000002.json").unlink()
            reset = _next_revision(first, status="paused")

            with self.assertRaises(SessionCorruptionError):
                store.append_revision(reset, expected_revision=1)

    def test_read_latest_rejects_a_dangling_revision_directory_symlink(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            store = self.make_store(base / "store")
            store.create(_valid_session())
            for revision_path in store._revisions_dir.iterdir():
                revision_path.unlink()
            store._revisions_dir.rmdir()
            store._revisions_dir.symlink_to(base / "missing", target_is_directory=True)

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_read_latest_rejects_a_symlinked_session_directory(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            actual = self.make_store(base / "actual")
            actual.create(_valid_session())
            linked = self.make_store(base / "linked")
            linked._sessions_dir.mkdir(parents=True)
            linked._session_dir.symlink_to(actual._session_dir, target_is_directory=True)

            with self.assertRaises(SessionCorruptionError):
                linked.read_latest()

    def test_read_latest_uses_the_directory_that_owns_the_acquired_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            store = self.make_store(base / "store")
            original = _valid_session()
            original["actionBudget"]["consumedActions"] = 12
            store.create(original)

            attacker_store = self.make_store(base / "attacker")
            attacker = _valid_session()
            attacker["actionBudget"]["consumedActions"] = 0
            attacker_store.create(attacker)

            sessions_dir = store._sessions_dir
            moved_sessions_dir = base / "store-sessions"
            real_flock = fcntl.flock
            swapped = False

            def swap_after_lock(fd, operation):
                nonlocal swapped
                real_flock(fd, operation)
                if operation == fcntl.LOCK_SH and not swapped:
                    sessions_dir.rename(moved_sessions_dir)
                    sessions_dir.symlink_to(
                        attacker_store._sessions_dir, target_is_directory=True
                    )
                    swapped = True

            with patch("bugmaster_core.session_store.fcntl.flock", side_effect=swap_after_lock):
                result = store.read_latest()

            self.assertTrue(swapped)
            self.assertEqual(result["actionBudget"]["consumedActions"], 12)

    def test_read_opens_revisions_after_waiting_for_initial_create_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)
            store._lock_path.touch(mode=0o600)
            reader_at_lock = threading.Event()
            release_reader = threading.Event()
            result = {}
            errors = []
            real_flock = fcntl.flock

            def pause_shared_reader(fd, operation):
                if (
                    operation == fcntl.LOCK_SH
                    and threading.current_thread().name == "initial-create-reader"
                ):
                    reader_at_lock.set()
                    if not release_reader.wait(5):
                        raise TimeoutError("reader lock was not released")
                return real_flock(fd, operation)

            def read_in_thread():
                try:
                    result["document"] = store.read_latest()
                except Exception as error:
                    errors.append(error)

            reader = threading.Thread(
                target=read_in_thread, name="initial-create-reader"
            )
            with patch(
                "bugmaster_core.session_store.fcntl.flock",
                side_effect=pause_shared_reader,
            ):
                reader.start()
                self.assertTrue(reader_at_lock.wait(5))
                first = _valid_session()
                store.create(first)
                release_reader.set()
                reader.join(5)

            self.assertFalse(reader.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(result["document"], first)

    def test_read_latest_tolerates_empty_session_directory_before_lock_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)

            self.assertIsNone(store.read_latest())
            self.assertFalse(store._lock_path.exists())

    def test_read_latest_rejects_persisted_data_when_session_lock_is_missing(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            store._lock_path.unlink()

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_append_rejects_persisted_session_when_lock_is_missing(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            store._lock_path.unlink()

            with self.assertRaises(SessionCorruptionError):
                store.append_revision(
                    _next_revision(first, status="ready"), expected_revision=1
                )

            self.assertFalse(store._lock_path.exists())

    def test_create_recovers_empty_session_directory_without_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)

            self.assertEqual(store.create(_valid_session()), _valid_session())
            self.assertTrue(store._lock_path.is_file())

    def test_create_recovers_legacy_empty_revisions_directory_without_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._revisions_dir.mkdir(parents=True)

            self.assertEqual(store.create(_valid_session()), _valid_session())
            self.assertTrue(store._lock_path.is_file())

    def test_read_returns_none_for_legacy_empty_revisions_directory_without_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._revisions_dir.mkdir(parents=True)

            self.assertIsNone(store.read_latest())

    def test_read_reopens_lock_if_legacy_revision_appears_after_directory_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._revisions_dir.mkdir(parents=True)
            first = _valid_session()
            session_stat = store._session_dir.stat()
            real_scandir = os.scandir
            injected = False

            class SnapshotScan:
                def __init__(self, names):
                    self.names = names

                def __enter__(self):
                    return iter(SnapshotEntry(name) for name in self.names)

                @staticmethod
                def __exit__(exc_type, exc_value, traceback):
                    return False

            class SnapshotEntry:
                def __init__(self, name):
                    self.name = name

            def create_after_session_listing(directory_fd):
                nonlocal injected
                current_stat = os.fstat(directory_fd)
                if (
                    not injected
                    and current_stat.st_dev == session_stat.st_dev
                    and current_stat.st_ino == session_stat.st_ino
                ):
                    with real_scandir(directory_fd) as entries:
                        names = [entry.name for entry in entries]
                    injected = True
                    store.create(first)
                    return SnapshotScan(names)
                return real_scandir(directory_fd)

            with patch(
                "bugmaster_core.session_store.os.scandir",
                side_effect=create_after_session_listing,
            ):
                self.assertEqual(store.read_latest(), first)

    def test_read_fails_closed_if_legacy_revisions_directory_disappears(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        import bugmaster_core.session_store as module

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._revisions_dir.mkdir(parents=True)
            real_open_child = module._open_child_directory

            def report_removed_revisions(parent_fd, name, **kwargs):
                if name == "revisions" and not kwargs["create"]:
                    return None
                return real_open_child(parent_fd, name, **kwargs)

            with patch(
                "bugmaster_core.session_store._open_child_directory",
                side_effect=report_removed_revisions,
            ), self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_read_fails_closed_if_legacy_revisions_scan_fails(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._revisions_dir.mkdir(parents=True)
            revisions_stat = store._revisions_dir.stat()
            real_scandir = os.scandir

            def fail_revisions_scan(directory_fd):
                current_stat = os.fstat(directory_fd)
                if (
                    current_stat.st_dev == revisions_stat.st_dev
                    and current_stat.st_ino == revisions_stat.st_ino
                ):
                    raise OSError("revision scan failed")
                return real_scandir(directory_fd)

            with patch(
                "bugmaster_core.session_store.os.scandir",
                side_effect=fail_revisions_scan,
            ), self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_read_reports_lock_reopen_permission_error_for_nonempty_legacy_directory(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._revisions_dir.mkdir(parents=True)
            (store._revisions_dir / "interrupted-write").write_bytes(b"pending")
            real_open = os.open
            lock_open_attempts = 0

            def fail_lock_reopen(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal lock_open_attempts
                if path == "session.lock":
                    lock_open_attempts += 1
                    if lock_open_attempts == 1:
                        raise FileNotFoundError(path)
                    raise PermissionError("lock reopen denied")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=fail_lock_reopen,
            ), self.assertRaisesRegex(SessionCorruptionError, "cannot open Session lock"):
                store.read_latest()

            self.assertEqual(lock_open_attempts, 2)

    def test_read_reopens_lock_created_after_initial_missing_lock_check(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)
            real_open = os.open
            lock_open_attempts = 0

            def create_lock_after_missed_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal lock_open_attempts
                if path == "session.lock":
                    lock_open_attempts += 1
                    if lock_open_attempts == 1:
                        created_fd = real_open(
                            path,
                            os.O_CREAT | os.O_EXCL | os.O_RDWR,
                            0o600,
                            dir_fd=dir_fd,
                        )
                        os.close(created_fd)
                        raise FileNotFoundError(path)
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=create_lock_after_missed_open,
            ):
                self.assertIsNone(store.read_latest())

            self.assertEqual(lock_open_attempts, 2)

    def test_read_reports_lock_that_disappears_during_retry(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)
            store._lock_path.touch(mode=0o600)
            real_open = os.open
            lock_open_attempts = 0

            def fail_lock_reopen(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal lock_open_attempts
                if path == "session.lock":
                    lock_open_attempts += 1
                    if lock_open_attempts == 1:
                        raise FileNotFoundError(path)
                    raise PermissionError("lock changed during retry")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=fail_lock_reopen,
            ), self.assertRaises(SessionCorruptionError):
                store.read_latest()

            self.assertEqual(lock_open_attempts, 2)

    def test_create_reopens_lock_won_by_a_concurrent_initializer(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)
            real_open = os.open
            lock_open_attempts = 0

            def win_lock_creation_race(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal lock_open_attempts
                if path == "session.lock":
                    lock_open_attempts += 1
                    if lock_open_attempts == 1:
                        raise FileNotFoundError(path)
                    if flags & os.O_EXCL:
                        created_fd = real_open(
                            path,
                            flags,
                            mode,
                            dir_fd=dir_fd,
                        )
                        os.close(created_fd)
                        raise FileExistsError(path)
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=win_lock_creation_race,
            ):
                self.assertEqual(store.create(_valid_session()), _valid_session())

            self.assertEqual(lock_open_attempts, 3)

    def test_create_reports_lock_creation_error_after_empty_directory_scan(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)
            real_open = os.open

            def fail_lock_creation(path, flags, mode=0o777, *, dir_fd=None):
                if path == "session.lock":
                    if flags & os.O_CREAT:
                        raise PermissionError("lock creation denied")
                    raise FileNotFoundError(path)
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=fail_lock_creation,
            ), self.assertRaisesRegex(SessionStoreError, "cannot create Session lock"):
                store.create(_valid_session())

    def test_create_reports_reopen_error_after_concurrent_lock_creation(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)
            real_open = os.open
            lock_open_attempts = 0

            def fail_lock_reopen(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal lock_open_attempts
                if path == "session.lock":
                    lock_open_attempts += 1
                    if lock_open_attempts == 1:
                        raise FileNotFoundError(path)
                    if flags & os.O_EXCL:
                        created_fd = real_open(
                            path, flags, mode, dir_fd=dir_fd
                        )
                        os.close(created_fd)
                        raise FileExistsError(path)
                    if flags & os.O_CREAT:
                        raise FileNotFoundError(path)
                    raise PermissionError("lock reopen denied")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=fail_lock_reopen,
            ), self.assertRaisesRegex(SessionStoreError, "cannot open Session lock"):
                store.create(_valid_session())

            self.assertEqual(lock_open_attempts, 3)

    def test_read_fails_closed_when_session_scan_fails_without_a_lock(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)

            with patch(
                "bugmaster_core.session_store.os.scandir",
                side_effect=OSError("cannot inspect Session directory"),
            ), self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_storage_directory_creation_errors_use_store_error(self):
        _, SessionStoreError, _ = _session_store_types(self)

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory) / "missing-root")
            with patch(
                "bugmaster_core.session_store.os.mkdir",
                side_effect=PermissionError("root mkdir denied"),
            ), self.assertRaises(SessionStoreError):
                store.create(_valid_session())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            store = self.make_store(root)
            with patch(
                "bugmaster_core.session_store.os.mkdir",
                side_effect=PermissionError("child mkdir denied"),
            ), self.assertRaises(SessionStoreError):
                store.create(_valid_session())

    def test_root_directory_reopen_error_uses_store_error(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing-root"
            store = self.make_store(root)
            real_open = os.open
            root_open_attempts = 0

            def fail_root_reopen(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal root_open_attempts
                if path == root.name:
                    root_open_attempts += 1
                    if root_open_attempts == 1:
                        raise FileNotFoundError(path)
                    raise PermissionError("root changed before reopen")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=fail_root_reopen,
            ), self.assertRaises(SessionStoreError):
                store.create(_valid_session())

    def test_head_binds_every_historical_revision(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            first["actionBudget"]["consumedActions"] = 5
            store.create(first)
            second = _next_revision(
                first,
                status="ready",
                actionBudget={"maxActions": 20, "consumedActions": 7},
            )
            store.append_revision(second, expected_revision=1)

            revision_one = store._revisions_dir / "00000001.json"
            rewritten = json.loads(revision_one.read_text(encoding="utf-8"))
            rewritten["actionBudget"]["consumedActions"] = 0
            revision_one.write_text(
                json.dumps(
                    rewritten, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()
            with self.assertRaises(SessionCorruptionError):
                store.read_revision(1)

    def test_uncommitted_revision_after_head_write_failure_is_recoverable(self):
        SessionStore, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(directory, "session-1", _accept_session)
            first = _valid_session()
            store.create(first)
            second = _next_revision(first, status="ready")

            def fail_head_write(*args, **kwargs):
                raise SessionStoreError("head publication failed")

            with patch.object(store, "_write_head_locked", side_effect=fail_head_write):
                with self.assertRaises(SessionStoreError):
                    store.append_revision(second, expected_revision=1)

            self.assertEqual(store.read_latest(), first)
            self.assertEqual(
                store.append_revision(second, expected_revision=1), second
            )
            self.assertEqual(store.read_latest(), second)

    def test_constructor_rejects_unresolvable_storage_root(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, "resolve", side_effect=RuntimeError("symlink loop")):
                with self.assertRaises(SessionStoreError):
                    self.make_store(Path(directory) / "store")

    def test_parent_symlink_retarget_does_not_redirect_existing_store(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first_target = base / "first-target"
            second_target = base / "second-target"
            first_target.mkdir()
            second_target.mkdir()
            alias = base / "alias"
            alias.symlink_to(first_target, target_is_directory=True)
            store = self.make_store(alias / "session-data")
            store.create(_valid_session())

            alias.unlink()
            alias.symlink_to(second_target, target_is_directory=True)

            self.assertEqual(store.read_latest(), _valid_session())
            self.assertTrue((first_target / "session-data" / "sessions").is_dir())
            self.assertFalse((second_target / "session-data").exists())

    def test_storage_root_swap_after_symlink_check_is_not_resolved_to_target(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "store"
            root.mkdir()
            moved_root = base / "store-original"
            attacker_root = base / "attacker"
            attacker_root.mkdir()
            real_is_symlink = Path.is_symlink

            def swap_root_after_check(path):
                if path == root:
                    root.rename(moved_root)
                    root.symlink_to(attacker_root, target_is_directory=True)
                    return False
                return real_is_symlink(path)

            with patch.object(Path, "is_symlink", new=swap_root_after_check):
                store = self.make_store(root)

            with self.assertRaises(SessionStoreError):
                store.create(_valid_session())
            self.assertFalse((attacker_root / "sessions").exists())

    def test_root_with_missing_component_then_parent_still_resolves_existing_store(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "store"
            store = self.make_store(root)
            first = _valid_session()
            store.create(first)

            alias = self.make_store(root / "absent-component" / "..")

            self.assertEqual(alias.read_latest(), first)
            with self.assertRaises(SessionStoreError):
                alias.create(first)
            self.assertFalse((root / "absent-component").exists())

    def test_fsync_directory_keeps_path_argument_compatibility(self):
        import bugmaster_core.session_store as module

        with tempfile.TemporaryDirectory() as directory:
            module._fsync_directory(Path(directory))

    def test_retry_syncs_parent_after_initial_storage_root_fsync_failure(self):
        import bugmaster_core.session_store as module

        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new-root"
            store = self.make_store(root)
            parent_stat = Path(directory).stat()
            real_fsync_directory = module._fsync_directory_fd
            failed_once = False

            def fail_first_parent_sync(directory_fd):
                nonlocal failed_once
                current_stat = os.fstat(directory_fd)
                if (
                    not failed_once
                    and current_stat.st_dev == parent_stat.st_dev
                    and current_stat.st_ino == parent_stat.st_ino
                ):
                    failed_once = True
                    raise OSError("root parent sync failed")
                return real_fsync_directory(directory_fd)

            with patch(
                "bugmaster_core.session_store._fsync_directory_fd",
                side_effect=fail_first_parent_sync,
            ), self.assertRaises(SessionStoreError):
                store.create(_valid_session())

            synced_parent = []

            def record_parent_sync(directory_fd):
                current_stat = os.fstat(directory_fd)
                if (
                    current_stat.st_dev == parent_stat.st_dev
                    and current_stat.st_ino == parent_stat.st_ino
                ):
                    synced_parent.append(True)
                return real_fsync_directory(directory_fd)

            with patch(
                "bugmaster_core.session_store._fsync_directory_fd",
                side_effect=record_parent_sync,
            ):
                store.create(_valid_session())

            self.assertTrue(synced_parent)

    def test_retry_syncs_existing_sessions_directory_after_parent_fsync_failure(self):
        import bugmaster_core.session_store as module

        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            store = self.make_store(root)
            root_stat = root.stat()
            real_fsync_directory = module._fsync_directory_fd
            failed_once = False

            def fail_first_root_sync(directory_fd):
                nonlocal failed_once
                current_stat = os.fstat(directory_fd)
                if (
                    not failed_once
                    and current_stat.st_dev == root_stat.st_dev
                    and current_stat.st_ino == root_stat.st_ino
                ):
                    failed_once = True
                    raise OSError("sessions parent sync failed")
                return real_fsync_directory(directory_fd)

            with patch(
                "bugmaster_core.session_store._fsync_directory_fd",
                side_effect=fail_first_root_sync,
            ), self.assertRaises(SessionStoreError):
                store.create(_valid_session())

            synced_root = []

            def record_root_sync(directory_fd):
                current_stat = os.fstat(directory_fd)
                if (
                    current_stat.st_dev == root_stat.st_dev
                    and current_stat.st_ino == root_stat.st_ino
                ):
                    synced_root.append(True)
                return real_fsync_directory(directory_fd)

            with patch(
                "bugmaster_core.session_store._fsync_directory_fd",
                side_effect=record_root_sync,
            ):
                store.create(_valid_session())

            self.assertTrue(synced_root)

    def test_read_lock_rejects_fifo_without_blocking(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            store._lock_path.unlink()
            os.mkfifo(store._lock_path, 0o600)
            real_open = os.open

            def require_nonblocking_lock(path, flags, *args, **kwargs):
                if path == "session.lock":
                    self.assertTrue(flags & os.O_NONBLOCK)
                return real_open(path, flags, *args, **kwargs)

            with patch(
                "bugmaster_core.session_store.os.open",
                side_effect=require_nonblocking_lock,
            ):
                with self.assertRaises(SessionStoreError):
                    store.read_latest()

    def test_open_storage_returns_absent_when_sessions_or_session_directory_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            store = self.make_store(root)
            self.assertIsNone(store.read_latest())

            (root / "sessions").mkdir()
            self.assertIsNone(store.read_latest())

    def test_ensure_directories_creates_the_private_storage_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory) / "store")
            store._ensure_directories()
            self.assertTrue(store._revisions_dir.is_dir())

    def test_read_rejects_nonregular_revision_file(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            revision_one = store._revisions_dir / "00000001.json"
            (store._revisions_dir / "00000002.json").symlink_to(revision_one)

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_read_rejects_nonsequential_uncommitted_revision(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            (store._revisions_dir / "00000003.json").write_bytes(b"{}\n")
            os.chmod(store._revisions_dir / "00000003.json", 0o600)

            with self.assertRaisesRegex(
                SessionCorruptionError, "invalid uncommitted revisions"
            ):
                store.read_latest()

    def test_read_rejects_uncommitted_revision_with_invalid_transition(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            first["actionBudget"]["consumedActions"] = 5
            store.create(first)
            pending = _next_revision(
                first,
                status="ready",
                actionBudget={"maxActions": 20, "consumedActions": 0},
            )
            payload = json.dumps(
                pending, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            (store._revisions_dir / "00000002.json").write_bytes(payload + b"\n")
            os.chmod(store._revisions_dir / "00000002.json", 0o600)

            with self.assertRaisesRegex(
                SessionCorruptionError, "uncommitted Session revision is inconsistent"
            ):
                store.read_latest()

    def test_read_only_reader_does_not_require_write_permission_on_lock(self):
        _, _, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            os.chmod(store._lock_path, 0o400)

            self.assertEqual(store.read_latest()["revision"], 1)
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
                store = self.make_store("session-data")
                os.chdir(second)
                store.create(_valid_session())
            finally:
                os.chdir(original_cwd)

            self.assertTrue((first / "session-data" / "sessions").is_dir())
            self.assertFalse((second / "session-data").exists())

    def test_missing_revisions_directory_with_head_fails_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            for revision_path in store._revisions_dir.iterdir():
                revision_path.unlink()
            store._revisions_dir.rmdir()

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_missing_head_with_revisions_fails_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            store._head_path.unlink()

            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_invalid_revision_heads_fail_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        corruptions = (
            "directory",
            "wrong-mode",
            "too-large",
            "incomplete",
            "invalid-json",
            "deep-json",
            "long-integer",
            "invalid-fields",
        )
        for corruption in corruptions:
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as directory:
                store = self.make_store(directory)
                store.create(_valid_session())
                store._head_path.unlink()
                if corruption == "directory":
                    store._head_path.mkdir()
                else:
                    if corruption == "too-large":
                        payload = b"x" * 1025 + b"\n"
                    elif corruption == "incomplete":
                        payload = b"{}"
                    elif corruption == "invalid-json":
                        payload = b"not-json\n"
                    elif corruption == "deep-json":
                        payload = b"[" * 10000 + b"0" + b"]" * 10000 + b"\n"
                    elif corruption == "long-integer":
                        payload = b'{"revision":' + b"9" * 5000 + b"}\n"
                    else:
                        payload = json.dumps(
                            {"sessionId": "session-1", "revision": 1, "revisionDigest": "bad"},
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8") + b"\n"
                    store._head_path.write_bytes(payload)
                    os.chmod(store._head_path, 0o644 if corruption == "wrong-mode" else 0o600)

                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_head_open_errors_fail_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            real_open = os.open

            def fail_head_open(path, flags, *args, **kwargs):
                if path == "session.head":
                    raise OSError("head unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.session_store.os.open", side_effect=fail_head_open):
                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_directory_inspection_errors_fail_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            real_open = os.open

            def fail_revision_open(path, flags, *args, **kwargs):
                if path == "revisions":
                    raise OSError("revision path unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.session_store.os.open", side_effect=fail_revision_open):
                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_head_write_failure_cleans_up_temporary_file(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            real_replace = os.replace

            def fail_head_replace(source, destination, **kwargs):
                if destination == "session.head":
                    os.unlink(source, dir_fd=kwargs["src_dir_fd"])
                    raise OSError("head publication failed")
                return real_replace(source, destination, **kwargs)

            with patch("bugmaster_core.session_store.os.replace", side_effect=fail_head_replace):
                with self.assertRaises(SessionStoreError):
                    store.create(_valid_session())

            self.assertEqual(list(store._session_dir.glob(".session-head-*")), [])

    def test_revision_head_mode_failure_cleans_up_open_file_and_temporary_file(self):
        import bugmaster_core.session_store as session_store_module

        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            real_create_temp = session_store_module._create_temporary_file
            real_fchmod = os.fchmod
            head_fds = set()

            def track_temp_file(directory_fd, prefix):
                fd, name = real_create_temp(directory_fd, prefix)
                if prefix == ".session-head-":
                    head_fds.add(fd)
                return fd, name

            def fail_head_mode(fd, mode):
                if fd in head_fds:
                    raise OSError("head mode unavailable")
                return real_fchmod(fd, mode)

            with patch(
                "bugmaster_core.session_store._create_temporary_file",
                side_effect=track_temp_file,
            ), patch("bugmaster_core.session_store.os.fchmod", side_effect=fail_head_mode):
                with self.assertRaises(SessionStoreError):
                    store.create(_valid_session())

            self.assertEqual(list(store._session_dir.glob(".session-head-*")), [])

    def test_storage_rejects_symlink_and_non_directory_paths(self):
        _, SessionStoreError, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            actual_root = base / "actual"
            actual_root.mkdir()
            linked_root = base / "linked"
            linked_root.symlink_to(actual_root, target_is_directory=True)
            with self.assertRaises(SessionStoreError):
                self.make_store(linked_root).create(_valid_session())

            file_root = base / "file-root"
            file_root.write_text("file", encoding="utf-8")
            with self.assertRaises(SessionStoreError):
                self.make_store(file_root).create(_valid_session())

            blocked_root = base / "blocked"
            blocked_root.mkdir()
            (blocked_root / "sessions").write_text("file", encoding="utf-8")
            with self.assertRaises(SessionStoreError):
                self.make_store(blocked_root).create(_valid_session())

            store = self.make_store(base / "linked-revisions")
            store.create(_valid_session())
            for revision_path in store._revisions_dir.iterdir():
                revision_path.unlink()
            store._revisions_dir.rmdir()
            outside = base / "outside-revisions"
            outside.mkdir()
            store._revisions_dir.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

    def test_lock_open_stat_and_flock_errors_fail_closed(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            real_open = os.open

            def fail_lock_open(path, flags, *args, **kwargs):
                if path == "session.lock":
                    raise OSError("lock unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.session_store.os.open", side_effect=fail_lock_open):
                with self.assertRaises(SessionStoreError):
                    store.read_latest()

            with patch(
                "bugmaster_core.session_store.os.fstat",
                return_value=type("FileStat", (), {"st_mode": stat.S_IFIFO})(),
            ):
                with self.assertRaises(SessionStoreError):
                    store.read_latest()

            with patch("bugmaster_core.session_store.fcntl.flock", side_effect=OSError("lock failed")):
                with self.assertRaises(SessionStoreError):
                    store.read_latest()

    def test_revision_directory_entries_and_listing_errors_fail_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            (store._revisions_dir / "unexpected.tmp").write_text("x", encoding="utf-8")
            with self.assertRaises(SessionCorruptionError):
                store.read_latest()

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            store._head_path.unlink()
            revision_stat = store._revisions_dir.stat()
            real_scandir = os.scandir

            for failing_call in (1, 2):
                calls = 0

                def fail_revision_listing(directory_fd):
                    nonlocal calls
                    directory_stat = os.fstat(directory_fd)
                    if (
                        directory_stat.st_dev == revision_stat.st_dev
                        and directory_stat.st_ino == revision_stat.st_ino
                    ):
                        calls += 1
                        if calls == failing_call:
                            raise OSError("listing failed")
                    return real_scandir(directory_fd)

                with patch(
                    "bugmaster_core.session_store.os.scandir",
                    side_effect=fail_revision_listing,
                ), self.assertRaises(SessionCorruptionError):
                    store.create(_valid_session())

    def test_revision_file_corruption_forms_fail_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        corruptions = [
            (lambda path: path.write_bytes(b"not-json\n"), None),
            (lambda path: path.write_bytes(b"\xff\n"), None),
            (lambda path: path.write_bytes(b"{}"), None),
            (lambda path: path.write_bytes(b"[" * 10000 + b"0" + b"]" * 10000 + b"\n"), 0o600),
            (lambda path: path.write_bytes(b'{"revision":' + b"9" * 5000 + b"}\n"), 0o600),
            (lambda path: path.write_text(json.dumps(_valid_session()) + "\n", encoding="utf-8"), None),
            (lambda path: path.write_text(json.dumps({**_valid_session(), "revision": 2}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"), None),
            (lambda path: os.chmod(path, 0o644), None),
            (lambda path: path.write_bytes(b"x" * (4 * 1024 * 1024 + 2)), 0o600),
        ]
        for index, (corrupt, mode) in enumerate(corruptions):
            with self.subTest(corruption=index), tempfile.TemporaryDirectory() as directory:
                store = self.make_store(directory)
                store.create(_valid_session())
                revision_path = next(store._revisions_dir.glob("*.json"))
                corrupt(revision_path)
                if mode is not None:
                    os.chmod(revision_path, mode)
                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_entry_stat_failure_is_reported_as_corruption(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())

            class FailingEntry:
                name = "00000001.json"

                @staticmethod
                def stat(*, follow_symlinks):
                    raise OSError("revision metadata unavailable")

            class FailingScan:
                def __enter__(self):
                    return iter([FailingEntry()])

                @staticmethod
                def __exit__(exc_type, exc_value, traceback):
                    return False

            revision_stat = store._revisions_dir.stat()
            real_scandir = os.scandir

            def fail_revision_entry_stat(directory_fd):
                current_stat = os.fstat(directory_fd)
                if (
                    current_stat.st_dev == revision_stat.st_dev
                    and current_stat.st_ino == revision_stat.st_ino
                ):
                    return FailingScan()
                return real_scandir(directory_fd)

            with patch(
                "bugmaster_core.session_store.os.scandir",
                side_effect=fail_revision_entry_stat,
            ):
                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_open_failure_is_reported_as_corruption(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            real_open = os.open

            def fail_revision_open(path, flags, *args, **kwargs):
                if str(path).endswith(".json"):
                    raise OSError("revision unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.session_store.os.open", side_effect=fail_revision_open):
                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_write_failures_clean_up_temporary_files(self):
        import bugmaster_core.session_store as session_store_module

        _, SessionStoreError, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            real_create_temp = session_store_module._create_temporary_file
            real_fchmod = os.fchmod
            revision_fds = set()

            def track_temp_file(directory_fd, prefix):
                fd, name = real_create_temp(directory_fd, prefix)
                if prefix == ".session-revision-":
                    revision_fds.add(fd)
                return fd, name

            def fail_revision_mode(fd, mode):
                if fd in revision_fds:
                    raise OSError("cannot secure revision")
                return real_fchmod(fd, mode)

            with patch(
                "bugmaster_core.session_store._create_temporary_file",
                side_effect=track_temp_file,
            ), patch("bugmaster_core.session_store.os.fchmod", side_effect=fail_revision_mode):
                with self.assertRaises(SessionStoreError):
                    store.create(_valid_session())
            self.assertEqual(list(store._session_dir.glob(".session-revision-*")), [])

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with patch("bugmaster_core.session_store.os.link", side_effect=FileExistsError("exists")):
                with self.assertRaises(SessionCorruptionError):
                    store.create(_valid_session())
            self.assertEqual(list(store._session_dir.glob(".session-revision-*")), [])

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            with patch("bugmaster_core.session_store.os.write", return_value=0):
                with self.assertRaises(SessionStoreError):
                    store.create(_valid_session())
            self.assertEqual(list(store._session_dir.glob(".session-revision-*")), [])

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)

            def unlink_then_fail(source, _destination, **kwargs):
                os.unlink(source, dir_fd=kwargs["src_dir_fd"])
                raise OSError("link failed after removing temporary file")

            with patch("bugmaster_core.session_store.os.link", side_effect=unlink_then_fail):
                with self.assertRaises(SessionStoreError):
                    store.create(_valid_session())
            self.assertEqual(list(store._session_dir.glob(".session-revision-*")), [])

    def test_directory_descriptor_helpers_fail_closed_on_open_errors_and_races(self):
        import bugmaster_core.session_store as module

        SessionStore, SessionStoreError, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_open = os.open

            def fail_anchor(path, flags, *args, **kwargs):
                if path == root.anchor:
                    raise OSError("root unavailable")
                return real_open(path, flags, *args, **kwargs)

            with patch("bugmaster_core.session_store.os.open", side_effect=fail_anchor):
                with self.assertRaises(SessionStoreError):
                    module._open_directory_path(
                        root / "store",
                        create=True,
                        error_type=SessionStoreError,
                        label="Session root",
                    )

            real_mkdir = os.mkdir

            def create_before_mkdir_returns_error(name, mode=0o777, *, dir_fd=None):
                real_mkdir(name, mode, dir_fd=dir_fd)
                raise FileExistsError(name)

            with patch(
                "bugmaster_core.session_store.os.mkdir",
                side_effect=create_before_mkdir_returns_error,
            ):
                fd = module._open_directory_path(
                    root.resolve(strict=False) / "raced",
                    create=True,
                    error_type=SessionStoreError,
                    label="Session root",
                )
                os.close(fd)

            parent = root / "parent"
            parent.mkdir()
            parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with patch(
                    "bugmaster_core.session_store.os.mkdir",
                    side_effect=create_before_mkdir_returns_error,
                ):
                    child_fd = module._open_child_directory(
                        parent_fd,
                        "raced-child",
                        create=True,
                        error_type=SessionStoreError,
                        label="Session",
                    )
                    os.close(child_fd)

                real_open_child = os.open
                open_calls = 0

                def fail_after_child_creation(name, flags, *args, **kwargs):
                    nonlocal open_calls
                    if name == "failed-child":
                        open_calls += 1
                        if open_calls == 1:
                            raise FileNotFoundError(name)
                        raise OSError("directory open failed")
                    return real_open_child(name, flags, *args, **kwargs)

                with patch(
                    "bugmaster_core.session_store.os.open",
                    side_effect=fail_after_child_creation,
                ):
                    with self.assertRaises(SessionStoreError):
                        module._open_child_directory(
                            parent_fd,
                            "failed-child",
                            create=True,
                            error_type=SessionStoreError,
                            label="Session",
                        )

                real_fchmod = os.fchmod

                def fail_directory_mode(fd, mode):
                    raise OSError("directory mode unavailable")

                with patch("bugmaster_core.session_store.os.fchmod", side_effect=fail_directory_mode):
                    with self.assertRaises(SessionCorruptionError):
                        module._open_child_directory(
                            parent_fd,
                            "raced-child",
                            create=True,
                            error_type=SessionCorruptionError,
                            label="Session",
                            private=True,
                        )
                self.assertIsNotNone(real_fchmod)
            finally:
                os.close(parent_fd)

    def test_temporary_file_name_collision_limit_fails(self):
        import bugmaster_core.session_store as module

        with tempfile.TemporaryDirectory() as directory:
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                attempts = 0

                def report_collision(path, flags, mode=0o777, *, dir_fd=None):
                    nonlocal attempts
                    attempts += 1
                    raise FileExistsError(path)

                with patch(
                    "bugmaster_core.session_store.secrets.token_hex",
                    return_value="repeat",
                ), patch(
                    "bugmaster_core.session_store.os.open",
                    side_effect=report_collision,
                ):
                    with self.assertRaises(FileExistsError):
                        module._create_temporary_file(directory_fd, ".tmp-")
                self.assertEqual(attempts, 8)
            finally:
                os.close(directory_fd)

    def test_next_write_removes_temporary_files_left_by_interrupted_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            first = _valid_session()
            store.create(first)
            stale_revision = store._session_dir / (
                ".session-revision-" + "a" * 32
            )
            stale_head = store._session_dir / (".session-head-" + "b" * 32)
            unrelated = store._session_dir / ".session-head-not-a-token"
            for path in (stale_revision, stale_head, unrelated):
                path.write_bytes(b"stale")
                os.chmod(path, 0o600)

            store.append_revision(
                _next_revision(first, status="ready"), expected_revision=1
            )

            self.assertFalse(stale_revision.exists())
            self.assertFalse(stale_head.exists())
            self.assertTrue(unrelated.exists())

    def test_next_write_rejects_a_temporary_symlink(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root / "store")
            first = _valid_session()
            store.create(first)
            target = root / "target"
            target.write_bytes(b"keep")
            temporary = store._session_dir / (
                ".session-revision-" + "c" * 32
            )
            temporary.symlink_to(target)

            with self.assertRaisesRegex(SessionStoreError, "not a regular file"):
                store.append_revision(
                    _next_revision(first, status="ready"), expected_revision=1
                )

            self.assertTrue(temporary.is_symlink())
            self.assertEqual(target.read_bytes(), b"keep")

    def test_next_write_reports_temporary_directory_scan_failure(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._session_dir.mkdir(parents=True)
            store._lock_path.touch(mode=0o600)
            with patch(
                "bugmaster_core.session_store.os.scandir",
                side_effect=OSError("directory scan failed"),
            ), self.assertRaisesRegex(SessionStoreError, "cannot clean interrupted"):
                store.create(_valid_session())

    def test_read_latest_returns_none_when_revisions_directory_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._ensure_directories()
            store._revisions_dir.rmdir()
            store._lock_path.touch(mode=0o600)

            self.assertIsNone(store.read_latest())

    def test_read_latest_rejects_zero_revision_filename(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._ensure_directories()
            (store._revisions_dir / "00000000.json").write_bytes(b"{}\n")
            store._lock_path.touch(mode=0o600)

            with self.assertRaisesRegex(SessionCorruptionError, "invalid entry"):
                store.read_latest()

    def test_read_latest_rejects_head_with_empty_revision_directory(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            (store._revisions_dir / "00000001.json").unlink()

            with self.assertRaisesRegex(
                SessionCorruptionError, "head exists without revisions"
            ):
                store.read_latest()

    def test_create_does_not_recover_initial_revision_with_extra_entries(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        import bugmaster_core.session_store as module

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store._ensure_directories()
            store._lock_path.touch(mode=0o600)
            first = _valid_session()
            second = _next_revision(first, status="ready")
            (store._revisions_dir / "00000001.json").write_bytes(
                module._canonical_bytes(first) + b"\n"
            )
            (store._revisions_dir / "00000002.json").write_bytes(
                module._canonical_bytes(second) + b"\n"
            )

            with self.assertRaisesRegex(SessionCorruptionError, "head is missing"):
                store.create(first)


if __name__ == "__main__":
    unittest.main()
