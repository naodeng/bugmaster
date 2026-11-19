"""Durable, append-only storage for versioned local Session documents.

This module persists validated Session revisions but does not authorize
actions or decide whether a Session is safe to resume.
"""

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
from contextlib import contextmanager
from pathlib import Path


_REVISION_FILE = re.compile(r"^([0-9]{8,})\.json$")
_MAX_SESSION_BYTES = 4 * 1024 * 1024
# A head contains the bounded Session ID and a small fixed amount of metadata.
_MAX_HEAD_BYTES = _MAX_SESSION_BYTES + 1024
_IMMUTABLE_FIELDS = (
    "schemaVersion",
    "sessionId",
    "projectRef",
    "hostRef",
    "environmentRef",
    "createdAt",
    "journalId",
)
_APPEND_ONLY_FIELDS = ("scopeHistory", "approvalRefs", "checkpointRefs")
_BUDGET_FIELDS = (
    ("maxActions", "consumedActions"),
    ("maxRequests", "consumedRequests"),
    ("maxDurationSeconds", "consumedDurationSeconds"),
)


class SessionStoreError(ValueError):
    """A Session revision cannot be safely stored or appended."""


class SessionCorruptionError(SessionStoreError):
    """Persisted Session revisions are missing, malformed, or inconsistent."""


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _canonical_bytes(document):
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _write_all(fd, payload):
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError("Session revision write made no forward progress")
        offset += written


def _fsync_directory(directory_fd):
    os.fsync(directory_fd)


def _open_directory_path(path, *, create, error_type, label):
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        current_fd = os.open(path.anchor, flags)
    except OSError as error:
        raise error_type("cannot inspect {} path".format(label)) from error
    try:
        for component in path.parts[1:]:
            try:
                next_fd = os.open(component, flags, dir_fd=current_fd)
            except FileNotFoundError:
                if not create:
                    os.close(current_fd)
                    current_fd = None
                    return None
                try:
                    os.mkdir(component, mode=0o700, dir_fd=current_fd)
                except FileExistsError:
                    pass
                else:
                    _fsync_directory(current_fd)
                next_fd = os.open(component, flags, dir_fd=current_fd)
            except OSError as error:
                raise error_type("cannot inspect {} path".format(label)) from error
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = None
        return result
    finally:
        if current_fd is not None:
            os.close(current_fd)


def _open_child_directory(parent_fd, name, *, create, error_type, label, private=False):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            return None
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        else:
            _fsync_directory(parent_fd)
        try:
            fd = os.open(name, flags, dir_fd=parent_fd)
        except OSError as error:
            raise error_type("cannot inspect {} path".format(label)) from error
    except OSError as error:
        raise error_type("cannot inspect {} path".format(label)) from error
    try:
        if private and create:
            os.fchmod(fd, 0o700)
    except OSError as error:
        os.close(fd)
        raise error_type("cannot secure {} directory".format(label)) from error
    return fd


def _create_temporary_file(directory_fd, prefix):
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    for _ in range(8):
        name = prefix + secrets.token_hex(16)
        try:
            return os.open(name, flags, 0o600, dir_fd=directory_fd), name
        except FileExistsError:
            continue
    raise FileExistsError("cannot allocate a unique Session temporary file")


def _advance_history_digest(previous_digest, payload):
    previous = bytes.fromhex(previous_digest)
    return hashlib.sha256(
        previous + len(payload).to_bytes(8, "big") + payload
    ).hexdigest()


_EMPTY_HISTORY_DIGEST = hashlib.sha256(b"BugMaster Session history v1").hexdigest()


class SessionStore:
    """Store immutable Session revisions under a local data directory.

    The caller supplies the versioned Session schema validator. Each revision
    is written to a private temporary file, synced, then linked into the
    revision directory without replacing an existing file. Writers serialize
    on a per-session POSIX lock and must provide the expected current revision.
    """

    def __init__(self, root, session_id, validator):
        if not _nonempty(session_id):
            raise SessionStoreError("session ID must be a non-empty string")
        if not callable(validator):
            raise SessionStoreError("a Session schema validator is required")
        try:
            storage_key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        except UnicodeEncodeError as error:
            raise SessionStoreError("session ID is not valid UTF-8") from error
        raw_root = Path(root).absolute()
        if raw_root.is_symlink():
            raise SessionStoreError("Session root must be a real directory")
        try:
            self.root = raw_root.resolve(strict=False)
        except (OSError, RuntimeError) as error:
            raise SessionStoreError("cannot resolve Session storage root") from error
        self.session_id = session_id
        self.validator = validator
        self._sessions_dir = self.root / "sessions"
        self._session_dir = self._sessions_dir / storage_key
        self._revisions_dir = self._session_dir / "revisions"
        self._lock_path = self._session_dir / "session.lock"
        self._head_path = self._session_dir / "session.head"

    def create(self, document):
        """Persist revision 1 if no revision for this Session exists."""
        payload, normalized = self._validate_document(document)
        if normalized["revision"] != 1:
            raise SessionStoreError("a new Session must start at revision 1")
        with self._locked() as storage:
            revisions = self._read_revisions_locked(storage, recover_pending=True)
            if revisions:
                raise SessionStoreError("Session already has a stored revision")
            history_digest = _advance_history_digest(_EMPTY_HISTORY_DIGEST, payload)
            head_payload = self._head_payload(1, payload, history_digest)
            self._write_revision_locked(storage, 1, payload)
            self._write_head_locked(storage, head_payload)
        return normalized

    def append_revision(self, document, expected_revision):
        """Append the next revision if the expected revision is still current."""
        if (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 1
        ):
            raise SessionStoreError("expected revision must be a positive integer")
        payload, normalized = self._validate_document(document)
        if normalized["revision"] != expected_revision + 1:
            raise SessionStoreError("new Session revision must follow expected revision")
        with self._locked() as storage:
            revisions = self._read_revisions_locked(storage, recover_pending=True)
            if not revisions:
                raise SessionStoreError("Session has no initial revision")
            current = revisions[-1]
            if current["revision"] != expected_revision:
                raise SessionStoreError("expected Session revision is stale")
            self._validate_transition(current, normalized)
            history_digest = self._history_digest(revisions)
            history_digest = _advance_history_digest(history_digest, payload)
            head_payload = self._head_payload(
                normalized["revision"], payload, history_digest
            )
            self._write_revision_locked(storage, normalized["revision"], payload)
            self._write_head_locked(storage, head_payload)
        return normalized

    def read_latest(self):
        """Return the latest validated revision, or None if no Session exists."""
        with self._locked(create_directories=False) as storage:
            revisions = self._read_revisions_locked(storage) if storage else []
        return revisions[-1] if revisions else None

    def read_revision(self, revision):
        """Return one validated revision, or None if that revision is absent."""
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise SessionStoreError("revision must be a positive integer")
        with self._locked(create_directories=False) as storage:
            revisions = self._read_revisions_locked(storage) if storage else []
        if revision > len(revisions):
            return None
        return revisions[revision - 1]

    def _validate_document(self, document, *, persisted=False):
        error_type = SessionCorruptionError if persisted else SessionStoreError
        if not isinstance(document, dict):
            raise error_type("Session document must be an object")
        if document.get("sessionId") != self.session_id:
            raise error_type("Session document identity does not match the store")
        revision = document.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise error_type("Session revision must be a positive integer")
        self._validate_references_and_budgets(document, error_type)
        try:
            payload = _canonical_bytes(document)
        except (TypeError, ValueError, UnicodeEncodeError) as error:
            raise error_type("Session document is not valid JSON data") from error
        if len(payload) > _MAX_SESSION_BYTES:
            raise error_type("Session document exceeds the storage size limit")
        normalized = json.loads(payload.decode("utf-8"))
        try:
            self.validator(normalized)
        except Exception as error:
            raise error_type("Session document does not satisfy its schema") from error
        return payload, normalized

    def _validate_references_and_budgets(self, document, error_type):
        scope_history = document.get("scopeHistory")
        approval_refs = document.get("approvalRefs")
        checkpoint_refs = document.get("checkpointRefs")
        budget = document.get("actionBudget")
        if not isinstance(scope_history, list) or not scope_history:
            raise error_type("Session must retain at least one Scope revision")
        if not isinstance(approval_refs, list) or not isinstance(checkpoint_refs, list):
            raise error_type("Session references must be arrays")
        if not isinstance(budget, dict):
            raise error_type("Session action budget must be an object")

        scope_keys = set()
        latest_scope_revisions = {}
        for reference in scope_history:
            if not isinstance(reference, dict):
                raise error_type("Scope revision reference must be an object")
            scope_id = reference.get("scopeId")
            scope_revision = reference.get("revision")
            if (
                not _nonempty(scope_id)
                or isinstance(scope_revision, bool)
                or not isinstance(scope_revision, int)
                or scope_revision < 1
            ):
                raise error_type("Scope revision reference is invalid")
            scope_key = (scope_id, scope_revision)
            previous_scope_revision = latest_scope_revisions.get(scope_id)
            if scope_key in scope_keys or (
                previous_scope_revision is not None
                and scope_revision <= previous_scope_revision
            ):
                raise error_type("Scope revision history must be unique and chronological")
            scope_keys.add(scope_key)
            latest_scope_revisions[scope_id] = scope_revision

        for reference in approval_refs:
            if not isinstance(reference, dict):
                raise error_type("Approval reference must be an object")
            approval_id = reference.get("approvalId")
            scope_id = reference.get("scopeId")
            scope_revision = reference.get("scopeRevision")
            if (
                not _nonempty(approval_id)
                or not _nonempty(scope_id)
                or isinstance(scope_revision, bool)
                or not isinstance(scope_revision, int)
                or (scope_id, scope_revision) not in scope_keys
            ):
                raise error_type("Approval reference is not bound to Session scope history")

        if any(not _nonempty(reference) for reference in checkpoint_refs):
            raise error_type("Checkpoint reference must be a non-empty string")

        if not _nonempty(document.get("journalId")):
            raise error_type("Session journal ID must be a non-empty string")

        for limit_field, consumed_field in _BUDGET_FIELDS:
            has_limit = limit_field in budget
            has_consumed = consumed_field in budget
            if has_limit != has_consumed:
                raise error_type("budget limit and consumed count must be paired")
            if not has_limit:
                continue
            limit = budget[limit_field]
            consumed = budget[consumed_field]
            if (
                isinstance(limit, bool)
                or not isinstance(limit, int)
                or limit < 0
                or isinstance(consumed, bool)
                or not isinstance(consumed, int)
                or consumed < 0
                or consumed > limit
            ):
                raise error_type("Session budget counters are invalid or exhausted")

    def _validate_transition(self, previous, current):
        for field in _IMMUTABLE_FIELDS:
            if previous.get(field) != current.get(field):
                raise SessionStoreError("Session field cannot change: {}".format(field))

        for field in _APPEND_ONLY_FIELDS:
            old_values = previous[field]
            new_values = current[field]
            if new_values[: len(old_values)] != old_values:
                raise SessionStoreError("Session history cannot remove or reorder {}".format(field))

        scope_added = len(current["scopeHistory"]) > len(previous["scopeHistory"])
        old_budget = previous["actionBudget"]
        new_budget = current["actionBudget"]
        for limit_field, consumed_field in _BUDGET_FIELDS:
            old_limit = old_budget.get(limit_field)
            new_limit = new_budget.get(limit_field)
            old_consumed = old_budget.get(consumed_field)
            new_consumed = new_budget.get(consumed_field)

            if old_consumed is not None and (
                new_consumed is None or new_consumed < old_consumed
            ):
                raise SessionStoreError("consumed Session budget cannot decrease")
            if old_consumed is None and new_consumed is not None:
                if not scope_added or new_consumed != 0:
                    raise SessionStoreError(
                        "a new budget counter requires a new Scope revision and starts at zero"
                    )
            if old_limit != new_limit and not scope_added:
                raise SessionStoreError("Session budget limit requires a new Scope revision")

    @contextmanager
    def _locked(self, create_directories=True):
        error_type = SessionStoreError if create_directories else SessionCorruptionError
        storage = self._open_storage_directories(create_directories, error_type)
        if storage is None:
            yield None
            return

        flags = os.O_RDWR | os.O_CREAT if create_directories else os.O_RDONLY
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = None
        acquired = False
        try:
            try:
                if create_directories:
                    fd = os.open(
                        "session.lock",
                        flags,
                        0o600,
                        dir_fd=storage["session_fd"],
                    )
                else:
                    fd = os.open(
                        "session.lock",
                        flags,
                        dir_fd=storage["session_fd"],
                    )
            except OSError as error:
                raise SessionStoreError("cannot open Session lock") from error
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise SessionStoreError("Session lock is not a regular file")
            if create_directories:
                os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX if create_directories else fcntl.LOCK_SH)
            acquired = True
            yield storage
        except OSError as error:
            raise SessionStoreError("Session storage lock failed") from error
        finally:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            if fd is not None:
                os.close(fd)
            self._close_storage_directories(storage)

    def _open_storage_directories(self, create_directories, error_type):
        opened = []
        try:
            root_fd = _open_directory_path(
                self.root,
                create=create_directories,
                error_type=error_type,
                label="Session root",
            )
            if root_fd is None:
                return None
            opened.append(root_fd)
            sessions_fd = _open_child_directory(
                root_fd,
                "sessions",
                create=create_directories,
                error_type=error_type,
                label="Session storage",
                private=True,
            )
            if sessions_fd is None:
                self._close_fds(opened)
                return None
            opened.append(sessions_fd)
            session_fd = _open_child_directory(
                sessions_fd,
                self._session_dir.name,
                create=create_directories,
                error_type=error_type,
                label="Session",
                private=True,
            )
            if session_fd is None:
                self._close_fds(opened)
                return None
            opened.append(session_fd)
            revisions_fd = _open_child_directory(
                session_fd,
                "revisions",
                create=create_directories,
                error_type=error_type,
                label="Session revisions",
                private=True,
            )
            if revisions_fd is not None:
                opened.append(revisions_fd)
            return {
                "root_fd": root_fd,
                "sessions_fd": sessions_fd,
                "session_fd": session_fd,
                "revisions_fd": revisions_fd,
            }
        except BaseException:
            self._close_fds(opened)
            raise

    @staticmethod
    def _close_fds(file_descriptors):
        for fd in reversed(file_descriptors):
            os.close(fd)

    def _close_storage_directories(self, storage):
        self._close_fds(
            [
                fd
                for fd in (
                    storage["root_fd"],
                    storage["sessions_fd"],
                    storage["session_fd"],
                    storage["revisions_fd"],
                )
                if fd is not None
            ]
        )

    def _ensure_directories(self):
        storage = self._open_storage_directories(True, SessionStoreError)
        self._close_storage_directories(storage)

    def _read_revisions_locked(self, storage, *, recover_pending=False):
        head = self._read_head_locked(storage)
        revisions_fd = storage["revisions_fd"]
        try:
            entries = os.listdir(revisions_fd) if revisions_fd is not None else []
        except OSError as error:
            raise SessionCorruptionError("cannot list Session revisions") from error

        revision_files = []
        for name in entries:
            match = _REVISION_FILE.fullmatch(name)
            if match is None or revisions_fd is None:
                raise SessionCorruptionError("Session revision directory has an invalid entry")
            try:
                file_stat = os.stat(
                    name, dir_fd=revisions_fd, follow_symlinks=False
                )
            except OSError as error:
                raise SessionCorruptionError("cannot inspect Session revision") from error
            if not stat.S_ISREG(file_stat.st_mode):
                raise SessionCorruptionError("Session revision directory has an invalid entry")
            revision_files.append((int(match.group(1)), name))
        revision_files.sort(key=lambda pair: pair[0])

        if not revision_files:
            if head is not None:
                raise SessionCorruptionError("Session head exists without revisions")
            return []
        if head is None:
            raise SessionCorruptionError("Session revision head is missing")

        committed_revision = head["revision"]
        committed_files = [
            item for item in revision_files if item[0] <= committed_revision
        ]
        pending_files = [
            item for item in revision_files if item[0] > committed_revision
        ]
        revisions = []
        history_digest = _EMPTY_HISTORY_DIGEST
        expected_revision = 1
        for revision, name in committed_files:
            if revision != expected_revision:
                raise SessionCorruptionError("Session revision sequence has a gap")
            document, payload = self._read_revision_file(
                storage, name, expected_revision
            )
            if revisions:
                try:
                    self._validate_transition(revisions[-1], document)
                except SessionStoreError as error:
                    raise SessionCorruptionError(
                        "persisted Session revision history is inconsistent"
                    ) from error
            revisions.append(document)
            history_digest = _advance_history_digest(history_digest, payload)
            expected_revision += 1
        if expected_revision != committed_revision + 1:
            raise SessionCorruptionError("Session revision sequence has a gap")

        pending_name_to_remove = None
        if pending_files:
            if (
                len(pending_files) != 1
                or pending_files[0][0] != committed_revision + 1
            ):
                raise SessionCorruptionError("Session has invalid uncommitted revisions")
            pending_revision, pending_name = pending_files[0]
            pending_document, _ = self._read_revision_file(
                storage, pending_name, pending_revision
            )
            try:
                self._validate_transition(revisions[-1], pending_document)
            except SessionStoreError as error:
                raise SessionCorruptionError(
                    "uncommitted Session revision is inconsistent"
                ) from error
            if recover_pending:
                pending_name_to_remove = pending_name

        latest = revisions[-1]
        expected_digest = hashlib.sha256(_canonical_bytes(latest)).hexdigest()
        if (
            head["revisionDigest"] != expected_digest
            or head["historyDigest"] != history_digest
        ):
            raise SessionCorruptionError(
                "Session revision history does not match its committed head"
            )
        if pending_name_to_remove is not None:
            os.unlink(pending_name_to_remove, dir_fd=revisions_fd)
            _fsync_directory(revisions_fd)
        return revisions

    @staticmethod
    def _history_digest(revisions):
        digest = _EMPTY_HISTORY_DIGEST
        for revision in revisions:
            digest = _advance_history_digest(digest, _canonical_bytes(revision))
        return digest

    def _head_payload(self, revision, payload, history_digest):
        head = {
            "sessionId": self.session_id,
            "revision": revision,
            "revisionDigest": hashlib.sha256(payload).hexdigest(),
            "historyDigest": history_digest,
        }
        return _canonical_bytes(head) + b"\n"

    def _read_head_locked(self, storage):
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            fd = os.open(
                "session.head", flags, dir_fd=storage["session_fd"]
            )
        except FileNotFoundError:
            return None
        except OSError as error:
            raise SessionCorruptionError("cannot open Session revision head") from error
        try:
            head_stat = os.fstat(fd)
            if not stat.S_ISREG(head_stat.st_mode) or stat.S_IMODE(head_stat.st_mode) != 0o600:
                raise SessionCorruptionError("Session revision head permissions are invalid")
            if head_stat.st_size > _MAX_HEAD_BYTES:
                raise SessionCorruptionError("Session revision head is too large")
            raw = bytearray()
            while True:
                chunk = os.read(fd, 1024)
                if not chunk:
                    break
                raw.extend(chunk)
        finally:
            os.close(fd)
        if not raw.endswith(b"\n"):
            raise SessionCorruptionError("Session revision head is incomplete")
        try:
            head = json.loads(bytes(raw[:-1]).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SessionCorruptionError("Session revision head is invalid JSON") from error
        if (
            not isinstance(head, dict)
            or set(head)
            != {"sessionId", "revision", "revisionDigest", "historyDigest"}
            or head.get("sessionId") != self.session_id
            or isinstance(head.get("revision"), bool)
            or not isinstance(head.get("revision"), int)
            or head["revision"] < 1
            or not isinstance(head.get("revisionDigest"), str)
            or re.fullmatch(r"[a-f0-9]{64}", head["revisionDigest"]) is None
            or not isinstance(head.get("historyDigest"), str)
            or re.fullmatch(r"[a-f0-9]{64}", head["historyDigest"]) is None
            or bytes(raw[:-1]) != _canonical_bytes(head)
        ):
            raise SessionCorruptionError("Session revision head fields are invalid")
        return head

    def _read_revision_file(self, storage, filename, expected_revision):
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            fd = os.open(
                filename, flags, dir_fd=storage["revisions_fd"]
            )
        except OSError as error:
            raise SessionCorruptionError("cannot open persisted Session revision") from error
        try:
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode) or stat.S_IMODE(file_stat.st_mode) != 0o600:
                raise SessionCorruptionError("Session revision file permissions are invalid")
            if file_stat.st_size > _MAX_SESSION_BYTES + 1:
                raise SessionCorruptionError("persisted Session revision is too large")
            raw = bytearray()
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                raw.extend(chunk)
        finally:
            os.close(fd)

        if not raw.endswith(b"\n"):
            raise SessionCorruptionError("persisted Session revision is incomplete")
        try:
            document = json.loads(bytes(raw[:-1]).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SessionCorruptionError("persisted Session revision is invalid JSON") from error
        payload, normalized = self._validate_document(document, persisted=True)
        if bytes(raw[:-1]) != payload:
            raise SessionCorruptionError("persisted Session revision is not canonical JSON")
        if normalized["revision"] != expected_revision:
            raise SessionCorruptionError("Session revision content does not match its file name")
        return normalized, payload

    def _write_revision_locked(self, storage, revision, payload):
        filename = "{:08d}.json".format(revision)
        fd, temporary_name = _create_temporary_file(
            storage["session_fd"], ".session-revision-"
        )
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, payload + b"\n")
            os.fsync(fd)
            os.close(fd)
            fd = None
            try:
                os.link(
                    temporary_name,
                    filename,
                    src_dir_fd=storage["session_fd"],
                    dst_dir_fd=storage["revisions_fd"],
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise SessionCorruptionError("Session revision file already exists") from error
            _fsync_directory(storage["revisions_fd"])
            os.unlink(temporary_name, dir_fd=storage["session_fd"])
            temporary_name = None
            _fsync_directory(storage["session_fd"])
        except OSError as error:
            raise SessionStoreError("cannot durably write Session revision") from error
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=storage["session_fd"])
                except FileNotFoundError:
                    pass

    def _write_head_locked(self, storage, encoded):
        fd, temporary_name = _create_temporary_file(
            storage["session_fd"], ".session-head-"
        )
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, encoded)
            os.fsync(fd)
            os.close(fd)
            fd = None
            os.replace(
                temporary_name,
                "session.head",
                src_dir_fd=storage["session_fd"],
                dst_dir_fd=storage["session_fd"],
            )
            temporary_name = None
            _fsync_directory(storage["session_fd"])
        except OSError as error:
            raise SessionStoreError("cannot durably update Session revision head") from error
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=storage["session_fd"])
                except FileNotFoundError:
                    pass
