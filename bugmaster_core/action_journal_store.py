"""Resolve append-only Action Journals from stable local identities."""

import hashlib
import os
import stat
from pathlib import Path

from .action_journal import (
    ActionJournal,
    JournalCorruptionError,
    JournalError,
    _fsync_directory,
    _nonempty,
)


class ActionJournalStoreError(JournalError):
    """A Journal identity or its deterministic storage path is invalid."""


class ActionJournalStore:
    """Map one Session and Journal identity to a canonical local file.

    The mapping is ``<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl``.
    It prevents callers of the reference validator from choosing an arbitrary
    file for a declared Journal ID. It does not authenticate local file content.
    """

    def __init__(self, root, session_id, journal_id):
        if not _nonempty(session_id):
            raise ActionJournalStoreError("session ID must be a non-empty string")
        if not _nonempty(journal_id):
            raise ActionJournalStoreError("journal ID must be a non-empty string")
        try:
            session_key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
            journal_key = hashlib.sha256(journal_id.encode("utf-8")).hexdigest()
        except UnicodeEncodeError as error:
            raise ActionJournalStoreError(
                "Journal identity is not valid UTF-8"
            ) from error
        self._root = Path(root).absolute()
        self._session_id = session_id
        self._journal_id = journal_id
        self._journals_dir = self._root / "journals"
        self._session_dir = self._journals_dir / session_key
        self._path = self._session_dir / (journal_key + ".jsonl")

    @property
    def path(self):
        """Return the deterministic path selected by this store's identities."""
        return self._path

    @property
    def root(self):
        """Return the storage root fixed when the store was constructed."""
        return self._root

    @property
    def session_id(self):
        """Return the Session identity fixed when the store was constructed."""
        return self._session_id

    @property
    def journal_id(self):
        """Return the Journal identity fixed when the store was constructed."""
        return self._journal_id

    def open(self):
        """Open an existing canonical Journal without creating or changing paths."""
        for directory in (self.root, self._journals_dir, self._session_dir):
            self._require_existing_directory(directory)
        try:
            file_stat = self.path.lstat()
        except FileNotFoundError as error:
            raise JournalCorruptionError("canonical journal file is missing") from error
        except OSError as error:
            raise ActionJournalStoreError("cannot inspect canonical Journal path") from error
        if not stat.S_ISREG(file_stat.st_mode):
            raise JournalCorruptionError("canonical journal path is not a regular file")
        return ActionJournal(
            self.path,
            self.session_id,
            self.journal_id,
            require_existing=True,
        )

    def initialize(self):
        """Create storage for a new Journal or reopen its canonical writer path."""
        self._ensure_directories()
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            fd = os.open(str(self.path), flags, 0o600)
        except FileExistsError:
            pass
        except OSError as error:
            raise ActionJournalStoreError("cannot initialize canonical Journal") from error
        else:
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise JournalCorruptionError(
                        "canonical journal path is not a regular file"
                    )
                os.fchmod(fd, 0o600)
                os.fsync(fd)
            except OSError as error:
                raise ActionJournalStoreError(
                    "cannot initialize canonical Journal"
                ) from error
            finally:
                os.close(fd)
            try:
                _fsync_directory(self._session_dir)
            except OSError as error:
                raise ActionJournalStoreError(
                    "cannot synchronize canonical Journal directory"
                ) from error
        return ActionJournal(
            self.path,
            self.session_id,
            self.journal_id,
            require_existing=True,
        )

    @staticmethod
    def _require_existing_directory(directory):
        try:
            directory_stat = directory.lstat()
        except FileNotFoundError as error:
            raise JournalCorruptionError("canonical Journal storage path is missing") from error
        except OSError as error:
            raise ActionJournalStoreError("cannot inspect Journal storage path") from error
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise ActionJournalStoreError("Journal storage path is not a real directory")

    def _ensure_directories(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as error:
            raise ActionJournalStoreError(
                "cannot prepare Journal storage root"
            ) from error
        if self.root.is_symlink() or not self.root.is_dir():
            raise ActionJournalStoreError(
                "Journal storage root must be a real directory"
            )
        self._ensure_private_directory(self._journals_dir)
        self._ensure_private_directory(self._session_dir)

    @staticmethod
    def _ensure_private_directory(directory):
        created = False
        try:
            directory.mkdir(mode=0o700)
            created = True
        except FileExistsError:
            pass
        if directory.is_symlink() or not directory.is_dir():
            raise ActionJournalStoreError(
                "Journal storage path must be a real directory"
            )
        os.chmod(directory, 0o700)
        if created:
            _fsync_directory(directory.parent)
