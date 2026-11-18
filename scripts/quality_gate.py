#!/usr/bin/env python3
"""Fail-closed release gate for unit line and feature/core functional coverage.
No assertion that evidence references are authentic: actual execution evidence requires independent audit.
"""
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def validate_coverage(report):
    if not report:
        return ['missing-unit-coverage-report']
    p=pathlib.Path(report)
    if not p.is_file():
        return ['missing-unit-coverage-report']
    data=json.loads(p.read_text(encoding='utf-8'))
    total=data.get('totals',{})
    measured=total.get('num_statements',0)
    covered=total.get('covered_lines',-1)
    if not measured or covered != measured:
        return ['unit-line-coverage-below-100-percent']
    return []
def validate_functional(ledger, matrix):
    reasons=[]
    data=json.loads(pathlib.Path(ledger).read_text(encoding='utf-8'))
    features=data.get('features',[])
    if not data.get('frozen') or not features:
        reasons.append('unfrozen-or-empty-feature-inventory')
    ids=[f['id'] for f in features]
    if len(ids)!=len(set(ids)):
        reasons.append('duplicate-feature-id')
    applicable=[f for f in features if f.get('applicable') is True]
    passed=[f for f in applicable if f.get('status')=='validated' and f.get('evidenceRefs') and f.get('oracleRef')]
    if not applicable or len(passed)*5 <= len(applicable)*3:
        reasons.append('functional-coverage-not-above-60-percent')
    cases=json.loads(pathlib.Path(matrix).read_text(encoding='utf-8')).get('cases',[])
    case_ids=[c.get('caseId') for c in cases]
    if len(case_ids)!=len(set(case_ids)):
        reasons.append('duplicate-case-id')
    for f in applicable:
        if not f.get('critical'):
            continue
        for kind in ('happy','negative','edge'):
            matches=[c for c in cases if c.get('featureId')==f['id'] and c.get('kind')==kind and c.get('result')=='passed' and c.get('evidenceRef') and c.get('oracleRef')]
            if not matches:
                reasons.append(f'missing-core-{kind}:{f["id"]}')
    return reasons

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['release','check'],default='check')
    parser.add_argument('--coverage',default=None)
    a=parser.parse_args()
    reasons=validate_coverage(a.coverage)+validate_functional(ROOT/'tests/quality/feature_coverage.json',ROOT/'tests/quality/core_case_matrix.json')
    if reasons:
        print('NO-GO: '+', '.join(reasons))
        return 1
    print('Local ledger gate passed; independent real-run and provenance audits still required.')
    return 0
if __name__=='__main__':sys.exit(main())
