import io
import json
import pathlib
import tempfile
import unittest

from bugmaster_core.openapi_cli import main


class OpenApiCliTests(unittest.TestCase):
    def write_document(self, root, content):
        path = pathlib.Path(root) / "openapi.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_reads_local_json_and_emits_source_linked_inventory(self):
        document = {
            "openapi": "3.1.0",
            "paths": {"/orders": {"get": {"summary": "List orders"}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_document(directory, json.dumps(document))
            output = io.StringIO()
            errors = io.StringIO()

            result = main([str(path), "--source-ref", "fixture/openapi.json"], output, errors)

        self.assertEqual(result, 0)
        self.assertEqual(errors.getvalue(), "")
        inventory = json.loads(output.getvalue())
        self.assertEqual(inventory["sourceRef"], "fixture/openapi.json")
        self.assertEqual(inventory["features"][0]["name"], "List orders")
        self.assertEqual(
            inventory["features"][0]["sourceRef"],
            "fixture/openapi.json#/paths/~1orders/get",
        )

    def test_defaults_source_ref_to_filename(self):
        document = {"openapi": "3.1.0", "paths": {}}
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_document(directory, json.dumps(document))
            output = io.StringIO()
            result = main([str(path)], output, io.StringIO())

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["sourceRef"], "openapi.json")

    def test_invalid_json_returns_error_without_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_document(directory, "not-json")
            output = io.StringIO()
            errors = io.StringIO()
            result = main([str(path)], output, errors)

        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("invalid JSON", errors.getvalue())

    def test_missing_file_returns_error_without_network_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "missing.json"
            output = io.StringIO()
            errors = io.StringIO()
            result = main([str(path)], output, errors)

        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("cannot read local OpenAPI file", errors.getvalue())

    def test_invalid_document_is_reported_as_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_document(directory, json.dumps({"openapi": "2.0.0", "paths": {}}))
            output = io.StringIO()
            errors = io.StringIO()
            result = main([str(path)], output, errors)

        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("only OpenAPI 3.x", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
