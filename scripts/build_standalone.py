#!/usr/bin/env python3
"""Copy a canonical skill and its referenced patterns into a portable local directory."""
import json,pathlib,shutil,argparse,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def build(skill,out):
    catalog=json.loads((ROOT/'registry/capabilities.json').read_text())
    ent=next((e for e in catalog['capabilities'] if e['skill']==skill),None)
    if not ent: raise ValueError('unknown-skill')
    out=pathlib.Path(out)
    if out.exists():shutil.rmtree(out)
    shutil.copytree(ROOT/'skills'/skill,out)
    for pid in ent['patternIds']:
        matches=list((ROOT/'patterns').glob(f'*/{pid}'))
        if len(matches)!=1: raise ValueError('missing-or-duplicate-pattern:'+pid)
        shutil.copytree(matches[0],out/'patterns'/pid)
    manifest={'skill':skill,'patterns':ent['patternIds'],'files':{}}
    for f in sorted(out.rglob('*')):
        if f.is_file():manifest['files'][str(f.relative_to(out))]=hashlib.sha256(f.read_bytes()).hexdigest()
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return out
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--skill',required=True);a.add_argument('--output');p=a.parse_args()
    print(build(p.skill,p.output or str(ROOT/'dist/standalone'/p.skill)))
