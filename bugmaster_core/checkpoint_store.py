"""Durable, immutable storage for local Session Checkpoint records.

A Checkpoint is a structural anchor only. This store does not verify the
referenced Session, Scope, Action Journal, current authorization, or resume
safety.
"""

import hashlib
import json
import os
import stat
from contextlib import contextmanager

from .session_store import (
    _MAX_SESSION_BYTES,
    _canonical_bytes,
    _create_temporary_file,
    _fsync_directory_fd,
    _nonempty,
    _open_child_directory,
    _write_all,
    SessionCorruptionError,
    SessionStore,
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
            self._session_store = SessionStore(
                root, session_id, lambda _document: None
            )
        except (SessionStoreError, OSError) as error:
            raise CheckpointStoreError(str(error)) from error
        self.root = self._session_store.root
        self.session_id = session_id
        self.validator = validator
        self._sessions_dir = self._session_store._sessions_dir
        self._session_dir = self._session_store._session_dir
        self._checkpoints_dir = self._session_dir / "checkpoints"
        self._lock_path = self._session_dir / "session.lock"

    def create(self, document):
        """Persist a new Checkpoint ID, rejecting replacement."""
        payload, normalized = self._validate_document(document)
        filename = self._checkpoint_filename(normalized["checkpointId"])
        with self._locked() as storage:
            checkpoints_fd = _open_child_directory(
                storage["session_fd"],
                "checkpoints",
                create=True,
                error_type=CheckpointStoreError,
                label="Checkpoint storage",
                private=True,
            )
            try:
                self._write_checkpoint_locked(storage, checkpoints_fd, filename, payload)
            finally:
                os.close(checkpoints_fd)
        return normalized

    def read(self, checkpoint_id):
        """Return a validated Checkpoint by ID, or None when it is absent."""
        if not _nonempty(checkpoint_id):
            raise CheckpointStoreError("checkpoint ID must be a non-empty string")
        filename = self._checkpoint_filename(checkpoint_id)
        with self._locked(create_directories=False) as storage:
            if storage is None:
                return None
            checkpoints_fd = _open_child_directory(
                storage["session_fd"],
                "checkpoints",
                create=False,
                error_type=CheckpointCorruptionError,
                label="Checkpoint storage",
            )
            if checkpoints_fd is None:
                return None
            try:
                directory_stat = os.fstat(checkpoints_fd)
                if stat.S_IMODE(directory_stat.st_mode) != 0o700:
                    raise CheckpointCorruptionError(
                        "Checkpoint directory permissions are invalid"
                    )
                return self._read_checkpoint_file(
                    checkpoints_fd, filename, checkpoint_id
                )
            finally:
                os.close(checkpoints_fd)

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
        except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as error:
            raise error_type("Checkpoint document is not valid JSON data") from error
        if len(payload) > _MAX_SESSION_BYTES:
            raise error_type("Checkpoint document exceeds the storage size limit")
        try:
            normalized = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError) as error:
            raise error_type("Checkpoint document is not valid JSON data") from error
        try:
            self.validator(normalized)
        except Exception as error:
            raise error_type("Checkpoint document does not satisfy its schema") from error
        return payload, normalized

    @contextmanager
    def _locked(self, create_directories=True):
        try:
            if not all(
                hasattr(os, name)
                for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
            ):
                raise CheckpointStoreError(
                    "secure Checkpoint directory operations are unavailable"
                )
            with self._session_store._locked(create_directories) as storage:
                yield storage
        except CheckpointCorruptionError:
            raise
        except SessionCorruptionError as error:
            raise CheckpointCorruptionError(
                "Checkpoint Session storage is corrupt"
            ) from error
        except CheckpointStoreError:
            raise
        except SessionStoreError as error:
            raise CheckpointStoreError(
                "cannot safely access Checkpoint Session storage"
            ) from error

    def _ensure_directories(self):
        try:
            self._session_store._ensure_directories()
        except SessionCorruptionError as error:
            raise CheckpointCorruptionError(
                "Checkpoint Session storage is corrupt"
            ) from error
        except SessionStoreError as error:
            raise CheckpointStoreError(
                "cannot safely prepare Checkpoint Session storage"
            ) from error

    def _read_checkpoint_file(self, checkpoints_fd, filename, expected_id):
        try:
            path_stat = os.stat(filename, dir_fd=checkpoints_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise CheckpointCorruptionError("cannot inspect persisted Checkpoint") from error
        if not stat.S_ISREG(path_stat.st_mode):
            raise CheckpointCorruptionError("Checkpoint record is not a regular file")

        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        try:
            fd = os.open(filename, flags, dir_fd=checkpoints_fd)
        except FileNotFoundError:
            return None
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
                if len(raw) + len(chunk) > _MAX_SESSION_BYTES + 1:
                    raise CheckpointCorruptionError("persisted Checkpoint is too large")
                raw.extend(chunk)
        finally:
            os.close(fd)

        if not raw.endswith(b"\n"):
            raise CheckpointCorruptionError("persisted Checkpoint is incomplete")
        try:
            document = json.loads(bytes(raw[:-1]).decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError) as error:
            raise CheckpointCorruptionError("persisted Checkpoint is invalid JSON") from error
        payload, normalized = self._validate_document(document, persisted=True)
        if bytes(raw[:-1]) != payload:
            raise CheckpointCorruptionError("persisted Checkpoint is not canonical JSON")
        if normalized["checkpointId"] != expected_id:
            raise CheckpointCorruptionError("Checkpoint ID does not match its storage key")
        return normalized

    def _write_checkpoint_locked(self, storage, checkpoints_fd, filename, payload):
        fd, temporary_name = _create_temporary_file(
            storage["session_fd"], ".checkpoint-"
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
                    dst_dir_fd=checkpoints_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise CheckpointStoreError("Checkpoint ID is already stored") from error
            _fsync_directory_fd(checkpoints_fd)
            os.unlink(temporary_name, dir_fd=storage["session_fd"])
            temporary_name = None
            _fsync_directory_fd(storage["session_fd"])
        except OSError as error:
            raise CheckpointStoreError("cannot durably write Checkpoint") from error
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=storage["session_fd"])
                except FileNotFoundError:
                    pass
