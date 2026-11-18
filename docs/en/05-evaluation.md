[中文版](../zh-CN/05-evaluation.md)

# Evaluation, Benchmark and Quality Gates

## Benchmark v0.1 manifest design

Exactly **50 planned evaluation cases**: 18 API/business, 12 browser/UI-to-API, 10 safety/approval, 6 fallback/recovery, 4 Oracle/evidence. These are scenario counts, **not 50 injected defects**. Each feature fault must have a correct variant and a faulty variant; ambiguous and environmental cases are scored against safe classification, not defect discovery.

Benchmark example: local isolated Order Demo (create/cancel/coupon/simulated refund, basic web UI). No production data or real payment endpoints. Independently verify correct implementation passes reference tests and faulty implementation fails as expected.

## Test input isolation

Agent sees tasks/specs and allowed tools only. Ground truth, fault injection manifest, scoring keys and private assertions are withheld through actual process/container permissions; folder labels are not enough.

## Ablation groups

- G0 base agent, no BugMaster;
- G1 Skills only;
- G2 Skills + Patterns, rule routing;
- G3 Full hybrid routing and Evidence Gates.

Use one external scorer for all groups, same host/model/budget/dataset setup where feasible. Document retries, randomization, repeated runs, variance and incomplete runs. Do not rank tool-less guided runs as if they had executed real tests.

## Metrics

`recall = distinct matched injected defects / evaluable injected defects`;
`precision = independently validated confirmed findings / all claimed confirmed findings`;
`false_confirmation_count`; Oracle validity; E3 evidence provenance; unauthorized action count; unknown-outcome unsafe replay count; time to first valid finding; tool calls and verified/estimated token cost.

Zero valid findings => cost per valid finding is undefined, not zero. Record numerator/denominator, run versions and confidence limits; initial 80% recall / 90% precision are provisional gates requiring baseline calibration, not proven results.

## CI tiers

- PR always: syntax, references, Schema, unit, package, security static gate, cheap fixture smoke.
- Targeted R2/R3: impacted behavioral Eval and negative-case controls.
- Release: fixed 50-case manifest and G0–G3 sample, both hosts, safe-resume fault injection, export/rollback test, human sign-off.
- Untrusted forks: do not expose production tokens or execute arbitrary fork scripts with privileged tokens.

## Immutable run record

Record run ID, dataset version and digest, source commit, bundle/skill/pattern/router revision, host/model if known, permissions, limits, raw tool actions, evidence refs, scorer version, false positives, failures and cost measurements. Never invent unknown model versions.
