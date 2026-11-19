import copy
import json
import os
import stat
import tempfile
import threading
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
                if Path(path) == store._head_path:
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
            original_lstat = Path.lstat

            def fail_revision_lstat(path):
                if path == store._revisions_dir:
                    raise OSError("revision path unavailable")
                return original_lstat(path)

            with patch.object(Path, "lstat", fail_revision_lstat):
                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_head_write_failure_cleans_up_temporary_file(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            real_replace = os.replace

            def fail_head_replace(source, destination):
                if Path(destination) == store._head_path:
                    Path(source).unlink()
                    raise OSError("head publication failed")
                return real_replace(source, destination)

            with patch("bugmaster_core.session_store.os.replace", side_effect=fail_head_replace):
                with self.assertRaises(SessionStoreError):
                    store.create(_valid_session())

            self.assertEqual(list(store._session_dir.glob(".session-head-*")), [])

    def test_revision_head_mode_failure_cleans_up_open_file_and_temporary_file(self):
        _, SessionStoreError, _ = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            real_fchmod = os.fchmod
            calls = 0

            def fail_head_mode(fd, mode):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError("head mode unavailable")
                return real_fchmod(fd, mode)

            with patch("bugmaster_core.session_store.os.fchmod", side_effect=fail_head_mode):
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
                if Path(path) == store._lock_path:
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
            original_iterdir = Path.iterdir

            def fail_revision_listing(path):
                if path == store._revisions_dir:
                    raise OSError("listing failed")
                return original_iterdir(path)

            with patch.object(Path, "iterdir", fail_revision_listing):
                with self.assertRaises(SessionCorruptionError):
                    store.read_latest()

    def test_revision_file_corruption_forms_fail_closed(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        corruptions = [
            (lambda path: path.write_bytes(b"not-json\n"), None),
            (lambda path: path.write_bytes(b"\xff\n"), None),
            (lambda path: path.write_bytes(b"{}"), None),
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

    def test_revision_open_failure_is_reported_as_corruption(self):
        _, _, SessionCorruptionError = _session_store_types(self)
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            store.create(_valid_session())
            real_open = os.open

            def fail_revision_open(path, flags, *args, **kwargs):
                if Path(path).parent == store._revisions_dir:
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
            real_fchmod = os.fchmod
            calls = 0

            def fail_revision_mode(fd, mode):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("cannot secure revision")
                return real_fchmod(fd, mode)

            with patch("bugmaster_core.session_store.os.fchmod", side_effect=fail_revision_mode):
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

            def unlink_then_fail(source, _destination):
                Path(source).unlink()
                raise OSError("link failed after removing temporary file")

            with patch("bugmaster_core.session_store.os.link", side_effect=unlink_then_fail):
                with self.assertRaises(SessionStoreError):
                    store.create(_valid_session())
            self.assertEqual(list(store._session_dir.glob(".session-revision-*")), [])


if __name__ == "__main__":
    unittest.main()
