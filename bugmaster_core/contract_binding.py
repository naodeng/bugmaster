"""Validate consistency across Scope, Action, and Approval records.

This module checks record structure and cross-record bindings only. It does not
authenticate provenance, authorize actions, or permit dispatch.
"""

import calendar
import json
import re
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path


_SCHEMA_FILES = {
    "scope": "scope.schema.json",
    "action": "action.schema.json",
    "approval": "approval.schema.json",
}
_ACTION_APPROVAL_STATUSES = frozenset(
    {
        "authorized",
        "prepared",
        "dispatched",
        "completed",
        "failed",
        "outcome_unknown",
        "reconciled_completed",
        "reconciled_not_executed",
        "needs_review",
    }
)
_RFC3339_DATE_TIME = re.compile(
    r"(?P<whole>[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?(?P<zone>[Zz]|[+-][0-9]{2}:[0-9]{2})\Z"
)


@lru_cache(maxsize=1)
def _schema_validators():
    from jsonschema import Draft202012Validator, FormatChecker

    schemas_directory = Path(__file__).resolve().parents[1] / "schemas"
    validators = {}
    for name, filename in _SCHEMA_FILES.items():
        schema = json.loads(
            (schemas_directory / filename).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )
    return validators


def _parse_date_time(value):
    match = _RFC3339_DATE_TIME.fullmatch(value)
    if match is None:
        return None
    whole = match["whole"].replace("t", "T", 1)
    zone = match["zone"]
    if zone in ("Z", "z"):
        zone = "+00:00"
    parsed = datetime.fromisoformat(whole + zone)
    fraction = match["fraction"]
    return (
        calendar.timegm(parsed.replace(tzinfo=None).timetuple())
        - int(parsed.utcoffset().total_seconds()),
        Decimal("0." + fraction) if fraction else Decimal(0),
    )


def _approval_index(approvals):
    index = {}
    for approval in approvals:
        index.setdefault(approval["approvalId"], []).append(approval)
    return index


def _resolve_approval(reference, index, reasons, missing_reason):
    matches = index.get(reference, ())
    if not matches:
        reasons.add(missing_reason)
        return None
    if len(matches) != 1:
        reasons.add("approval-reference-ambiguous")
        return None
    return matches[0]


def _scope_approval_matches(approval, scope, target):
    return (
        approval["kind"] == "scope"
        and approval["scopeId"] == scope["scopeId"]
        and approval["scopeRevision"] == scope["revision"]
        and approval["targetRef"] == target["targetRef"]
        and approval["environmentRef"] == scope["environmentRef"]
        and approval["identityRef"] == scope["identityRef"]
    )


def _action_approval_matches(approval, scope, action):
    return (
        approval["kind"] == "action"
        and approval["scopeId"] == scope["scopeId"]
        and approval["scopeRevision"] == scope["revision"]
        and approval["targetRef"] == action["targetRef"]
        and approval["environmentRef"] == scope["environmentRef"]
        and approval["identityRef"] == scope["identityRef"]
        and approval["actionDigest"] == action["intentDigest"]
        and approval["method"] == action["method"]
        and approval["parameterDigest"] == action["parameterDigest"]
        and approval["risk"] == action["risk"]
        and approval["count"] == action["count"]
    )


def validate_contract_bindings(scope, action, approvals):
    """Return whether valid contract records agree, without granting authority."""
    if not isinstance(approvals, list):
        return {"bindingConsistent": False, "reasonCodes": ["schema-invalid"]}

    validators = _schema_validators()
    if not validators["scope"].is_valid(scope):
        return {"bindingConsistent": False, "reasonCodes": ["schema-invalid"]}
    if not validators["action"].is_valid(action):
        return {"bindingConsistent": False, "reasonCodes": ["schema-invalid"]}
    if _parse_date_time(action["createdAt"]) is None:
        return {"bindingConsistent": False, "reasonCodes": ["schema-invalid"]}
    if not all(validators["approval"].is_valid(item) for item in approvals):
        return {"bindingConsistent": False, "reasonCodes": ["schema-invalid"]}

    reasons = set()
    for approval in approvals:
        issued_at = _parse_date_time(approval["issuedAt"])
        expires_at = _parse_date_time(approval["expiresAt"])
        if issued_at is None or expires_at is None:
            return {"bindingConsistent": False, "reasonCodes": ["schema-invalid"]}
        if expires_at <= issued_at:
            reasons.add("approval-time-invalid")

    index = _approval_index(approvals)

    if (
        action["scopeId"] != scope["scopeId"]
        or action["scopeRevision"] != scope["revision"]
        or action["environmentRef"] != scope["environmentRef"]
    ):
        reasons.add("scope-action-mismatch")
    if action["risk"] not in scope["allowedRisks"]:
        reasons.add("risk-not-allowed")

    matching_targets = [
        target
        for target in scope["targets"]
        if target["targetRef"] == action["targetRef"]
        and target["surface"] == action["surface"]
    ]
    if not matching_targets:
        reasons.add("scope-target-missing")
    elif len(matching_targets) > 1:
        reasons.add("scope-target-ambiguous")
    elif matching_targets[0]["decision"] != "in_scope":
        reasons.add("target-not-in-scope")

    for target in scope["targets"]:
        reference = target.get("approvalRef")
        if reference is None:
            continue
        approval = _resolve_approval(
            reference, index, reasons, "scope-approval-missing"
        )
        if approval is None:
            continue
        if not _scope_approval_matches(approval, scope, target):
            reasons.add("scope-approval-mismatch")
        elif (
            target["decision"] == "in_scope"
            and approval["status"] != "approved"
        ):
            reasons.add("scope-approval-not-approved")

    action_reference = action.get("approvalRef")
    if action_reference is not None:
        approval = _resolve_approval(
            action_reference, index, reasons, "action-approval-missing"
        )
        if approval is not None:
            if not _action_approval_matches(approval, scope, action):
                reasons.add("action-approval-mismatch")
            elif (
                action["risk"] == "R2"
                and action["status"] in _ACTION_APPROVAL_STATUSES
                and approval["status"] != "approved"
            ):
                reasons.add("action-approval-mismatch")

    reason_codes = sorted(reasons)
    return {
        "bindingConsistent": not reason_codes,
        "reasonCodes": reason_codes,
    }
