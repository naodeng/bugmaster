import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from build_standalone import build


class StandaloneBundleTests(unittest.TestCase):
    def test_all_eleven_skills_build_with_exact_pattern_closures_and_digests(self):
        catalog = json.loads(
            (ROOT / "registry" / "capabilities.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = pathlib.Path(temporary_directory)
            for entry in catalog["capabilities"]:
                skill = entry["skill"]
                with self.subTest(skill=skill):
                    package = build(skill, output_root / skill)
                    self.assertTrue((package / "SKILL.md").is_file())
                    manifest = json.loads(
                        (package / "manifest.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(manifest["skill"], skill)
                    self.assertEqual(manifest["patterns"], entry["patternIds"])
                    actual_patterns = {
                        path.parent.name
                        for path in (package / "patterns").glob("*/pattern.json")
                    }
                    self.assertEqual(actual_patterns, set(entry["patternIds"]))
                    for relative_path, expected_digest in manifest["files"].items():
                        actual_digest = hashlib.sha256(
                            (package / relative_path).read_bytes()
                        ).hexdigest()
                        self.assertEqual(actual_digest, expected_digest)


if __name__ == "__main__":
    unittest.main()
