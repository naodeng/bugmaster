# W6 未知结果 Action 重放门禁 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6；`F-RECOVERY`；`TDD-ACT-010`

**风险：** R3；未知副作用恢复边界，独立 Security Reviewer 审查前不得合并。

**实现提交：** `91e79ee1857f7e986f97431d850a1e2b6faa0037`；草稿 PR [#9](https://github.com/naodeng/bugmaster/pull/9)，基于 PR #8 `codex/journal-path-resolution`，尚未合并。

## 需求与 Oracle

`scripts/validate_gates.py` 的 `can_replay()` 原先仅凭输入字典中 `reconcilerVerified=True`、`newAuthorizationValid=True` 和 `outcome=reconciled-not-executed` 返回可重放。仓库并未接入可信只读 reconciliation verifier 或当前授权门禁；调用方自报布尔值不是信任根，不能解锁未知外部副作用。Oracle 来自冻结的恢复不变量：未知结果必须经权威只读对账后才可能考虑重放；当前没有可信核验器，因此必须 fail-closed。

本切片只阻断当前辅助门禁的重放允许结果。它不实现 reconciliation、重新授权或安全恢复，也不声称任何外部动作已执行。

## RED

先新增 `test_self_asserted_reconciliation_cannot_authorize_replay`，向原函数传入全部为真的 `reconcilerVerified` 与 `newAuthorizationValid` 字段。实现前运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py' -k self_asserted_reconciliation_cannot_authorize_replay -v
```

测试失败：`AssertionError: True is not false`，明确证明普通字典中的自报字段当前可以开放重放。检查原测试后发现它还要求上述输入返回 True，与“没有可信核验器，不可盲目重放”的已冻结不变量冲突；在实现前移除该错误正向期望，并保留单独负例来约束 fail-closed 行为。

**2026-11-21 复核补充：** 原始 RED 记录未保存该次运行的 Git SHA。为补足可复现证据，在生产代码基线 `99fe47e808a01c6b9964a3da38a59a506de16bc9` 上重建仅含该合同测试变更的测试专用提交 `0c607ae10b9f2742a31ebc702ec9b82954c99de1`；测试文件内容取自实现提交 `91e79ee1857f7e986f97431d850a1e2b6faa0037`，未改动生产代码。环境为 macOS/POSIX、Python 3.12.16，工作目录 `/private/tmp/bugmaster-pr9-red`。运行上方命令的输出为 `Ran 1 test`、`FAILED (failures=1)`，断言仍为 `AssertionError: True is not false`。这是针对旧生产代码的补充重现，不冒充 2026-11-19 原始运行快照。

## GREEN / REFACTOR

`can_replay()` 在可信只读 verifier 和当前授权门禁接入前固定返回 False，并注明调用方布尔字段不能授权重放。没有添加模拟的可信状态、签名或 verifier 参数，也没有扩大到真实工具执行。

## VERIFY

环境：macOS；Python 3.12；契约测试依赖 `jsonschema[format-nongpl]==4.26.0` 位于 `/private/tmp`。

| 检查 | 命令 / 结果 |
|---|---|
| 重放门禁合同 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py'`：12/12 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：78/78 PASS |
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-replay-gate.coverage -m unittest discover -s tests/unit`：145/145 PASS |
| 核心语句/分支覆盖 | `/private/tmp/bugmaster-replay-gate-coverage.json`：`bugmaster_core` 1060/1060 语句、428/428 分支（100%）。该数字只描述已声明核心模块范围；新增 helper 的行为由合同测试直接验证 |
| Catalog / Benchmark / 品牌 / Diff | Catalog PASS；Benchmark 清单结构 PASS（50 场景未执行）；品牌扫描 PASS；`git diff --check` PASS |
| Release 门禁 | **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%、核心功能 Happy/Negative/Edge 执行证据缺失 |
| GitHub Actions | [Run 44457678961](https://github.com/naodeng/bugmaster/actions/runs/44457678961)：单元、契约、行覆盖、Catalog、Benchmark 结构与品牌步骤全部成功 |

## 后续缺口

可信只读 reconciliation verifier、当前授权真实性/修订绑定、预算与 Journal 消费对账、未知结果的权威状态来源以及安全恢复流程仍未实现。不能因为此 helper 当前全部拒绝重放，就把 W6 或 BLK-03 标记完成。Release 维持 **No-Go**。
