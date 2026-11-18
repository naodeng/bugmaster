import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "approval.schema.json"
EXAMPLES = ROOT / "examples" / "contracts"


class ApprovalSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )
        cls.scope_approval = json.loads(
            (EXAMPLES / "scope-approval.json").read_text(encoding="utf-8")
        )
        cls.action_approval = json.loads(
            (EXAMPLES / "action-approval.json").read_text(encoding="utf-8")
        )

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_scope_approval_binds_target_scope_revision_and_source_event(self):
        self.assertEqual(list(self.validator.iter_errors(self.scope_approval)), [])

    def test_action_approval_binds_normalized_r2_intent(self):
        self.assertEqual(list(self.validator.iter_errors(self.action_approval)), [])

    def test_action_approval_requires_action_and_parameter_digests(self):
        document = copy.deepcopy(self.action_approval)
        del document["actionDigest"]
        del document["parameterDigest"]
        self.assert_invalid(document)

    def test_action_approval_cannot_authorize_r3(self):
        document = copy.deepcopy(self.action_approval)
        document["risk"] = "R3"
        self.assert_invalid(document)

    def test_rejected_approval_requires_reason(self):
        document = copy.deepcopy(self.scope_approval)
        document["status"] = "rejected"
        self.assert_invalid(document)

    def test_invalid_timestamps_are_rejected(self):
        document = copy.deepcopy(self.scope_approval)
        document["expiresAt"] = "tomorrow"
        self.assert_invalid(document)

    def test_untrusted_provenance_claim_is_not_an_approval_field(self):
        document = copy.deepcopy(self.action_approval)
        document["provenanceVerified"] = True
        self.assert_invalid(document)


if __name__ == "__main__":
    unittest.main()
