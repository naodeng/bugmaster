# Session Schema 实施 TDD 记录

**日期：** 2026-11-19  
**Workstream / 义务：** W1 数据契约、W6 安全恢复；`TDD-CON-014` / `F-RECOVERY` 的结构前置条件  
**风险：** R2（Session 保存授权引用与预算计数，错误契约可能影响恢复边界）  
**实现提交：** `aaa5564964c85f8d8a1f61fe693f11deea151eec`  
**状态：** Session 结构 Schema 与 9 项契约测试本地通过；PR #2 Actions Run `44438620887` 在提交 `cb7d5661b887ed746e87a7ee95fb73ad8a7c9052` 全步骤通过。不包含 Session 持久化或可信恢复逻辑；独立质量审查前不得合并。

## 需求与 Oracle

`docs/development/BUGMASTER_FINAL_MASTER_SPEC_ZH.md` 第 9 节要求 Session 保存 Action Journal、Scope 修订历史、权限、预算和断点；Q13 冻结 Session/Action Journal/Checkpoint/Safe Resume。`docs/en/03-contracts.md` 规定 Session 具有稳定 ID 和不可变 revision，并使用统一的 Session 生命周期状态。

本次只定义可验证的结构边界：记录 Session revision、规范状态、项目/宿主/环境引用、Scope 历史、绑定 Scope revision 的审批引用、预算上限和已用计数、Journal ID 与 Checkpoint 引用。Approval 引用不代表授权；预算计数需要由恢复验证器与 Scope/Journal 对账，Schema 不声明当前操作获批或可安全恢复。

## RED

先增加 `tests/contracts/test_session_schema.py`，覆盖有效 Session、无 Approval/Checkpoint 的初始状态、正整数 revision、规范状态、Scope revision、Approval 到 Scope revision 的绑定、非负预算计数、RFC3339 时间和拒绝模型自批字段。

执行：

```text
PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -p 'test_session_schema.py' -v
```

结果：exit 5。测试类 setup 因 `schemas/session.schema.json` 不存在而失败（0 项测试运行）；失败原因是待实现契约缺失。

## GREEN

新增 `schemas/session.schema.json`，用 JSON Schema Draft 2020-12 约束固定生命周期、必要 Session 字段、非空 Scope 历史、Approval 引用绑定、非负预算计数、可空的启动 Checkpoint 列表，以及成对出现的可选请求/时长预算上限与已用计数。

再次运行上述定向命令：9/9 PASS。Validator 同时执行 `Draft202012Validator.check_schema` 与 RFC3339 `FormatChecker`。

## REFACTOR

同步英文与中文 Schema 文档，明确 Session 引用只是结构信息。无生产 Python 代码改动，未新增运行时授权能力；预算已用值是否超过上限、Scope 引用的真实性、Journal/Session 一致性和恢复权限仍须后续可信验证器检查。

## VERIFY

环境：隔离工作树 `/Users/inaodeng/.codex/worktrees/session-contract/bugmaster`；Python 3.12；契约测试使用 `jsonschema[format-nongpl]==4.26.0`（`/private/tmp/bugmaster-jsonschema`）。

| 检查 | 命令 / 结果 |
|---|---|
| RED 定向测试 | 上述定向命令：Session Schema 缺失，exit 5，0 项运行 |
| GREEN 定向测试 | 上述定向命令：9/9 PASS |
| 全单元 | `python3.12 -m unittest discover -s tests/unit -v`：56/56 PASS |
| 全契约 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v`：73/73 PASS |
| 品牌 / Catalog / Benchmark | `scripts/check_branding.py`、`scripts/validate_catalog.py`：PASS；`scripts/validate_benchmark.py`：结构 PASS，场景未执行 |
| GitHub Actions | [Run `44438620887`](https://github.com/naodeng/bugmaster/actions/runs/44438620887)，提交 `cb7d5661b887ed746e87a7ee95fb73ad8a7c9052`：所有步骤 PASS，包括单测、契约、coverage JSON 精确行数断言、Catalog、Benchmark 结构和品牌扫描 |
| Release Gate | `scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-core-coverage.json`：按预期 NO-GO；功能清单未冻结、业务覆盖率未超过 60%、核心功能 Happy/Negative/Edge 证据缺失 |
| 本地 Coverage 工具 | 当前隔离环境没有安装 `coverage` 模块；未修改 Python 生产代码。基线远端 Run `44304702509` 曾对 `bugmaster_core` 执行精确行覆盖率检查并通过；本分支新契约的远端运行待核验 |

## 限制与后续门禁

Session Schema 不是 Session Store，也不是恢复门禁。它不证明审批来源、不比较预算计数与预算上限、不证明 Checkpoint/Journal 内容真实或完整，也不阻止运行时重置预算。需要 W6 持久化与可信恢复验证器实现后，再验证这些语义约束。业务功能覆盖和核心三类实际执行证据未因此增加；完整 Release 仍为 **No-Go**。该 R2 变更需要独立质量审查，禁止自审后合并。
