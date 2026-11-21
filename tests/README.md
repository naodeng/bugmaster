# BugMaster test suites

[中文测试规范](../docs/development/QUALITY_GATE_POLICY_ZH.md) · [开发手册](../docs/development/DEVELOPMENT_PLAYBOOK_ZH.md)

`unit` is strictly measured for 100% of current maintained production Python line coverage in `bugmaster_core/` and `scripts/`; branch coverage is reported separately. `functional` requires >60% approved functionality coverage on actual run evidence. Every core feature needs Happy, Negative, Edge. `contracts`, `integration`, `e2e`, `security`, `eval` cannot be marked passed without real execution. Empty directories are not completed work.

JSON Schema contract tests use Python 3.12 with `jsonschema[format-nongpl]==4.26.0` so timestamp formats are actually checked; GitHub Actions pins this test-only dependency in `contract.yml`. Journal unit tests use real temporary files and cover write-ahead ordering, restart blocking, reconciliation, hash verification, and truncated-log fail-closed behavior.
