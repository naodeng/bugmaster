"""Naming and distributable entrypoint contract. Public names are frozen for v0.1."""
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_branding import scan

EXPECTED = {
    'bug-discovery',
    'discover-business-logic',
    'discover-boundary-defects',
    'discover-state-defects',
    'discover-api-contract-defects',
    'discover-api-idempotency-defects',
    'discover-web-interaction-defects',
    'discover-ui-api-inconsistencies',
    'bug-validation',
    'bug-reporting',
    'bug-regression-recommendation',
}

class SkillNamingContract(unittest.TestCase):
    def test_exact_eleven_skill_directories(self):
        actual = {p.name for p in (ROOT / 'skills').iterdir() if p.is_dir()}
        self.assertEqual(EXPECTED, actual)

    def test_skill_frontmatter_matches_directory(self):
        for name in sorted(EXPECTED):
            with self.subTest(skill=name):
                text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
                self.assertRegex(text, r'\A---\n')
                self.assertRegex(text, r'(?m)^name: ' + re.escape(name) + r'$')

    def test_registry_refs_and_ids(self):
        reg = json.loads((ROOT / 'registry/capabilities.json').read_text())
        self.assertEqual(EXPECTED, {x['skill'] for x in reg['capabilities']})
        for cap in reg['capabilities']:
            self.assertEqual('discovery.' + cap['skill'], cap['id'])

    def test_old_identifiers_absent(self):
        self.assertEqual([], scan(ROOT))

if __name__ == '__main__':
    unittest.main()
