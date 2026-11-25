# BugMaster · Bug 大师

**Evidence-driven Bug Discovery Skills for AI Agents**

[中文说明](README.zh-CN.md) · [Product requirements](PRODUCT.md) · [Architecture](docs/en/02-architecture.md) · [Contributing](CONTRIBUTING.md)

> **Engineering starter — NOT a released/verified bug-finding product.** No hosted runtime, dashboard or complete autonomous exploration has been verified yet.

BugMaster's target is a portable Agent Skills bundle for evidence-driven exploratory testing on **authorized** APIs and web applications. The current local implementation can create a source-linked inventory from an OpenAPI 3 JSON file. URL/Browser discovery, risk-driven execution, and autonomous end-to-end testing are not implemented or verified.

The W7 data layer now has versioned Candidate and Finding schemas and private local metadata persistence. Revisions retain identifiers, references, and digests, not raw Evidence bytes. The store has no Evidence Blob field or blob service. It does not detect raw or Base64-encoded evidence placed in free-text fields, so callers must keep evidence content out of those fields. This storage checks local structure and integrity only: it does not authenticate sources or reviewers, connect the records to a trusted workflow, or unlock Finding confirmation.

W1-02 adds `bugmaster_core.contract_binding.validate_contract_bindings()` to validate Scope, Action, and Approval schemas and their cross-record references. Its result reports consistency only; it does not authenticate approvals, authorize actions, or enable dispatch.

## Target installation (not verified)
```bash
# Repository exists; this host install path remains unverified until release checks pass.
npx skills add https://github.com/AI-Native-QA-Lab/bugmaster -g -a codex
```

## Developer bootstrap (now)
```bash
python3.12 -m pip install coverage==7.13.3 'jsonschema[format-nongpl]==4.26.0'
python3.12 -m unittest discover -s tests/unit -v
python3.12 -m unittest discover -s tests/contracts -v
python3.12 scripts/discover_openapi.py examples/openapi/orders.json --source-ref examples/openapi/orders.json
python3.12 scripts/validate_catalog.py
python3.12 scripts/validate_benchmark.py
```

There are 11 **candidate** Skills, 16 **candidate** Patterns and 50 **planned** Benchmark cases. Initial contract tests are not evidence of autonomous bug discovery.

## Guides
- [Product](PRODUCT.md) · [中文产品文档](PRODUCT.zh-CN.md)
- [Rules and Oracles](docs/en/11-bug-judgment-rules.md) · [中文](docs/zh-CN/11-bug-judgment-rules.md)
- [Surface / scope / reporting](docs/en/12-scope-surfaces-and-reporting.md) · [中文](docs/zh-CN/12-scope-surfaces-and-reporting.md)
- [TDD policy](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md) (Chinese)
- [Quality gate](docs/development/QUALITY_GATE_POLICY_ZH.md) (Chinese)
- [Engineering status](docs/development/IMPLEMENTATION_STATUS_ZH.md) (Chinese)

**[Complete engineering baseline / 完整最终开发规范（中文）](docs/development/BUGMASTER_FINAL_MASTER_SPEC_ZH.md)**

## Development with Codex
- [Codex implementation prompt (中文)](docs/development/CODEX_FULL_IMPLEMENTATION_PROMPT_ZH.md)
