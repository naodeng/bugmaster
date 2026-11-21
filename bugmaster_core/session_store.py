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

from .filesystem_security import _has_extended_acl


_REVISION_FILE = re.compile(r"^([0-9]{8,})\.json$")
_TEMPORARY_FILE = re.compile(
    r"^\.(?:session-head|session-revision|checkpoint)-[a-f0-9]{32}$"
)
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


def _fsync_directory(directory):
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory_fd = os.open(directory, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _fsync_directory_fd(directory_fd):
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
                except OSError as error:
                    raise error_type("cannot create {} path".format(label)) from error
                try:
                    next_fd = os.open(component, flags, dir_fd=current_fd)
                except OSError as error:
                    raise error_type("cannot inspect {} path".format(label)) from error
            except OSError as error:
                raise error_type("cannot inspect {} path".format(label)) from error
            if create:
                try:
                    _fsync_directory_fd(current_fd)
                except OSError as error:
                    os.close(next_fd)
                    raise error_type("cannot sync {} path".format(label)) from error
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = None
        return result
    finally:
        if current_fd is not None:
            os.close(current_fd)


def _require_private_directory(
    directory_fd, error_type, label, *, allow_permission_repair=False
):
    metadata = os.fstat(directory_fd)
    if not stat.S_ISDIR(metadata.st_mode):
        raise error_type("{} is not a directory".format(label))
    if metadata.st_uid != os.geteuid():
        raise error_type("{} has an unsafe owner".format(label))
    if not allow_permission_repair and metadata.st_mode & (0o077 | 0o7000):
        raise error_type("{} permissions are unsafe".format(label))
    try:
        has_extended_acl = _has_extended_acl(directory_fd)
    except OSError as error:
        raise error_type(
            "cannot inspect access control for {}".format(label)
        ) from error
    if has_extended_acl:
        raise error_type("{} must not have an extended ACL".format(label))
    return metadata


def _require_private_file(file_descriptor, error_type, label):
    metadata = os.fstat(file_descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise error_type("{} is not a regular file".format(label))
    if metadata.st_uid != os.geteuid():
        raise error_type("{} has an unsafe owner".format(label))
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise error_type("{} permissions are invalid".format(label))
    try:
        has_extended_acl = _has_extended_acl(file_descriptor)
    except OSError as error:
        raise error_type(
            "cannot inspect access control for {}".format(label)
        ) from error
    if has_extended_acl:
        raise error_type("{} must not have an extended ACL".format(label))
    return metadata


def _require_canonical_file_link(
    metadata, session_fd, temporary_prefix, error_type, label
):
    if metadata.st_nlink == 1:
        return
    if metadata.st_nlink != 2 or temporary_prefix is None:
        raise error_type("{} has an unsafe number of hard links".format(label))

    temporary_name = re.compile(
        r"^{}[a-f0-9]{{32}}$".format(re.escape(temporary_prefix))
    )
    try:
        with os.scandir(session_fd) as entries:
            for entry in entries:
                if temporary_name.fullmatch(entry.name) is None:
                    continue
                linked_stat = entry.stat(follow_symlinks=False)
                if (
                    stat.S_ISREG(linked_stat.st_mode)
                    and linked_stat.st_dev == metadata.st_dev
                    and linked_stat.st_ino == metadata.st_ino
                ):
                    return
    except OSError as error:
        raise error_type(
            "cannot inspect temporary links for {}".format(label)
        ) from error
    raise error_type("{} has an unrecognized hard link".format(label))


def _sync_interrupted_publication(
    session_fd, temporary_stat, directory_name, expected_filename, label
):
    directory_fd = _open_child_directory(
        session_fd,
        directory_name,
        create=False,
        error_type=SessionStoreError,
        label=label,
        private=True,
    )
    if directory_fd is None:
        raise SessionStoreError("{} directory is missing".format(label))
    try:
        try:
            published_stat = os.stat(
                expected_filename, dir_fd=directory_fd, follow_symlinks=False
            )
        except FileNotFoundError as error:
            raise SessionStoreError(
                "{} canonical publication is missing".format(label)
            ) from error
        if (
            not stat.S_ISREG(published_stat.st_mode)
            or published_stat.st_dev != temporary_stat.st_dev
            or published_stat.st_ino != temporary_stat.st_ino
        ):
            raise SessionStoreError(
                "{} canonical publication does not match its temporary file".format(
                    label
                )
            )
        _fsync_directory_fd(directory_fd)
    finally:
        os.close(directory_fd)


def _require_private_lock_file(file_descriptor):
    metadata = os.fstat(file_descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise SessionStoreError("Session lock is not a regular file")
    if metadata.st_uid != os.geteuid():
        raise SessionStoreError("Session lock has an unsafe owner")
    if metadata.st_nlink != 1:
        raise SessionStoreError("Session lock must not have hard links")
    if metadata.st_mode & (0o077 | 0o7000):
        raise SessionStoreError("Session lock permissions are unsafe")
    try:
        has_extended_acl = _has_extended_acl(file_descriptor)
    except OSError as error:
        raise SessionStoreError(
            "cannot inspect access control for Session lock"
        ) from error
    if has_extended_acl:
        raise SessionStoreError("Session lock must not have an extended ACL")
    return metadata


def _open_child_directory(parent_fd, name, *, create, error_type, label, private=False):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    created = False
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            return None
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as error:
            raise error_type("cannot create {} directory".format(label)) from error
        else:
            created = True
        try:
            fd = os.open(name, flags, dir_fd=parent_fd)
        except OSError as error:
            raise error_type("cannot inspect {} path".format(label)) from error
    except OSError as error:
        raise error_type("cannot inspect {} path".format(label)) from error
    try:
        if private:
            _require_private_directory(
                fd,
                error_type,
                label,
                allow_permission_repair=create,
            )
            if create:
                os.fchmod(fd, 0o700)
    except OSError as error:
        os.close(fd)
        if created:
            try:
                os.rmdir(name, dir_fd=parent_fd)
            except OSError:
                pass
        raise error_type("cannot secure {} directory".format(label)) from error
    except BaseException:
        os.close(fd)
        if created:
            try:
                os.rmdir(name, dir_fd=parent_fd)
            except OSError:
                pass
        raise
    if create:
        try:
            _fsync_directory_fd(parent_fd)
        except OSError as error:
            os.close(fd)
            raise error_type("cannot sync {} directory".format(label)) from error
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
            self.root = (
                raw_root.resolve(strict=False)
                if raw_root.name == ".."
                else raw_root.parent.resolve(strict=False) / raw_root.name
            )
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
            recovered_initial = self._recover_initial_revision_locked(
                storage, expected_payload=payload
            )
            history = self._read_revisions_locked(storage, recover_pending=True)
            if history["count"]:
                if recovered_initial and history["count"] == 1 and history["latest"] == normalized:
                    return normalized
                raise SessionStoreError("Session already has a stored revision")
            history_digest = _advance_history_digest(_EMPTY_HISTORY_DIGEST, payload)
            head_payload = self._head_payload(1, payload, history_digest)
            self._write_revision_locked(storage, 1, payload)
            self._write_head_locked(storage, head_payload)
        return normalized

    @contextmanager
    def lock_revisions(self, *, root_fd=None):
        """Hold the exclusive Session lock while yielding its committed count."""
        with self._locked(root_fd=root_fd) as storage:
            yield self._read_revisions_locked(storage)["count"]

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
            history = self._read_revisions_locked(storage, recover_pending=True)
            if not history["count"]:
                raise SessionStoreError("Session has no initial revision")
            current = history["latest"]
            if current["revision"] != expected_revision:
                raise SessionStoreError("expected Session revision is stale")
            self._validate_transition(current, normalized)
            history_digest = history["history_digest"]
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
            history = self._read_revisions_locked(storage) if storage else None
        return history["latest"] if history else None

    def read_revision(self, revision):
        """Return one validated revision, or None if that revision is absent."""
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise SessionStoreError("revision must be a positive integer")
        with self._locked(create_directories=False) as storage:
            history = (
                self._read_revisions_locked(storage, requested_revision=revision)
                if storage
                else None
            )
        return history["requested"] if history else None

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
        except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as error:
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
    def _locked(self, create_directories=True, *, root_fd=None):
        error_type = SessionStoreError if create_directories else SessionCorruptionError
        storage = self._open_storage_directories(
            create_directories, error_type, root_fd=root_fd
        )
        if storage is None:
            yield None
            return

        flags = os.O_RDWR if create_directories else os.O_RDONLY
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = None
        created_lock = False
        acquired = False
        try:
            try:
                fd = os.open(
                    "session.lock",
                    flags,
                    dir_fd=storage["session_fd"],
                )
            except FileNotFoundError as error:
                try:
                    with os.scandir(storage["session_fd"]) as entries:
                        names = {entry.name for entry in entries}
                except OSError as scan_error:
                    raise error_type(
                        "cannot inspect Session directory without its lock"
                    ) from scan_error
                empty_uninitialized_session = not names
                if names == {"revisions"}:
                    revisions_fd = _open_child_directory(
                        storage["session_fd"],
                        "revisions",
                        create=False,
                        error_type=error_type,
                        label="Session revisions",
                        private=True,
                    )
                    if revisions_fd is not None:
                        try:
                            with os.scandir(revisions_fd) as entries:
                                empty_uninitialized_session = next(entries, None) is None
                        except OSError as scan_error:
                            raise error_type(
                                "cannot inspect Session revisions without its lock"
                            ) from scan_error
                        finally:
                            os.close(revisions_fd)
                if "session.lock" in names:
                    try:
                        fd = os.open(
                            "session.lock",
                            flags,
                            dir_fd=storage["session_fd"],
                        )
                    except OSError as open_error:
                        raise error_type("cannot open Session lock") from open_error
                elif not empty_uninitialized_session:
                    try:
                        fd = os.open(
                            "session.lock",
                            flags,
                            dir_fd=storage["session_fd"],
                        )
                    except FileNotFoundError as missing_lock_error:
                        raise SessionCorruptionError(
                            "Session lock is missing"
                        ) from missing_lock_error
                    except OSError as open_error:
                        raise error_type("cannot open Session lock") from open_error
                elif not create_directories:
                    yield None
                    return
                else:
                    try:
                        fd = os.open(
                            "session.lock",
                            flags | os.O_CREAT | os.O_EXCL,
                            0o600,
                            dir_fd=storage["session_fd"],
                        )
                        created_lock = True
                    except FileExistsError:
                        try:
                            fd = os.open(
                                "session.lock",
                                flags,
                                dir_fd=storage["session_fd"],
                            )
                        except OSError as open_error:
                            raise SessionStoreError(
                                "cannot open Session lock"
                            ) from open_error
                    except OSError as create_error:
                        raise SessionStoreError(
                            "cannot create Session lock"
                        ) from create_error
            except OSError as error:
                raise error_type("cannot open Session lock") from error
            _require_private_lock_file(fd)
            if created_lock:
                os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX if create_directories else fcntl.LOCK_SH)
            acquired = True
            if create_directories:
                self._cleanup_temporary_files_locked(storage["session_fd"])
            storage["revisions_fd"] = _open_child_directory(
                storage["session_fd"],
                "revisions",
                create=create_directories,
                error_type=error_type,
                label="Session revisions",
                private=True,
            )
            yield storage
        except OSError as error:
            raise SessionStoreError("Session storage lock failed") from error
        finally:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            if fd is not None:
                os.close(fd)
            self._close_storage_directories(storage)

    def _open_storage_directories(self, create_directories, error_type, *, root_fd=None):
        opened = []
        try:
            if root_fd is None:
                root_fd = _open_directory_path(
                    self.root,
                    create=create_directories,
                    error_type=error_type,
                    label="Session root",
                )
            else:
                root_fd = os.dup(root_fd)
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
            return {
                "root_fd": root_fd,
                "sessions_fd": sessions_fd,
                "session_fd": session_fd,
                "revisions_fd": None,
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
        try:
            revisions_fd = _open_child_directory(
                storage["session_fd"],
                "revisions",
                create=True,
                error_type=SessionStoreError,
                label="Session revisions",
                private=True,
            )
            os.close(revisions_fd)
        finally:
            self._close_storage_directories(storage)

    def _cleanup_temporary_files_locked(self, session_fd):
        removed = False
        try:
            with os.scandir(session_fd) as entries:
                for entry in entries:
                    if _TEMPORARY_FILE.fullmatch(entry.name) is None:
                        continue
                    entry_stat = entry.stat(follow_symlinks=False)
                    if not stat.S_ISREG(entry_stat.st_mode):
                        raise SessionStoreError(
                            "Session temporary file is not a regular file"
                        )
                    if entry.name.startswith(".session-revision-"):
                        target_directory, target_label = "revisions", "Session revisions"
                    elif entry.name.startswith(".checkpoint-"):
                        target_directory, target_label = "checkpoints", "Checkpoint storage"
                    else:
                        target_directory, target_label = None, None
                    if target_directory is None:
                        if entry_stat.st_nlink != 1:
                            raise SessionStoreError(
                                "Session head temporary file has an unsafe link count"
                            )
                    elif entry_stat.st_nlink == 2:
                        expected_filename = (
                            self._expected_temporary_publication_filename(
                                session_fd,
                                entry.name,
                                entry_stat,
                                target_directory,
                            )
                        )
                        _sync_interrupted_publication(
                            session_fd,
                            entry_stat,
                            target_directory,
                            expected_filename,
                            target_label,
                        )
                    elif entry_stat.st_nlink != 1:
                        raise SessionStoreError(
                            "Session temporary file has an unsafe link count"
                        )
                    os.unlink(entry.name, dir_fd=session_fd)
                    removed = True
        except OSError as error:
            raise SessionStoreError("cannot clean interrupted Session writes") from error
        if removed:
            _fsync_directory_fd(session_fd)

    def _expected_temporary_publication_filename(
        self, session_fd, temporary_name, expected_stat, target_directory
    ):
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            fd = os.open(temporary_name, flags, dir_fd=session_fd)
        except OSError as error:
            raise SessionStoreError(
                "cannot open interrupted Session publication"
            ) from error
        try:
            file_stat = _require_private_file(
                fd, SessionStoreError, "Session temporary publication"
            )
            if (
                file_stat.st_dev != expected_stat.st_dev
                or file_stat.st_ino != expected_stat.st_ino
                or file_stat.st_nlink != 2
            ):
                raise SessionStoreError(
                    "Session temporary publication changed during inspection"
                )
            if file_stat.st_size > _MAX_SESSION_BYTES + 1:
                raise SessionStoreError(
                    "Session temporary publication exceeds the size limit"
                )
            raw = bytearray()
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                if len(raw) + len(chunk) > _MAX_SESSION_BYTES + 1:
                    raise SessionStoreError(
                        "Session temporary publication exceeds the size limit"
                    )
                raw.extend(chunk)
        finally:
            os.close(fd)

        if not raw.endswith(b"\n"):
            raise SessionStoreError("Session temporary publication is incomplete")
        try:
            document = json.loads(bytes(raw[:-1]).decode("utf-8"))
            payload = _canonical_bytes(document)
        except (
            UnicodeDecodeError,
            ValueError,
            TypeError,
            UnicodeEncodeError,
            RecursionError,
        ) as error:
            raise SessionStoreError(
                "Session temporary publication is invalid JSON"
            ) from error
        if bytes(raw[:-1]) != payload:
            raise SessionStoreError(
                "Session temporary publication is not canonical JSON"
            )

        if target_directory == "revisions":
            _, normalized = self._validate_document(document, persisted=True)
            return "{:08d}.json".format(normalized["revision"])
        if (
            not isinstance(document, dict)
            or document.get("sessionId") != self.session_id
            or not _nonempty(document.get("checkpointId"))
        ):
            raise SessionStoreError(
                "Checkpoint temporary publication identity is invalid"
            )
        checkpoint_id = document["checkpointId"].encode("utf-8")
        return hashlib.sha256(checkpoint_id).hexdigest() + ".json"

    def _read_revisions_locked(
        self, storage, *, recover_pending=False, requested_revision=None
    ):
        head = self._read_head_locked(storage)
        revisions_fd = storage["revisions_fd"]
        if revisions_fd is None:
            if head is not None:
                raise SessionCorruptionError("Session head exists without revisions")
            return {
                "count": 0,
                "latest": None,
                "requested": None,
                "history_digest": _EMPTY_HISTORY_DIGEST,
            }

        entry_count = 0
        pending_name = None
        try:
            with os.scandir(revisions_fd) as entries:
                for entry in entries:
                    match = _REVISION_FILE.fullmatch(entry.name)
                    if match is None:
                        raise SessionCorruptionError(
                            "Session revision directory has an invalid entry"
                        )
                    revision = int(match.group(1))
                    if revision < 1 or entry.name != "{:08d}.json".format(revision):
                        raise SessionCorruptionError(
                            "Session revision directory has an invalid entry"
                        )
                    try:
                        file_stat = entry.stat(follow_symlinks=False)
                    except OSError as error:
                        raise SessionCorruptionError(
                            "cannot inspect Session revision"
                        ) from error
                    if not stat.S_ISREG(file_stat.st_mode):
                        raise SessionCorruptionError(
                            "Session revision directory has an invalid entry"
                        )
                    entry_count += 1
                    if head is not None and revision > head["revision"]:
                        if (
                            pending_name is not None
                            or revision != head["revision"] + 1
                        ):
                            raise SessionCorruptionError(
                                "Session has invalid uncommitted revisions"
                            )
                        pending_name = entry.name
        except OSError as error:
            raise SessionCorruptionError("cannot list Session revisions") from error

        if entry_count == 0:
            if head is not None:
                raise SessionCorruptionError("Session head exists without revisions")
            return {
                "count": 0,
                "latest": None,
                "requested": None,
                "history_digest": _EMPTY_HISTORY_DIGEST,
            }
        if head is None:
            raise SessionCorruptionError("Session revision head is missing")

        committed_revision = head["revision"]
        committed_count = entry_count - (1 if pending_name is not None else 0)
        if committed_count != committed_revision:
            raise SessionCorruptionError("Session revision sequence has a gap")

        previous = None
        latest = None
        requested = None
        history_digest = _EMPTY_HISTORY_DIGEST
        for revision in range(1, committed_revision + 1):
            filename = "{:08d}.json".format(revision)
            document, payload = self._read_revision_file(
                storage, filename, revision
            )
            if previous is not None:
                try:
                    self._validate_transition(previous, document)
                except SessionStoreError as error:
                    raise SessionCorruptionError(
                        "persisted Session revision history is inconsistent"
                    ) from error
            history_digest = _advance_history_digest(history_digest, payload)
            if revision == requested_revision:
                requested = document
            previous = latest = document

        pending_name_to_remove = None
        if pending_name is not None:
            pending_revision = committed_revision + 1
            pending_document, _ = self._read_revision_file(
                storage, pending_name, pending_revision
            )
            try:
                self._validate_transition(latest, pending_document)
            except SessionStoreError as error:
                raise SessionCorruptionError(
                    "uncommitted Session revision is inconsistent"
                ) from error
            if recover_pending:
                pending_name_to_remove = pending_name

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
            _fsync_directory_fd(revisions_fd)
        return {
            "count": committed_revision,
            "latest": latest,
            "requested": requested,
            "history_digest": history_digest,
        }

    def _recover_initial_revision_locked(self, storage, *, expected_payload):
        if self._read_head_locked(storage) is not None or storage["revisions_fd"] is None:
            return False
        try:
            with os.scandir(storage["revisions_fd"]) as entries:
                first_entry = next(entries, None)
                if first_entry is None or first_entry.name != "00000001.json":
                    return False
                if next(entries, None) is not None:
                    return False
        except OSError as error:
            raise SessionCorruptionError("cannot list Session revisions") from error
        document, payload = self._read_revision_file(
            storage, "00000001.json", expected_revision=1
        )
        if payload != expected_payload:
            raise SessionStoreError(
                "interrupted initial revision differs from create request"
            )
        history_digest = _advance_history_digest(_EMPTY_HISTORY_DIGEST, payload)
        head_payload = self._head_payload(1, payload, history_digest)
        _fsync_directory_fd(storage["revisions_fd"])
        self._write_head_locked(storage, head_payload)
        return True

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
            head_stat = _require_private_file(
                fd, SessionCorruptionError, "Session revision head"
            )
            _require_canonical_file_link(
                head_stat,
                storage["session_fd"],
                None,
                SessionCorruptionError,
                "Session revision head",
            )
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
        except (UnicodeDecodeError, ValueError, RecursionError) as error:
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
            file_stat = _require_private_file(
                fd, SessionCorruptionError, "Session revision file"
            )
            _require_canonical_file_link(
                file_stat,
                storage["session_fd"],
                ".session-revision-",
                SessionCorruptionError,
                "Session revision file",
            )
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
        except (UnicodeDecodeError, ValueError, RecursionError) as error:
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
        publication_linked = False
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
            publication_linked = True
            _fsync_directory_fd(storage["revisions_fd"])
            os.unlink(temporary_name, dir_fd=storage["session_fd"])
            temporary_name = None
            _fsync_directory_fd(storage["session_fd"])
        except OSError as error:
            raise SessionStoreError("cannot durably write Session revision") from error
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_name is not None and not publication_linked:
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
            _fsync_directory_fd(storage["session_fd"])
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
