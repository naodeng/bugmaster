import copy
import json
import pathlib
import unittest

from bugmaster_core.contract_binding import validate_contract_bindings


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "examples" / "contracts"


def _load(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


class ContractBindingTests(unittest.TestCase):
    def setUp(self):
        self.scope = _load("scope-proposal.json")
        self.action = _load("action-readonly.json")
        self.scope_approval = _load("scope-approval.json")

    def _result(self, scope=None, action=None, approvals=None):
        return validate_contract_bindings(
            self.scope if scope is None else scope,
            self.action if action is None else action,
            [self.scope_approval] if approvals is None else approvals,
        )

    def _r2_context(self):
        scope = copy.deepcopy(self.scope)
        action = _load("action-r2-authorized.json")
        scope_approval = copy.deepcopy(self.scope_approval)
        action_approval = _load("action-approval.json")
        scope["allowedRisks"].append("R2")
        scope["targets"][0]["targetRef"] = action["targetRef"]
        scope_approval["targetRef"] = action["targetRef"]
        return scope, action, scope_approval, action_approval

    def assert_reason(self, result, reason):
        self.assertFalse(result["bindingConsistent"])
        self.assertIn(reason, result["reasonCodes"])

    def test_matching_scope_and_readonly_action_are_consistent_without_authority_claims(self):
        scope_before = copy.deepcopy(self.scope)
        action_before = copy.deepcopy(self.action)
        approval_before = copy.deepcopy(self.scope_approval)

        result = self._result()

        self.assertEqual(
            result, {"bindingConsistent": True, "reasonCodes": []}
        )
        self.assertEqual(set(result), {"bindingConsistent", "reasonCodes"})
        self.assertEqual(self.scope, scope_before)
        self.assertEqual(self.action, action_before)
        self.assertEqual(self.scope_approval, approval_before)

    def test_matching_r2_action_requires_and_binds_both_approvals(self):
        scope, action, scope_approval, action_approval = self._r2_context()
        result = self._result(
            scope, action, [scope_approval, action_approval]
        )
        self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

    def test_action_scope_identity_environment_and_risk_must_match(self):
        mutations = (
            ("scopeId", "other-scope", "scope-action-mismatch"),
            ("scopeRevision", 2, "scope-action-mismatch"),
            ("environmentRef", "other-env", "scope-action-mismatch"),
            ("risk", "R3", "risk-not-allowed"),
        )
        for field, value, reason in mutations:
            with self.subTest(field=field):
                action = copy.deepcopy(self.action)
                action[field] = value
                self.assert_reason(self._result(action=action), reason)

    def test_action_target_must_match_exactly_one_scope_target(self):
        action = copy.deepcopy(self.action)
        action["targetRef"] = "https://outside.example.test/api"
        self.assert_reason(
            self._result(action=action), "scope-target-missing"
        )

        scope = copy.deepcopy(self.scope)
        scope["targets"].append(copy.deepcopy(scope["targets"][0]))
        self.assert_reason(
            self._result(scope=scope), "scope-target-ambiguous"
        )

    def test_action_cannot_bind_to_pending_or_out_of_scope_target(self):
        action = copy.deepcopy(self.action)
        action["targetRef"] = self.scope["targets"][1]["targetRef"]
        action["surface"] = self.scope["targets"][1]["surface"]
        self.assert_reason(
            self._result(action=action), "target-not-in-scope"
        )

    def test_every_in_scope_target_must_resolve_to_a_scope_approval(self):
        self.assert_reason(self._result(approvals=[]), "scope-approval-missing")

    def test_optional_scope_references_are_checked_but_do_not_promote_targets(self):
        scope = copy.deepcopy(self.scope)
        pending_target = scope["targets"][1]
        outside_target = scope["targets"][2]
        pending_target["approvalRef"] = "approval-pending-001"
        outside_target["approvalRef"] = "approval-outside-001"

        pending_approval = copy.deepcopy(self.scope_approval)
        pending_approval["approvalId"] = "approval-pending-001"
        pending_approval["targetRef"] = pending_target["targetRef"]
        outside_approval = copy.deepcopy(self.scope_approval)
        outside_approval["approvalId"] = "approval-outside-001"
        outside_approval["targetRef"] = outside_target["targetRef"]
        outside_approval["status"] = "rejected"
        outside_approval["reason"] = "Target remains out of scope."

        result = self._result(
            scope=scope,
            approvals=[self.scope_approval, pending_approval, outside_approval],
        )
        self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

        action = copy.deepcopy(self.action)
        action["targetRef"] = pending_target["targetRef"]
        action["surface"] = pending_target["surface"]
        self.assert_reason(
            self._result(
                scope=scope,
                action=action,
                approvals=[self.scope_approval, pending_approval, outside_approval],
            ),
            "target-not-in-scope",
        )

    def test_optional_scope_reference_must_resolve(self):
        scope = copy.deepcopy(self.scope)
        scope["targets"][1]["approvalRef"] = "approval-missing-optional"
        self.assert_reason(
            self._result(scope=scope), "scope-approval-missing"
        )

    def test_scope_approval_kind_fields_and_decision_status_are_bound(self):
        approval = copy.deepcopy(self.scope_approval)
        approval["identityRef"] = "different-identity"
        self.assert_reason(
            self._result(approvals=[approval]), "scope-approval-mismatch"
        )

        approval = copy.deepcopy(self.scope_approval)
        approval["status"] = "rejected"
        approval["reason"] = "Owner rejected this scope."
        self.assert_reason(
            self._result(approvals=[approval]), "scope-approval-not-approved"
        )

    def test_scope_approval_binds_all_scope_fields_and_kind(self):
        mutations = (
            ("scopeId", "other-scope"),
            ("scopeRevision", 2),
            ("targetRef", "https://other.example.test"),
            ("environmentRef", "other-env"),
            ("identityRef", "other-identity"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                approval = copy.deepcopy(self.scope_approval)
                approval[field] = value
                self.assert_reason(
                    self._result(approvals=[approval]),
                    "scope-approval-mismatch",
                )

        scope = copy.deepcopy(self.scope)
        action_approval = _load("action-approval.json")
        scope["targets"][0]["approvalRef"] = action_approval["approvalId"]
        self.assert_reason(
            self._result(scope=scope, approvals=[action_approval]),
            "scope-approval-mismatch",
        )

    def test_duplicate_approval_ids_are_ambiguous(self):
        self.assert_reason(
            self._result(approvals=[self.scope_approval, self.scope_approval]),
            "approval-reference-ambiguous",
        )

    def test_action_approval_reference_must_resolve(self):
        scope, action, scope_approval, _ = self._r2_context()
        self.assert_reason(
            self._result(scope, action, [scope_approval]),
            "action-approval-missing",
        )

    def test_action_approval_binds_kind_status_identity_and_intent_fields(self):
        scope, action, scope_approval, action_approval = self._r2_context()
        mutations = (
            ("scopeId", "other-scope"),
            ("scopeRevision", 2),
            ("targetRef", "https://other.example.test"),
            ("environmentRef", "other-env"),
            ("identityRef", "other-identity"),
            ("actionDigest", "f" * 64),
            ("method", "DELETE"),
            ("parameterDigest", "e" * 64),
            ("count", 2),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                approval = copy.deepcopy(action_approval)
                approval[field] = value
                self.assert_reason(
                    self._result(
                        scope,
                        action,
                        [scope_approval, approval],
                    ),
                    "action-approval-mismatch",
                )

        wrong_kind = copy.deepcopy(scope_approval)
        wrong_kind["approvalId"] = action["approvalRef"]
        self.assert_reason(
            self._result(
                scope,
                action,
                [scope_approval, wrong_kind],
            ),
            "action-approval-mismatch",
        )

        rejected = copy.deepcopy(action_approval)
        rejected["status"] = "rejected"
        rejected["reason"] = "Owner rejected this action."
        self.assert_reason(
            self._result(scope, action, [scope_approval, rejected]),
            "action-approval-mismatch",
        )

    def test_proposed_r2_with_optional_matching_rejected_approval_is_consistent(self):
        scope, action, scope_approval, action_approval = self._r2_context()
        action["status"] = "proposed"
        action_approval["status"] = "rejected"
        action_approval["reason"] = "Owner rejected this action."
        result = self._result(
            scope, action, [scope_approval, action_approval]
        )
        self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

    def test_r2_statuses_require_approved_action_approval_only_when_schema_requires_it(self):
        required_statuses = (
            "authorized",
            "prepared",
            "dispatched",
            "completed",
            "failed",
            "outcome_unknown",
            "reconciled_completed",
            "reconciled_not_executed",
            "needs_review",
        )
        for status in required_statuses:
            with self.subTest(status=status):
                scope, action, scope_approval, action_approval = self._r2_context()
                action["status"] = status
                action_approval["status"] = "rejected"
                action_approval["reason"] = "Owner rejected this action."
                self.assert_reason(
                    self._result(
                        scope,
                        action,
                        [scope_approval, action_approval],
                    ),
                    "action-approval-mismatch",
                )

        for status in ("proposed", "rejected", "cancelled"):
            with self.subTest(status=status):
                scope, action, scope_approval, action_approval = self._r2_context()
                action["status"] = status
                action_approval["status"] = "rejected"
                action_approval["reason"] = "Owner rejected this action."
                result = self._result(
                    scope,
                    action,
                    [scope_approval, action_approval],
                )
                self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

    def test_invalid_schema_or_datetime_format_fails_before_binding(self):
        action = copy.deepcopy(self.action)
        action["createdAt"] = "tomorrow"
        self.assert_reason(self._result(action=action), "schema-invalid")

        action = copy.deepcopy(self.action)
        action["method"] = "GET\n"
        self.assert_reason(self._result(action=action), "schema-invalid")

        action = copy.deepcopy(self.action)
        action["selfApproved"] = True
        self.assert_reason(self._result(action=action), "schema-invalid")

        scope = copy.deepcopy(self.scope)
        del scope["scopeId"]
        self.assert_reason(self._result(scope=scope), "schema-invalid")

        approval = copy.deepcopy(self.scope_approval)
        approval["provenanceVerified"] = True
        self.assert_reason(self._result(approvals=[approval]), "schema-invalid")

    def test_approval_datetime_trailing_newline_returns_schema_invalid(self):
        for field in ("issuedAt", "expiresAt"):
            with self.subTest(field=field):
                approval = copy.deepcopy(self.scope_approval)
                approval[field] = "2026-11-19T09:00:00Z\n"
                self.assert_reason(
                    self._result(approvals=[approval]), "schema-invalid"
                )

    def test_action_created_at_trailing_newline_returns_schema_invalid(self):
        action = copy.deepcopy(self.action)
        action["createdAt"] = "2026-11-19T09:00:00Z\n"
        self.assert_reason(self._result(action=action), "schema-invalid")

    def test_rfc3339_timezone_offsets_and_lowercase_markers_are_compared(self):
        approval = copy.deepcopy(self.scope_approval)
        approval["issuedAt"] = "2026-11-19t09:00:00z"
        approval["expiresAt"] = "2026-11-19T09:30:00+00:00"
        result = self._result(approvals=[approval])
        self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

    def test_approval_interval_preserves_submicrosecond_precision(self):
        approval = copy.deepcopy(self.scope_approval)
        approval["issuedAt"] = "2026-11-19T09:00:00.0000001Z"
        approval["expiresAt"] = "2026-11-19T09:00:00.0000002Z"
        result = self._result(approvals=[approval])
        self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

        approval["expiresAt"] = "2026-11-19T09:00:00.0000000Z"
        self.assert_reason(
            self._result(approvals=[approval]), "approval-time-invalid"
        )

    def test_approval_interval_handles_utc_offsets_at_datetime_year_bounds(self):
        approval = copy.deepcopy(self.scope_approval)
        intervals = (
            (
                "0001-01-01T00:00:00+01:00",
                "0001-01-01T00:00:01+01:00",
            ),
            (
                "9999-12-31T23:59:58-01:00",
                "9999-12-31T23:59:59-01:00",
            ),
        )
        for issued_at, expires_at in intervals:
            with self.subTest(issued_at=issued_at):
                approval["issuedAt"] = issued_at
                approval["expiresAt"] = expires_at
                result = self._result(approvals=[approval])
                self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

        approval["issuedAt"] = "2026-11-19t09:00:00+01:00"
        approval["expiresAt"] = "2026-11-19T08:30:00Z"
        result = self._result(approvals=[approval])
        self.assertTrue(result["bindingConsistent"], result["reasonCodes"])

    def test_approval_expiry_must_follow_issue_time(self):
        approval = copy.deepcopy(self.scope_approval)
        approval["issuedAt"] = "2026-11-19T09:00:00Z"
        approval["expiresAt"] = "2026-11-18T09:00:00Z"
        self.assert_reason(
            self._result(approvals=[approval]), "approval-time-invalid"
        )

        approval["expiresAt"] = approval["issuedAt"]
        self.assert_reason(
            self._result(approvals=[approval]), "approval-time-invalid"
        )

    def test_multiple_reason_codes_are_stable_and_deduplicated(self):
        action = copy.deepcopy(self.action)
        action["scopeId"] = "other-scope"
        action["risk"] = "R3"
        action["targetRef"] = "https://outside.example.test"
        result = self._result(action=action, approvals=[])

        self.assertEqual(result["reasonCodes"], sorted(set(result["reasonCodes"])))
        self.assertEqual(
            result["reasonCodes"],
            [
                "risk-not-allowed",
                "scope-action-mismatch",
                "scope-approval-missing",
                "scope-target-missing",
            ],
        )

    def test_non_list_approvals_fails_schema_validation(self):
        self.assert_reason(self._result(approvals=()), "schema-invalid")


if __name__ == "__main__":
    unittest.main()
