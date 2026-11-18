# GitHub Actions 覆盖率断言修复 TDD 记录

**日期：** 2026-11-18
**工作流 / 门禁：** W11 开发反馈 CI；`GATE-U100`
**风险：** R2（覆盖率门禁准确性）
**状态：** 本地定向检查通过；GitHub PR Actions 运行 `44304069748` 在提交 `ef5bc1d37fc3775c6f38fc6ca0a1fde1326f4920` 上全步骤通过。PR #1 仍为草稿，等待独立质量审查，尚未合并。

## 需求与 Oracle

CI 必须以 Coverage JSON 的 `covered_lines` 和 `num_statements` 精确比较单元测试行覆盖率。Oracle 是 `AGENTS.md` 与 `docs/development/QUALITY_GATE_POLICY_ZH.md` 的 GATE-U100：分子等于分母才通过；不能依赖百分比字段或四舍五入。

## RED

用户提供的 [GitHub Actions 运行 44300382541](https://github.com/naodeng/bugmaster/actions/runs/44300382541) 对提交 `bcf7e0c` 的运行日志显示：单元 56/56、契约 63/63 均通过，随后覆盖率检查因读取不存在的 `totals.percent_covered_lines` 而以 `KeyError` 失败。

先在 `tests/contracts/test_quality_gate.py` 添加 `WorkflowCoverageGateTests.test_contract_workflow_compares_covered_lines_to_statements`，针对现有工作流断言实际字段运行：

```text
python3.12 -m unittest discover -s tests/contracts -p 'test_quality_gate.py' -v
```

结果：exit 1；5 项测试中 1 项按预期失败，旧工作流行缺少 `covered_lines`。测试选择器首次将 JSON 生成步骤和检查步骤都选中（2 行）；收窄到覆盖率检查命令后，RED 对准了错误字段。

## GREEN

将 `.github/workflows/contract.yml` 中的断言改为 `covered_lines == num_statements`。回归测试现在通过；对本地 Coverage JSON 使用同一比较表达式也通过。

## REFACTOR

工作流只保留精确分子/分母判断，不读取 Coverage 的显示百分比。未改变门禁阈值或业务覆盖要求。

## VERIFY

环境：macOS；Python 3.12；Coverage 7.13.3；jsonschema 4.26.0。

| 检查 | 命令 / 结果 |
|---|---|
| 配置定向回归 | `python3.12 -m unittest discover -s tests/contracts -p 'test_quality_gate.py' -v`：5/5 PASS |
| 全单元 | `python3.12 -m unittest discover -s tests/unit -v`：56/56 PASS |
| 全契约 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v`：64/64 PASS |
| CI 覆盖率步骤 | `covered_lines == num_statements`：432/432 PASS；`coverage report --fail-under=100`：PASS |
| 品牌 / Catalog | `scripts/check_branding.py`、`scripts/validate_catalog.py`：PASS |
| Benchmark Manifest | `scripts/validate_benchmark.py`：结构 PASS，场景未执行 |

远端验证：[GitHub Actions 运行 44304069748](https://github.com/naodeng/bugmaster/actions/runs/44304069748) 在修复提交 `ef5bc1d37fc3775c6f38fc6ca0a1fde1326f4920` 上成功；单测、契约、覆盖率精确比较、Catalog、Benchmark 结构及品牌步骤均通过。对应 [草稿 PR #1](https://github.com/naodeng/bugmaster/pull/1) 尚未合并，仍需独立质量审查。本次只修复 CI 覆盖率字段错误。完整 Release 仍为 No-Go，真实业务覆盖、核心三类执行证据、双宿主和独立审批尚未达标。
