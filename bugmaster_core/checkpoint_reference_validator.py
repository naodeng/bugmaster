"""Cross-check local Checkpoint, Session, Scope, and Journal references."""

from pathlib import Path


class CheckpointReferenceError(ValueError):
    """A Checkpoint reference is absent or inconsistent with stored records."""


class CheckpointReferenceValidator:
    """Validate local references without authorizing or performing resume.

    The stores must share one local root and Session identity. Callers provide
    the ActionJournal instance associated with that Session; this validator
    checks its Session identity and hash-chain prefix, but does not establish
    journal ID-to-path provenance or event truth.
    """

    def __init__(self, checkpoint_store, session_store, journal):
        session_ids = (
            checkpoint_store.session_id,
            session_store.session_id,
            journal.session_id,
        )
        if len(set(session_ids)) != 1:
            raise CheckpointReferenceError(
                "Checkpoint, Session, and Journal must belong to one Session"
            )
        if Path(checkpoint_store.root).absolute() != Path(session_store.root).absolute():
            raise CheckpointReferenceError(
                "Checkpoint and Session stores must share one storage root"
            )
        self.checkpoint_store = checkpoint_store
        self.session_store = session_store
        self.journal = journal

    def validate(self, checkpoint_id):
        """Return a Checkpoint whose local Session, Scope, and Journal anchors match."""
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise CheckpointReferenceError(
                "Checkpoint ID must be a non-empty string"
            )
        filename = self.checkpoint_store._checkpoint_filename(checkpoint_id)
        with self.checkpoint_store._locked(create_directories=False) as storage:
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
        if not self.journal.matches_prefix(
            checkpoint["journalSequence"], checkpoint["journalHeadHash"]
        ):
            raise CheckpointReferenceError(
                "Checkpoint Journal prefix does not match the stored Journal"
            )
        return checkpoint

