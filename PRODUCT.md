# BugMaster — Product Requirements and Delivery Baseline

[中文版](PRODUCT.zh-CN.md) · [Engineering guide / 开发指南](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md)

## Mission
BugMaster is an independent evidence-driven Agent Skill Bundle for **autonomous, bounded exploratory bug discovery**: discover what to test, explore actual behavior, validate anomalies against project-specific Oracles, and report evidence-backed findings.

## User-facing journey
1. User provides a permitted site URL, an API endpoint/OpenAPI file, or a specific feature and test context.
2. Identify target and authorization boundaries (URL alone is not test authorization).
3. Read-only authorized discovery of routes, features, endpoints, schemas and relationships; record provenance and uncertainty.
4. Build a proposed Feature Inventory and risk-ranked scope with included/excluded/pending targets and explicit authorization for mutating actions.
5. Run bounded hypothesis → experiment → observation → update loops via host-provided API/Browser tools, only after permission gates.
6. Validate actual observations using applicable Oracle, execution provenance, reproduction/causal checks and review gates; never invent defects.
7. Export a Session Summary showing discovered scope, selected scope, executed feature coverage, blocked/untested areas, finding counts by surface and cross-surface deduplicated findings; link independent detailed Bug Reports and regression **recommendations only**.

## v0.1 product contract
- API: REST/JSON, OpenAPI with endpoint-first discovery, contract/boundary/idempotency/state and business logic.
- Web: Browser Basic (navigation, form interaction, observable browser-to-API effects and basic state consistency).
- Android/iOS: classification and future adapter hooks only; NO autonomous native testing claim in v0.1.
- 11 standalone Skills, 16 stable-ID Patterns, 50 **executable** Benchmark cases, Codex-first and Claude Code verified; full scope in one MVP release.
- Pattern finds hypotheses; Oracle establishes expected behavior; Validation Gate evaluates evidence. No Pattern alone is proof of a bug.
- Discovery surface (`api`, `web`, `android`, `ios`) is distinct from suspected responsibility (`frontend`, `api`, `backend`, `data`, `unknown`), defect type and root-cause verification status.
- Cross-surface matches are linked/deduplicated by an evidence-based canonical finding identity; do not count one defect twice.
- Tests of scope, permission, report accuracy and risk-based selection must include URL-only and OpenAPI-only tasks with no predeclared test features.
- All users' results stored local-first at `.bugmaster/`; do not rewrite/migrate arbitrary old data implicitly.

## Non-goals
- Independent always-running agent runtime, hosted product or web dashboard.
- Automated mobile device interaction in v0.1.
- Security scanning/penetration testing or unapproved targets.
- Automatic code fixes, test-code generation or PR submission in v0.1.
- Guaranteed defect discovery, or calling a scenario 'passed' just because no bug was observed.

## Success criteria and quality
- Genuine environment-gated autonomous exploration that adapts the plan based on real observations; correct and faulty baselines are both needed.
- Human can tell what was discovered, authorized, explored, not explored and why, tied to action/evidence IDs.
- A confirmed finding requires validated Oracle and >=E3 authentic evidence; suspected is separate.
- Unit line coverage 100%; functional coverage >60% of frozen obligation inventory; Happy/Negative/Edge real test evidence for every core feature.
- Both hosts, authorization and crash-recovery Spikes, governance, reproducible G0–G3 comparative Benchmark, final two-person release approval verified before public release.

## Delivery status (2026-11-18)
Architecture frozen, Q17 initial local engineering baseline exists. Current deliverable is an implementation starter; functional integration, host E2E, full Benchmarks and independent release approval are **NOT complete**. Public release remains No-Go.
