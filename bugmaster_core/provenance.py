"""Fail-closed local Oracle and Evidence binding checks.

Successful checks establish content integrity and local references only. They
never authenticate a source or authorize a confirmed Finding.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from .action_journal import ActionJournal, JournalError


_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ORACLE_ID = re.compile(r"^OR-[A-Z0-9][A-Z0-9-]{0,63}$")
_EVIDENCE_ID = re.compile(r"^EV-[A-Z0-9][A-Z0-9-]{0,63}$")
_WHITESPACE = frozenset(
    "\u0009\u000a\u000b\u000c\u000d\u001c\u001d\u001e\u001f\u0020"
    "\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
)
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_ORACLE_KEYS = {
    "schemaVersion",
    "oracleId",
    "revision",
    "statement",
    "appliesTo",
    "source",
    "recordedAt",
}
_EVIDENCE_KEYS = {
    "schemaVersion",
    "evidenceId",
    "evidenceLevel",
    "capturedAt",
    "artifact",
    "oracleRef",
    "journalRef",
}
_JOURNAL_VALIDATION_METHODS = (
    "recorded_outcome",
    "_load_current",
    "_open_parent",
    "_validate_journal_file",
    "_verify_journal_path",
)


class ProvenanceError(ValueError):
    """An Oracle, Evidence artifact, or Journal reference does not bind safely."""


@dataclass(frozen=True)
class ProvenanceAssessment:
    """Result of local integrity checks without source authentication."""

    artifact_integrity: str
    oracle_binding: str
    journal_binding: str
    source_authenticity: str
    finding_gate: str


def canonical_record_sha256(record):
    """Hash a record's canonical JSON bytes for stable revision references."""
    if type(record) is not dict:
        raise ProvenanceError("record must be a JSON object")
    try:
        canonical = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ProvenanceError("record cannot be encoded as canonical JSON") from error
    return hashlib.sha256(canonical).hexdigest()


def _object(value, keys, label):
    if type(value) is not dict or set(value) != keys:
        raise ProvenanceError("{} fields are invalid".format(label))
    return value


def _text(value, label):
    if type(value) is not str or not value or all(
        character in _WHITESPACE for character in value
    ):
        raise ProvenanceError("{} must be a non-empty string".format(label))
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProvenanceError("{} must be valid UTF-8".format(label)) from error
    return value


def _positive_integer(value, label, allow_zero=False):
    if type(value) is float and value.is_integer():
        value = int(value)
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        raise ProvenanceError("{} must be a valid integer".format(label))
    return value


def _digest(value, label):
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProvenanceError("{} must be a lowercase SHA-256 digest".format(label))
    return value


def _timestamp(value, label):
    if type(value) is not str or _RFC3339.fullmatch(value) is None:
        raise ProvenanceError("{} must be an RFC3339 timestamp".format(label))
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ProvenanceError("{} is not a valid timestamp".format(label)) from error


def _bytes(value, label):
    if type(value) is not bytes:
        raise ProvenanceError("{} must be supplied as bytes".format(label))
    return value


def _check_oracle(oracle, source_bytes):
    _object(oracle, _ORACLE_KEYS, "Oracle")
    schema_version = _text(oracle["schemaVersion"], "Oracle schema version")
    if schema_version != "1.0":
        raise ProvenanceError("Oracle schema version is unsupported")
    oracle_id = _text(oracle["oracleId"], "Oracle ID")
    if _ORACLE_ID.fullmatch(oracle_id) is None:
        raise ProvenanceError("Oracle ID has an invalid format")
    revision = _positive_integer(oracle["revision"], "Oracle revision")
    _text(oracle["statement"], "Oracle statement")
    applies_to = _object(
        oracle["appliesTo"], {"targetRef", "featureRef"}, "Oracle applicability"
    )
    _text(applies_to["targetRef"], "Oracle target reference")
    _text(applies_to["featureRef"], "Oracle feature reference")
    source = _object(
        oracle["source"], {"reference", "sha256", "byteLength"}, "Oracle source"
    )
    _text(source["reference"], "Oracle source reference")
    _digest(source["sha256"], "Oracle source digest")
    _positive_integer(source["byteLength"], "Oracle source byte length", allow_zero=True)
    _timestamp(oracle["recordedAt"], "Oracle recordedAt")
    source_bytes = _bytes(source_bytes, "Oracle source")
    if len(source_bytes) != source["byteLength"]:
        raise ProvenanceError("Oracle source byte length does not match")
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    if source_digest != source["sha256"]:
        raise ProvenanceError("Oracle source digest does not match")
    return oracle_id, revision, canonical_record_sha256(oracle)


def _check_evidence(evidence, artifact_bytes):
    _object(evidence, _EVIDENCE_KEYS, "Evidence")
    schema_version = _text(evidence["schemaVersion"], "Evidence schema version")
    if schema_version != "1.0":
        raise ProvenanceError("Evidence schema version is unsupported")
    evidence_id = _text(evidence["evidenceId"], "Evidence ID")
    if _EVIDENCE_ID.fullmatch(evidence_id) is None:
        raise ProvenanceError("Evidence ID has an invalid format")
    evidence_level = _text(evidence["evidenceLevel"], "Evidence level")
    if evidence_level not in ("E0", "E1", "E2", "E3", "E4"):
        raise ProvenanceError("Evidence level is invalid")
    _timestamp(evidence["capturedAt"], "Evidence capturedAt")
    artifact = _object(
        evidence["artifact"],
        {"reference", "mediaType", "sha256", "byteLength"},
        "Evidence artifact",
    )
    _text(artifact["reference"], "Evidence artifact reference")
    _text(artifact["mediaType"], "Evidence artifact media type")
    _digest(artifact["sha256"], "Evidence artifact digest")
    _positive_integer(artifact["byteLength"], "Evidence artifact byte length", allow_zero=True)
    artifact_bytes = _bytes(artifact_bytes, "Evidence artifact")
    if len(artifact_bytes) != artifact["byteLength"]:
        raise ProvenanceError("Evidence artifact byte length does not match")
    if hashlib.sha256(artifact_bytes).hexdigest() != artifact["sha256"]:
        raise ProvenanceError("Evidence artifact digest does not match")

    oracle_ref = _object(
        evidence["oracleRef"], {"oracleId", "revision", "sha256"}, "Evidence Oracle reference"
    )
    _text(oracle_ref["oracleId"], "Evidence Oracle ID")
    _positive_integer(oracle_ref["revision"], "Evidence Oracle revision")
    _digest(oracle_ref["sha256"], "Evidence Oracle record digest")

    journal_ref = _object(
        evidence["journalRef"],
        {
            "sessionId",
            "journalId",
            "actionId",
            "outcome",
            "resultRef",
            "sequence",
            "entryHash",
        },
        "Evidence Journal reference",
    )
    for field in ("sessionId", "journalId", "actionId", "resultRef"):
        _text(journal_ref[field], "Evidence Journal {}".format(field))
    outcome = _text(journal_ref["outcome"], "Evidence Journal outcome")
    if outcome not in ("completed", "failed"):
        raise ProvenanceError("Evidence must reference a recorded terminal outcome")
    _positive_integer(journal_ref["sequence"], "Evidence Journal sequence")
    _digest(journal_ref["entryHash"], "Evidence Journal event hash")
    if artifact["reference"] != journal_ref["resultRef"]:
        raise ProvenanceError("Evidence artifact and Journal result references differ")
    return artifact, oracle_ref, journal_ref


def verify_provenance(oracle, evidence, oracle_source_bytes, artifact_bytes, journal):
    """Check bytes and exact Oracle/Journal references, then remain provisional.

    This does not authenticate Oracle authors, Evidence capture, Action Journal
    events, or external facts. It cannot make a Finding eligible for confirmation.
    """
    oracle_id, oracle_revision, oracle_digest = _check_oracle(
        oracle, oracle_source_bytes
    )
    _, oracle_ref, journal_ref = _check_evidence(evidence, artifact_bytes)
    if (
        oracle_ref["oracleId"] != oracle_id
        or oracle_ref["revision"] != oracle_revision
        or oracle_ref["sha256"] != oracle_digest
    ):
        raise ProvenanceError("Evidence does not reference this exact Oracle revision")
    if type(journal) is not ActionJournal:
        raise ProvenanceError("a concrete ActionJournal instance is required")
    if any(method_name in vars(journal) for method_name in _JOURNAL_VALIDATION_METHODS):
        raise ProvenanceError("ActionJournal validation methods must not be overridden")
    try:
        recorded = ActionJournal.recorded_outcome(
            journal, journal_ref["actionId"]
        )
    except JournalError as error:
        raise ProvenanceError("Action Journal outcome cannot be validated") from error
    expected = {
        "sessionId": journal_ref["sessionId"],
        "journalId": journal_ref["journalId"],
        "actionId": journal_ref["actionId"],
        "outcome": journal_ref["outcome"],
        "resultRef": journal_ref["resultRef"],
        "sequence": journal_ref["sequence"],
        "entryHash": journal_ref["entryHash"],
    }
    if recorded != expected:
        raise ProvenanceError("Evidence does not match the recorded Journal outcome")
    return ProvenanceAssessment(
        artifact_integrity="matched",
        oracle_binding="matched",
        journal_binding="matched",
        source_authenticity="unverified",
        finding_gate="blocked",
    )
