#!/usr/bin/env python3
"""Copy a canonical skill and its referenced patterns into a portable local directory."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import tempfile
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]


def build(skill, out):
    catalog = json.loads((ROOT / "registry/capabilities.json").read_text())
    entry = next((item for item in catalog["capabilities"] if item["skill"] == skill), None)
    if not entry:
        raise ValueError("unknown-skill")

    pattern_sources = {}
    for pattern_id in entry["patternIds"]:
        matches = list((ROOT / "patterns").glob(f"*/{pattern_id}"))
        if len(matches) != 1:
            raise ValueError("missing-or-duplicate-pattern:" + pattern_id)
        pattern_sources[pattern_id] = matches[0]

    requested_output = pathlib.Path(out)
    out = pathlib.Path(os.path.abspath(out))
    if out.is_symlink():
        raise ValueError("unsafe-output-path")
    root = ROOT.resolve()
    resolved_out = out.resolve()
    bundle_root = root / "dist" / "standalone"

    try:
        out.relative_to(pathlib.Path(os.path.abspath(ROOT)))
    except ValueError:
        output_is_in_repository = False
    else:
        output_is_in_repository = True

    try:
        relative_output = resolved_out.relative_to(bundle_root)
    except ValueError:
        if (
            output_is_in_repository
            or root == resolved_out
            or root in resolved_out.parents
            or resolved_out in root.parents
        ):
            raise ValueError("unsafe-output-path")
    else:
        if not relative_output.parts:
            raise ValueError("unsafe-output-path")
        out = resolved_out

    if out.exists() and not out.is_dir():
        raise ValueError("unsafe-output-path")

    out.parent.mkdir(parents=True, exist_ok=True)
    stage_root = pathlib.Path(tempfile.mkdtemp(prefix=f".{out.name}.stage-", dir=out.parent))
    staged = stage_root / "package"
    backup = None
    try:
        shutil.copytree(ROOT / "skills" / skill, staged)
        for pattern_id, source in pattern_sources.items():
            shutil.copytree(source, staged / "patterns" / pattern_id)

        manifest = {"skill": skill, "patterns": entry["patternIds"], "files": {}}
        for file_path in sorted(staged.rglob("*")):
            if file_path.is_file():
                manifest["files"][str(file_path.relative_to(staged))] = hashlib.sha256(
                    file_path.read_bytes()
                ).hexdigest()
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        if out.exists():
            backup = out.with_name(f".{out.name}.backup-{uuid.uuid4().hex}")
            out.replace(backup)
        try:
            staged.replace(out)
        except OSError:
            if backup is not None:
                backup.replace(out)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return requested_output
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", required=True)
    parser.add_argument("--output")
    arguments = parser.parse_args()
    output = arguments.output or str(ROOT / "dist/standalone" / arguments.skill)
    print(build(arguments.skill, output))
