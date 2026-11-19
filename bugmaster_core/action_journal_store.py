"""Resolve append-only Action Journals from stable local identities."""

import hashlib
import os
from pathlib import Path

from .action_journal import ActionJournal, JournalError, _fsync_directory, _nonempty


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
        self._root = Path(root)
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
        """Return an ActionJournal reader/writer at the canonical local path."""
        self._ensure_directories()
        return ActionJournal(self.path, self.session_id, self.journal_id)

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
