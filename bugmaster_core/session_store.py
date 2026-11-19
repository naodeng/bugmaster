"""Durable, append-only storage for versioned local Session documents.

This module persists validated Session revisions but does not authorize
actions or decide whether a Session is safe to resume.
"""

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path


_REVISION_FILE = re.compile(r"^([0-9]{8,})\.json$")
_MAX_SESSION_BYTES = 4 * 1024 * 1024
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
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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
        self.root = Path(root).absolute()
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
        with self._locked():
            if self._read_revisions_locked():
                raise SessionStoreError("Session already has a stored revision")
            self._write_revision_locked(1, payload)
            self._write_head_locked(1, payload)
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
        with self._locked():
            revisions = self._read_revisions_locked()
            if not revisions:
                raise SessionStoreError("Session has no initial revision")
            current = revisions[-1]
            if current["revision"] != expected_revision:
                raise SessionStoreError("expected Session revision is stale")
            self._validate_transition(current, normalized)
            self._write_revision_locked(normalized["revision"], payload)
            self._write_head_locked(normalized["revision"], payload)
        return normalized

    def read_latest(self):
        """Return the latest validated revision, or None if no Session exists."""
        with self._locked(create_directories=False):
            revisions = self._read_revisions_locked()
        return revisions[-1] if revisions else None

    def read_revision(self, revision):
        """Return one validated revision, or None if that revision is absent."""
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise SessionStoreError("revision must be a positive integer")
        with self._locked(create_directories=False):
            revisions = self._read_revisions_locked()
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
        if create_directories:
            self._ensure_directories()
        else:
            for directory in (self.root, self._sessions_dir, self._session_dir):
                if not self._existing_directory(directory, "Session storage"):
                    yield
                    return

        flags = os.O_RDONLY if not create_directories else os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            if create_directories:
                fd = os.open(str(self._lock_path), flags, 0o600)
            else:
                fd = os.open(str(self._lock_path), flags)
        except OSError as error:
            raise SessionStoreError("cannot open Session lock") from error
        acquired = False
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise SessionStoreError("Session lock is not a regular file")
            if create_directories:
                os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX if create_directories else fcntl.LOCK_SH)
            acquired = True
            yield
        except OSError as error:
            raise SessionStoreError("Session storage lock failed") from error
        finally:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _ensure_directories(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.root.is_symlink() or not self.root.is_dir():
                raise SessionStoreError("Session root must be a real directory")
            self._ensure_private_directory(self._sessions_dir)
            self._ensure_private_directory(self._session_dir)
            self._ensure_private_directory(self._revisions_dir)
        except OSError as error:
            raise SessionStoreError("cannot prepare Session storage directories") from error

    @staticmethod
    def _existing_directory(directory, label, error_type=SessionCorruptionError):
        try:
            directory_stat = directory.lstat()
        except FileNotFoundError:
            return False
        except OSError as error:
            raise error_type("cannot inspect {} path".format(label)) from error
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise error_type("{} path is not a real directory".format(label))
        return True

    def _ensure_private_directory(self, directory):
        created = False
        try:
            directory.mkdir(mode=0o700)
            created = True
        except FileExistsError:
            pass
        if directory.is_symlink() or not directory.is_dir():
            raise SessionStoreError("Session storage path must be a real directory")
        os.chmod(directory, 0o700)
        if created:
            _fsync_directory(directory.parent)

    def _read_revisions_locked(self):
        revisions = []
        if self._existing_directory(self._revisions_dir, "Session revisions"):
            try:
                entries = list(self._revisions_dir.iterdir())
            except OSError as error:
                raise SessionCorruptionError("cannot list Session revisions") from error

            revision_files = []
            for entry in entries:
                match = _REVISION_FILE.fullmatch(entry.name)
                if match is None or entry.is_symlink() or not entry.is_file():
                    raise SessionCorruptionError("Session revision directory has an invalid entry")
                revision_files.append((int(match.group(1)), entry))
            revision_files.sort(key=lambda pair: pair[0])

            expected_revision = 1
            for revision, path in revision_files:
                if revision != expected_revision:
                    raise SessionCorruptionError("Session revision sequence has a gap")
                document = self._read_revision_file(path, revision)
                if revisions:
                    try:
                        self._validate_transition(revisions[-1], document)
                    except SessionStoreError as error:
                        raise SessionCorruptionError(
                            "persisted Session revision history is inconsistent"
                        ) from error
                revisions.append(document)
                expected_revision += 1

        head = self._read_head_locked()
        if not revisions:
            if head is not None:
                raise SessionCorruptionError("Session head exists without revisions")
            return []
        if head is None:
            raise SessionCorruptionError("Session revision head is missing")
        latest = revisions[-1]
        expected_digest = hashlib.sha256(_canonical_bytes(latest)).hexdigest()
        if head["revision"] != latest["revision"] or head["revisionDigest"] != expected_digest:
            raise SessionCorruptionError("Session revision history does not match its committed head")
        return revisions

    def _read_head_locked(self):
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(str(self._head_path), flags)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise SessionCorruptionError("cannot open Session revision head") from error
        try:
            head_stat = os.fstat(fd)
            if not stat.S_ISREG(head_stat.st_mode) or stat.S_IMODE(head_stat.st_mode) != 0o600:
                raise SessionCorruptionError("Session revision head permissions are invalid")
            if head_stat.st_size > 1024:
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
            or set(head) != {"sessionId", "revision", "revisionDigest"}
            or head.get("sessionId") != self.session_id
            or isinstance(head.get("revision"), bool)
            or not isinstance(head.get("revision"), int)
            or head["revision"] < 1
            or not isinstance(head.get("revisionDigest"), str)
            or re.fullmatch(r"[a-f0-9]{64}", head["revisionDigest"]) is None
            or bytes(raw[:-1]) != _canonical_bytes(head)
        ):
            raise SessionCorruptionError("Session revision head fields are invalid")
        return head

    def _read_revision_file(self, path, expected_revision):
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(str(path), flags)
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
        return normalized

    def _write_revision_locked(self, revision, payload):
        filename = "{:08d}.json".format(revision)
        final_path = self._revisions_dir / filename
        fd, temporary_path = tempfile.mkstemp(
            prefix=".session-revision-", dir=str(self._session_dir)
        )
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, payload + b"\n")
            os.fsync(fd)
            os.close(fd)
            fd = None
            try:
                os.link(temporary_path, final_path)
            except FileExistsError as error:
                raise SessionCorruptionError("Session revision file already exists") from error
            _fsync_directory(self._revisions_dir)
            os.unlink(temporary_path)
            temporary_path = None
            _fsync_directory(self._session_dir)
        except OSError as error:
            raise SessionStoreError("cannot durably write Session revision") from error
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass

    def _write_head_locked(self, revision, payload):
        head = {
            "sessionId": self.session_id,
            "revision": revision,
            "revisionDigest": hashlib.sha256(payload).hexdigest(),
        }
        encoded = _canonical_bytes(head) + b"\n"
        fd, temporary_path = tempfile.mkstemp(
            prefix=".session-head-", dir=str(self._session_dir)
        )
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, encoded)
            os.fsync(fd)
            os.close(fd)
            fd = None
            os.replace(temporary_path, self._head_path)
            temporary_path = None
            _fsync_directory(self._session_dir)
        except OSError as error:
            raise SessionStoreError("cannot durably update Session revision head") from error
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
