import copy
import io
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator

from bugmaster_core.openapi_cli import main


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "feature-inventory.schema.json"
OPENAPI_PATH = ROOT / "examples" / "openapi" / "orders.json"
SOURCE_REF = "examples/openapi/orders.json"


class FeatureInventorySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def generated_inventory(self):
        output = io.StringIO()
        errors = io.StringIO()
        result = main(
            [str(OPENAPI_PATH), "--source-ref", SOURCE_REF], output, errors
        )
        self.assertEqual(result, 0, errors.getvalue())
        return json.loads(output.getvalue())

    def assert_invalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_openapi_cli_output_matches_feature_inventory_contract(self):
        inventory = self.generated_inventory()
        self.assertEqual(list(self.validator.iter_errors(inventory)), [])
        self.assertEqual(len(inventory["features"]), 2)

    def test_discovery_status_cannot_claim_authorization(self):
        inventory = self.generated_inventory()
        inventory["features"][0]["discoveryStatus"] = "in_scope"
        self.assert_invalid(inventory)

    def test_execution_and_authorization_ledgers_are_not_embedded(self):
        inventory = self.generated_inventory()
        inventory["features"][0]["executionStatus"] = "explored"
        self.assert_invalid(inventory)

    def test_source_evidence_is_required(self):
        inventory = self.generated_inventory()
        del inventory["features"][0]["sourceRef"]
        self.assert_invalid(inventory)

    def test_feature_id_format_is_deterministic_and_bounded(self):
        inventory = self.generated_inventory()
        inventory["features"][0]["featureId"] = "feature-1"
        self.assert_invalid(inventory)

    def test_empty_inventory_is_valid(self):
        inventory = self.generated_inventory()
        inventory["features"] = []
        self.assertEqual(list(self.validator.iter_errors(inventory)), [])

    def test_unknown_authorization_field_is_rejected(self):
        inventory = copy.deepcopy(self.generated_inventory())
        inventory["authorizationStatus"] = "approved"
        self.assert_invalid(inventory)


if __name__ == "__main__":
    unittest.main()
