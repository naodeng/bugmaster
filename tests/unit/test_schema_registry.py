import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bugmaster_core.schema_registry import (
    SchemaRegistryError,
    get_schema_validator,
    validate_schema_registry,
)


_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(schema_id="urn:bugmaster:test:schema:1.0"):
    return {
        "$schema": _DRAFT,
        "$id": schema_id,
        "type": "object",
        "required": ["schemaVersion"],
        "properties": {"schemaVersion": {"const": "1.0"}},
    }


class SchemaRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def write_schema(self, filename, schema):
        (self.directory / filename).write_text(
            json.dumps(schema), encoding="utf-8"
        )

    def assert_registry_error(self, expected_code):
        with self.assertRaisesRegex(SchemaRegistryError, expected_code):
            validate_schema_registry(self.directory)

    def test_repository_schema_registry_has_pinned_versions_and_closed_refs(self):
        validate_schema_registry()
        self.assertEqual(
            get_schema_validator("action.schema.json").schema["$id"],
            "urn:bugmaster:schema:action:1.0",
        )

    def test_local_cross_schema_reference_resolves_without_remote_fetch(self):
        child_id = "urn:bugmaster:test:child:1.0"
        child = _schema(child_id)
        child["$defs"] = {
            "state": {"type": "string", "enum": ["ok", "blocked"]}
        }
        root = _schema("urn:bugmaster:test:root:1.0")
        root["required"].append("state")
        root["properties"]["state"] = {
            "$ref": child_id + "#/$defs/state"
        }
        self.write_schema("child.schema.json", child)
        self.write_schema("root.schema.json", root)

        validator = get_schema_validator("root.schema.json", self.directory)

        self.assertTrue(validator.is_valid({"schemaVersion": "1.0", "state": "ok"}))
        self.assertFalse(
            validator.is_valid({"schemaVersion": "1.0", "state": "unknown"})
        )

    def test_uri_equivalent_cross_schema_reference_resolves_locally(self):
        child_id = "https://example.test/child.schema.json"
        child = _schema(child_id)
        root = _schema("https://example.test/root.schema.json")
        root["required"].append("child")
        root["properties"]["child"] = {
            "$ref": "HTTPS://EXAMPLE.TEST:443/child.schema.json"
        }
        self.write_schema("child.schema.json", child)
        self.write_schema("root.schema.json", root)

        validator = get_schema_validator("root.schema.json", self.directory)

        self.assertTrue(
            validator.is_valid(
                {"schemaVersion": "1.0", "child": {"schemaVersion": "1.0"}}
            )
        )

    def test_ref_shaped_default_data_is_not_traversed_as_a_schema_reference(self):
        schema = _schema()
        schema["properties"]["payload"] = {
            "type": "object",
            "default": {"$ref": "https://schemas.invalid/data-only"},
        }
        self.write_schema("data-value.schema.json", schema)

        validator = get_schema_validator("data-value.schema.json", self.directory)

        self.assertTrue(validator.is_valid({"schemaVersion": "1.0"}))

    def test_nested_schema_id_resolves_its_relative_references(self):
        root = _schema("https://example.test/root.json")
        nested = {
            "$id": "sub/nested.json",
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"$ref": "#/$defs/state"}},
            "$defs": {"state": {"$ref": "allowed.json"}},
        }
        root["required"].append("nested")
        root["properties"]["nested"] = {"$ref": "#/$defs/nested"}
        root["$defs"] = {"nested": nested}
        allowed = _schema("https://example.test/sub/allowed.json")
        allowed["required"].append("kind")
        allowed["properties"]["kind"] = {"const": "ok"}
        self.write_schema("root.schema.json", root)
        self.write_schema("allowed.schema.json", allowed)

        validator = get_schema_validator("root.schema.json", self.directory)

        self.assertTrue(
            validator.is_valid(
                {
                    "schemaVersion": "1.0",
                    "nested": {"value": {"schemaVersion": "1.0", "kind": "ok"}},
                }
            )
        )
        self.assertFalse(
            validator.is_valid(
                {
                    "schemaVersion": "1.0",
                    "nested": {"value": {"schemaVersion": "1.0", "kind": "bad"}},
                }
            )
        )

    def test_nested_schema_id_cannot_include_a_fragment(self):
        schema = _schema("https://example.test/root.json")
        schema["$defs"] = {
            "nested": {
                "$id": "nested.json#fragment",
                "type": "object",
            }
        }
        self.write_schema("fragmented-nested.schema.json", schema)

        self.assert_registry_error("schema-invalid")

    def test_nested_schema_id_cannot_include_an_empty_fragment(self):
        schema = _schema("https://example.test/root.json")
        schema["$defs"] = {
            "nested": {
                "$id": "nested.json#",
                "type": "object",
            }
        }
        self.write_schema("nested-empty-fragment.schema.json", schema)

        self.assert_registry_error("schema-id-invalid")

    def test_root_schema_id_cannot_include_an_empty_fragment(self):
        self.write_schema(
            "empty-fragment.schema.json",
            _schema("https://example.test/schema.json#"),
        )

        self.assert_registry_error("schema-id-invalid")

    def test_relative_nested_id_under_opaque_root_id_is_rejected(self):
        schema = _schema("urn:bugmaster:test:opaque-root:1.0")
        schema["$defs"] = {
            "nested": {
                "$id": "nested.json",
                "type": "object",
            }
        }
        self.write_schema("opaque-root.schema.json", schema)

        self.assert_registry_error("schema-id-invalid")

    def test_malformed_nested_id_is_rejected(self):
        schema = _schema("https://example.test/root.json")
        schema["$defs"] = {
            "nested": {
                "$id": "http://[::1",
                "type": "object",
            }
        }
        self.write_schema("malformed-nested-id.schema.json", schema)

        self.assert_registry_error("schema-invalid")

    def test_unresolved_local_pointer_is_rejected(self):
        schema = _schema()
        schema["properties"]["value"] = {"$ref": "#/$defs/missing"}
        self.write_schema("broken.schema.json", schema)

        self.assert_registry_error("schema-reference-unresolved")

    def test_reference_to_a_scalar_pointer_is_rejected(self):
        schema = _schema()
        schema["properties"]["value"] = {"type": "string"}
        schema["allOf"] = [{"$ref": "#/properties/value/type"}]
        self.write_schema("scalar-reference.schema.json", schema)

        self.assert_registry_error("schema-reference-target-invalid")

    def test_reference_to_an_invalid_schema_object_is_rejected(self):
        schema = _schema()
        schema["properties"]["value"] = {
            "type": "object",
            "default": {"type": "not-a-schema-type"},
        }
        schema["allOf"] = [{"$ref": "#/properties/value/default"}]
        self.write_schema("invalid-schema-reference.schema.json", schema)

        self.assert_registry_error("schema-reference-target-invalid")

    def test_reference_to_a_boolean_schema_is_valid(self):
        schema = _schema()
        schema["$defs"] = {"never": False}
        schema["properties"]["value"] = {"$ref": "#/$defs/never"}
        self.write_schema("boolean-schema-reference.schema.json", schema)

        validator = get_schema_validator(
            "boolean-schema-reference.schema.json", self.directory
        )

        self.assertTrue(validator.is_valid({"schemaVersion": "1.0"}))
        self.assertFalse(
            validator.is_valid({"schemaVersion": "1.0", "value": "x"})
        )

    def test_unregistered_external_reference_is_rejected(self):
        schema = _schema()
        schema["properties"]["value"] = {
            "$ref": "https://schemas.invalid/unregistered.json"
        }
        self.write_schema("remote.schema.json", schema)

        self.assert_registry_error("schema-reference-unresolved")

    def test_unregistered_dynamic_reference_is_rejected(self):
        schema = _schema()
        schema["properties"]["value"] = {
            "$dynamicRef": "https://schemas.invalid/dynamic#target"
        }
        self.write_schema("dynamic.schema.json", schema)

        self.assert_registry_error("schema-reference-unresolved")

    def test_duplicate_schema_ids_are_rejected(self):
        self.write_schema("first.schema.json", _schema("urn:duplicate:1.0"))
        self.write_schema("second.schema.json", _schema("urn:duplicate:1.0"))

        self.assert_registry_error("schema-id-duplicate")

        self.directory.joinpath("first.schema.json").unlink()
        self.directory.joinpath("second.schema.json").unlink()
        root = _schema("https://example.test/root.json")
        root["$defs"] = {
            "nested": {
                "$id": "https://EXAMPLE.TEST/shared.json",
                "type": "string",
            }
        }
        self.write_schema("root.schema.json", root)
        self.write_schema(
            "shared.schema.json", _schema("https://example.test/shared.json")
        )
        self.assert_registry_error("schema-id-duplicate")

    def test_uri_equivalent_root_schema_ids_are_rejected(self):
        self.write_schema(
            "first.schema.json", _schema("https://example.test/shared.json")
        )
        self.write_schema(
            "second.schema.json", _schema("HTTPS://EXAMPLE.TEST:443/shared.json")
        )

        self.assert_registry_error("schema-id-duplicate")

    def test_uri_equivalent_ipv6_ids_ignore_host_case_and_default_port(self):
        self.write_schema(
            "first.schema.json", _schema("https://[2001:DB8::1]:443/shared.json")
        )
        self.write_schema(
            "second.schema.json", _schema("HTTPS://[2001:db8::1]/shared.json")
        )

        self.assert_registry_error("schema-id-duplicate")

    def test_distinct_nondefault_ports_are_preserved(self):
        self.write_schema(
            "default-port.schema.json", _schema("https://example.test/shared.json")
        )
        self.write_schema(
            "custom-port.schema.json",
            _schema("https://example.test:8443/shared.json"),
        )

        validate_schema_registry(self.directory)

    def test_out_of_range_port_is_rejected(self):
        self.write_schema(
            "invalid-port.schema.json",
            _schema("https://example.test:70000/schema.json"),
        )

        self.assert_registry_error("schema-id-invalid")

    def test_schema_requires_an_id_and_supported_draft(self):
        missing_id = _schema()
        del missing_id["$id"]
        self.write_schema("missing-id.schema.json", missing_id)
        self.assert_registry_error("schema-id-invalid")

        self.directory.joinpath("missing-id.schema.json").unlink()
        relative_id = _schema("relative/schema.json")
        self.write_schema("relative-id.schema.json", relative_id)
        self.assert_registry_error("schema-id-invalid")

        self.directory.joinpath("relative-id.schema.json").unlink()
        fragmented_id = _schema("https://example.test/schema.json#fragment")
        self.write_schema("fragment-id.schema.json", fragmented_id)
        self.assert_registry_error("schema-id-invalid")

        self.directory.joinpath("fragment-id.schema.json").unlink()
        malformed_id = _schema("http://[::1")
        self.write_schema("malformed-id.schema.json", malformed_id)
        self.assert_registry_error("schema-id-invalid")

        self.directory.joinpath("malformed-id.schema.json").unlink()
        unsupported_draft = _schema()
        unsupported_draft["$schema"] = "https://json-schema.org/draft/2019-09/schema"
        self.write_schema("unsupported-draft.schema.json", unsupported_draft)
        self.assert_registry_error("schema-draft-unsupported")

    def test_schema_document_must_be_a_json_object(self):
        self.write_schema("not-an-object.schema.json", [])
        self.assert_registry_error("schema-object-invalid")

    def test_schema_version_must_be_required_and_pinned_to_major_minor(self):
        for index, version_schema, required in (
            (1, {"const": "1"}, ["schemaVersion"]),
            (2, {"type": "string"}, ["schemaVersion"]),
            (3, {"const": "1.0"}, []),
        ):
            with self.subTest(index=index):
                self.directory.joinpath("invalid.schema.json").unlink(missing_ok=True)
                schema = _schema()
                schema["properties"]["schemaVersion"] = version_schema
                schema["required"] = required
                self.write_schema("invalid.schema.json", schema)
                self.assert_registry_error("schema-version-invalid")

    def test_invalid_json_schema_definition_is_rejected(self):
        schema = _schema()
        schema["type"] = "not-a-json-schema-type"
        self.write_schema("invalid.schema.json", schema)

        self.assert_registry_error("schema-invalid")

    def test_missing_schema_validator_dependency_is_reported(self):
        self.write_schema("valid.schema.json", _schema())
        with mock.patch.dict(sys.modules, {"jsonschema": None}):
            self.assert_registry_error("schema-validator-dependency-missing")

    def test_invalid_local_resource_registration_is_reported(self):
        self.write_schema("valid.schema.json", _schema())
        with mock.patch(
            "referencing.Resource.from_contents",
            side_effect=ValueError("unsupported resource"),
        ):
            self.assert_registry_error("schema-resource-invalid")

    def test_nested_resource_registration_failure_is_reported(self):
        from referencing import Registry

        schema = _schema("https://example.test/root.json")
        schema["$defs"] = {
            "nested": {
                "$id": "nested.json",
                "type": "object",
            }
        }
        self.write_schema("nested.schema.json", schema)
        original_with_resource = Registry.with_resource

        def fail_nested_resource(registry, uri, resource):
            if uri.endswith("/nested.json"):
                raise ValueError("nested resource registration failed")
            return original_with_resource(registry, uri, resource)

        with mock.patch.object(
            Registry, "with_resource", new=fail_nested_resource
        ):
            self.assert_registry_error("schema-resource-invalid")

    def test_invalid_json_and_empty_directories_are_rejected(self):
        self.directory.joinpath("bad.schema.json").write_text("{", encoding="utf-8")
        self.assert_registry_error("schema-json-invalid")

        self.directory.joinpath("bad.schema.json").unlink()
        self.assert_registry_error("schema-bundle-empty")

    def test_unknown_schema_name_is_rejected(self):
        self.write_schema("known.schema.json", _schema())

        with self.assertRaisesRegex(SchemaRegistryError, "schema-not-found"):
            get_schema_validator("missing.schema.json", self.directory)


if __name__ == "__main__":
    unittest.main()
