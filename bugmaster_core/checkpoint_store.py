"""Durable, immutable storage for local Session Checkpoint records.

A Checkpoint is a structural anchor only. This store does not verify the
referenced Session, Scope, Action Journal, current authorization, or resume
safety.
"""

import fcntl
import hashlib
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .session_store import (
    _MAX_SESSION_BYTES,
    _canonical_bytes,
    _fsync_directory,
    _nonempty,
    _write_all,
    SessionCorruptionError,
    SessionStoreError,
)


class CheckpointStoreError(SessionStoreError):
    """A Checkpoint cannot be safely validated, stored, or read."""


class CheckpointCorruptionError(SessionCorruptionError):
    """A persisted Checkpoint record is malformed or inconsistent."""


class CheckpointStore:
    """Persist immutable Checkpoints under a session-scoped local directory.

    The caller supplies the versioned Checkpoint schema validator. Each record
    is keyed by a hash of its Checkpoint ID, written through a synced temporary
    file, and linked without replacement. Reads fail closed on malformed data.
    Writers share the Session lock used by ``SessionStore``.
    """

    def __init__(self, root, session_id, validator):
        if not _nonempty(session_id):
            raise CheckpointStoreError("session ID must be a non-empty string")
        if not callable(validator):
            raise CheckpointStoreError("a Checkpoint schema validator is required")
        try:
            storage_key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        except UnicodeEncodeError as error:
            raise CheckpointStoreError("session ID is not valid UTF-8") from error
        self.root = Path(root)
        self.session_id = session_id
        self.validator = validator
        self._sessions_dir = self.root / "sessions"
        self._session_dir = self._sessions_dir / storage_key
        self._checkpoints_dir = self._session_dir / "checkpoints"
        self._lock_path = self._session_dir / "session.lock"

    def create(self, document):
        """Persist a new Checkpoint ID, rejecting replacement."""
        payload, normalized = self._validate_document(document)
        filename = self._checkpoint_filename(normalized["checkpointId"])
        with self._locked():
            self._ensure_private_directory(self._checkpoints_dir)
            self._write_checkpoint_locked(filename, payload)
        return normalized

    def read(self, checkpoint_id):
        """Return a validated Checkpoint by ID, or None when it is absent."""
        if not _nonempty(checkpoint_id):
            raise CheckpointStoreError("checkpoint ID must be a non-empty string")
        filename = self._checkpoint_filename(checkpoint_id)
        with self._locked(create_directories=False):
            if self._checkpoints_dir.is_symlink():
                raise CheckpointCorruptionError("Checkpoint storage path cannot be a symlink")
            if not self._checkpoints_dir.exists():
                return None
            if not self._checkpoints_dir.is_dir():
                raise CheckpointCorruptionError("Checkpoint storage path is not a directory")
            path = self._checkpoints_dir / filename
            if path.is_symlink():
                raise CheckpointCorruptionError("Checkpoint record cannot be a symlink")
            if not path.exists():
                return None
            if not path.is_file():
                raise CheckpointCorruptionError("Checkpoint record is not a regular file")
            return self._read_checkpoint_file(path, checkpoint_id)

    def _checkpoint_filename(self, checkpoint_id):
        try:
            key = hashlib.sha256(checkpoint_id.encode("utf-8")).hexdigest()
        except UnicodeEncodeError as error:
            raise CheckpointStoreError("checkpoint ID is not valid UTF-8") from error
        return key + ".json"

    def _validate_document(self, document, *, persisted=False):
        error_type = CheckpointCorruptionError if persisted else CheckpointStoreError
        if not isinstance(document, dict):
            raise error_type("Checkpoint document must be an object")
        if document.get("sessionId") != self.session_id:
            raise error_type("Checkpoint session identity does not match the store")
        if not _nonempty(document.get("checkpointId")):
            raise error_type("Checkpoint ID must be a non-empty string")
        try:
            payload = _canonical_bytes(document)
        except (TypeError, ValueError, UnicodeEncodeError) as error:
            raise error_type("Checkpoint document is not valid JSON data") from error
        if len(payload) > _MAX_SESSION_BYTES:
            raise error_type("Checkpoint document exceeds the storage size limit")
        normalized = json.loads(payload.decode("utf-8"))
        try:
            self.validator(normalized)
        except Exception as error:
            raise error_type("Checkpoint document does not satisfy its schema") from error
        return payload, normalized

    @contextmanager
    def _locked(self, create_directories=True):
        if create_directories:
            self._ensure_directories()
        elif not self._session_dir.exists():
            yield
            return

        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(str(self._lock_path), flags, 0o600)
        except OSError as error:
            raise CheckpointStoreError("cannot open Session lock") from error
        acquired = False
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise CheckpointStoreError("Session lock is not a regular file")
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            acquired = True
            yield
        except OSError as error:
            raise CheckpointStoreError("Checkpoint storage lock failed") from error
        finally:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _ensure_directories(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.root.is_symlink() or not self.root.is_dir():
                raise CheckpointStoreError("Checkpoint root must be a real directory")
            self._ensure_private_directory(self._sessions_dir)
            self._ensure_private_directory(self._session_dir)
        except OSError as error:
            raise CheckpointStoreError("cannot prepare Checkpoint storage directories") from error

    def _ensure_private_directory(self, directory):
        created = False
        try:
            directory.mkdir(mode=0o700)
            created = True
        except FileExistsError:
            pass
        if directory.is_symlink() or not directory.is_dir():
            raise CheckpointStoreError("Checkpoint storage path must be a real directory")
        os.chmod(directory, 0o700)
        if created:
            _fsync_directory(directory.parent)

    def _read_checkpoint_file(self, path, expected_id):
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(str(path), flags)
        except OSError as error:
            raise CheckpointCorruptionError("cannot open persisted Checkpoint") from error
        try:
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode) or stat.S_IMODE(file_stat.st_mode) != 0o600:
                raise CheckpointCorruptionError("Checkpoint file permissions are invalid")
            if file_stat.st_size > _MAX_SESSION_BYTES + 1:
                raise CheckpointCorruptionError("persisted Checkpoint is too large")
            raw = bytearray()
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                raw.extend(chunk)
        finally:
            os.close(fd)

        if not raw.endswith(b"\n"):
            raise CheckpointCorruptionError("persisted Checkpoint is incomplete")
        try:
            document = json.loads(bytes(raw[:-1]).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CheckpointCorruptionError("persisted Checkpoint is invalid JSON") from error
        payload, normalized = self._validate_document(document, persisted=True)
        if bytes(raw[:-1]) != payload:
            raise CheckpointCorruptionError("persisted Checkpoint is not canonical JSON")
        if normalized["checkpointId"] != expected_id:
            raise CheckpointCorruptionError("Checkpoint ID does not match its storage key")
        return normalized

    def _write_checkpoint_locked(self, filename, payload):
        final_path = self._checkpoints_dir / filename
        fd, temporary_path = tempfile.mkstemp(
            prefix=".checkpoint-", dir=str(self._session_dir)
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
                raise CheckpointStoreError("Checkpoint ID is already stored") from error
            _fsync_directory(self._checkpoints_dir)
            os.unlink(temporary_path)
            temporary_path = None
            _fsync_directory(self._session_dir)
        except OSError as error:
            raise CheckpointStoreError("cannot durably write Checkpoint") from error
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
