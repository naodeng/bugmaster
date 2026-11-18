# Contributing to BugMaster

[中文版 / 中文开发流程](CONTRIBUTING.zh-CN.md) · [Agent instructions](AGENTS.md)

All development-process records and pull request evidence must be in Chinese. Public product and technical references are English-first with Chinese links.

**Strict test-first TDD**: RED (failing test+evidence) → GREEN (minimum change) → REFACTOR (full regression) → VERIFY (quality gates and recorded evidence). A PR with no demonstrable RED evidence cannot claim TDD compliance.

Coverage: 100% unit line coverage, >60% validated business-feature coverage and Happy/Negative/Edge scenario evidence for every critical feature. Do not reduce test assertions or hide exclusions to make a gate pass.

Use `.github/pull_request_template.md` and [Chinese development playbook](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md). Follow Q15 independent risk review and Q16 two-person release approval.
