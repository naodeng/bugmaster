[中文版](../zh-CN/06-repository.md)

# Repository, Contribution and Bilingual Standards

## Target repository layout

```text
BugMaster/
├── README.md / README.zh-CN.md / AGENTS.md
├── CONTRIBUTING.md / CONTRIBUTING.zh-CN.md / SECURITY.md
├── CHANGELOG.md / RELEASE_POLICY.md / LICENSE
├── skills/                        # 11 canonical SKILL.md folders
├── patterns/                      # 16 canonical Pattern folders + catalog/taxonomy
├── registry/capabilities.json
├── routing/                       # deterministic helpers and semantic templates
├── policies/                      # scope/approval/action/routing/session
├── schemas/                       # versioned JSON Schemas
├── scripts/                       # deterministic validator/packager/export/resume
├── templates/                     # report and regression advice
├── adapters/codex/ / adapters/claude-code/
├── compatibility/                 # evidenced host matrix
├── benchmark/fixtures/order-demo/ # correct + faulty versions
├── benchmark/datasets/v0.1/       # 50 cases, versioned manifest
├── eval/                          # run records and rubrics
├── tests/unit/ contract/ integration/ security/ packaging/ recovery/
├── docs/en/ / docs/zh-CN/ / docs/development/
├── .github/workflows/ / .github/ISSUE_TEMPLATE/
└── dist/                           # generated, not edited
```

User project output resides in `.bugmaster/` (gitignored by default for private evidence), **not** in the source repository `benchmark/` directory. Keep runtime and development assets separate.

## Authoring rules

- `SKILL.md` canonical English executable text; Chinese `references/*.zh-CN.md` and bilingual examples. No duplicate independent Chinese SKILL.md logic trees.
- `Pattern` canonical `pattern.json`, English methodology and translated Chinese methodology; metadata shared, never fork IDs by language.
- File path and resource closure verified by installed-package tests; release `dist` built reproducibly, never hand-patched.
- Main work discussion/ADR process Chinese; user-facing project docs in paired English(default)/Chinese.
- Public code license to be selected before public release; reused third-party text must be separately licensed and attributed. Do not blindly copy third-party comparator project content.

## Contributions

Proposal -> uniqueness / license / source review -> RED test -> implementation -> GREEN -> behavioral and execution Eval -> impact regression -> security review -> maintainer acceptance -> release. Risk levels R0 docs, R1 additive, R2 semantic/behavior, R3 security or contract; highest risk wins. Community fork PRs run without secrets.

## AGENTS.md policy essentials

Never fabricate tool execution, evidence, human approval or benchmark results. Do not mutate production targets. Do not write regression test code under the Q9 workflow. Do not change canonical states or schema fields without tests. Preserve signed-off historical Finding/Evidence and revisions. No external QA Skill dependency. Explicitly mark capabilities that are guidance-only.
