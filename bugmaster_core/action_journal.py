"""Durable local Action Journal with conservative recovery decisions.

This module records action intent and outcomes. It is not an authorization
gateway and does not dispatch API or browser actions.
"""

import fcntl
import hashlib
import hmac
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

from .filesystem_security import _has_extended_acl


_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_EVENT_KEYS = frozenset(
    {
        "schemaVersion",
        "sessionId",
        "journalId",
        "sequence",
        "eventType",
        "actionId",
        "recordedAt",
        "data",
        "previousHash",
        "entryHash",
    }
)
_ZERO_HASH = None


class JournalError(ValueError):
    """An attempted journal operation violates the action state machine."""


class JournalCorruptionError(JournalError):
    """The on-disk journal is incomplete, inconsistent, or has changed."""


def _canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("journal JSON object contains a duplicate key")
        value[key] = item
    return value


def _digest_matches(value):
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _valid_recorded_at(value):
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        return False
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def _require_action_id(action_id):
    if not _nonempty(action_id):
        raise JournalError("action ID must be a non-empty string")


def _needs_reconciliation(state):
    status = state["status"]
    if status in ("prepared", "dispatched", "outcome_unknown", "reconciliation_claimed"):
        return True
    return status == "failed" and state["risk"] != "R0"


def _entry_hash(event_without_hash):
    return hashlib.sha256(_canonical_bytes(event_without_hash)).hexdigest()


def _read_fd(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _apply_event(states, event, corruption):
    error = JournalCorruptionError if corruption else JournalError
    action_id = event["actionId"]
    event_type = event["eventType"]
    data = event["data"]
    state = states.get(action_id)

    if event_type == "action_prepared":
        required = {"intentDigest", "scopeRevision", "risk", "approvalRef"}
        if set(data) != required:
            raise error("prepared event fields are invalid")
        if state is not None:
            raise error("action ID is already present in the journal")
        if not _digest_matches(data["intentDigest"]):
            raise error("prepared event intent digest is invalid")
        revision = data["scopeRevision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise error("prepared event scope revision is invalid")
        risk = data["risk"]
        if risk not in ("R0", "R1", "R2"):
            raise error("prepared event risk is invalid")
        approval_ref = data["approvalRef"]
        if approval_ref is not None and not _nonempty(approval_ref):
            raise error("prepared event approval reference is invalid")
        if risk == "R2" and not _nonempty(approval_ref):
            raise error("R2 actions require an action approval reference")
        states[action_id] = {
            "status": "prepared",
            "intentDigest": data["intentDigest"],
            "risk": risk,
        }
        return

    if state is None:
        raise error("action must be prepared before later events")

    if event_type == "action_dispatched":
        if set(data) != {"intentDigest"}:
            raise error("dispatched event fields are invalid")
        if state["status"] != "prepared":
            raise error("only a prepared action can be marked dispatched")
        if not hmac.compare_digest(data["intentDigest"], state["intentDigest"]):
            raise error("dispatch intent does not match the prepared action")
        state["status"] = "dispatched"
        return

    if event_type == "action_outcome":
        if set(data) != {"outcome", "resultRef"}:
            raise error("outcome event fields are invalid")
        if state["status"] != "dispatched":
            raise error("an outcome requires a dispatched action")
        outcome = data["outcome"]
        if outcome not in ("completed", "failed", "outcome_unknown"):
            raise error("action outcome is invalid")
        result_ref = data["resultRef"]
        if result_ref is not None and not _nonempty(result_ref):
            raise error("action result reference is invalid")
        if outcome in ("completed", "failed") and not _nonempty(result_ref):
            raise error("known outcomes require a tool result reference")
        state["status"] = outcome
        return

    if event_type == "action_reconciliation_claimed":
        required = {"outcome", "observationRef", "observerRef", "basis"}
        if set(data) != required:
            raise error("reconciliation event fields are invalid")
        if state["status"] not in ("prepared", "dispatched", "outcome_unknown"):
            raise error("only an uncertain action can be reconciled")
        if data["outcome"] not in ("completed", "not_executed"):
            raise error("reconciliation outcome is invalid")
        if not _nonempty(data["observationRef"]) or not _nonempty(
            data["observerRef"]
        ):
            raise error("reconciliation requires observation and observer references")
        if data["basis"] != "authoritative-read-only":
            raise error("reconciliation claim must cite a read-only basis")
        state["status"] = "reconciliation_claimed"
        return

    raise error("journal event type is not supported")


def _load_events(fd, session_id, journal_id):
    raw = _read_fd(fd)
    if not raw:
        return [], {}
    if not raw.endswith(b"\n"):
        raise JournalCorruptionError("journal ends with an incomplete event")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise JournalCorruptionError("journal is not valid UTF-8") from error

    events = []
    states = {}
    previous_hash = _ZERO_HASH
    for expected_sequence, line in enumerate(text[:-1].split("\n"), start=1):
        if not line:
            raise JournalCorruptionError("journal contains an empty event line")
        try:
            event = json.loads(line, object_pairs_hook=_unique_json_object)
        except (ValueError, RecursionError) as error:
            raise JournalCorruptionError("journal contains invalid JSON") from error
        if not isinstance(event, dict) or set(event) != _EVENT_KEYS:
            raise JournalCorruptionError("journal event fields are invalid")
        if event["schemaVersion"] != "1.1":
            raise JournalCorruptionError("journal schema version is unsupported")
        if event["sessionId"] != session_id:
            raise JournalError("journal belongs to a different session")
        if event["journalId"] != journal_id:
            raise JournalCorruptionError("journal event ID does not match the reader")
        if (
            isinstance(event["sequence"], bool)
            or not isinstance(event["sequence"], int)
            or event["sequence"] != expected_sequence
        ):
            raise JournalCorruptionError("journal event sequence is invalid")
        if not _nonempty(event["actionId"]) or not _valid_recorded_at(
            event["recordedAt"]
        ):
            raise JournalCorruptionError("journal event identity or timestamp is invalid")
        if not isinstance(event["data"], dict):
            raise JournalCorruptionError("journal event data must be an object")
        if event["previousHash"] != previous_hash:
            raise JournalCorruptionError("journal previous hash does not match")
        if not _digest_matches(event["entryHash"]):
            raise JournalCorruptionError("journal entry hash is invalid")
        unhashed = dict(event)
        del unhashed["entryHash"]
        try:
            calculated_hash = _entry_hash(unhashed)
        except (UnicodeError, ValueError, RecursionError) as error:
            raise JournalCorruptionError("journal event cannot be hashed") from error
        if not hmac.compare_digest(calculated_hash, event["entryHash"]):
            raise JournalCorruptionError("journal event hash does not match")
        try:
            _apply_event(states, event, corruption=True)
        except (KeyError, TypeError) as error:
            raise JournalCorruptionError("journal event is malformed") from error
        events.append(event)
        previous_hash = event["entryHash"]
    return events, states


def _write_all(fd, payload):
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError("journal append made no forward progress")
        offset += written


class ActionJournal:
    """Append-only per-session event log with restart-safe replay blocking.

    A pending intent can be dispatched only by the same live instance that
    durably prepared it. A restarted instance requires reconciliation for any
    intent that lacks a recorded result, including an intent with no dispatch
    marker. Reconciliation records are unverified claims and never unlock
    dispatch; a trusted read-only verifier is not implemented here.
    """

    def __init__(
        self,
        path,
        session_id,
        journal_id=None,
        *,
        require_existing=False,
        directory_fd=None,
    ):
        if not _nonempty(session_id):
            raise JournalError("session ID must be a non-empty string")
        try:
            session_id.encode("utf-8")
        except UnicodeEncodeError as error:
            raise JournalError("session ID must be valid UTF-8") from error
        if journal_id is None:
            journal_id = "journal-{}".format(session_id)
        if not _nonempty(journal_id):
            raise JournalError("journal ID must be a non-empty string")
        try:
            journal_id.encode("utf-8")
        except UnicodeEncodeError as error:
            raise JournalError("journal ID must be valid UTF-8") from error
        requested_path = Path(path).absolute()
        self.path = requested_path
        self._directory_fd = directory_fd
        self._closed = False
        self._require_existing = require_existing
        try:
            if directory_fd is None:
                anchor_path = requested_path.parent
                missing_parent_parts = []
                while True:
                    try:
                        anchor_stat = anchor_path.stat()
                    except FileNotFoundError:
                        if anchor_path.parent == anchor_path:
                            raise JournalError(
                                "journal path has no existing parent directory"
                            )
                        missing_parent_parts.append(anchor_path.name)
                        anchor_path = anchor_path.parent
                        continue
                    except OSError as error:
                        raise JournalError(
                            "journal parent path cannot be inspected"
                        ) from error
                    if not stat.S_ISDIR(anchor_stat.st_mode):
                        raise JournalError("journal parent path is not a directory")
                    try:
                        anchor_path = anchor_path.resolve(strict=True)
                        anchor_stat = anchor_path.stat()
                    except OSError as error:
                        raise JournalError(
                            "journal parent path cannot be resolved"
                        ) from error
                    if not stat.S_ISDIR(anchor_stat.st_mode):
                        raise JournalError("journal parent path is not a directory")
                    existing_parent_parts = anchor_path.parts[1:]
                    self._anchor_path = Path("/")
                    root_stat = self._anchor_path.stat()
                    self._anchor_identity = (root_stat.st_dev, root_stat.st_ino)
                    self._relative_parent_parts = (
                        *existing_parent_parts,
                        *reversed(missing_parent_parts),
                    )
                    self._directory_identities = {}
                    existing_path = Path("/")
                    for index, component in enumerate(
                        existing_parent_parts, start=1
                    ):
                        existing_path /= component
                        component_stat = existing_path.stat()
                        self._directory_identities[
                            tuple(self._relative_parent_parts[:index])
                        ] = (component_stat.st_dev, component_stat.st_ino)
                    self._directory_chain_synced = False
                    self.path = Path("/").joinpath(
                        *self._relative_parent_parts, requested_path.name
                    )
                    break
                self._parent_identity = None
            else:
                directory_stat = os.fstat(directory_fd)
                if not stat.S_ISDIR(directory_stat.st_mode):
                    raise JournalCorruptionError(
                        "pinned Journal storage descriptor is not a directory"
                    )
                if (
                    directory_stat.st_uid != os.geteuid()
                    or directory_stat.st_mode & (0o077 | 0o7000)
                ):
                    raise JournalCorruptionError(
                        "pinned Journal storage directory is unsafe"
                    )
                self._anchor_path = Path("/")
                self._anchor_identity = None
                self._relative_parent_parts = ()
                self._directory_identities = {}
                self._directory_chain_synced = True
                self._parent_identity = (directory_stat.st_dev, directory_stat.st_ino)

            self.session_id = session_id
            self._journal_id = journal_id
            self._file_identity = None
            self._prepared_in_process = set()
            self._dispatched_in_process = set()
            self._load_current()
        except BaseException:
            self.close()
            raise

    @property
    def journal_id(self):
        """Return the stable Journal identity selected when this reader was created."""
        return self._journal_id

    def close(self):
        """Close the pinned storage directory owned by this Journal, if any."""
        directory_fd = getattr(self, "_directory_fd", None)
        if directory_fd is not None:
            self._directory_fd = None
            self._closed = True
            os.close(directory_fd)

    def __enter__(self):
        if self._closed:
            raise JournalError("journal is closed")
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        self.close()

    def __del__(self):
        try:
            self.close()
        except OSError:
            pass

    def _open_parent(self, *, create=False):
        if self._closed:
            raise JournalCorruptionError("journal storage descriptor is closed")
        if self._directory_fd is not None:
            fd = None
            try:
                fd = os.dup(self._directory_fd)
                directory_stat = os.fstat(fd)
            except OSError as error:
                if fd is not None:
                    os.close(fd)
                raise JournalCorruptionError(
                    "pinned Journal storage directory cannot be opened"
                ) from error
            if (
                not stat.S_ISDIR(directory_stat.st_mode)
                or directory_stat.st_uid != os.geteuid()
                or directory_stat.st_mode & (0o077 | 0o7000)
            ):
                os.close(fd)
                raise JournalCorruptionError(
                    "pinned Journal storage directory is unsafe"
                )
            try:
                has_extended_acl = _has_extended_acl(fd)
            except OSError as error:
                os.close(fd)
                raise JournalCorruptionError(
                    "pinned Journal storage directory access control cannot be verified"
                ) from error
            if has_extended_acl:
                os.close(fd)
                raise JournalCorruptionError(
                    "pinned Journal storage directory must not have an extended access control list"
                )
            return fd

        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(str(self._anchor_path), flags)
        except OSError as error:
            raise JournalCorruptionError(
                "journal anchor directory cannot be opened safely"
            ) from error

        try:
            anchor_stat = os.fstat(fd)
            if (anchor_stat.st_dev, anchor_stat.st_ino) != self._anchor_identity:
                raise JournalCorruptionError(
                    "journal anchor directory identity changed"
                )

            prefix = ()
            for component in self._relative_parent_parts:
                prefix += (component,)
                expected_identity = self._directory_identities.get(prefix)
                try:
                    next_fd = os.open(component, flags, dir_fd=fd)
                except FileNotFoundError as error:
                    if expected_identity is not None:
                        raise JournalCorruptionError(
                            "journal parent directory disappeared"
                        ) from error
                    if not create:
                        return None
                    try:
                        os.mkdir(component, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                    except OSError as create_error:
                        raise JournalCorruptionError(
                            "journal parent directory cannot be created"
                        ) from create_error
                    try:
                        next_fd = os.open(component, flags, dir_fd=fd)
                    except OSError as open_error:
                        raise JournalCorruptionError(
                            "journal parent path cannot be opened safely"
                        ) from open_error
                except OSError as error:
                    raise JournalCorruptionError(
                        "journal parent path cannot be opened safely"
                    ) from error

                previous_fd = fd
                fd = next_fd
                try:
                    component_stat = os.fstat(fd)
                    identity = (component_stat.st_dev, component_stat.st_ino)
                    if (
                        expected_identity is not None
                        and identity != expected_identity
                    ):
                        raise JournalCorruptionError(
                            "journal parent directory identity changed"
                        )
                    self._directory_identities.setdefault(prefix, identity)
                    if create and not self._directory_chain_synced:
                        os.fsync(previous_fd)
                finally:
                    os.close(previous_fd)

            if create:
                self._directory_chain_synced = True

            parent_stat = os.fstat(fd)
            identity = (parent_stat.st_dev, parent_stat.st_ino)
            if self._parent_identity is None:
                self._parent_identity = identity
            elif identity != self._parent_identity:
                raise JournalCorruptionError(
                    "journal parent directory identity changed"
                )
            parent_fd = fd
            fd = None
            return parent_fd
        finally:
            if fd is not None:
                os.close(fd)

    def _load_current(self):
        parent_fd = self._open_parent()
        if parent_fd is None:
            if self._require_existing:
                raise JournalCorruptionError("canonical journal file is missing")
            return [], {}
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            try:
                fd = os.open(self.path.name, flags, dir_fd=parent_fd)
            except FileNotFoundError as error:
                if self._require_existing or self._file_identity is not None:
                    raise JournalCorruptionError(
                        "canonical journal file is missing or disappeared"
                    ) from error
                return [], {}
            except OSError as error:
                raise JournalCorruptionError(
                    "journal path cannot be opened safely"
                ) from error
            locked = False
            try:
                self._validate_journal_file(fd)
                fcntl.flock(fd, fcntl.LOCK_EX)
                locked = True
                self._verify_journal_path(fd, parent_fd)
                events_and_states = _load_events(
                    fd, self.session_id, self.journal_id
                )
                self._verify_journal_path(fd, parent_fd)
                return events_and_states
            finally:
                try:
                    if locked:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        finally:
            os.close(parent_fd)

    def _validate_journal_file(self, fd):
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise JournalCorruptionError("journal path is not a regular file")
        if file_stat.st_nlink != 1:
            raise JournalCorruptionError("journal path must not be hard linked")
        if self._directory_fd is not None and (
            file_stat.st_uid != os.geteuid()
            or file_stat.st_mode & (0o077 | 0o7000)
        ):
            raise JournalCorruptionError(
                "journal file ownership or permissions are unsafe"
            )
        if self._directory_fd is not None:
            try:
                has_extended_acl = _has_extended_acl(fd)
            except OSError as error:
                raise JournalCorruptionError(
                    "journal file access control cannot be verified"
                ) from error
            if has_extended_acl:
                raise JournalCorruptionError(
                    "journal file must not have an extended access control list"
                )
        identity = (file_stat.st_dev, file_stat.st_ino)
        if self._file_identity is None:
            self._file_identity = identity
        elif identity != self._file_identity:
            raise JournalCorruptionError("journal file identity changed")

    def _verify_journal_path(self, fd, parent_fd):
        current_parent_fd = self._open_parent()
        try:
            current_parent_stat = os.fstat(current_parent_fd)
            opened_parent_stat = os.fstat(parent_fd)
            if (current_parent_stat.st_dev, current_parent_stat.st_ino) != (
                opened_parent_stat.st_dev,
                opened_parent_stat.st_ino,
            ):
                raise JournalCorruptionError(
                    "journal path no longer names the open parent directory"
                )
        finally:
            os.close(current_parent_fd)

        file_stat = os.fstat(fd)
        self._validate_journal_file(fd)
        try:
            entry_stat = os.stat(
                self.path.name, dir_fd=parent_fd, follow_symlinks=False
            )
        except OSError as error:
            raise JournalCorruptionError(
                "journal directory entry changed while it was open"
            ) from error
        if not stat.S_ISREG(entry_stat.st_mode) or entry_stat.st_nlink != 1:
            raise JournalCorruptionError("journal directory entry is unsafe")
        if (entry_stat.st_dev, entry_stat.st_ino) != (
            file_stat.st_dev,
            file_stat.st_ino,
        ):
            raise JournalCorruptionError(
                "journal directory entry no longer names the open file"
            )

    def matches_prefix(self, sequence, head_hash):
        """Return whether sequence and hash identify a validated journal prefix.

        This checks local hash-chain consistency only. It does not establish
        event authenticity, source truth, authorization, or safe resumption.
        """
        if isinstance(sequence, float) and sequence.is_integer():
            sequence = int(sequence)
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 0
        ):
            raise JournalError("journal sequence must be a non-negative integer")

        events, _ = self._load_current()
        if sequence == 0:
            return head_hash is None
        if not _digest_matches(head_hash) or sequence > len(events):
            return False
        return hmac.compare_digest(events[sequence - 1]["entryHash"], head_hash)

    def _append(self, event_type, action_id, data):
        parent_fd = self._open_parent(create=True)
        flags = (
            os.O_RDWR
            | os.O_APPEND
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            if self._require_existing:
                try:
                    fd = os.open(self.path.name, flags, dir_fd=parent_fd)
                except FileNotFoundError as error:
                    raise JournalCorruptionError(
                        "canonical journal file is missing or disappeared"
                    ) from error
                except OSError as error:
                    raise JournalCorruptionError(
                        "journal path cannot be opened safely"
                    ) from error
            elif self._file_identity is None:
                try:
                    fd = os.open(
                        self.path.name,
                        flags | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                except FileExistsError:
                    try:
                        fd = os.open(self.path.name, flags, dir_fd=parent_fd)
                    except OSError as error:
                        raise JournalCorruptionError(
                            "journal path cannot be opened safely"
                        ) from error
                except OSError as error:
                    raise JournalCorruptionError(
                        "journal path cannot be opened safely"
                    ) from error
            else:
                try:
                    fd = os.open(self.path.name, flags, dir_fd=parent_fd)
                except FileNotFoundError as error:
                    raise JournalCorruptionError(
                        "journal file disappeared after observation"
                    ) from error
                except OSError as error:
                    raise JournalCorruptionError(
                        "journal path cannot be opened safely"
                    ) from error

            locked = False
            try:
                self._validate_journal_file(fd)
                os.fsync(parent_fd)
                fcntl.flock(fd, fcntl.LOCK_EX)
                locked = True
                self._verify_journal_path(fd, parent_fd)
                events, states = _load_events(
                    fd, self.session_id, self.journal_id
                )
                if event_type == "action_dispatched" and any(
                    other_id != action_id
                    and _needs_reconciliation(state)
                    for other_id, state in states.items()
                ):
                    raise JournalError(
                        "session has unresolved action outcomes; dispatch is blocked"
                    )
                self._verify_journal_path(fd, parent_fd)
                os.fchmod(fd, 0o600)
                event = {
                    "schemaVersion": "1.1",
                    "sessionId": self.session_id,
                    "journalId": self.journal_id,
                    "sequence": len(events) + 1,
                    "eventType": event_type,
                    "actionId": action_id,
                    "recordedAt": datetime.now(timezone.utc)
                    .isoformat(timespec="microseconds")
                    .replace("+00:00", "Z"),
                    "data": data,
                    "previousHash": events[-1]["entryHash"] if events else _ZERO_HASH,
                }
                _apply_event(states, event, corruption=False)
                event["entryHash"] = _entry_hash(event)
                encoded = _canonical_bytes(event) + b"\n"
                _write_all(fd, encoded)
                os.fsync(fd)
                self._verify_journal_path(fd, parent_fd)
                return event
            finally:
                try:
                    if locked:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        finally:
            os.close(parent_fd)

    def prepare(
        self, action_id, intent_digest, scope_revision, risk, approval_ref=None
    ):
        _require_action_id(action_id)
        if not _digest_matches(intent_digest):
            raise JournalError("intent digest must be a lowercase SHA-256")
        if (
            isinstance(scope_revision, bool)
            or not isinstance(scope_revision, int)
            or scope_revision < 1
        ):
            raise JournalError("scope revision must be a positive integer")
        if risk not in ("R0", "R1", "R2"):
            raise JournalError("R3 and unknown risks cannot be prepared")
        if approval_ref is not None and not _nonempty(approval_ref):
            raise JournalError("approval reference must be a non-empty string")
        if risk == "R2" and not _nonempty(approval_ref):
            raise JournalError("R2 actions require an action approval reference")
        event = self._append(
            "action_prepared",
            action_id,
            {
                "intentDigest": intent_digest,
                "scopeRevision": scope_revision,
                "risk": risk,
                "approvalRef": approval_ref,
            },
        )
        self._prepared_in_process.add(action_id)
        return event

    def mark_dispatched(self, action_id, intent_digest):
        _require_action_id(action_id)
        if action_id not in self._prepared_in_process:
            raise JournalError(
                "only a newly prepared action in this process may be dispatched"
            )
        if not _digest_matches(intent_digest):
            raise JournalError("intent digest must be a lowercase SHA-256")
        event = self._append(
            "action_dispatched", action_id, {"intentDigest": intent_digest}
        )
        self._prepared_in_process.remove(action_id)
        self._dispatched_in_process.add(action_id)
        return event

    def record_outcome(self, action_id, outcome, result_ref=None):
        _require_action_id(action_id)
        if action_id not in self._dispatched_in_process:
            raise JournalError(
                "outcomes must be recorded by the process that dispatched the action"
            )
        if outcome not in ("completed", "failed", "outcome_unknown"):
            raise JournalError("action outcome is invalid")
        if result_ref is not None and not _nonempty(result_ref):
            raise JournalError("result reference must be a non-empty string")
        if outcome in ("completed", "failed") and not _nonempty(result_ref):
            raise JournalError("known outcomes require a tool result reference")
        event = self._append(
            "action_outcome",
            action_id,
            {"outcome": outcome, "resultRef": result_ref},
        )
        self._dispatched_in_process.remove(action_id)
        return event

    def record_reconciliation_claim(
        self,
        action_id,
        outcome,
        observation_ref,
        observer_ref,
        basis,
    ):
        _require_action_id(action_id)
        if outcome not in ("completed", "not_executed"):
            raise JournalError("reconciliation outcome is invalid")
        if not _nonempty(observation_ref) or not _nonempty(observer_ref):
            raise JournalError(
                "reconciliation requires observation and observer references"
            )
        if basis != "authoritative-read-only":
            raise JournalError("reconciliation claim must cite a read-only basis")
        return self._append(
            "action_reconciliation_claimed",
            action_id,
            {
                "outcome": outcome,
                "observationRef": observation_ref,
                "observerRef": observer_ref,
                "basis": basis,
            },
        )

    def recovery_status(self, action_id):
        _require_action_id(action_id)
        _, states = self._load_current()
        state = states.get(action_id)
        if state is None:
            raise JournalError("action ID is not present in this session")
        if _needs_reconciliation(state):
            return "needs_reconciliation"
        return {
            "completed": "terminal",
            "failed": "terminal",
        }[state["status"]]

