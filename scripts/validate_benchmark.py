import json, pathlib, sys
R=pathlib.Path(__file__).resolve().parents[1]
def validate():
    m=json.loads((R/'benchmark/datasets/v0.1/manifest.json').read_text())
    cases=m['cases'];errors=[]
    if len(cases)!=50: errors.append('case-count')
    if len({x['id'] for x in cases})!=len(cases): errors.append('duplicate-case-id')
    if any(x['status']!='planned' for x in cases): errors.append('unverified-claim')
    return errors
if __name__=='__main__':
    e=validate();print('PASS benchmark manifest structure (NOT executed)' if not e else e);sys.exit(bool(e))
