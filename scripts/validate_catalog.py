#!/usr/bin/env python3
"""Offline deterministic checks of canonical skill and pattern refs."""
import json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def validate(root=ROOT):
    errors=[]
    reg=json.loads((root/'registry/capabilities.json').read_text())
    tax=json.loads((root/'patterns/taxonomy.json').read_text())
    patterns={}
    for file in (root/'patterns').glob('*/BP-*/pattern.json'):
        try:
            x=json.loads(file.read_text())
            p=x['id']
            if p in patterns: errors.append(f'duplicate-pattern:{p}')
            patterns[p]=x
            if file.parent.name!=p: errors.append(f'id-path-mismatch:{p}')
            if x.get('category') not in tax['categories']: errors.append(f'bad-category:{p}')
            if x.get('status') not in {'candidate','reviewed','verified','deprecated'}: errors.append(f'bad-status:{p}')
            if x.get('status')=='verified' and x.get('evaluation',{}).get('status')!='verified': errors.append(f'unproven-pattern:{p}')
        except Exception as e: errors.append(f'bad-pattern:{file}:{e}')
    if len(patterns)!=16: errors.append(f'pattern-count:{len(patterns)}')
    ids=set()
    for entry in reg['capabilities']:
        cid=entry['id'];name=entry['skill']
        if cid in ids: errors.append(f'duplicate-capability:{cid}')
        ids.add(cid)
        skill=root/'skills'/name/'SKILL.md'
        if not skill.exists(): errors.append(f'missing-skill:{name}')
        for pid in entry['patternIds']:
            if pid not in patterns: errors.append(f'missing-pattern:{pid}')
    if len(ids)!=11: errors.append(f'capability-count:{len(ids)}')
    return errors
if __name__=='__main__':
    errs=validate()
    print('PASS catalog/registry' if not errs else '\n'.join(errs))
    sys.exit(bool(errs))
