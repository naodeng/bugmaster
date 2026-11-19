# Action 待对账枚举与进程崩溃注入 TDD 记录

**日期：** 2026-11-19  
**Workstream / 义务：** W6 安全恢复；`F-RECOVERY` / `TDD-ACT-011`  
**风险：** R3（恢复诊断；不授权执行）  
**实现提交：** `8129838d0165115a78bf7435f1cdced7fa3de601`  
**崩溃注入测试提交：** `72157f7e9d8df73f324d8432555d16e3ac1ef988`
**PR：** [#10](https://github.com/naodeng/bugmaster/pull/10)，基于 Draft PR #9  
**状态：** 只读待对账 Action 枚举，以及 Journal/SessionStore/CheckpointStore 进程崩溃注入已本地和 Actions 验证；可信外部核验、恢复授权与真实 API/Browser 执行仍未实现。

## 需求与边界

W6 要求 Journal/安全恢复、未知副作用对账和崩溃故障注入。Journal 已有单个 Action 的恢复状态查询，但恢复进程没有 API 枚举所有尚待核查的 Action。SessionStore 与 CheckpointStore 使用临时文件及 hard link 发布不可变数据，本轮补充进程退出注入来核查这些发布阶段。Action 枚举必须来自完整校验后的本地 Journal 状态；本地日志、哈希链与对账引用都不能证明外部事实。

本切片新增 `ActionJournal.actions_needing_reconciliation()`，按 Action 首次写入顺序返回状态仍需对账的 ID 元组。它不验证外部副作用、不认证对账声明，也不授权重放；`can_replay()` 继续对所有请求 fail-closed。预算计数时点和真实观察器未在本次推断或实现。

## RED

先加入 9 个 Journal 子进程退出故障注入场景，覆盖准备/派发/结果事件的部分写入、事件写完但未同步、同步后退出、未知结果、未验证对账声明及已记录完成结果。定向运行 9/9 PASS，说明现有 Journal 对这些进程退出状态已经采取保守处理。

随后增加枚举接口行为测试，并在生产代码修改前运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_crash_recovery.py' -k recovery_can_enumerate -v
```

结果：按预期失败，`AttributeError: 'ActionJournal' object has no attribute 'actions_needing_reconciliation'`。

另新增 SessionStore 与 CheckpointStore 各 4 个崩溃注入点：临时文件部分写入、发布 hard link 前、发布后目录同步前、目录同步后临时文件清理前。首次执行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_store_crash_recovery.py' -v
```

结果 6/8；2 个 Checkpoint 场景的注入夹具先命中了首次创建 `checkpoints/` 子目录的同步，而不是记录发布后的同步。预先建立目标目录后重跑同一命令为 8/8 PASS；没有生产代码缺陷或放宽断言。

## GREEN

实现只读枚举：重读并验证本地 Journal，再用现有 `_needs_reconciliation` 状态判定返回 Action ID 元组。损坏日志仍抛出既有 `JournalCorruptionError`；不完整、不可信或恢复声明状态仍不会被转成可重放。SessionStore/CheckpointStore 的 8 个注入场景验证了已发布记录可完整读回，发布前中断不会暴露记录且允许重试；这部分只增加验证，没有修改既有存储实现。

## REFACTOR

保持最小 API，不添加外部核验器、批准状态或 Session 预算计算。同步英文和中文合同说明，注明 API 的诊断性质与失效关闭行为。总计 17 个进程崩溃场景使用子进程 `os._exit` 模拟应用进程突然退出，不等价于断电、内核崩溃、文件系统故障或 Windows 验证。

## VERIFY

环境：隔离工作树 `/Users/inaodeng/.codex/worktrees/session-contract/bugmaster`，分支 `codex/recovery-observation`；Python 3.12；`coverage.py` 和 `jsonschema` 位于 `/private/tmp`，未修改产品运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| RED 定向测试 | 上述枚举测试命令：因新接口缺失失败，exit 1 |
| Journal 崩溃 / 恢复定向测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_crash_recovery.py' -v`：11/11 PASS，包含 9 个进程退出场景 |
| Session / Checkpoint 崩溃定向测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_store_crash_recovery.py' -v`：8/8 PASS |
| Journal 定向测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v`：38/38 PASS |
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit`：164/164 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：78/78 PASS |
| 行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-recovery-observation-v2.coverage -m unittest discover -s tests/unit`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage json --data-file=/private/tmp/bugmaster-recovery-observation-v2.coverage -o /private/tmp/bugmaster-recovery-observation-v2-coverage.json`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage report --data-file=/private/tmp/bugmaster-recovery-observation-v2.coverage --include='bugmaster_core/*'`：`bugmaster_core` 1063/1063 语句、428/428 分支；`action_journal.py` 304/304 语句、140/140 分支 |
| Catalog / 品牌 / Benchmark | Catalog PASS；品牌扫描 PASS；Benchmark manifest 结构 PASS（50 个场景未执行） |
| 补丁检查 | `git diff --check`：PASS |
| Release Gate | `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-recovery-observation-v2-coverage.json`：按预期 NO-GO；业务功能清单未冻结、业务覆盖率未超过 60%，核心 Happy/Negative/Edge 缺实证 |
| GitHub Actions | [Run `44472202033`](https://github.com/naodeng/bugmaster/actions/runs/44472202033)，含实现提交 `8129838d0165115a78bf7435f1cdced7fa3de601` 与崩溃测试提交 `72157f7e9d8df73f324d8432555d16e3ac1ef988`：单元、契约、行覆盖率断言、Catalog、Benchmark manifest 和品牌检查全步骤成功 |

## 后续门禁

本切片只让恢复流程枚举本地尚待核查的 Action。它不提供 trusted read-only observer、授权网关、预算与 Journal 对账或安全恢复执行；这些能力仍需真实宿主/目标集成及独立 R3 Security Review。业务功能覆盖、核心三类真实执行证据、50 个 Benchmark、双宿主与 Release 均未因此通过。
