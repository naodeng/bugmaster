[中文版](../zh-CN/08-implementation-governance.md)

# Q15 Implementation Governance — Risk-based Code and Security Scans

> ADR-015 · Q15=D · owner amendment 2026-11-22. Codex scans PRs; the project owner reviews results and merges manually. Q16 release authorization remains separate.

## Frozen scope

Q1–Q15: **A,A,B,B,B,B,B,B,A,B,B,B,B,A,D**. Q14=A means **one complete v0.1 MVP release**, including 11 canonical Skills, 16 Patterns, 50 benchmark scenarios, API-first + Browser Basic, Codex and Claude Code validation, Routing, approvals, Oracle/Evidence/Finding, safe resume, evidence bundles, regression **recommendations only**, and release gates. VS-01 is an internal integration checkpoint, never a reduced public MVP. Q15 requires a Codex code scan for every PR and a security scan for R2/R3 changes. The project owner reviews results and merges manually; no independent human Q15 signature is required.

## Roles and responsibilities

| Role | Responsibility | Independence |
|---|---|---|
| Project owner | Reviews Q15 scan results, decides material trade-offs, and merges PRs manually | Q15 decision owner; no independent PR signature is required |
| Codex | Code scan on every PR; security scan for R2/R3 changes | Records findings and the scanned commit; cannot claim human approval |
| EC — Evaluation Custodian | Ground-truth isolation, dataset freeze and scoring integrity | Keep answers inaccessible to the agent |
| RI / IRR | Final Q16 release request and authorization | Two distinct real people approve the same frozen release manifest |

Q15 scan evidence is part of PR records. Missing scans or unresolved findings are brought to the project owner; they are not replaced by a fictitious human signature. Q16 still requires distinct RI and IRR identities for public release.

## W0–W11 ownership and acceptance

| Stream | Accountable | Q15 scans | Dependencies | Required evidence |
|---|---|---|---|---|
| W0 Architecture | Project owner | Code; security for R2/R3 | None | Frozen identifiers, state machines, layout, seven blockers |
| W1 Contracts | Project owner | Code; security for R2/R3 | W0 | TDD-CON-001..020, schema/transition/reference checks |
| W2 Skills | Project owner | Code; security for R2/R3 | W1 | All 11 Skills, bilingual resources, TDD-SKL-001..011, standalone installs |
| W3 Patterns | Project owner | Code; security for R2/R3 | W1 | All 16 patterns, taxonomy, provenance, positive/negative Eval |
| W4 Routing | Project owner | Code; security for R2/R3 | W1,W3 | Three-valued filtering, hybrid selection, novel hypothesis, fallback |
| W5 Tools/Permissions | Project owner | Code + security | W1 | TDD-SEC-001..012, enforced approval and scope, BLK-02/06 |
| W6 Session | Project owner | Code + security | W1,W5 | Journal/checkpoint/reconciliation, TDD-ACT and TDD-FS, BLK-03 |
| W7 Evidence/Finding | Project owner | Code + security | W1,W6 | E0-E4, oracle, revisions, bundles, TDD-FND, BLK-04 |
| W8 Regression | Project owner | Code; security for R2/R3 | W7 | Recommendation only, zero test-code writes |
| W9 Benchmark | EC | Code + security | W1,W5 | Correct/faulty fixtures, 50 cases, private ground truth, G0–G3, BLK-05 |
| W10 Hosts | Project owner | Code + security | W2–W9 | TDD-HOST-001..030, Codex/Claude Code evidence, BLK-01/06 |
| W11 Release | Project owner | Code + security | W1–W10 | CI, full benchmark, manifests, rollback and Go/No-Go, BLK-07 |

Feature implementation is sequential, one PR at a time. Complete and verify the active PR, run its Q15 scans, and let the project owner review results and merge manually before starting the next feature. Fix and rescan actionable findings; discuss material trade-offs with the owner. Do not auto-merge, stack feature branches or open parallel implementation PRs. Workstream dependencies still define order and acceptance, but interface freeze is not permission to parallelize implementation. No intermediate partial MVP release is authorized. VS-01 covers a real order-idempotency API flow, risk-based human R2 action approval, write-ahead action intent, authentic evidence, E3 plus separate gates, immutable findings, redacted report/bundle, recommendation only, and safe resume against correct, faulty and unknown-timeout variants.

## Blocking spikes (Q14 identifiers)

- **BLK-01:** Clean standalone installs in both hosts with complete Pattern/Schema closure and artifact digests.
- **BLK-02:** Unauthorized R2 actions, changed approval parameters and tool-bypass attempts are *actually blocked*, otherwise affected execution modes are disabled.
- **BLK-03:** Eight crash injection boundaries show valid revision pointers, no unsafe replay and no budget reset.
- **BLK-04:** Fabricated tool artifacts and model-reported execution cannot reach Confirmed.
- **BLK-05:** Ground truth cannot be read by an agent with the full permitted tool surface.
- **BLK-06:** Real browser/API golden paths and redirect/target constraints are verified per host or limitations are declared without falsely claiming support.
- **BLK-07:** VS-01 and a complete-scope RC dry run pass; no scope omission.

## TDD/Eval and release evidence

Keep Q14 identifier ranges: `TDD-CON-001..020`, `TDD-PAT-001..016`, `TDD-SKL-001..011`, `TDD-SEC-001..012`, `TDD-ACT-001..012`, `TDD-FND-001..012`, `TDD-FS-001..008`, `TDD-HOST-001..030`, `TDD-EVAL-001..050`. Reserve `TDD-ROUTE-*` and `TDD-REG-*` after deduplication. An ID reservation is **not** a passing test. Evidence records must link source commit, datasets, artifacts, run ID, tool environment, negative cases, applicable Q15 scan records, owner decision and remaining failures. The 50 benchmark cases are 18 API/business, 12 Browser/UI-API, 10 safety/approval, 6 fallback/recovery and 4 Oracle/evidence—not 50 independent bugs.

## GitHub work items

Create 12 W0–W11 Epics. Each task specifies workstream, risk R0–R3, owner, required code/security scan, dependencies, RED test IDs, acceptance artifacts, safety impact and DoD. Add seven BLK spike tasks. Every PR records a code scan; R2/R3 PRs also record a security scan. The project owner reviews findings and merges manually. Fork PR workflows cannot access secrets or privileged release tokens.

## Release decision

Status today: **Conditional Go for implementation / No-Go for public release**. The project owner consolidates release evidence; Q15 scan records must cover the PR heads. Q16 RI and a different IRR authorize the same fixed release manifest. Go requires the entire MVP scope, zero fixed-scenario unsafe actions/replays/approval reuse, valid Evidence Gates, correct/faulty benchmark and G0–G3 results, both host claims evidenced by run IDs, crash recovery, reproducible release artifacts, license, bilingual docs, rollback rehearsals and all mandatory gates. No critical gate can be bypassed through routine risk acceptance.

## Q16 release authorization

Q16=B remains in force: the release initiator and a different authorized real person approve the same fixed release manifest. Q16 governs public release authorization; it does not require independent human signatures on PRs and cannot be replaced by Q15 scans.
