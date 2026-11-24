"""Persist versioned Candidate and Finding metadata on the local filesystem.

This store keeps evidence references and digests only. It does not save evidence
bytes, authenticate provenance or reviewers, or authorize a confirmed Finding.
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

from .action_journal_store import (
    ActionJournalStoreError,
    _normalize_storage_root,
    _open_absolute_directory,
    _open_directory_at,
    _reject_extended_acl,
)
from .filesystem_security import _has_extended_acl


_REVISION_FILE = re.compile(r"^([0-9]{8,})\.json$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_MAX_RECORD_BYTES = 4 * 1024 * 1024
_MAX_HEAD_BYTES = 1024
_EMPTY_HISTORY_DIGEST = hashlib.sha256(b"BugMaster metadata history v1").hexdigest()
_CANDIDATE_STATUSES = frozenset({"candidate", "needs_review", "duplicate"})
_FINDING_STATUSES = frozenset({"hypothesis", "observed", "suspected", "needs_review"})


class MetadataStoreError(ValueError):
    """A metadata record or its local storage path is invalid."""


class MetadataCorruptionError(MetadataStoreError):
    """Persisted metadata is missing, malformed, or inconsistent."""


class RevisionConflictError(MetadataStoreError):
    """A record already exists or its expected revision is stale."""


def _canonical_bytes(document):
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _normalize_schema_integers(value):
    if type(value) is dict:
        return {
            key: _normalize_schema_integers(item)
            for key, item in value.items()
        }
    if type(value) is list:
        return [_normalize_schema_integers(item) for item in value]
    if type(value) is float and value.is_integer():
        return int(value)
    return value


def _advance_history_digest(previous_digest, payload):
    return hashlib.sha256(
        bytes.fromhex(previous_digest) + len(payload).to_bytes(8, "big") + payload
    ).hexdigest()


def _write_all(file_descriptor, payload):
    offset = 0
    while offset < len(payload):
        written = os.write(file_descriptor, payload[offset:])
        if written <= 0:
            raise OSError("metadata write made no forward progress")
        offset += written


def _create_temporary_file(directory_fd, prefix):
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    for _ in range(8):
        name = prefix + secrets.token_hex(16)
        try:
            return os.open(name, flags, 0o600, dir_fd=directory_fd), name
        except FileExistsError:
            continue
    raise FileExistsError("cannot allocate a unique metadata temporary file")


def _schema_validator(schema_name):
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from referencing import Registry, Resource

        schemas_directory = Path(__file__).resolve().parents[1] / "schemas"
        schema = json.loads(
            (schemas_directory / schema_name).read_text(encoding="utf-8")
        )
        registry = Registry()
        if schema_name == "candidate.schema.json":
            assessment = json.loads(
                (schemas_directory / "candidate-assessment.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            registry = registry.with_resource(
                assessment["$id"], Resource.from_contents(assessment)
            )
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(
            schema, registry=registry, format_checker=FormatChecker()
        ).validate
    except (ImportError, OSError, ValueError, KeyError) as error:
        raise MetadataStoreError(
            "cannot load the {} contract validator".format(schema_name)
        ) from error


class _RevisionedMetadataStore:
    entity_field = None
    storage_name = None
    schema_name = None
    label = None
    identifier_pattern = None

    def __init__(self, root, validator=None):
        try:
            root_path = Path(os.path.abspath(os.fspath(root)))
            self.root = _normalize_storage_root(root_path)
        except (ActionJournalStoreError, OSError, TypeError, ValueError) as error:
            raise MetadataStoreError("metadata storage root is invalid") from error
        self.contract_validator = _schema_validator(self.schema_name)
        self.validator = validator
        if validator is not None and not callable(validator):
            raise MetadataStoreError("a metadata schema validator is required")

    def create(self, document):
        """Create immutable revision 1 for a new record ID."""
        normalized, payload = self._validate_document(document)
        if normalized["revision"] != 1:
            raise MetadataStoreError("a new {} must start at revision 1".format(self.label))
        self._validate_revision_history({1: normalized})
        identifier = normalized[self.entity_field]
        with self._locked(identifier, create=True) as storage:
            history = self._read_history(storage, identifier)
            if history["count"]:
                raise RevisionConflictError("{} already exists".format(self.label))
            history_digest = _advance_history_digest(
                _EMPTY_HISTORY_DIGEST, payload
            )
            self._write_revision(storage, 1, payload)
            self._write_head(storage, 1, payload, history_digest)
        return normalized

    def append_revision(self, document, expected_revision):
        """Append one immutable revision if the current revision still matches."""
        if type(expected_revision) is not int or expected_revision < 1:
            raise MetadataStoreError("expected revision must be a positive integer")
        normalized, payload = self._validate_document(document)
        if normalized["revision"] != expected_revision + 1:
            raise MetadataStoreError(
                "new {} revision must follow expected revision".format(self.label)
            )
        identifier = normalized[self.entity_field]
        with self._locked(identifier, create=True) as storage:
            history = self._read_history(storage, identifier)
            if not history["count"]:
                raise MetadataStoreError("{} has no initial revision".format(self.label))
            if history["latest"]["revision"] != expected_revision:
                raise RevisionConflictError("expected {} revision is stale".format(self.label))
            self._validate_transition(history["latest"], normalized)
            revisions = dict(history["revisions"])
            revisions[normalized["revision"]] = normalized
            self._validate_revision_history(revisions)
            history_digest = _advance_history_digest(
                history["historyDigest"], payload
            )
            revision = normalized["revision"]
            self._write_revision(storage, revision, payload)
            self._write_head(storage, revision, payload, history_digest)
        return normalized

    def read_latest(self, identifier):
        """Return the latest validated revision, or None when the ID is absent."""
        identifier = self._validate_identifier(identifier)
        with self._locked(identifier, create=False) as storage:
            if storage is None:
                return None
            history = self._read_history(storage, identifier)
        return history["latest"]

    def read_revision(self, identifier, revision):
        """Return one validated revision, or None when the ID/revision is absent."""
        identifier = self._validate_identifier(identifier)
        if type(revision) is not int or revision < 1:
            raise MetadataStoreError("revision must be a positive integer")
        with self._locked(identifier, create=False) as storage:
            if storage is None:
                return None
            history = self._read_history(storage, identifier)
        if revision > history["count"]:
            return None
        return history["revisions"][revision]

    def _validate_identifier(self, identifier, *, persisted=False):
        error_type = MetadataCorruptionError if persisted else MetadataStoreError
        if type(identifier) is not str or self.identifier_pattern.fullmatch(identifier) is None:
            raise error_type("{} ID is invalid".format(self.label))
        return identifier

    def _validate_document(self, document, *, persisted=False):
        error_type = MetadataCorruptionError if persisted else MetadataStoreError
        if type(document) is not dict:
            raise error_type("{} must be a JSON object".format(self.label))
        try:
            payload = _canonical_bytes(document)
            normalized = _normalize_schema_integers(
                json.loads(payload.decode("utf-8"))
            )
            payload = _canonical_bytes(normalized)
            if len(payload) > _MAX_RECORD_BYTES:
                raise error_type("{} metadata exceeds the size limit".format(self.label))
            validators = (self.contract_validator, self.validator)
            for validator in validators:
                if validator is None:
                    continue
                try:
                    validator(json.loads(payload.decode("utf-8")))
                except Exception as error:
                    raise error_type(
                        "{} metadata does not match its schema".format(self.label)
                    ) from error
            self._validate_record(normalized, error_type)
        except MetadataStoreError:
            raise
        except (TypeError, ValueError, UnicodeError, RecursionError) as error:
            raise error_type("{} metadata is invalid".format(self.label)) from error
        return normalized, payload

    def _validate_record(self, document, error_type):
        return self._validate_identifier(
            document.get(self.entity_field), persisted=error_type is MetadataCorruptionError
        )

    def _validate_revision_history(self, revisions, *, persisted=False):
        return None

    def _storage_key(self, identifier):
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    @contextmanager
    def _locked(self, identifier, *, create):
        error_type = MetadataStoreError if create else MetadataCorruptionError
        descriptors = []
        lock_fd = None
        acquired = False
        storage = None
        try:
            try:
                root_fd = _open_absolute_directory(
                    self.root, create=create, repair_root=False
                )
            except FileNotFoundError:
                yield None
                return
            except ActionJournalStoreError as error:
                raise error_type("cannot open a safe metadata storage root") from error
            descriptors.append(root_fd)
            parent_fd = root_fd
            for component in (self.storage_name, self._storage_key(identifier)):
                try:
                    child_fd = _open_directory_at(
                        parent_fd,
                        component,
                        create=create,
                        private=True,
                        repair=create,
                    )
                except FileNotFoundError:
                    if not create:
                        yield None
                        return
                    raise error_type("metadata storage directory is missing")
                except ActionJournalStoreError as error:
                    raise error_type("cannot open a safe metadata directory") from error
                descriptors.append(child_fd)
                parent_fd = child_fd

            lock_flags = (
                os.O_RDWR
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_CLOEXEC", 0)
            )
            try:
                lock_fd = os.open("metadata.lock", lock_flags, dir_fd=parent_fd)
            except FileNotFoundError:
                if not create:
                    raise error_type("metadata lock file is missing")
                try:
                    lock_fd = os.open(
                        "metadata.lock",
                        lock_flags | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                except FileExistsError:
                    lock_fd = os.open("metadata.lock", lock_flags, dir_fd=parent_fd)
                else:
                    os.fchmod(lock_fd, 0o600)
                    os.fsync(parent_fd)
            self._require_private_file(lock_fd, error_type, "metadata lock")
            fcntl.flock(lock_fd, fcntl.LOCK_EX if create else fcntl.LOCK_SH)
            acquired = True
            try:
                revisions_fd = _open_directory_at(
                    parent_fd,
                    "revisions",
                    create=create,
                    private=True,
                    repair=create,
                )
            except FileNotFoundError:
                revisions_fd = None
            except ActionJournalStoreError as error:
                raise error_type("cannot open safe metadata revisions") from error
            if revisions_fd is not None:
                descriptors.append(revisions_fd)
            storage = {
                "entity_fd": parent_fd,
                "revisions_fd": revisions_fd,
                "lock_fd": lock_fd,
            }
            yield storage
        except MetadataStoreError:
            raise
        except OSError as error:
            raise error_type("metadata storage operation failed") from error
        finally:
            if acquired:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            if lock_fd is not None:
                os.close(lock_fd)
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    @staticmethod
    def _require_private_file(file_descriptor, error_type, label):
        metadata = os.fstat(file_descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise error_type("{} is not a regular file".format(label))
        if metadata.st_uid != os.geteuid():
            raise error_type("{} has an unsafe owner".format(label))
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise error_type("{} permissions are unsafe".format(label))
        if metadata.st_nlink != 1:
            raise error_type("{} has an unsafe hard link".format(label))
        try:
            if _has_extended_acl(file_descriptor):
                raise error_type("{} has an extended access control list".format(label))
        except OSError as error:
            raise error_type("cannot inspect {} access control".format(label)) from error
        return metadata

    def _read_history(self, storage, identifier):
        self._validate_entity_entries(storage)
        head = self._read_head(storage)
        revisions_fd = storage["revisions_fd"]
        if revisions_fd is None:
            if head is not None:
                raise MetadataCorruptionError("metadata head exists without revisions")
            return {"count": 0, "latest": None, "revisions": {}, "historyDigest": _EMPTY_HISTORY_DIGEST}

        filenames = []
        try:
            with os.scandir(revisions_fd) as entries:
                for entry in entries:
                    match = _REVISION_FILE.fullmatch(entry.name)
                    if match is None:
                        raise MetadataCorruptionError("metadata revisions contain an invalid entry")
                    revision = int(match.group(1))
                    if revision < 1 or entry.name != "{:08d}.json".format(revision):
                        raise MetadataCorruptionError("metadata revision filename is invalid")
                    try:
                        entry_stat = entry.stat(follow_symlinks=False)
                    except OSError as error:
                        raise MetadataCorruptionError("cannot inspect a metadata revision") from error
                    if not stat.S_ISREG(entry_stat.st_mode):
                        raise MetadataCorruptionError("metadata revision is not a regular file")
                    filenames.append((revision, entry.name))
        except MetadataStoreError:
            raise
        except OSError as error:
            raise MetadataCorruptionError("cannot list metadata revisions") from error

        if not filenames:
            if head is not None:
                raise MetadataCorruptionError("metadata head exists without revisions")
            return {"count": 0, "latest": None, "revisions": {}, "historyDigest": _EMPTY_HISTORY_DIGEST}
        if head is None or len(filenames) != head["revision"]:
            raise MetadataCorruptionError("metadata revision history does not match its head")
        filenames.sort()
        if any(revision != index for index, (revision, _) in enumerate(filenames, 1)):
            raise MetadataCorruptionError("metadata revision history has a gap or orphan")

        records = {}
        history_digest = _EMPTY_HISTORY_DIGEST
        previous = None
        latest_payload = None
        for revision, filename in filenames:
            document, payload = self._read_revision(
                storage, filename, revision, identifier
            )
            if previous is not None:
                self._validate_transition(previous, document, persisted=True)
            records[revision] = document
            previous = document
            latest_payload = payload
            history_digest = _advance_history_digest(history_digest, payload)

        if (
            head["revisionDigest"] != hashlib.sha256(latest_payload).hexdigest()
            or head["historyDigest"] != history_digest
        ):
            raise MetadataCorruptionError("metadata revisions do not match their head digest")
        self._validate_revision_history(records, persisted=True)
        return {
            "count": head["revision"],
            "latest": records[head["revision"]],
            "revisions": records,
            "historyDigest": history_digest,
        }

    def _validate_entity_entries(self, storage):
        expected = {"metadata.lock"}
        if storage["revisions_fd"] is not None:
            expected.add("revisions")
        if self._head_exists(storage):
            expected.add("metadata.head")
        try:
            with os.scandir(storage["entity_fd"]) as entries:
                actual = {entry.name for entry in entries}
        except OSError as error:
            raise MetadataCorruptionError("cannot list metadata record directory") from error
        if actual != expected:
            raise MetadataCorruptionError("metadata record directory has unexpected entries")

    @staticmethod
    def _head_exists(storage):
        try:
            os.stat("metadata.head", dir_fd=storage["entity_fd"], follow_symlinks=False)
        except FileNotFoundError:
            return False
        except OSError as error:
            raise MetadataCorruptionError("cannot inspect metadata head") from error
        return True

    def _read_head(self, storage):
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            file_descriptor = os.open("metadata.head", flags, dir_fd=storage["entity_fd"])
        except FileNotFoundError:
            return None
        except OSError as error:
            raise MetadataCorruptionError("cannot open metadata head") from error
        try:
            metadata = self._require_private_file(
                file_descriptor, MetadataCorruptionError, "metadata head"
            )
            if metadata.st_size > _MAX_HEAD_BYTES:
                raise MetadataCorruptionError("metadata head exceeds the size limit")
            raw = self._read_all(file_descriptor, _MAX_HEAD_BYTES, "metadata head")
        finally:
            os.close(file_descriptor)
        head = self._decode_canonical_json(raw, "metadata head")
        if (
            type(head) is not dict
            or set(head) != {"schemaVersion", "revision", "revisionDigest", "historyDigest"}
            or head["schemaVersion"] != "1.0"
            or type(head["revision"]) is not int
            or head["revision"] < 1
            or type(head["revisionDigest"]) is not str
            or _SHA256.fullmatch(head["revisionDigest"]) is None
            or type(head["historyDigest"]) is not str
            or _SHA256.fullmatch(head["historyDigest"]) is None
        ):
            raise MetadataCorruptionError("metadata head fields are invalid")
        return head

    def _read_revision(self, storage, filename, expected_revision, identifier):
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            file_descriptor = os.open(
                filename, flags, dir_fd=storage["revisions_fd"]
            )
        except OSError as error:
            raise MetadataCorruptionError("cannot open metadata revision") from error
        try:
            metadata = self._require_private_file(
                file_descriptor, MetadataCorruptionError, "metadata revision"
            )
            if metadata.st_size > _MAX_RECORD_BYTES + 1:
                raise MetadataCorruptionError("metadata revision exceeds the size limit")
            raw = self._read_all(file_descriptor, _MAX_RECORD_BYTES + 1, "metadata revision")
        finally:
            os.close(file_descriptor)
        document = self._decode_canonical_json(raw, "metadata revision")
        normalized, payload = self._validate_document(document, persisted=True)
        if payload != raw[:-1] or normalized[self.entity_field] != identifier:
            raise MetadataCorruptionError("metadata revision identity or encoding is invalid")
        if normalized["revision"] != expected_revision:
            raise MetadataCorruptionError("metadata revision does not match its filename")
        return normalized, payload

    @staticmethod
    def _read_all(file_descriptor, maximum, label):
        raw = bytearray()
        while len(raw) <= maximum:
            chunk = os.read(file_descriptor, min(65536, maximum + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > maximum:
            raise MetadataCorruptionError("{} exceeds the size limit".format(label))
        return bytes(raw)

    @staticmethod
    def _decode_canonical_json(raw, label):
        if not raw.endswith(b"\n"):
            raise MetadataCorruptionError("{} is incomplete".format(label))
        try:
            document = json.loads(raw[:-1].decode("utf-8"))
            canonical = _canonical_bytes(document)
        except (UnicodeDecodeError, ValueError, TypeError, RecursionError) as error:
            raise MetadataCorruptionError("{} is invalid JSON".format(label)) from error
        if canonical != raw[:-1]:
            raise MetadataCorruptionError("{} is not canonical JSON".format(label))
        return document

    def _write_revision(self, storage, revision, payload):
        revisions_fd = storage["revisions_fd"]
        filename = "{:08d}.json".format(revision)
        file_descriptor, temporary_name = _create_temporary_file(
            revisions_fd, ".metadata-revision-"
        )
        linked = False
        try:
            os.fchmod(file_descriptor, 0o600)
            _write_all(file_descriptor, payload + b"\n")
            os.fsync(file_descriptor)
            os.close(file_descriptor)
            file_descriptor = None
            try:
                os.link(
                    temporary_name,
                    filename,
                    src_dir_fd=revisions_fd,
                    dst_dir_fd=revisions_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise MetadataCorruptionError("metadata revision already exists") from error
            linked = True
            os.fsync(revisions_fd)
            os.unlink(temporary_name, dir_fd=revisions_fd)
            temporary_name = None
            os.fsync(revisions_fd)
        except MetadataStoreError:
            raise
        except OSError as error:
            raise MetadataStoreError("cannot durably write metadata revision") from error
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            if temporary_name is not None and not linked:
                try:
                    os.unlink(temporary_name, dir_fd=revisions_fd)
                except FileNotFoundError:
                    pass

    def _write_head(self, storage, revision, payload, history_digest):
        head = {
            "schemaVersion": "1.0",
            "revision": revision,
            "revisionDigest": hashlib.sha256(payload).hexdigest(),
            "historyDigest": history_digest,
        }
        encoded = _canonical_bytes(head) + b"\n"
        file_descriptor, temporary_name = _create_temporary_file(
            storage["entity_fd"], ".metadata-head-"
        )
        try:
            os.fchmod(file_descriptor, 0o600)
            _write_all(file_descriptor, encoded)
            os.fsync(file_descriptor)
            os.close(file_descriptor)
            file_descriptor = None
            os.replace(
                temporary_name,
                "metadata.head",
                src_dir_fd=storage["entity_fd"],
                dst_dir_fd=storage["entity_fd"],
            )
            temporary_name = None
            os.fsync(storage["entity_fd"])
        except OSError as error:
            raise MetadataStoreError("cannot durably update metadata head") from error
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=storage["entity_fd"])
                except FileNotFoundError:
                    pass


class CandidateStore(_RevisionedMetadataStore):
    """Persist provisional Candidate revisions without authenticating claims."""

    entity_field = "candidateId"
    storage_name = "candidates"
    schema_name = "candidate.schema.json"
    label = "Candidate"
    identifier_pattern = re.compile(r"^CF-[A-Z0-9][A-Z0-9-]{0,63}$")

    def _validate_record(self, document, error_type):
        identifier = super()._validate_record(document, error_type)
        assessment = document["candidateAssessment"]
        linked_fields = (
            "candidateId",
            "revision",
            "observedSurface",
            "patternId",
            "oracleRef",
            "evidenceRefs",
            "falsePositiveChecks",
            "identity",
        )
        if any(assessment.get(field) != document.get(field) for field in linked_fields):
            raise error_type("Candidate Assessment does not match its Candidate revision")
        identity = document.get("identity")
        if identity is not None and identity["oracleRef"] != document.get("oracleRef"):
            raise error_type("Candidate identity does not match its Oracle reference")
        if assessment["review"]["required"] is not document["reviewRequired"]:
            raise error_type("Candidate review requirement is inconsistent")
        if assessment["decision"] not in _CANDIDATE_STATUSES:
            raise error_type("Candidate decision requires an unavailable trusted verifier")
        if (
            assessment["decision"] == "duplicate"
            and assessment["duplicateOf"]["candidateId"] == identifier
        ):
            raise error_type("Candidate cannot be a duplicate of itself")
        seen_event_ids = set()
        assessment_evidence_refs = set(assessment["evidenceRefs"])
        for event in assessment["review"]["events"]:
            if (
                event["candidateId"] != identifier
                or event["candidateRevision"] > document["revision"]
                or event["eventId"] in seen_event_ids
                or not set(event["evidenceRefs"]).issubset(assessment_evidence_refs)
            ):
                raise error_type("Candidate review event does not bind to its record")
            seen_event_ids.add(event["eventId"])
        return identifier

    def _validate_revision_history(self, revisions, *, persisted=False):
        error_type = MetadataCorruptionError if persisted else MetadataStoreError
        for document in revisions.values():
            events = document["candidateAssessment"]["review"]["events"]
            for event in events:
                reviewed_revision = revisions.get(event["candidateRevision"])
                if reviewed_revision is None or not set(event["evidenceRefs"]).issubset(
                    reviewed_revision["evidenceRefs"]
                ):
                    raise error_type(
                        "Candidate review evidence does not belong to its referenced revision"
                    )

    def _validate_transition(self, previous, current, *, persisted=False):
        error_type = MetadataCorruptionError if persisted else MetadataStoreError
        for field in ("candidateId", "observedSurface", "patternId", "oracleRef", "identity"):
            if previous.get(field) != current.get(field):
                raise error_type("Candidate identity cannot change across revisions")
        for old_values, new_values in (
            (previous["evidenceRefs"], current["evidenceRefs"]),
            (previous["falsePositiveChecks"], current["falsePositiveChecks"]),
            (
                previous["candidateAssessment"]["review"]["events"],
                current["candidateAssessment"]["review"]["events"],
            ),
        ):
            if new_values[: len(old_values)] != old_values:
                raise error_type("Candidate history references cannot be removed or reordered")


class FindingStore(_RevisionedMetadataStore):
    """Persist suspected Finding metadata while keeping confirmation blocked."""

    entity_field = "findingId"
    storage_name = "findings"
    schema_name = "finding.schema.json"
    label = "Finding"
    identifier_pattern = re.compile(r"^FND-[A-Z0-9][A-Z0-9-]{0,63}$")

    def _validate_record(self, document, error_type):
        identifier = super()._validate_record(document, error_type)
        if document["status"] not in _FINDING_STATUSES:
            raise error_type("Finding status requires human review or a trusted gate")
        evidence_ids = [reference["evidenceId"] for reference in document["evidenceRefs"]]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise error_type("Finding evidence IDs must be unique")
        return identifier

    def _validate_transition(self, previous, current, *, persisted=False):
        error_type = MetadataCorruptionError if persisted else MetadataStoreError
        for field in ("candidateRefs", "observedSurfaces", "actionRefs", "evidenceRefs"):
            old_values = previous[field]
            new_values = current[field]
            if new_values[: len(old_values)] != old_values:
                raise error_type("Finding provenance references cannot be removed or reordered")

