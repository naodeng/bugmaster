import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "scope.schema.json"
SAMPLE_SCOPE_PATH = ROOT / "examples" / "contracts" / "scope-proposal.json"


class ScopeSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.sample_scope = json.loads(SAMPLE_SCOPE_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_valid_scope_records_authorized_pending_and_excluded_targets(self):
        self.assertEqual(list(self.validator.iter_errors(self.sample_scope)), [])

    def test_scope_example_approval_reference_matches_approval_fixture(self):
        approval = json.loads(
            (ROOT / "examples" / "contracts" / "scope-approval.json").read_text(
                encoding="utf-8"
            )
        )
        target = self.sample_scope["targets"][0]
        self.assertEqual(target["approvalRef"], approval["approvalId"])
        self.assertEqual(target["targetRef"], approval["targetRef"])
        self.assertEqual(self.sample_scope["scopeId"], approval["scopeId"])
        self.assertEqual(self.sample_scope["revision"], approval["scopeRevision"])

    def test_in_scope_target_requires_an_approval_reference(self):
        document = copy.deepcopy(self.sample_scope)
        del document["targets"][0]["approvalRef"]
        self.assert_invalid(document)

    def test_mobile_surface_cannot_be_marked_executable_in_scope(self):
        document = copy.deepcopy(self.sample_scope)
        document["targets"][0]["surface"] = "android"
        self.assert_invalid(document)

    def test_unknown_risk_level_is_rejected(self):
        document = copy.deepcopy(self.sample_scope)
        document["allowedRisks"].append("R4")
        self.assert_invalid(document)

    def test_pending_scope_can_have_no_execution_budget(self):
        document = copy.deepcopy(self.sample_scope)
        document["targets"] = [document["targets"][1]]
        document["identityRef"] = "unknown"
        document["environmentRef"] = "unknown"
        document["allowedRisks"] = []
        document["actionBudget"] = {"maxActions": 0}
        self.assertEqual(list(self.validator.iter_errors(document)), [])

    def test_in_scope_requires_a_nonzero_budget_and_risk_allowance(self):
        document = copy.deepcopy(self.sample_scope)
        document["allowedRisks"] = []
        document["actionBudget"]["maxActions"] = 0
        self.assert_invalid(document)

    def test_additional_properties_are_rejected(self):
        document = copy.deepcopy(self.sample_scope)
        document["approvedByModel"] = True
        self.assert_invalid(document)


if __name__ == "__main__":
    unittest.main()
