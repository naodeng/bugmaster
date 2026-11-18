import copy
import unittest

from bugmaster_core.openapi_discovery import discover_openapi_features


OPENAPI_DOCUMENT = {
    "openapi": "3.1.0",
    "security": [{"bearerAuth": []}],
    "paths": {
        "/orders/{orderId}": {
            "parameters": [{"name": "orderId", "in": "path", "required": True}],
            "get": {
                "operationId": "getOrder",
                "summary": "Read an order",
                "tags": ["Orders", "Read"],
                "parameters": [{"name": "expand", "in": "query"}],
                "responses": {"200": {"description": "Order found"}},
            },
            "post": {
                "summary": "Update an order",
                "requestBody": {"$ref": "#/components/requestBodies/UpdateOrder"},
                "responses": {"204": {"description": "Updated"}},
                "security": [],
            },
        },
        "/health": {"get": {"responses": {"200": {"description": "Ready"}}}},
    },
}


class OpenApiDiscoveryTests(unittest.TestCase):
    def test_discovers_declared_operations_with_source_evidence(self):
        features = discover_openapi_features(OPENAPI_DOCUMENT, "openapi.json")

        self.assertEqual(len(features), 3)
        read_order = next(
            feature
            for feature in features
            if feature.get("operationId") == "getOrder"
        )
        self.assertEqual(read_order["name"], "Read an order")
        self.assertEqual(read_order["surface"], "api")
        self.assertEqual(read_order["discoveryStatus"], "discovered")
        self.assertEqual(read_order["observationKind"], "openapi-declaration")
        self.assertEqual(
            read_order["sourceRef"],
            "openapi.json#/paths/~1orders~1%7BorderId%7D/get",
        )
        self.assertEqual(
            read_order["parameterRefs"],
            [
                "openapi.json#/paths/~1orders~1%7BorderId%7D/parameters/0",
                "openapi.json#/paths/~1orders~1%7BorderId%7D/get/parameters/0",
            ],
        )
        self.assertEqual(
            read_order["securityRef"],
            "openapi.json#/security",
        )
        update_order = next(
            feature for feature in features if feature["method"] == "POST"
        )
        self.assertEqual(
            update_order["requestBodyRef"],
            "openapi.json#/paths/~1orders~1%7BorderId%7D/post/requestBody",
        )
        self.assertEqual(
            update_order["securityRef"],
            "openapi.json#/paths/~1orders~1%7BorderId%7D/post/security",
        )

    def test_non_operation_path_fields_are_not_discovered_as_features(self):
        document = {
            "openapi": "3.1.0",
            "paths": {
                "/health": {
                    "parameters": [],
                    "servers": [{"url": "https://example.test"}],
                    "x-note": "metadata",
                    "get": {"responses": {"200": {}}},
                }
            },
        }
        features = discover_openapi_features(document, "spec.json")
        self.assertEqual([feature["method"] for feature in features], ["GET"])

    def test_feature_ids_and_order_are_deterministic(self):
        original = discover_openapi_features(OPENAPI_DOCUMENT, "spec.json")
        reordered = copy.deepcopy(OPENAPI_DOCUMENT)
        reordered["paths"] = dict(reversed(list(reordered["paths"].items())))
        reordered["paths"]["/orders/{orderId}"] = dict(
            reversed(list(reordered["paths"]["/orders/{orderId}"].items()))
        )
        self.assertEqual(original, discover_openapi_features(reordered, "spec.json"))

    def test_feature_id_does_not_change_when_summary_changes(self):
        original = discover_openapi_features(OPENAPI_DOCUMENT, "spec.json")
        changed = copy.deepcopy(OPENAPI_DOCUMENT)
        changed["paths"]["/orders/{orderId}"]["get"]["summary"] = "Changed copy"
        updated = discover_openapi_features(changed, "spec.json")
        original_order = next(
            feature for feature in original if feature.get("operationId") == "getOrder"
        )
        updated_order = next(
            feature for feature in updated if feature.get("operationId") == "getOrder"
        )
        self.assertEqual(original_order["featureId"], updated_order["featureId"])

    def test_operation_id_or_method_and_path_provide_name_fallbacks(self):
        document = {
            "openapi": "3.0.3",
            "paths": {
                "/orders": {"get": {"operationId": "listOrders", "responses": {}}},
                "/ready": {"head": {"responses": {}}},
            },
        }
        features = discover_openapi_features(document, "spec.json")
        self.assertEqual(features[0]["name"], "listOrders")
        self.assertEqual(features[1]["name"], "HEAD /ready")

    def test_empty_paths_produce_an_empty_inventory(self):
        self.assertEqual(
            discover_openapi_features({"openapi": "3.1.0", "paths": {}}, "spec.json"),
            [],
        )

    def test_partial_operation_without_responses_is_still_a_discovered_declaration(self):
        document = {"openapi": "3.1.0", "paths": {"/partial": {"get": {}}}}
        feature = discover_openapi_features(document, "spec.json")[0]
        self.assertEqual(feature["responseRefs"], [])

    def test_pointer_escaping_covers_tilde_and_slash(self):
        document = {
            "openapi": "3.1.0",
            "paths": {"/files/{id~name}": {"get": {"responses": {}}}},
        }
        feature = discover_openapi_features(document, "spec.json")[0]
        self.assertEqual(
            feature["sourceRef"],
            "spec.json#/paths/~1files~1%7Bid~0name%7D/get",
        )

    def test_invalid_operation_fields_are_rejected(self):
        invalid_documents = []
        for operation in (
            {"summary": 12},
            {"operationId": 12},
            {"tags": {}},
            {"tags": [12]},
            {"tags": [""]},
            {"parameters": [None]},
            {"security": {}},
            {"requestBody": []},
        ):
            invalid_documents.append(
                {"openapi": "3.1.0", "paths": {"/invalid": {"get": operation}}}
            )
        invalid_documents.extend(
            [
                {
                    "openapi": "3.1.0",
                    "paths": {"/invalid": {"get": {}, 1: "non-string key"}},
                },
                {
                    "openapi": "3.1.0",
                    "security": {},
                    "paths": {"/invalid": {"get": {}}},
                },
            ]
        )
        for document in invalid_documents:
            with self.subTest(document=document):
                with self.assertRaises(ValueError):
                    discover_openapi_features(document, "spec.json")

    def test_invalid_documents_and_source_refs_are_rejected(self):
        invalid_inputs = [
            ([], "spec.json"),
            ({"paths": {}}, "spec.json"),
            ({"openapi": "2.0.0", "paths": {}}, "spec.json"),
            ({"openapi": "3.", "paths": {}}, "spec.json"),
            ({"openapi": "3.1.0", "paths": []}, "spec.json"),
            ({"openapi": "3.1.0", "paths": {"orders": {}}}, "spec.json"),
            ({"openapi": "3.1.0", "paths": {"/x": []}}, "spec.json"),
            ({"openapi": "3.1.0", "paths": {"/x": {"get": []}}}, "spec.json"),
            ({"openapi": "3.1.0", "paths": {"/x": {"get": {"parameters": {}}}}}, "spec.json"),
            ({"openapi": "3.1.0", "paths": {"/x": {"get": {"responses": []}}}}, "spec.json"),
            ({"openapi": "3.1.0"}, "spec.json"),
            ({"openapi": 3.1, "paths": {}}, "spec.json"),
            ({"openapi": "3.1.0", "paths": {}}, ""),
            ({"openapi": "3.1.0", "paths": {}}, None),
            ({"openapi": "3.1.0", "paths": {}}, "   "),
            ({"openapi": "3.1.0", "paths": {}}, "spec.json#/already-has-fragment"),
            ({"openapi": "3.1.0", "paths": {1: {}}}, "spec.json"),
        ]
        for document, source_ref in invalid_inputs:
            with self.subTest(document=document, source_ref=source_ref):
                with self.assertRaises(ValueError):
                    discover_openapi_features(document, source_ref)


if __name__ == "__main__":
    unittest.main()
