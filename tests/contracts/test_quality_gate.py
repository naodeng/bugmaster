import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from quality_gate import validate_coverage,validate_functional
class GateContractTests(unittest.TestCase):
    def test_missing_coverage_fails(self):
        self.assertIn('missing-unit-coverage-report',validate_coverage(None))
    def test_99_percent_fails_and_100_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'coverage.json'
            p.write_text(json.dumps({'totals':{'covered_lines':99,'num_statements':100}}))
            self.assertTrue(validate_coverage(p))
            p.write_text(json.dumps({'totals':{'covered_lines':100,'num_statements':100}}))
            self.assertEqual(validate_coverage(p),[])
    def test_equal_sixty_percent_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); ledger=p/'features.json'; matrix=p/'cases.json'
            fs=[{'id':str(i),'applicable':True,'status':'validated' if i<3 else 'planned','evidenceRefs':['e'] if i<3 else [],'oracleRef':'o' if i<3 else None,'critical':False} for i in range(5)]
            ledger.write_text(json.dumps({'frozen':True,'features':fs}));matrix.write_text(json.dumps({'cases':[]}))
            self.assertIn('functional-coverage-not-above-60-percent',validate_functional(ledger,matrix))
            fs[3]['status']='validated';fs[3]['evidenceRefs']=['e'];fs[3]['oracleRef']='o';ledger.write_text(json.dumps({'frozen':True,'features':fs}))
            self.assertNotIn('functional-coverage-not-above-60-percent',validate_functional(ledger,matrix))
    def test_core_requires_three_real_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);ledger=p/'features.json';matrix=p/'cases.json'
            ledger.write_text(json.dumps({'frozen':True,'features':[{'id':'F','applicable':True,'status':'validated','evidenceRefs':['a'],'oracleRef':'o','critical':True}]}))
            matrix.write_text(json.dumps({'cases':[]}))
            self.assertIn('missing-core-edge:F',validate_functional(ledger,matrix))
            cases=[{'caseId':k,'featureId':'F','kind':k,'result':'passed','evidenceRef':'E'+k,'oracleRef':'O'} for k in ('happy','negative','edge')]
            matrix.write_text(json.dumps({'cases':cases}))
            self.assertEqual(validate_functional(ledger,matrix),[])

class WorkflowCoverageGateTests(unittest.TestCase):
    def test_contract_workflow_compares_covered_lines_to_statements(self):
        workflow=(ROOT/'.github'/'workflows'/'contract.yml').read_text(encoding='utf-8')
        coverage_steps=[
            line.strip()
            for line in workflow.splitlines()
            if line.strip().startswith('- run: python -c') and 'coverage.json' in line
        ]

        self.assertEqual(len(coverage_steps),1)
        self.assertIn("['covered_lines']",coverage_steps[0])
        self.assertIn("['num_statements']",coverage_steps[0])
        self.assertNotIn('percent_covered_lines',coverage_steps[0])
