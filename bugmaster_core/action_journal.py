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
from datetime import datetime, timezone
from pathlib import Path


_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_EVENT_KEYS = frozenset(
    {
        "schemaVersion",
        "sessionId",
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


def _load_events(fd, session_id):
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
    for expected_sequence, line in enumerate(text.splitlines(), start=1):
        if not line:
            raise JournalCorruptionError("journal contains an empty event line")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise JournalCorruptionError("journal contains invalid JSON") from error
        if not isinstance(event, dict) or set(event) != _EVENT_KEYS:
            raise JournalCorruptionError("journal event fields are invalid")
        if event["schemaVersion"] != "1.0":
            raise JournalCorruptionError("journal schema version is unsupported")
        if event["sessionId"] != session_id:
            raise JournalError("journal belongs to a different session")
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
        if not hmac.compare_digest(_entry_hash(unhashed), event["entryHash"]):
            raise JournalCorruptionError("journal event hash does not match")
        try:
            _apply_event(states, event, corruption=True)
        except (KeyError, TypeError) as error:
            raise JournalCorruptionError("journal event is malformed") from error
        events.append(event)
        previous_hash = event["entryHash"]
    return events, states


def _fsync_directory(directory):
    directory_fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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

    def __init__(self, path, session_id):
        if not _nonempty(session_id):
            raise JournalError("session ID must be a non-empty string")
        self.path = Path(path)
        self.session_id = session_id
        self._prepared_in_process = set()
        self._dispatched_in_process = set()
        self._load_current()

    def _load_current(self):
        try:
            fd = os.open(str(self.path), os.O_RDONLY)
        except FileNotFoundError:
            return [], {}
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return _load_events(fd, self.session_id)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def matches_prefix(self, sequence, head_hash):
        """Return whether sequence and hash identify a validated journal prefix.

        This checks local hash-chain consistency only. It does not establish
        event authenticity, source truth, authorization, or safe resumption.
        """
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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        created = False
        flags = os.O_RDWR | os.O_APPEND
        try:
            fd = os.open(
                str(self.path), flags | os.O_CREAT | os.O_EXCL, 0o600
            )
            created = True
        except FileExistsError:
            fd = os.open(str(self.path), flags)

        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.fchmod(fd, 0o600)
            if created:
                _fsync_directory(self.path.parent)
            events, states = _load_events(fd, self.session_id)
            if event_type == "action_dispatched" and any(
                other_id != action_id
                and _needs_reconciliation(state)
                for other_id, state in states.items()
            ):
                raise JournalError(
                    "session has unresolved action outcomes; dispatch is blocked"
                )
            event = {
                "schemaVersion": "1.0",
                "sessionId": self.session_id,
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
            return event
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

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
