import json, pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_catalog import validate
from validate_gates import eligible_confirmed,can_dispatch,can_replay
from build_standalone import build
from validate_benchmark import validate as validate_benchmark
class CoreContractTests(unittest.TestCase):
    def test_catalog(self): self.assertEqual(validate(),[])
    def test_50_planned_cases_not_execution_claims(self):self.assertEqual(validate_benchmark(),[])
    def test_model_assertion_is_not_evidence(self):
        x=eligible_confirmed({'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed','environmentCheck':'passed','reviewRequired':False},[{'source':'model-analysis','provenanceVerified':True,'integrityVerified':True}],{'status':'validated','sourceRef':'req.md'})
        self.assertFalse(x['eligible']);self.assertIn('no-verifiable-execution',x['reasons'])
    def test_missing_oracle_blocks(self):
        x=eligible_confirmed({'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed','environmentCheck':'passed'},[{'source':'tool-execution','provenanceVerified':True,'integrityVerified':True}],{'status':'pending'})
        self.assertFalse(x['eligible'])
    def test_review_blocks(self):
        x=eligible_confirmed({'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed','environmentCheck':'passed','reviewRequired':True,'reviewStatus':'pending'},[{'source':'tool-execution','provenanceVerified':True,'integrityVerified':True}],{'status':'validated','sourceRef':'req.md'})
        self.assertFalse(x['eligible'])
    def test_r2_without_enforcement_denied(self):
        a={'risk':'R2','digest':'x','scopeRevision':1}
        p={'status':'approved','provenanceVerified':True,'actionDigest':'x','scopeRevision':1}
        self.assertFalse(can_dispatch(a,p,{'enforcement':'advisory'}))
        self.assertFalse(can_dispatch(a,p,{'enforcement':'enforced'}))
    def test_r2_self_asserted_fields_never_substitute_for_trusted_gateway(self):
        action={'risk':'R2','digest':'x','scopeRevision':1}
        approval={
            'status':'approved','provenanceVerified':True,'consumed':False,
            'actionDigest':'x','scopeRevision':1,
        }
        policy={'enforcement':'enforced','scopeValidated':True}
        self.assertFalse(can_dispatch(action,approval,policy))
    def test_r3_never_dispatches(self):self.assertFalse(can_dispatch({'risk':'R3'}, {}, {'scopeValidated':True}))
    def test_unknown_outcome_never_replays(self):
        self.assertFalse(can_replay({'outcome':'unknown','newAuthorizationValid':True}))
        self.assertFalse(can_replay({'outcome':'reconciled-not-executed','reconcilerVerified':True,'newAuthorizationValid':True}))
    def test_self_asserted_r0_and_r1_scope_never_dispatches(self):
        for risk in ('R0','R1'):
            self.assertFalse(can_dispatch({'risk':risk}, {}, {'scopeValidated':True}))
    def test_self_asserted_evidence_and_oracle_never_confirms_finding(self):
        result=eligible_confirmed(
            {'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed','environmentCheck':'passed','reviewRequired':False},
            [{'source':'tool-execution','provenanceVerified':True,'integrityVerified':True}],
            {'status':'validated','sourceRef':'req.md'},
        )
        self.assertFalse(result['eligible'])
        self.assertIn('trusted-evidence-verifier-unavailable',result['reasons'])
    def test_self_asserted_reconciliation_cannot_authorize_replay(self):
        action = {
            'outcome': 'reconciled-not-executed',
            'reconcilerVerified': True,
            'newAuthorizationValid': True,
        }
        self.assertFalse(can_replay(action))
    def test_standalone_contains_patterns(self):
        with tempfile.TemporaryDirectory() as d:
            p=build('discover-api-idempotency-defects',pathlib.Path(d)/'skill')
            self.assertTrue((p/'patterns/BP-API-002/pattern.json').is_file())
            self.assertTrue((p/'manifest.json').is_file())
    def test_bad_registry_ref_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);(p/'registry').mkdir();(p/'patterns').mkdir();(p/'skills').mkdir()
            (p/'registry/capabilities.json').write_text(json.dumps({'capabilities':[{'id':'c','skill':'nonexistent','patternIds':['INVALID']}]}))
            (p/'patterns/taxonomy.json').write_text(json.dumps({'categories':[]}))
            self.assertTrue(validate(p))
if __name__=='__main__':unittest.main()
