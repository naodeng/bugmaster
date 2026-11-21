"""Cross-check local Checkpoint, Session, Scope, and Journal references."""

import os
from pathlib import Path

from .action_journal_store import ActionJournalStore


class CheckpointReferenceError(ValueError):
    """A Checkpoint reference is absent or inconsistent with stored records."""


class CheckpointReferenceValidator:
    """Validate local references without authorizing or performing resume.

    The stores must share one local root and Session identity. The validator
    resolves the Journal through its deterministic Session/Journal ID mapping;
    it does not establish event authenticity or external truth.
    """

    def __init__(self, checkpoint_store, session_store, journal_store):
        if not isinstance(journal_store, ActionJournalStore):
            raise CheckpointReferenceError(
                "Checkpoint validation requires a deterministic Journal store"
            )
        session_ids = (
            checkpoint_store.session_id,
            session_store.session_id,
            journal_store.session_id,
        )
        if len(set(session_ids)) != 1:
            raise CheckpointReferenceError(
                "Checkpoint, Session, and Journal must belong to one Session"
            )
        roots = {
            Path(checkpoint_store.root).absolute(),
            Path(session_store.root).absolute(),
            Path(journal_store._resolved_root).absolute(),
        }
        if len(roots) != 1:
            raise CheckpointReferenceError(
                "Checkpoint, Session, and Journal stores must share one storage root"
            )
        self.checkpoint_store = checkpoint_store
        self.session_store = session_store
        self.journal_store = journal_store

    def validate(self, checkpoint_id):
        """Return a Checkpoint whose local Session, Scope, and Journal anchors match."""
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise CheckpointReferenceError(
                "Checkpoint ID must be a non-empty string"
            )
        try:
            root_fd = self.journal_store._open_root_directory(create=False)
        except FileNotFoundError as error:
            raise CheckpointReferenceError("Checkpoint storage root is missing") from error
        try:
            filename = self.checkpoint_store._checkpoint_filename(checkpoint_id)
            with self.checkpoint_store._locked(
                create_directories=False, root_fd=root_fd
            ) as storage:
                if storage is None:
                    raise CheckpointReferenceError("Checkpoint is not stored")
                checkpoint = self.checkpoint_store._read_locked(
                    storage, checkpoint_id, filename
                )
                if checkpoint is None:
                    raise CheckpointReferenceError("Checkpoint is not stored")

                session_revision = checkpoint["sessionRevision"]
                if isinstance(session_revision, float):
                    if not session_revision.is_integer():
                        raise CheckpointReferenceError(
                            "Checkpoint Session revision must be an integer"
                        )
                    session_revision = int(session_revision)
                if (
                    isinstance(session_revision, bool)
                    or not isinstance(session_revision, int)
                    or session_revision < 1
                ):
                    raise CheckpointReferenceError(
                        "Checkpoint Session revision must be a positive integer"
                    )
                history = self.session_store._read_revisions_locked(
                    storage, requested_revision=session_revision
                )
                session = history["requested"]
                latest_session = history["latest"]
                if session is None:
                    raise CheckpointReferenceError(
                        "Checkpoint Session revision is not stored"
                    )
                scope_anchor_exists = any(
                    reference["scopeId"] == checkpoint["scopeId"]
                    and reference["revision"] == checkpoint["scopeRevision"]
                    for reference in session["scopeHistory"]
                )
                if not scope_anchor_exists:
                    raise CheckpointReferenceError(
                        "Checkpoint Scope revision is absent from its Session revision"
                    )

                if checkpoint_id not in latest_session["checkpointRefs"]:
                    raise CheckpointReferenceError(
                        "Latest Session revision does not reference the Checkpoint"
                    )
                if self.journal_store.journal_id != latest_session["journalId"]:
                    raise CheckpointReferenceError(
                        "Session Journal ID does not match the Journal store"
                    )
                journal = self.journal_store._open_from_root_fd(storage["root_fd"])
            with journal:
                if not journal.matches_prefix(
                    checkpoint["journalSequence"], checkpoint["journalHeadHash"]
                ):
                    raise CheckpointReferenceError(
                        "Checkpoint Journal prefix does not match the stored Journal"
                    )
            return checkpoint
        finally:
            os.close(root_fd)
