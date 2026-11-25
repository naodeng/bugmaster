import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "action.schema.json"
EXAMPLES = ROOT / "examples" / "contracts"


class ActionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )
        cls.readonly_action = json.loads(
            (EXAMPLES / "action-readonly.json").read_text(encoding="utf-8")
        )
        cls.r2_action = json.loads(
            (EXAMPLES / "action-r2-authorized.json").read_text(encoding="utf-8")
        )

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_readonly_r0_action_is_valid(self):
        self.assertEqual(list(self.validator.iter_errors(self.readonly_action)), [])

    def test_action_method_rejects_trailing_newline(self):
        for separator in ("\r", "\n", "\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)):
                document = copy.deepcopy(self.readonly_action)
                document["method"] = f"GET{separator}"
                self.assert_invalid(document)

    def test_action_digests_reject_trailing_newline(self):
        for field in ("intentDigest", "parameterDigest"):
            for separator in ("\r", "\n", "\u2028", "\u2029"):
                with self.subTest(field=field, separator=repr(separator)):
                    document = copy.deepcopy(self.readonly_action)
                    document[field] = "a" * 64 + separator
                    self.assert_invalid(document)

    def test_r2_action_binds_scope_and_action_approval_references(self):
        self.assertEqual(list(self.validator.iter_errors(self.r2_action)), [])
        approval = json.loads(
            (EXAMPLES / "action-approval.json").read_text(encoding="utf-8")
        )
        self.assertEqual(self.r2_action["approvalRef"], approval["approvalId"])
        self.assertEqual(self.r2_action["intentDigest"], approval["actionDigest"])
        self.assertEqual(self.r2_action["parameterDigest"], approval["parameterDigest"])
        self.assertEqual(self.r2_action["targetRef"], approval["targetRef"])
        self.assertEqual(self.r2_action["scopeRevision"], approval["scopeRevision"])

    def test_r2_proposed_action_does_not_claim_approval(self):
        document = copy.deepcopy(self.r2_action)
        document["status"] = "proposed"
        del document["approvalRef"]
        self.assertEqual(list(self.validator.iter_errors(document)), [])

    def test_r0_mutation_is_rejected(self):
        document = copy.deepcopy(self.readonly_action)
        document["operationMutates"] = True
        self.assert_invalid(document)

    def test_r2_execution_status_requires_approval_reference(self):
        document = copy.deepcopy(self.r2_action)
        del document["approvalRef"]
        self.assert_invalid(document)

    def test_r1_mutation_requires_enforcement_reference_before_dispatch(self):
        document = copy.deepcopy(self.readonly_action)
        document.update(
            {"risk": "R1", "operationMutates": True, "status": "completed"}
        )
        self.assert_invalid(document)

    def test_r1_mutation_with_enforcement_reference_is_structurally_valid(self):
        document = copy.deepcopy(self.readonly_action)
        document.update(
            {
                "risk": "R1",
                "operationMutates": True,
                "status": "completed",
                "enforcementRef": "host-policy-isolation-001",
            }
        )
        self.assertEqual(list(self.validator.iter_errors(document)), [])

    def test_r3_cannot_be_marked_dispatched(self):
        document = copy.deepcopy(self.r2_action)
        document["risk"] = "R3"
        document["status"] = "dispatched"
        self.assert_invalid(document)

    def test_mobile_surface_cannot_be_marked_executed(self):
        document = copy.deepcopy(self.readonly_action)
        document["surface"] = "ios"
        document["status"] = "completed"
        self.assert_invalid(document)

    def test_digest_must_be_sha256_and_mutability_must_be_boolean(self):
        document = copy.deepcopy(self.readonly_action)
        document["intentDigest"] = "sha256:short"
        document["operationMutates"] = "false"
        self.assert_invalid(document)

    def test_unknown_action_fields_are_rejected(self):
        document = copy.deepcopy(self.readonly_action)
        document["trusted"] = True
        self.assert_invalid(document)


if __name__ == "__main__":
    unittest.main()
