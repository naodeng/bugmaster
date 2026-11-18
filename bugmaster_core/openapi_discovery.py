"""Local, source-linked discovery of API features from OpenAPI 3 documents."""

import hashlib
import re
from collections.abc import Mapping
from urllib.parse import quote


HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)
OPENAPI_3_VERSION = re.compile(r"3\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")


def _escape_pointer_token(token):
    return str(token).replace("~", "~0").replace("/", "~1")


def _append_pointer(source_ref, *tokens):
    escaped = "/".join(
        quote(_escape_pointer_token(token), safe="~") for token in tokens
    )
    return "{}#/{}".format(source_ref, escaped)


def _parameter_refs(container, source_ref, *base_tokens):
    if "parameters" not in container:
        return []
    parameters = container["parameters"]
    if not isinstance(parameters, list):
        raise ValueError("OpenAPI parameters must be an array")
    refs = []
    for index, parameter in enumerate(parameters):
        if not isinstance(parameter, Mapping):
            raise ValueError("OpenAPI parameter entries must be objects")
        refs.append(_append_pointer(source_ref, *base_tokens, "parameters", index))
    return refs


def _feature_name(operation, method, path):
    summary = operation.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("OpenAPI operation summary must be a string")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    operation_id = operation.get("operationId")
    if operation_id is not None and not isinstance(operation_id, str):
        raise ValueError("OpenAPI operationId must be a string")
    if isinstance(operation_id, str) and operation_id.strip():
        return operation_id.strip()
    return "{} {}".format(method.upper(), path)


def _operation_tags(operation):
    tags = operation.get("tags", [])
    if not isinstance(tags, list):
        raise ValueError("OpenAPI operation tags must be an array")
    if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise ValueError("OpenAPI operation tags must be non-empty strings")
    return sorted(set(tags))


def _responses(operation):
    responses = operation.get("responses", {})
    if not isinstance(responses, Mapping):
        raise ValueError("OpenAPI operation responses must be an object")
    return responses


def _security_ref(document, operation, source_ref, operation_tokens):
    if "security" in operation:
        security = operation["security"]
        pointer_tokens = (*operation_tokens, "security")
    elif "security" in document:
        security = document["security"]
        pointer_tokens = ("security",)
    else:
        return None
    if not isinstance(security, list):
        raise ValueError("OpenAPI security requirements must be an array")
    return _append_pointer(source_ref, *pointer_tokens)


def _feature_id(method, path):
    stable_key = "{}\n{}".format(method.upper(), path).encode("utf-8")
    return "api-{}".format(hashlib.sha256(stable_key).hexdigest()[:16])


def discover_openapi_features(document, source_ref):
    """Extract declared API operations without fetching or executing anything.

    Source references use JSON Pointer fragments into the supplied document.
    Discovery records what the OpenAPI document declares; it does not prove the
    endpoint exists in a running environment or grant authorization to call it.
    """
    if not isinstance(document, Mapping):
        raise ValueError("OpenAPI document must be an object")
    if not isinstance(source_ref, str) or not source_ref.strip() or "#" in source_ref:
        raise ValueError("source_ref must be a non-empty document reference without a fragment")
    source_ref = source_ref.strip()
    version = document.get("openapi")
    if not isinstance(version, str) or not OPENAPI_3_VERSION.fullmatch(version):
        raise ValueError("only OpenAPI 3.x documents are supported")
    paths = document.get("paths")
    if not isinstance(paths, Mapping):
        raise ValueError("OpenAPI paths must be an object")
    if any(not isinstance(path, str) for path in paths):
        raise ValueError("OpenAPI path keys must be strings")

    features = []
    for path in sorted(paths):
        if not path.startswith("/"):
            raise ValueError("OpenAPI path keys must start with '/'")
        path_item = paths[path]
        if not isinstance(path_item, Mapping):
            raise ValueError("OpenAPI path items must be objects")
        if any(not isinstance(key, str) for key in path_item):
            raise ValueError("OpenAPI path item keys must be strings")
        path_tokens = ("paths", path)
        path_parameter_refs = _parameter_refs(path_item, source_ref, *path_tokens)

        for method_key in sorted(path_item, key=str.lower):
            method = method_key.lower()
            if method not in HTTP_METHODS:
                continue
            operation = path_item[method_key]
            if not isinstance(operation, Mapping):
                raise ValueError("OpenAPI operation objects must be objects")
            operation_tokens = (*path_tokens, method_key)
            operation_ref = _append_pointer(source_ref, *operation_tokens)
            parameter_refs = path_parameter_refs + _parameter_refs(
                operation, source_ref, *operation_tokens
            )
            responses = _responses(operation)
            tags = _operation_tags(operation)
            name = _feature_name(operation, method, path)
            operation_id = operation.get("operationId")
            if "requestBody" in operation and not isinstance(
                operation["requestBody"], Mapping
            ):
                raise ValueError("OpenAPI requestBody must be an object")

            feature = {
                "featureId": _feature_id(method, path),
                "name": name,
                "surface": "api",
                "discoveryStatus": "discovered",
                "observationKind": "openapi-declaration",
                "sourceRef": operation_ref,
                "method": method.upper(),
                "path": path,
                "tags": tags,
                "parameterRefs": parameter_refs,
                "requestBodyRef": (
                    _append_pointer(source_ref, *operation_tokens, "requestBody")
                    if "requestBody" in operation
                    else None
                ),
                "responseRefs": [
                    _append_pointer(source_ref, *operation_tokens, "responses", code)
                    for code in sorted(responses)
                ],
                "securityRef": _security_ref(
                    document, operation, source_ref, operation_tokens
                ),
            }
            if isinstance(operation_id, str) and operation_id.strip():
                feature["operationId"] = operation_id.strip()
            features.append(feature)
    return features
