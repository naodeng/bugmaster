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
    def test_candidate_assessment_scenarios_refine_existing_50_cases(self):
        manifest=json.loads((ROOT/'benchmark/datasets/v0.1/manifest.json').read_text())
        self.assertEqual(len(manifest['cases']),50)
        cases={case['id']:case for case in manifest['cases']}
        expected={
            'BENCH-API-BUSINESS-01':'candidate-positive',
            'BENCH-API-BUSINESS-02':'counterevidence-normal-behavior',
            'BENCH-API-BUSINESS-03':'ambiguous-oracle-needs-review',
            'BENCH-API-BUSINESS-04':'model-disagrees-with-execution',
            'BENCH-API-BUSINESS-05':'false-negative-rejection-risk',
            'BENCH-API-BUSINESS-06':'human-review-feedback',
            'BENCH-BROWSER-UI-API-01':'cross-surface-deduplication',
        }
        for case_id,focus in expected.items():
            self.assertEqual(cases[case_id].get('assessmentFocus'),focus)
            self.assertEqual(cases[case_id]['status'],'planned')
            self.assertFalse(cases[case_id]['executionVerified'])
    def test_model_assertion_is_not_evidence(self):
        x=eligible_confirmed({'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed','environmentCheck':'passed','reviewRequired':False},[{'source':'model-analysis','provenanceVerified':True,'integrityVerified':True}],{'status':'validated','sourceRef':'req.md'})
        self.assertFalse(x['eligible']);self.assertIn('no-verifiable-execution',x['reasons'])
    def test_missing_oracle_blocks(self):
        x=eligible_confirmed({'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed','environmentCheck':'passed'},[{'source':'tool-execution','provenanceVerified':True,'integrityVerified':True}],{'status':'pending'})
        self.assertFalse(x['eligible'])
    def test_review_blocks(self):
        x=eligible_confirmed({'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed','environmentCheck':'passed','reviewRequired':True,'reviewStatus':'pending'},[{'source':'tool-execution','provenanceVerified':True,'integrityVerified':True}],{'status':'validated','sourceRef':'req.md'})
        self.assertFalse(x['eligible'])
    def test_candidate_assessment_cannot_be_confirmed(self):
        x=eligible_confirmed(
            {
                'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed',
                'environmentCheck':'passed','reviewRequired':False,
                'candidateAssessment':{'decision':'candidate','candidateId':'CF-001'},
            },
            [{'source':'tool-execution','provenanceVerified':True,'integrityVerified':True}],
            {'status':'validated','sourceRef':'req.md'},
        )
        self.assertFalse(x['eligible'])
        self.assertIn('candidate-assessment-not-confirmed-finding',x['reasons'])
    def test_any_candidate_assessment_field_blocks_confirmed_gate(self):
        for malformed_assessment in (None, 'candidate'):
            x=eligible_confirmed(
                {
                    'evidenceLevel':'E3','oracleViolation':True,'causalCheck':'passed',
                    'environmentCheck':'passed','reviewRequired':False,
                    'candidateAssessment':malformed_assessment,
                },
                [{'source':'tool-execution','provenanceVerified':True,'integrityVerified':True}],
                {'status':'validated','sourceRef':'req.md'},
            )
            self.assertFalse(x['eligible'])
            self.assertIn('candidate-assessment-not-confirmed-finding',x['reasons'])
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
