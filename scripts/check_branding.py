#!/usr/bin/env python3
"""Check brand and unreleased public skill naming against approved BugMaster baseline."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TEXT = {'.md', '.json', '.yaml', '.yml', '.csv', '.py', '.txt', '.toml', '.sh'}
SKIP = {'__pycache__', '.git', '.coverage', 'dist'}
# Split forbidden tokens to keep the checker from matching its own patterns.
LEGACY = [
    re.compile('ai' + r'[-_ ]?' + 'bug' + r'[-_ ]?' + 'hunter', re.I),
    re.compile(r'\b' + 'bug' + r'[-_ ]' + 'hunting' + r'\b', re.I),
    re.compile(r'\b' + 'hunt' + r'[-_]' + r'[a-z0-9_-]+\b', re.I),
    re.compile(r'\b' + 'hunting' + r'[.][a-z0-9_-]+\b', re.I),
    re.compile(r'\b' + 'Hybrid ' + 'Hunting' + r'\b', re.I),
    re.compile(r'\b' + 'Hunting ' + 'Session' + r'\b', re.I),
]

def scan(root=ROOT):
    errors = []
    for f in root.rglob('*'):
        relative = f.relative_to(root)
        if any(part in SKIP for part in relative.parts):
            continue
        if any(p.search(str(relative)) for p in LEGACY):
            errors.append('filename:' + str(relative))
        if not f.is_file() or f.suffix.lower() not in TEXT:
            continue
        try:
            content = f.read_text(encoding='utf-8')
        except UnicodeError:
            errors.append('non-utf8:' + str(relative))
            continue
        for pattern in LEGACY:
            if pattern.search(content):
                errors.append('content:' + str(relative))
                break
    return sorted(set(errors))

if __name__ == '__main__':
    failures = scan()
    print('Brand and Skill name scan:', 'PASS' if not failures else 'FAIL:\n' + '\n'.join(failures))
    sys.exit(bool(failures))
