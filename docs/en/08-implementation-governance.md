[中文版](../zh-CN/08-implementation-governance.md)

# Q15 Implementation Governance — Risk-based Dual Review

> ADR-015 · Q15=B · 2026-11-18 · Design only / not implemented. Based on Q14 implementation, review, contracts and release documents.

## Frozen scope

Q1–Q15: **A,A,B,B,B,B,B,B,A,B,B,B,B,A,B**. Q14=A means **one complete v0.1 MVP release**, including 11 canonical Skills, 16 Patterns, 50 benchmark scenarios, API-first + Browser Basic, Codex and Claude Code validation, Routing, approvals, Oracle/Evidence/Finding, safe resume, evidence bundles, regression **recommendations only**, and release gates. VS-01 is an internal integration checkpoint, never a reduced public MVP.

## Roles and independence

| Role | Responsibility | Independence |
|---|---|---|
| IM — Integrating Maintainer | Integration, dependency coordination, release-candidate preparation | Cannot self-approve an R3 change |
| QR — Domain/Quality Reviewer | Oracle, scenario correctness, TDD, Eval regression | R2 reviewer must differ from the author |
| SR — Independent Security Reviewer | R3 tool approval, credentials, sensitive data, recovery and release security | Must differ from author; review must be verifiable |
| EC — Evaluation Custodian | Ground-truth isolation, dataset freeze and scoring integrity | Keep answers inaccessible to the agent |
| RA — Release Approver | Final Go/No-Go based on recorded evidence | Cannot replace independent QR/SR approvals |

These are **roles to be staffed**, not claims that reviewers have been assigned. When an independent R3 reviewer is unavailable, development may proceed safely but public release stays **No-Go**. AI review is supplementary, never a human signature.

## W0–W11 ownership and acceptance

| Stream | Accountable | Reviewer | Dependencies | Required evidence |
|---|---|---|---|---|
| W0 Architecture | IM | QR/SR as appropriate | None | Frozen identifiers, state machines, layout, seven blockers |
| W1 Contracts | IM | QR; SR for approval/security | W0 | TDD-CON-001..020, schema/transition/reference checks |
| W2 Skills | IM | QR | W1 | All 11 Skills, bilingual resources, TDD-SKL-001..011, standalone installs |
| W3 Patterns | IM | QR+EC | W1 | All 16 patterns, taxonomy, provenance, positive/negative Eval |
| W4 Routing | IM | QR | W1,W3 | Three-valued filtering, hybrid selection, novel hypothesis, fallback |
| W5 Tools/Permissions | IM | SR | W1 | TDD-SEC-001..012, enforced approval and scope, BLK-02/06 |
| W6 Session | IM | QR+SR | W1,W5 | Journal/checkpoint/reconciliation, TDD-ACT and TDD-FS, BLK-03 |
| W7 Evidence/Finding | IM | QR+SR | W1,W6 | E0-E4, oracle, revisions, bundles, TDD-FND, BLK-04 |
| W8 Regression | IM | QR | W7 | Recommendation only, zero test-code writes |
| W9 Benchmark | EC | QR+SR | W1,W5 | Correct/faulty fixtures, 50 cases, private ground truth, G0–G3, BLK-05 |
| W10 Hosts | IM | QR+SR | W2–W9 | TDD-HOST-001..030, Codex/Claude Code evidence, BLK-01/06 |
| W11 Release | RA | QR+SR | W1–W10 | CI, full benchmark, manifests, rollback and Go/No-Go, BLK-07 |

Feature implementation is sequential, one PR at a time. Complete, verify, review, approve, and merge the active PR before starting the next feature; do not stack feature branches or open parallel implementation PRs. Workstream dependencies still define order and acceptance, but interface freeze is not permission to parallelize implementation. No intermediate partial MVP release is authorized. VS-01 covers a real order-idempotency API flow, risk-based human R2 approval, write-ahead action intent, authentic evidence, E3 plus separate gates, immutable findings, redacted report/bundle, recommendation only, and safe resume against correct, faulty and unknown-timeout variants.

## Blocking spikes (Q14 identifiers)

- **BLK-01:** Clean standalone installs in both hosts with complete Pattern/Schema closure and artifact digests.
- **BLK-02:** Unauthorized R2 actions, changed approval parameters and tool-bypass attempts are *actually blocked*, otherwise affected execution modes are disabled.
- **BLK-03:** Eight crash injection boundaries show valid revision pointers, no unsafe replay and no budget reset.
- **BLK-04:** Fabricated tool artifacts and model-reported execution cannot reach Confirmed.
- **BLK-05:** Ground truth cannot be read by an agent with the full permitted tool surface.
- **BLK-06:** Real browser/API golden paths and redirect/target constraints are verified per host or limitations are declared without falsely claiming support.
- **BLK-07:** VS-01 and a complete-scope RC dry run pass; no scope omission.

## TDD/Eval and release evidence

Keep Q14 identifier ranges: `TDD-CON-001..020`, `TDD-PAT-001..016`, `TDD-SKL-001..011`, `TDD-SEC-001..012`, `TDD-ACT-001..012`, `TDD-FND-001..012`, `TDD-FS-001..008`, `TDD-HOST-001..030`, `TDD-EVAL-001..050`. Reserve `TDD-ROUTE-*` and `TDD-REG-*` after deduplication. An ID reservation is **not** a passing test. Evidence records must link source commit, datasets, artifacts, run ID, tool environment, negative cases, approved reviewer and remaining failures. The 50 benchmark cases are 18 API/business, 12 Browser/UI-API, 10 safety/approval, 6 fallback/recovery and 4 Oracle/evidence—not 50 independent bugs.

## GitHub work items

Create 12 W0–W11 Epics. Each task specifies workstream, risk R0–R3, author/owner role, independent reviewer, dependencies, RED test IDs, acceptance artifacts, safety impact and DoD. Add seven BLK spike tasks. For R2 require a distinct human QR; for R3 require a distinct SR. Fork PR workflows cannot access secrets or privileged release tokens.

## Release decision

Status today: **Conditional Go for implementation / No-Go for public release**. RA consolidates release evidence; QR verifies quality/Eval, SR verifies R3 controls. Go requires the entire MVP scope, zero fixed-scenario unsafe actions/replays/approval reuse, valid Evidence Gates, correct/faulty benchmark and G0–G3 results, both host claims evidenced by run IDs, crash recovery, reproducible release artifacts, license, bilingual docs, rollback rehearsals and all mandatory human approvals. No critical gate can be bypassed through routine risk acceptance.

## Suggested Q16

**Release execution authorization and sign-off:** A — IM alone executes a release after all independent review gates pass; **B — two-person release authorization: RA initiates and a separate authorized reviewer verifies the final manifest and assets (recommended)**; C — automated publishing after green CI without a separate final human authorization. Q16 concerns release signing and authorization, and does **not** reopen Q15's independent R2/R3 review requirement.
