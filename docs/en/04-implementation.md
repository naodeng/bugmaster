[中文版](../zh-CN/04-implementation.md)

# Complete MVP Implementation Plan (Q14=A)

## Scope contract

Ship all: 11 canonical Skills, 16 Patterns, 50 benchmark cases, API and basic browser real paths, Codex and Claude Code verified core, Finding/Evidence/Oracle/Session contracts, recovery, export, regression recommendations and CI governance. **Do not release VS-01 alone as MVP**. A vertical slice is an internal integration test milestone; feature work may be parallelized but one MVP Go/No-Go covers the complete agreed scope.

## Workstream ownership / dependency graph

| Workstream | Tasks (TDD first) | Hard dependencies | Acceptance |
|---|---|---|---|
| W0 Architecture | freeze IDs, directory, decisions and blockers | none | reviewed baseline and open risks |
| W1 Contracts | write invalid/valid fixtures; JSON schemas; state transition tables; cross-ref validator | W0 | all contract tests green |
| W2 Portable skills | 11 SKILL.md + English/Chinese references; individual closure packaging | W1 | all clean standalone installs |
| W3 Knowledge | 16 Patterns; taxonomy, provenance, candidate/verified state and 1+1 positive/negative | W1 | no invalid stable patterns |
| W4 Routing | rule eligibility with unknown state, ranking, semantic contract, open hypothesis | W1,W3 | valid references, safe fallback |
| W5 Tools / safety | scope, approval, action gateway, API and Playwright adapter mappings | W1 | zero unauthorized fixture actions |
| W6 Persistence | action journal, immutable revisions, checkpoints, read-only reconciliation | W1,W5 | all crash points recover safely |
| W7 Findings | Oracle, E0-E4, evidence, human review, reports, bundle export | W1,W6 | correct/buggy/ambiguous test cases |
| W8 Regression | recommendation schema and Markdown (no code writes) | W7 | advice traceable, no source edits |
| W9 Benchmark | local Order Demo, correct/buggy variants, private truth, 50 cases | W1, W5 | reference tests detect faults |
| W10 Host verification | real Codex and Claude Code installation/API/browser flows | W2–W9 | target compatibility matrix verified |
| W11 Release | R0-R3 review, PR CI, Eval G0–G3, immutable manifests, rollback dry run | W1–W10 | one complete MVP Go/No-Go |

## Vertical Slice VS-01 (internal integration milestone)

Run a local isolated `POST /orders` idempotency case: user scope → `bug-discovery` → `discover-api-idempotency-defects` → canonical BP-API-002 → validated Oracle → trusted R2 action approval → actual API call → Action Journal → evidence capture → E0–E3 gates → immutable Finding revision → Markdown + redacted bundle → regression recommendation → checkpoint and safe resume. Include correct implementation (no confirmed defect), faulty duplicate side effect (validated finding), and timeout/unknown outcome (no blind replay). Demonstrate within the full MVP branch; do **not** label it the MVP release.

## Concrete acceptance IDs by workstream

- TDD-CON-001..020: schemas, ID uniqueness, states, ref integrity, approval binding.
- TDD-PAT-001..016: all canonical patterns valid and positive/negative linked.
- TDD-SKL-001..011: each Skill discoverable and standalone closures complete.
- TDD-SEC-001..012: out-of-scope, no approval, prompt injection, secret redaction.
- TDD-ACT-001..012: journal-before-dispatch; timeout, unknown side effects, expired approvals.
- TDD-FND-001..012: Oracle, E3 gate, reproduction, dedup, review binding.
- TDD-FS-001..008: staged write crash, journal truncation, pointer and digest recovery.
- TDD-HOST-001..030: both hosts discovery, execution, tool mapping, fallback.
- TDD-EVAL-001..050: benchmark tasks, control variants, scoring and isolation.

## Definition of Done

All planned deliverables present, mandatory deterministic tests green, fixed safety fixtures all pass, positive and negative real executions evidenced, staged/full evaluation executed, both host compatibility claims match real logs, independent scorer produces G0–G3 analysis, English/Chinese documentation reviewed, blocker register empty or resolved by explicitly reducing a **capability claim** only where baseline allows (no silent scope removal), user-data recovery verified. The complete scope may require revisiting Q14 if hard blockers make it infeasible; no unilateral redefinition.
