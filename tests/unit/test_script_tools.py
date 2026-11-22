import io
import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_standalone
import quality_gate
from build_standalone import build
from check_branding import scan
from quality_gate import validate_coverage, validate_functional
from validate_catalog import validate as validate_catalog
from validate_gates import can_dispatch, can_replay, eligible_confirmed


class ScriptToolsTests(unittest.TestCase):
    def test_standalone_builder_rejects_unknown_skills_and_missing_patterns(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "registry").mkdir()
            (root / "skills" / "sample").mkdir(parents=True)
            (root / "patterns").mkdir()
            (root / "registry" / "capabilities.json").write_text(
                json.dumps(
                    {
                        "capabilities": [
                            {
                                "skill": "sample",
                                "patternIds": ["BP-API-001"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(build_standalone, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "unknown-skill"):
                    build("missing", root / "out")
                with self.assertRaisesRegex(ValueError, "missing-or-duplicate-pattern"):
                    build("sample", root / "out")

    def test_standalone_builder_replaces_only_the_requested_output_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "package"
            output.mkdir()
            (output / "stale.txt").write_text("stale", encoding="utf-8")

            package = build("discover-api-idempotency-defects", output)

            self.assertFalse((package / "stale.txt").exists())
            self.assertTrue((package / "manifest.json").is_file())

    def test_branding_scan_reports_bad_names_invalid_text_and_forbidden_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            skipped = root / ".git"
            skipped.mkdir()
            (skipped / "legacy.md").write_text("ignored", encoding="utf-8")
            bad_directory = root / ("hunt-" + "directory")
            bad_directory.mkdir()
            (root / "invalid.md").write_bytes(b"\xff")
            (root / "dirty.md").write_text(
                "Hunting" + " " + "Session", encoding="utf-8"
            )
            (root / "asset.bin").write_bytes(b"not scanned as text")

            errors = scan(root)

            self.assertIn("filename:" + "hunt-" + "directory", errors)
            self.assertIn("non-utf8:invalid.md", errors)
            self.assertIn("content:dirty.md", errors)
            self.assertNotIn("content:.git/legacy.md", errors)

    def test_quality_gate_handles_missing_reports_and_duplicate_inventory_ids(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.assertEqual(validate_coverage(None), ["missing-unit-coverage-report"])
            self.assertEqual(
                validate_coverage(root / "missing.json"),
                ["missing-unit-coverage-report"],
            )
            ledger = root / "features.json"
            matrix = root / "cases.json"
            feature = {
                "id": "F-DUPLICATE",
                "applicable": True,
                "critical": False,
                "status": "planned",
                "evidenceRefs": [],
                "oracleRef": None,
            }
            ledger.write_text(
                json.dumps({"frozen": False, "features": [feature, feature]}),
                encoding="utf-8",
            )
            matrix.write_text(json.dumps({"cases": []}), encoding="utf-8")

            reasons = validate_functional(ledger, matrix)

            self.assertIn("unfrozen-or-empty-feature-inventory", reasons)
            self.assertIn("duplicate-feature-id", reasons)

    def test_quality_gate_rejects_incomplete_coverage_and_core_case_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            coverage = root / "coverage.json"
            coverage.write_text(
                json.dumps({"totals": {"covered_lines": 1, "num_statements": 2}}),
                encoding="utf-8",
            )
            self.assertEqual(
                validate_coverage(coverage),
                ["unit-line-coverage-below-100-percent"],
            )

            ledger = root / "features.json"
            matrix = root / "cases.json"
            feature = {
                "id": "F-CORE",
                "applicable": True,
                "critical": True,
                "status": "validated",
                "evidenceRefs": ["local-run"],
                "oracleRef": "local-oracle",
            }
            ledger.write_text(
                json.dumps({"frozen": True, "features": [feature]}),
                encoding="utf-8",
            )
            matrix.write_text(
                json.dumps({
                    "cases": [
                        {"caseId": "duplicate", "featureId": "F-OTHER"},
                        {"caseId": "duplicate", "featureId": "F-OTHER"},
                    ]
                }),
                encoding="utf-8",
            )

            reasons = validate_functional(ledger, matrix)

            self.assertIn("duplicate-case-id", reasons)
            self.assertIn("missing-core-happy:F-CORE", reasons)
            self.assertIn("missing-core-negative:F-CORE", reasons)
            self.assertIn("missing-core-edge:F-CORE", reasons)

            matrix.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "caseId": "CASE-" + kind,
                                "featureId": "F-CORE",
                                "kind": kind,
                                "result": "passed",
                                "evidenceRef": "run-" + kind,
                                "oracleRef": "oracle-1",
                            }
                            for kind in ("happy", "negative", "edge")
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(validate_functional(ledger, matrix), [])

    def test_quality_gate_main_covers_pass_and_no_go_results(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            quality = root / "tests" / "quality"
            quality.mkdir(parents=True)
            ledger = quality / "feature_coverage.json"
            matrix = quality / "core_case_matrix.json"
            report = root / "coverage.json"
            report.write_text(
                json.dumps({"totals": {"covered_lines": 1, "num_statements": 1}}),
                encoding="utf-8",
            )
            feature = {
                "id": "F-LOCAL",
                "applicable": True,
                "critical": False,
                "status": "validated",
                "evidenceRefs": ["local-run"],
                "oracleRef": "local-oracle",
            }
            ledger.write_text(
                json.dumps({"frozen": True, "features": [feature]}),
                encoding="utf-8",
            )
            matrix.write_text(json.dumps({"cases": []}), encoding="utf-8")

            with patch.object(quality_gate, "ROOT", root), patch.object(
                sys,
                "argv",
                ["quality_gate", "--mode", "check", "--coverage", str(report)],
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(quality_gate.main(), 0)

            ledger.write_text(
                json.dumps({"frozen": False, "features": [feature]}),
                encoding="utf-8",
            )
            with patch.object(quality_gate, "ROOT", root), patch.object(
                sys,
                "argv",
                ["quality_gate", "--mode", "check", "--coverage", str(report)],
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(quality_gate.main(), 1)

    def test_dispatch_gate_rejects_r0_without_a_validated_scope(self):
        self.assertFalse(can_dispatch({"risk": "R0"}, {}, {"scopeValidated": False}))

    def test_finding_and_replay_gates_require_every_safety_condition(self):
        rejected = eligible_confirmed(
            {
                "evidenceLevel": "E2",
                "oracleViolation": False,
                "causalCheck": "pending",
                "environmentCheck": "pending",
                "blockingContradictions": ["unresolved"],
                "reviewRequired": True,
                "reviewStatus": "pending",
            },
            [],
            {"status": "draft"},
        )
        self.assertFalse(rejected["eligible"])
        self.assertIn("trusted-evidence-verifier-unavailable", rejected["reasons"])
        self.assertEqual(len(rejected["reasons"]), 9)

        self.assertFalse(can_replay({"outcome": "unknown"}))

    def test_dispatch_gate_rejects_high_risk_and_unscoped_actions(self):
        self.assertFalse(can_dispatch({"risk": "R3"}, {}, {"scopeValidated": True}))
        self.assertFalse(can_dispatch({"risk": "R2"}, {}, {"scopeValidated": True}))
        self.assertFalse(can_dispatch({"risk": "R1"}, {}, {"scopeValidated": False}))
        self.assertFalse(can_dispatch({"risk": "R1"}, {}, {"scopeValidated": True}))

    def test_script_cli_entrypoints_execute_with_local_inputs(self):
        output = io.StringIO()
        scripts = ROOT / "scripts"
        with tempfile.TemporaryDirectory() as temporary_directory:
            package = Path(temporary_directory) / "standalone"

            def run_script(path, arguments):
                with patch.object(sys, "argv", [str(path), *arguments]):
                    with redirect_stdout(output):
                        try:
                            runpy.run_path(str(path), run_name="__main__")
                        except SystemExit as exit_result:
                            return exit_result.code
                return None

            self.assertEqual(
                run_script(
                    scripts / "discover_openapi.py",
                    [
                        str(ROOT / "examples" / "openapi" / "orders.json"),
                        "--source-ref",
                        "examples/openapi/orders.json",
                    ],
                ),
                0,
            )
            self.assertEqual(
                run_script(
                    scripts / "build_standalone.py",
                    [
                        "--skill",
                        "discover-api-idempotency-defects",
                        "--output",
                        str(package),
                    ],
                ),
                None,
            )
            self.assertTrue((package / "manifest.json").is_file())
            self.assertEqual(run_script(scripts / "check_branding.py", []), False)
            self.assertEqual(run_script(scripts / "quality_gate.py", []), 1)
            self.assertEqual(run_script(scripts / "validate_benchmark.py", []), False)
            self.assertEqual(run_script(scripts / "validate_catalog.py", []), False)
            for path in (
                scripts / "discover_openapi.py",
                scripts / "build_standalone.py",
                scripts / "check_branding.py",
                scripts / "quality_gate.py",
                scripts / "validate_benchmark.py",
                scripts / "validate_catalog.py",
            ):
                runpy.run_path(str(path), run_name="script_import_probe")

    def test_catalog_reports_malformed_pattern_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "registry").mkdir()
            pattern = root / "patterns" / "api" / "BP-API-001"
            pattern.mkdir(parents=True)
            (root / "registry" / "capabilities.json").write_text(
                json.dumps({"capabilities": []}), encoding="utf-8"
            )
            (root / "patterns" / "taxonomy.json").write_text(
                json.dumps({"categories": ["api"]}), encoding="utf-8"
            )
            (pattern / "pattern.json").write_text("{", encoding="utf-8")

            errors = validate_catalog(root)

            self.assertTrue(any(error.startswith("bad-pattern:") for error in errors))


if __name__ == "__main__":
    unittest.main()
