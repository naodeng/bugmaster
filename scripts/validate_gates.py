#!/usr/bin/env python3
"""Conservative gate: model assertions do not count as execution evidence."""
VALID_LEVELS={'E0','E1','E2','E3','E4'}
def eligible_confirmed(finding, evidences, oracle):
    reasons=[]
    if finding.get('evidenceLevel') not in {'E3','E4'}: reasons.append('evidence-level-below-E3')
    if oracle.get('status')!='validated' or not oracle.get('sourceRef'): reasons.append('oracle-not-validated')
    valid_tool_evidence=[e for e in evidences if e.get('source')=='tool-execution' and e.get('provenanceVerified') is True and e.get('integrityVerified') is True]
    if not valid_tool_evidence: reasons.append('no-verifiable-execution')
    if finding.get('oracleViolation') is not True: reasons.append('no-demonstrated-violation')
    if finding.get('causalCheck')!='passed': reasons.append('causal-check-not-passed')
    if finding.get('environmentCheck')!='passed': reasons.append('environment-check-not-passed')
    if finding.get('blockingContradictions'): reasons.append('unresolved-contradictions')
    if finding.get('reviewRequired') and finding.get('reviewStatus')!='approved': reasons.append('review-not-approved')
    return {'eligible':not reasons,'reasons':reasons}

def can_dispatch(action, approval, policy):
    if action.get('risk')=='R3':return False
    if action.get('risk')=='R2':
        # This repository has no trusted approval gateway yet. These dictionaries
        # may contain model- or user-asserted claims, so R2 stays fail-closed.
        return False
    return action.get('risk') in ('R0','R1') and policy.get('scopeValidated') is True

def can_replay(action):
    return action.get('outcome')=='reconciled-not-executed' and action.get('reconcilerVerified') is True and action.get('newAuthorizationValid') is True
