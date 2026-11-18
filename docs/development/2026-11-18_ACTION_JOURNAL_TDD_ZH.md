# W6 Action Journal 与 Safe Resume TDD 记录

**日期：** 2026-11-18
**Workstream：** W6 Session Persistence / W1 Action Contract
**验收义务：** `TDD-ACT-001`、`TDD-ACT-003`、`TDD-FS-002`
**风险：** 进程在副作用请求发出后崩溃，恢复时重复执行可能产生重复订单或其他重复写入。

## 约束与 Oracle

Oracle 取自 `docs/en/03-contracts.md` 的 Checkpoint invariant 及 `docs/zh-CN/03-contracts.md` 的“审批与恢复”：Action Intent 必须先于派发持久化；`prepared` 或 `dispatched` 后没有确定结果时，恢复必须核对，不能盲目重放；不能承诺外部系统 exactly-once，恢复不得重置预算或审批。

本切片实现本地 Action Journal 的持久追加、状态读取与恢复阻断。它不是 HTTP/Browser 工具网关，不认证人工身份、不证明证据真实，也不授予动作权限。Journal 中的审批、观察者及证据字段只是带来源的引用。哈希链用于发现未重算摘要的意外修改，不构成防篡改签名或真实性证明。

## 用例义务

| 类型 | 用例 | 预期 |
|---|---|---|
| Happy | 新进程读取已派发但没有结果的 Action | 状态为 `needs_reconciliation`，继续派发同一 Action 被拒绝 |
| Negative | 重复 Action ID、意图摘要不匹配或缺少 R2 审批引用 | Journal 拒绝追加，原有事件不变 |
| Negative | 未经权威只读核对就尝试结束未知 Action | 拒绝；不能把模型声明当成恢复事实 |
| Edge | 进程中断留下半行或事件摘要/前序摘要不匹配 | 打开失败关闭，不自动截断或重写日志 |
| Edge | 已核对为未执行 | 旧 Action 仍不可重放；后续需新 Action ID 与新授权 |

## RED

先增加了 `tests/unit/test_action_journal.py::test_restart_blocks_replaying_an_action_with_unknown_result`。第一次真实运行没有生产模块，按测试断言失败而非收集错误：

```text
python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v
Ran 1 test
FAILED (failures=1)
AssertionError: a restarted session must detect a dispatched action with no result and block replay until reconciliation
```

加入写前日志、状态转换、恢复与边界用例后，未实现模块的 RED 结果为 `Ran 12 tests / FAILED (failures=12)`，均由同一个明确的缺失能力断言失败。实现初版通过 12 项后，又新增一项反例：重启后的实例可接受未经核对的完成声明，RED 为 `AssertionError: JournalError not raised`。此测试证实旧实现缺少进程内派发来源约束。

事件 Schema 单独先写契约测试，RED 为 `Ran 2 tests / FAILED (failures=2)`，原因是 `schemas/event.schema.json` 尚不存在。

RFC3339 时间校验也先加了负例；格式错误、无时区和无效日历日期三种输入均产生 `JournalCorruptionError not raised`，作为时间校验缺失的 RED。

## GREEN / REFACTOR

- `bugmaster_core/action_journal.py` 仅接受新建 Action 的同一进程写入 `dispatched` 事件；重启后 `prepared`、`dispatched`、`outcome_unknown` 均进入 `needs_reconciliation`。重启后的 `record_outcome` 不能把没有结果的 Action 直接改成完成声明。
- R3 不可准备；R2 必须带 Action Approval 引用；相同 Action ID 不能复用；准备摘要与派发摘要必须一致。已知完成/失败需要结果引用。
- 未知结果只接受带 `authoritative-read-only` basis、观察引用和观察者引用的 reconciliation 记录。该记录自身不认证身份或观测真实性；`reconciled_not_executed` 后旧 ID 仍不能重放，必须新建 Action 并重新走授权。
- 每条事件追加后 `fsync`；首次建文件后同步目录；文件权限设为 `0600`；POSIX `flock` 序列化每次读取/追加；SHA-256 哈希链、序号和 Session ID 在读取时核验。截断、无效 JSON、无效时间、状态转换错误和摘要不匹配都失败关闭，不自动修复。
- 新增 `schemas/event.schema.json`，以实际日志验证四类事件；结构 Schema 不替代运行时的链完整性和状态转换校验。

修复了边界输入测试发现的两个问题：无效 reconciliation 测试最初遗漏必需的 `basis` 参数（测试错误，修正后继续）；列表型 Action ID 最初触发裸 `TypeError`（新增 RED 后统一转为 `JournalError`）。

## VERIFY

环境：macOS/POSIX；默认 Python 3.9.6；质量验证 Python 3.12；契约依赖 `jsonschema[format-nongpl]==4.26.0` 安装在 `/private/tmp/bugmaster-jsonschema`，Coverage 安装在 `/private/tmp/bugmaster-coverage`。

| 检查 | 命令 / 结果 |
|---|---|
| W6 定向单元 | `python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v`：28 项通过 |
| 全单元 | Python 3.12：55/55 通过；Python 3.9：55/55 通过 |
| 全契约 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v`：55/55 通过 |
| 核心代码覆盖 | `coverage run --branch --source=bugmaster_core -m unittest discover -s tests/unit`：423/423 语句、188/188 分支，100% / 100% |
| 品牌 / Catalog | `scripts/check_branding.py`、`scripts/validate_catalog.py`：PASS |
| Benchmark | `scripts/validate_benchmark.py`：结构 PASS，50 场景仍**未执行** |
| OpenAPI 示例 | `scripts/discover_openapi.py examples/openapi/orders.json --source-ref examples/openapi/orders.json`：输出 2 个有 JSON Pointer 来源的声明操作 |
| Release 门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-core-coverage.json`：预期 exit 1 / No-Go；单元覆盖报告有效，但功能清单未冻结、真实覆盖未超过 60%、核心三类执行证据缺失 |
| Diff 空白 | `git diff --check`：PASS |

当前 W6 工作树变更基于已推送基线 `cef3cb514c5502c62a3060c789649b3916aca2ae`；本轮 W6 代码尚未提交。100% 覆盖只针对维护范围 `bugmaster_core`，不覆盖独立 `scripts/`，也不是业务功能覆盖。

## 未通过或未执行项

这不是 BLK-03 完成证明：八个文件系统断点、长时间/多进程竞争、断电级持久性、Windows 锁实现尚未验证。Action Journal 尚未接入可信 HTTP/Browser 工具网关、不可变 Session Revision 或 Checkpoint；R2 仍由现有 gate fail-closed。没有调用外部目标，也没有真实订单 API 集成或功能覆盖证据。整体 Release 维持 No-Go。
