"""Command-line entry point for local OpenAPI feature discovery."""

import argparse
import json
import sys
from pathlib import Path

from .openapi_discovery import discover_openapi_features


def main(argv=None, stdout=None, stderr=None):
    """Read a local OpenAPI JSON file and print its declared feature inventory."""
    output = stdout if stdout is not None else sys.stdout
    errors = stderr if stderr is not None else sys.stderr
    parser = argparse.ArgumentParser(
        description="Discover declared operations in a local OpenAPI 3 JSON document."
    )
    parser.add_argument("document", type=Path, help="local OpenAPI JSON file")
    parser.add_argument(
        "--source-ref",
        help="stable non-secret document reference to include in evidence pointers",
    )
    args = parser.parse_args(argv)

    try:
        raw_document = args.document.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print("ERROR: cannot read local OpenAPI file: {}".format(error), file=errors)
        return 2

    try:
        document = json.loads(raw_document)
    except json.JSONDecodeError as error:
        print("ERROR: invalid JSON in local OpenAPI file: {}".format(error), file=errors)
        return 2

    source_ref = (
        args.source_ref if args.source_ref is not None else args.document.name
    )
    try:
        features = discover_openapi_features(document, source_ref)
    except ValueError as error:
        print("ERROR: {}".format(error), file=errors)
        return 2

    inventory = {
        "schemaVersion": "1.0",
        "sourceRef": source_ref,
        "features": features,
    }
    print(json.dumps(inventory, indent=2, sort_keys=True), file=output)
    return 0
