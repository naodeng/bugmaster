"""Cross-check local Checkpoint, Session, Scope, and Journal references."""

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
            Path(journal_store.root).absolute(),
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
        checkpoint = self.checkpoint_store.read(checkpoint_id)
        if checkpoint is None:
            raise CheckpointReferenceError("Checkpoint is not stored")

        session = self.session_store.read_revision(checkpoint["sessionRevision"])
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

        latest_session = self.session_store.read_latest()
        if latest_session is None:
            raise CheckpointReferenceError("Session history is not stored")
        if checkpoint_id not in latest_session["checkpointRefs"]:
            raise CheckpointReferenceError(
                "Latest Session revision does not reference the Checkpoint"
            )
        if self.journal_store.journal_id != latest_session["journalId"]:
            raise CheckpointReferenceError(
                "Session Journal ID does not match the Journal store"
            )
        journal = self.journal_store.open()
        if not journal.matches_prefix(
            checkpoint["journalSequence"], checkpoint["journalHeadHash"]
        ):
            raise CheckpointReferenceError(
                "Checkpoint Journal prefix does not match the stored Journal"
            )
        return checkpoint
