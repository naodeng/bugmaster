"""Load versioned JSON Schemas from a closed, local registry."""

import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit


_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_SCHEMA_VERSION = re.compile(r"[0-9]+\.[0-9]+")
_REFERENCE_KEYWORDS = ("$ref", "$dynamicRef")


class SchemaRegistryError(ValueError):
    """A local schema bundle is invalid or contains an unresolved reference."""


class _BaseUriTracker:
    def __init__(self, base_uri):
        self.base_uri = base_uri

    def in_subresource(self, subresource):
        resource_id = subresource.id()
        if resource_id is None:
            return self
        return _BaseUriTracker(urljoin(self.base_uri, resource_id))


def _pointer_base_uri(registry, base_uri, pointer):
    resource = registry.get_or_retrieve(base_uri).value
    tracker = _BaseUriTracker(base_uri)
    resolved = resource.pointer(pointer, tracker)
    return resolved.resolver.base_uri


def _schema_id_key(uri):
    parsed = urlsplit(uri)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc
    hostname = parsed.hostname
    if hostname is not None:
        userinfo, separator, _ = netloc.rpartition("@")
        hostname = hostname.lower()
        if ":" in hostname:
            hostname = "[{}]".format(hostname)
        try:
            port = parsed.port
        except ValueError as error:
            raise SchemaRegistryError("schema-id-invalid") from error
        default_port = {"http": 80, "https": 443}.get(scheme)
        port_suffix = (
            "" if port is None or port == default_port else ":{}".format(port)
        )
        netloc = "{}{}{}{}".format(userinfo, separator, hostname, port_suffix)
    return urlunsplit((scheme, netloc, parsed.path, parsed.query, ""))


def _schema_resources(resource, base_uri, root_base_is_effective=False):
    contents = resource.contents
    declared_id = contents.get("$id") if isinstance(contents, dict) else None
    if isinstance(declared_id, str) and "#" in declared_id:
        raise SchemaRegistryError("schema-id-invalid")
    resource_id = resource.id()
    if root_base_is_effective and resource_id:
        try:
            declared_uri = urljoin(base_uri, resource_id)
            parsed_declared_uri = urlsplit(declared_uri)
        except ValueError as error:
            raise SchemaRegistryError("schema-id-invalid") from error
        if not parsed_declared_uri.scheme or parsed_declared_uri.fragment:
            raise SchemaRegistryError("schema-id-invalid")
    effective_uri = (
        base_uri
        if root_base_is_effective or not resource_id
        else urljoin(base_uri, resource_id)
    )
    parsed_effective_uri = urlsplit(effective_uri)
    if not parsed_effective_uri.scheme or parsed_effective_uri.fragment:
        raise SchemaRegistryError("schema-id-invalid")
    yield resource, effective_uri
    for subresource in resource.subresources():
        yield from _schema_resources(subresource, effective_uri)


def _reference_base_uri(base_uri, reference):
    try:
        if reference.startswith("#"):
            return urldefrag(base_uri)[0]
        return urldefrag(urljoin(base_uri, reference))[0]
    except ValueError as error:
        raise SchemaRegistryError(
            "schema-reference-unresolved:{}".format(reference)
        ) from error


def _load_schema_bundle(schemas_directory):
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from jsonschema.exceptions import SchemaError
        from referencing import Registry, Resource
        from referencing.exceptions import Unresolvable
        from referencing.jsonschema import DRAFT202012
    except ImportError as error:
        raise SchemaRegistryError("schema-validator-dependency-missing") from error

    schema_files = sorted(Path(schemas_directory).glob("*.schema.json"))
    if not schema_files:
        raise SchemaRegistryError("schema-bundle-empty")

    schemas = {}
    schema_ids = set()
    for schema_path in schema_files:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as error:
            raise SchemaRegistryError(
                "schema-json-invalid:{}".format(schema_path.name)
            ) from error

        if not isinstance(schema, dict):
            raise SchemaRegistryError(
                "schema-object-invalid:{}".format(schema_path.name)
            )
        if schema.get("$schema") != _DRAFT_2020_12:
            raise SchemaRegistryError(
                "schema-draft-unsupported:{}".format(schema_path.name)
            )

        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise SchemaRegistryError(
                "schema-id-invalid:{}".format(schema_path.name)
            )
        try:
            parsed_schema_id = urlsplit(schema_id)
        except ValueError as error:
            raise SchemaRegistryError(
                "schema-id-invalid:{}".format(schema_path.name)
            ) from error
        if not parsed_schema_id.scheme or "#" in schema_id:
            raise SchemaRegistryError(
                "schema-id-invalid:{}".format(schema_path.name)
            )
        schema_id_key = _schema_id_key(schema_id)
        if schema_id_key in schema_ids:
            raise SchemaRegistryError(
                "schema-id-duplicate:{}".format(schema_path.name)
            )

        required = schema.get("required")
        properties = schema.get("properties")
        version_property = (
            properties.get("schemaVersion")
            if isinstance(properties, dict)
            else None
        )
        version = (
            version_property.get("const")
            if isinstance(version_property, dict)
            else None
        )
        if (
            not isinstance(required, list)
            or "schemaVersion" not in required
            or not isinstance(version, str)
            or _SCHEMA_VERSION.fullmatch(version) is None
        ):
            raise SchemaRegistryError(
                "schema-version-invalid:{}".format(schema_path.name)
            )

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise SchemaRegistryError(
                "schema-invalid:{}".format(schema_path.name)
            ) from error

        schemas[schema_path.name] = schema
        schema_ids.add(schema_id_key)

    registry = Registry()
    root_resources = {}
    for schema in schemas.values():
        try:
            resource = Resource.from_contents(deepcopy(schema))
            registry = registry.with_resource(schema["$id"], resource)
            root_resources[schema["$id"]] = resource
        except (ValueError, TypeError) as error:
            raise SchemaRegistryError("schema-resource-invalid") from error

    registered_ids = set(schema_ids)
    resources_by_id_key = {
        _schema_id_key(schema_id): resource
        for schema_id, resource in root_resources.items()
    }
    resources_by_contents_id = {
        id(resource.contents): resource for resource in root_resources.values()
    }
    root_resource_contents_ids = set(resources_by_contents_id)
    resource_uris_by_contents_id = {
        id(resource.contents): schema_id
        for schema_id, resource in root_resources.items()
    }

    def register_resources(
        resource,
        base_uri,
        root_base_is_effective=False,
        skip_root=False,
    ):
        nonlocal registry
        try:
            for candidate, effective_uri in _schema_resources(
                resource,
                base_uri,
                root_base_is_effective=root_base_is_effective,
            ):
                if skip_root and candidate is resource:
                    continue
                contents_id = id(candidate.contents)
                if contents_id in resources_by_contents_id:
                    continue
                if candidate.id() is None:
                    continue

                effective_uri_key = _schema_id_key(effective_uri)
                if effective_uri_key in registered_ids:
                    raise SchemaRegistryError("schema-id-duplicate")
                candidate.contents["$id"] = effective_uri
                registry = registry.with_resource(effective_uri, candidate)
                registered_ids.add(effective_uri_key)
                resources_by_id_key[effective_uri_key] = candidate
                resources_by_contents_id[contents_id] = candidate
                resource_uris_by_contents_id[contents_id] = effective_uri
        except SchemaRegistryError:
            raise
        except (ValueError, TypeError) as error:
            raise SchemaRegistryError("schema-resource-invalid") from error

    for root_resource in root_resources.values():
        register_resources(root_resource, "")

    pending_resources = []
    for root_resource in root_resources.values():
        pending_resources.extend(_schema_resources(root_resource, ""))

    visited_resources = set()
    while pending_resources:
        resource, effective_uri = pending_resources.pop()
        visit_key = (id(resource.contents), effective_uri)
        if visit_key in visited_resources:
            continue
        visited_resources.add(visit_key)

        contents = resource.contents
        if not isinstance(contents, dict):
            continue
        for keyword in _REFERENCE_KEYWORDS:
            if keyword not in contents:
                continue
            reference = contents[keyword]
            reference_uri = _reference_base_uri(effective_uri, reference)
            resolver = registry.resolver(base_uri=effective_uri)
            try:
                resolved = resolver.lookup(reference)
            except (Unresolvable, ValueError, TypeError) as error:
                try:
                    target_resource = resources_by_id_key[
                        _schema_id_key(reference_uri)
                    ]
                    registry = registry.with_resource(
                        reference_uri, target_resource
                    )
                    resolved = registry.resolver(
                        base_uri=effective_uri
                    ).lookup(reference)
                except (
                    KeyError,
                    Unresolvable,
                    ValueError,
                    TypeError,
                ) as alias_error:
                    raise SchemaRegistryError(
                        "schema-reference-unresolved:{}".format(reference)
                    ) from alias_error
            try:
                Draft202012Validator.check_schema(resolved.contents)
            except SchemaError as error:
                raise SchemaRegistryError(
                    "schema-reference-target-invalid:{}".format(reference)
                ) from error

            resolved_contents_id = id(resolved.contents)
            target_is_registered_resource = (
                resolved_contents_id in resources_by_contents_id
            )
            reference_fragment = urldefrag(reference)[1]
            pointer_reference = reference_fragment.startswith("/")
            if pointer_reference:
                target_base_uri = _pointer_base_uri(
                    registry,
                    reference_uri,
                    reference_fragment,
                )
            elif (
                target_is_registered_resource
                and resolved_contents_id not in root_resource_contents_ids
            ):
                target_base_uri = resource_uris_by_contents_id[
                    resolved_contents_id
                ]
            else:
                target_base_uri = reference_uri
            target_resource = Resource.from_contents(
                resolved.contents,
                default_specification=DRAFT202012,
            )
            target_base_is_effective = (
                target_is_registered_resource or pointer_reference
            )
            register_resources(
                target_resource,
                target_base_uri,
                root_base_is_effective=target_base_is_effective,
                skip_root=(pointer_reference and not target_is_registered_resource),
            )
            pending_resources.extend(
                _schema_resources(
                    target_resource,
                    target_base_uri,
                    root_base_is_effective=target_base_is_effective,
                )
            )

    return schemas, registry


def _default_schema_bundle():
    schemas_directory = Path(__file__).resolve().parents[1] / "schemas"
    return _load_schema_bundle(schemas_directory)


def validate_schema_registry(schemas_directory=None):
    """Raise SchemaRegistryError unless the bundle is versioned and closed."""
    if schemas_directory is None:
        _default_schema_bundle()
    else:
        _load_schema_bundle(schemas_directory)


def get_schema_validator(schema_name, schemas_directory=None):
    """Return a validator whose references resolve only from the local bundle."""
    if schemas_directory is None:
        schemas, registry = _default_schema_bundle()
    else:
        schemas, registry = _load_schema_bundle(schemas_directory)

    if not isinstance(schema_name, str) or schema_name not in schemas:
        raise SchemaRegistryError("schema-not-found:{}".format(schema_name))

    from jsonschema import Draft202012Validator, FormatChecker

    return Draft202012Validator(
        schemas[schema_name],
        registry=registry,
        format_checker=FormatChecker(),
    )
