import io
import json
import re
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
    @staticmethod
    def _create_minimal_standalone_repository(root):
        skill = root / "skills" / "sample"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("sample skill", encoding="utf-8")
        (root / "patterns").mkdir()
        (root / "registry").mkdir()
        (root / "registry" / "capabilities.json").write_text(
            json.dumps({"capabilities": [{"skill": "sample", "patternIds": []}]}),
            encoding="utf-8",
        )
        return skill

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
            build("discover-api-idempotency-defects", output)
            (output / "stale.txt").write_text("stale", encoding="utf-8")

            package = build("discover-api-idempotency-defects", output)

            self.assertFalse((package / "stale.txt").exists())
            self.assertTrue((package / "manifest.json").is_file())

    def test_standalone_builder_preserves_unmanaged_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "repository"
            self._create_minimal_standalone_repository(root)
            output = base / "user-data"
            output.mkdir()
            (output / "keep.txt").write_text("user data", encoding="utf-8")

            with patch.object(build_standalone, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "unsafe-output-path"):
                    build("sample", output)

            self.assertEqual((output / "keep.txt").read_text(), "user data")

    def test_standalone_builder_never_removes_repository_or_skill_sources(self):
        for output_name in ("repository", "skill/package"):
            with self.subTest(output=output_name), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory) / "repository"
                skill = root / "skills" / "sample"
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text("keep", encoding="utf-8")
                (root / "patterns").mkdir()
                (root / "registry").mkdir()
                (root / "registry" / "capabilities.json").write_text(
                    json.dumps({"capabilities": [{"skill": "sample", "patternIds": []}]}),
                    encoding="utf-8",
                )
                output = root if output_name == "repository" else skill / "package"

                with patch.object(build_standalone, "ROOT", root):
                    try:
                        build("sample", output)
                    except (OSError, ValueError) as error:
                        self.assertIsInstance(error, ValueError)
                        self.assertRegex(str(error), "unsafe-output-path")
                    else:
                        self.fail("unsafe output path was accepted")
                    self.assertTrue((skill / "SKILL.md").is_file())
                    self.assertEqual((skill / "SKILL.md").read_text(), "keep")

    def test_standalone_builder_preserves_existing_output_when_pattern_validation_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "repository"
            (root / "registry").mkdir(parents=True)
            (root / "skills" / "sample").mkdir(parents=True)
            (root / "patterns").mkdir()
            (root / "registry" / "capabilities.json").write_text(
                json.dumps(
                    {"capabilities": [{"skill": "sample", "patternIds": ["BP-MISSING"]}]}
                ),
                encoding="utf-8",
            )
            output = base / "package"
            output.mkdir()
            (output / "keep.txt").write_text("previous", encoding="utf-8")

            with patch.object(build_standalone, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "missing-or-duplicate-pattern"):
                    build("sample", output)

            self.assertTrue((output / "keep.txt").is_file())
            self.assertEqual((output / "keep.txt").read_text(), "previous")

    def test_standalone_builder_rejects_repository_root_ancestor_and_bundle_root(self):
        for output_kind in ("repository", "ancestor", "bundle-root"):
            with self.subTest(output=output_kind), tempfile.TemporaryDirectory() as temporary_directory:
                base = Path(temporary_directory)
                root = base / "repository"
                skill = self._create_minimal_standalone_repository(root)
                (base / "preserve.txt").write_text("keep", encoding="utf-8")
                output = {
                    "repository": root,
                    "ancestor": base,
                    "bundle-root": root / "dist" / "standalone",
                }[output_kind]

                with patch.object(build_standalone, "ROOT", root):
                    with self.assertRaisesRegex(ValueError, "unsafe-output-path"):
                        build("sample", output)

                self.assertEqual((skill / "SKILL.md").read_text(), "sample skill")
                self.assertEqual((base / "preserve.txt").read_text(), "keep")

    def test_standalone_builder_allows_the_repository_managed_bundle_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            self._create_minimal_standalone_repository(root)
            output = root / "dist" / "standalone" / "sample"

            with patch.object(build_standalone, "ROOT", root):
                package = build("sample", output)

            self.assertEqual(package, output)
            self.assertTrue((package / "manifest.json").is_file())

    def test_standalone_builder_rejects_symlinked_repository_output_parent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "repository"
            skill = self._create_minimal_standalone_repository(root)
            external = base / "external"
            external.mkdir()
            (external / "preserve.txt").write_text("keep", encoding="utf-8")
            (root / "dist").symlink_to(external, target_is_directory=True)
            output = root / "dist" / "standalone" / "sample"

            with patch.object(build_standalone, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "unsafe-output-path"):
                    build("sample", output)

            self.assertEqual((skill / "SKILL.md").read_text(), "sample skill")
            self.assertEqual((external / "preserve.txt").read_text(), "keep")

    def test_standalone_builder_rejects_file_and_symlink_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "repository"
            self._create_minimal_standalone_repository(root)
            file_output = base / "file-output"
            file_output.write_text("keep", encoding="utf-8")
            target = base / "target"
            target.mkdir()
            (target / "keep.txt").write_text("keep", encoding="utf-8")
            symlink_output = base / "symlink-output"
            symlink_output.symlink_to(target, target_is_directory=True)

            with patch.object(build_standalone, "ROOT", root):
                for output in (file_output, symlink_output):
                    with self.subTest(output=output):
                        with self.assertRaisesRegex(ValueError, "unsafe-output-path"):
                            build("sample", output)

            self.assertEqual(file_output.read_text(), "keep")
            self.assertEqual((target / "keep.txt").read_text(), "keep")

    def test_standalone_builder_restores_previous_output_when_publish_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "repository"
            self._create_minimal_standalone_repository(root)
            output = base / "package"
            with patch.object(build_standalone, "ROOT", root):
                build("sample", output)
            (output / "keep.txt").write_text("previous", encoding="utf-8")
            original_replace = Path.replace

            def fail_staged_publish(path, target):
                if path.parent.name.startswith(".package.stage-") and target == output:
                    raise OSError("publish-failed")
                return original_replace(path, target)

            with patch.object(Path, "replace", autospec=True, side_effect=fail_staged_publish):
                with patch.object(build_standalone, "ROOT", root):
                    with self.assertRaisesRegex(OSError, "publish-failed"):
                        build("sample", output)

            self.assertEqual((output / "keep.txt").read_text(), "previous")
            self.assertEqual(list(base.glob(".package.backup-*")), [])

    def test_standalone_builder_does_not_publish_when_first_publish_fails(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            root = base / "repository"
            self._create_minimal_standalone_repository(root)
            output = base / "package"
            original_replace = Path.replace

            def fail_staged_publish(path, target):
                if path.parent.name.startswith(".package.stage-") and target == output:
                    raise OSError("publish-failed")
                return original_replace(path, target)

            with patch.object(Path, "replace", autospec=True, side_effect=fail_staged_publish):
                with patch.object(build_standalone, "ROOT", root):
                    with self.assertRaisesRegex(OSError, "publish-failed"):
                        build("sample", output)

            self.assertFalse(output.exists())

    def test_github_workflows_pin_actions_to_full_commit_shas(self):
        workflow_directory = ROOT / ".github" / "workflows"
        action_references = []
        for workflow in workflow_directory.glob("*.y*ml"):
            action_references.extend(
                re.findall(r"^\s*-\s*uses:\s*([^\s#]+)", workflow.read_text(), re.MULTILINE)
            )

        self.assertTrue(action_references)
        self.assertTrue(
            all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference) for reference in action_references),
            action_references,
        )

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

    def test_dispatch_gate_rejects_self_asserted_scope_for_r0_and_r1(self):
        for risk in ("R0", "R1"):
            self.assertFalse(
                can_dispatch(
                    {"risk": risk},
                    {"status": "approved", "provenanceVerified": True},
                    {"enforcement": "enforced", "scopeValidated": True},
                )
            )

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

    def test_finding_gate_rejects_self_asserted_execution_and_oracle_claims(self):
        result = eligible_confirmed(
            {
                "evidenceLevel": "E3",
                "oracleViolation": True,
                "causalCheck": "passed",
                "environmentCheck": "passed",
                "reviewRequired": False,
            },
            [
                {
                    "source": "tool-execution",
                    "provenanceVerified": True,
                    "integrityVerified": True,
                }
            ],
            {"status": "validated", "sourceRef": "oracle.json"},
        )

        self.assertFalse(result["eligible"])
        self.assertIn("trusted-evidence-verifier-unavailable", result["reasons"])

    def test_finding_gate_rejects_any_candidate_assessment_field(self):
        result = eligible_confirmed(
            {
                "evidenceLevel": "E3",
                "oracleViolation": True,
                "causalCheck": "passed",
                "environmentCheck": "passed",
                "reviewRequired": False,
                "candidateAssessment": None,
            },
            [
                {
                    "source": "tool-execution",
                    "provenanceVerified": True,
                    "integrityVerified": True,
                }
            ],
            {"status": "validated", "sourceRef": "oracle.json"},
        )

        self.assertFalse(result["eligible"])
        self.assertIn(
            "candidate-assessment-not-confirmed-finding", result["reasons"]
        )

    def test_replay_gate_rejects_self_asserted_reconciliation_and_authorization(self):
        self.assertFalse(
            can_replay(
                {
                    "outcome": "reconciled-not-executed",
                    "reconcilerVerified": True,
                    "newAuthorizationValid": True,
                }
            )
        )

    def test_dispatch_gate_rejects_high_risk_and_unscoped_actions(self):
        self.assertFalse(can_dispatch({"risk": "R3"}, {}, {"scopeValidated": True}))
        self.assertFalse(can_dispatch({"risk": "R2"}, {}, {"scopeValidated": True}))
        self.assertFalse(can_dispatch({"risk": "R1"}, {}, {"scopeValidated": False}))

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
