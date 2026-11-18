#!/usr/bin/env python3
"""Discover API features from a local OpenAPI JSON file; no network access."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bugmaster_core.openapi_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
