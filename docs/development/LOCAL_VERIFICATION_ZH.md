# BugMaster 本地验证记录（2026-11-18）

## unit — PASS
```text
test_api_allowed (test_scope.ScopeTests.test_api_allowed) ... ok
test_future_mobile_denied (test_scope.ScopeTests.test_future_mobile_denied) ... ok
test_isolated_gate (test_scope.ScopeTests.test_isolated_gate) ... ok
test_mutating_blocked_without_per_action_gateway (test_scope.ScopeTests.test_mutating_blocked_without_per_action_gateway) ... ok
test_readonly_allowed (test_scope.ScopeTests.test_readonly_allowed) ... ok
test_unapproved_denied (test_scope.ScopeTests.test_unapproved_denied) ... ok
test_unrecognized_denied (test_scope.ScopeTests.test_unrecognized_denied) ... ok
test_web_allowed (test_scope.ScopeTests.test_web_allowed) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.000s

OK

```

## contracts — PASS
```text
test_50_planned_cases_not_execution_claims (test_contracts.CoreContractTests.test_50_planned_cases_not_execution_claims) ... ok
test_bad_registry_ref_rejected (test_contracts.CoreContractTests.test_bad_registry_ref_rejected) ... ok
test_catalog (test_contracts.CoreContractTests.test_catalog) ... ok
test_missing_oracle_blocks (test_contracts.CoreContractTests.test_missing_oracle_blocks) ... ok
test_model_assertion_is_not_evidence (test_contracts.CoreContractTests.test_model_assertion_is_not_evidence) ... ok
test_r2_without_enforcement_denied (test_contracts.CoreContractTests.test_r2_without_enforcement_denied) ... ok
test_r3_never_dispatches (test_contracts.CoreContractTests.test_r3_never_dispatches) ... ok
test_review_blocks (test_contracts.CoreContractTests.test_review_blocks) ... ok
test_standalone_contains_patterns (test_contracts.CoreContractTests.test_standalone_contains_patterns) ... ok
test_unknown_outcome_never_replays (test_contracts.CoreContractTests.test_unknown_outcome_never_replays) ... ok
test_99_percent_fails_and_100_passes (test_quality_gate.GateContractTests.test_99_percent_fails_and_100_passes) ... ok
test_core_requires_three_real_cases (test_quality_gate.GateContractTests.test_core_requires_three_real_cases) ... ok
test_equal_sixty_percent_fails (test_quality_gate.GateContractTests.test_equal_sixty_percent_fails) ... ok
test_missing_coverage_fails (test_quality_gate.GateContractTests.test_missing_coverage_fails) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.009s

OK

```

## catalog — PASS
```text
PASS catalog/registry

```

## benchmark_manifest — PASS
```text
PASS benchmark manifest structure (NOT executed)

```

## branding — PASS
```text
Brand scan: PASS

```

## unit_coverage — PASS
```text
{
  "covered_lines": 16,
  "num_statements": 16,
  "percent_covered": 100.0,
  "percent_covered_display": "100",
  "missing_lines": 0,
  "excluded_lines": 0,
  "percent_statements_covered": 100.0,
  "percent_statements_covered_display": "100"
}
```

## release_gate — FAIL / EXPECTED NO-GO
```text
NO-GO: unfrozen-or-empty-feature-inventory, functional-coverage-not-above-60-percent, missing-core-happy:F-SCOPE, missing-core-negative:F-SCOPE, missing-core-edge:F-SCOPE, missing-core-happy:F-AUTH, missing-core-negative:F-AUTH, missing-core-edge:F-AUTH, missing-core-happy:F-API, missing-core-negative:F-API, missing-core-edge:F-API, missing-core-happy:F-WEB, missing-core-negative:F-WEB, missing-core-edge:F-WEB, missing-core-happy:F-ORACLE, missing-core-negative:F-ORACLE, missing-core-edge:F-ORACLE, missing-core-happy:F-FINDING, missing-core-negative:F-FINDING, missing-core-edge:F-FINDING, missing-core-happy:F-REPORT, missing-core-negative:F-REPORT, missing-core-edge:F-REPORT, missing-core-happy:F-DEDUP, missing-core-negative:F-DEDUP, missing-core-edge:F-DEDUP, missing-core-happy:F-RECOVERY, missing-core-negative:F-RECOVERY, missing-core-edge:F-RECOVERY, missing-core-happy:F-ROUTING, missing-core-negative:F-ROUTING, missing-core-edge:F-ROUTING, missing-core-happy:F-PATTERN, missing-core-negative:F-PATTERN, missing-core-edge:F-PATTERN, missing-core-happy:F-HOST, missing-core-negative:F-HOST, missing-core-edge:F-HOST, missing-core-happy:F-DISTRIBUTION, missing-core-negative:F-DISTRIBUTION, missing-core-edge:F-DISTRIBUTION, missing-core-happy:F-BENCHMARK, missing-core-negative:F-BENCHMARK, missing-core-edge:F-BENCHMARK, missing-core-happy:F-RELEASE, missing-core-negative:F-RELEASE, missing-core-edge:F-RELEASE

```


单元行覆盖仅基于新增 `bugmaster_core` 初始代码范围，尚未覆盖所有生产脚本；不能宣称全项目 U100 达标。Release No-Go 是预期安全行为：没有真实功能及核心三类执行证据。
