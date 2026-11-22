# AGENTS.md — BugMaster Engineering Instructions

[最终开发总规范（中文）](docs/development/BUGMASTER_FINAL_MASTER_SPEC_ZH.md) · [中文开发指南](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md) · [Product](PRODUCT.md) · [产品说明](PRODUCT.zh-CN.md)

## Source of truth
- Product and technical docs default to English, link their Chinese counterparts.
- **All development-process docs, plans, PR evidence, test records, and decisions are written in Chinese.**
- Q1–Q17 are frozen baseline decisions; no unapproved scope reduction. API-first + Browser Basic only; Android/iOS reserved, not executable MVP.
- 11 Skills, 16 Patterns and 50 real executable Benchmark cases in the single complete v0.1 release. Current candidate assets do NOT imply validation.
- All public branding, filesystem runtime directory, package, command, and repository references are **BugMaster** / `bugmaster`; no legacy brand aliases in release.
- Maintain stable Pattern IDs (e.g. BP-API-002), Finding IDs, and ADR/Q decision numbers. The 11 unreleased public Skill IDs have been migrated to the Discovery/Validation/Reporting naming baseline; never recreate earlier names.

## Strict TDD: mandatory in this order
1. **RED**: write one or more tests first; run them and capture failure evidence before production implementation. No test-less behavior change.
2. **GREEN**: implement the smallest safe change; run targeted tests with evidence.
3. **REFACTOR**: improve structure without behavior changes; rerun targeted and regression tests.
4. **VERIFY**: run all relevant tests, coverage and security gates; record traceable command, commit SHA, result, and environment in a Chinese development log/PR.
5. AI-authored tests require independent verification, meaningful assertions and false-positive checks; never weaken a test to force GREEN.

## Coverage and core case obligations
- **Unit test code line coverage = 100%** across the declared maintained production-code unit scope; no undocumented excludes. Branch coverage must be measured and reported separately; expand threshold with evidence, not misrepresent line coverage as branch coverage.
- **Business functional coverage >60%** of the approved, versioned feature/obligation inventory, measured by features with validated execution evidence, NOT code statements or planned tests. Exact 60% fails.
- Every core feature needs at least **one Happy Path, one Negative Case and one Edge Case**, with actual execution evidence; three scenarios per core feature minimum.
- Changing the denominator requires review; missing evidence counts as uncovered. No real execution = No-Go.
- Gate sources: `scripts/quality_gate.py`, `tests/quality/feature_coverage.json`, `tests/quality/core_case_matrix.json`, `docs/development/QUALITY_GATE_POLICY_ZH.md`.

## Trust & permission invariants
- URL/API input is only a candidate target, never permission for unsafe execution. Scope discovery and authorization are separate.
- Default R0 read-only; R2 requires enforced action-level approval; R3 forbidden by default. Prompt-only authorization is not enforcement.
- No confirmed defect without valid project Oracle + E3 evidence + provenance + causal checks + required human review.
- Unknown side effect cannot be replayed without reconciliation; never silently reset budgets or approvals.
- Do not claim real API/Browser tests, dual-host compatibility, security audit, 50 executed Eval scenarios or production release until verified.
- Do not generate/commit regression tests as part of Q9: output recommendations only.

## Pull requests
- Work on one implementation PR at a time. Finish its implementation, verification, review, and required approvals, then merge it before starting the next feature or opening its PR.
- Do not stack feature branches or PRs on unmerged PRs. Start the next feature from the latest merged base.
- If the active PR is blocked on CI, review, or approval, pause subsequent feature work and resolve the active PR first; report any human-only blocker instead of accumulating downstream PRs.
- Reference workstream W0–W11 and a Feature/Obligation ID.
- Show RED → GREEN → REFACTOR → VERIFY with links, test and coverage reports, and approvals in Chinese.
- For R2 require independent Quality Reviewer, for R3 independent Security Reviewer. Two distinct real people for final release RI + IRR; no self approval.
- Do not merge solely based on generated markdown or passing placeholder fixtures.

## Codex execution entry
- [Codex full project development instruction (Chinese)](docs/development/CODEX_FULL_IMPLEMENTATION_PROMPT_ZH.md)
