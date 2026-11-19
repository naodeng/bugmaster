# W6 Action Journal Checkpoint 前缀核验 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6-02 Safe Resume；`F-RECOVERY`；`TDD-ACT-006`

**风险：** R3；合并前需要独立 Security Reviewer。

**实现提交：** `b108b7c7f12d14a3f11d3a9f49fdd843afd2f8d1`；草稿 PR [#5](https://github.com/naodeng/bugmaster/pull/5)，以 CheckpointStore PR #4 的 `codex/checkpoint-store` 为 base，尚未合并。

## Oracle 与范围

Checkpoint Schema 用 `journalSequence` 和 `journalHeadHash` 锚定 append-only Journal 的前缀。对空前缀，序号必须为 `0` 且哈希为 `null`；非空前缀的头部哈希必须等于对应序号事件的 `entryHash`。Journal 仍须通过完整事件结构、状态转换、序号和哈希链校验。

本切片只增加 `ActionJournal.matches_prefix(sequence, head_hash)`，重读当前 Journal 并验证前缀锚点。它不把哈希解释为事件来源或事实真实性，不核验 Session/Scope 引用、审批、预算或 `journalId` 绑定，不恢复 Session、不重新授权，也不构成 Safe Resume、BLK-03 或 exactly-once 完成证据。

## RED

先在 `tests/unit/test_action_journal.py` 增加 5 个真实文件行为测试：已有有效前缀（包括追加后较早前缀仍有效）、空前缀、错误哈希/不存在序号/非法锚点、布尔/负数/非整数序号，以及完整 Journal 损坏时失败关闭。

执行命令：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v
```

实现前运行 34 项：原有 29 项通过；新增用例的 12 个断言因 `ActionJournal.matches_prefix` 尚不存在而按预期失败。失败经测试 helper 断言公开能力缺失，不是导入、fixture 或测试异常。

## GREEN / REFACTOR

在 `ActionJournal` 增加只读 `matches_prefix`：先验证序号类型和值，再通过现有 `_load_current()` 重放并验证完整日志；空序号只匹配 `null` 哈希；非空锚点要求合法 SHA-256、序号已存在并用常量时间比较核对 `entryHash`。非法序号抛 `JournalError`，锚点不匹配返回 `False`，持久化日志损坏抛 `JournalCorruptionError`。

复查后保留这一最小实现，无需增加第二条事件解析路径。GREEN 后定向 ActionJournal 测试 34/34 通过。

## VERIFY

环境：macOS/POSIX；Python 3.12；coverage.py 7.13.3；契约测试使用 `jsonschema[format-nongpl]==4.26.0`（测试依赖位于 `/private/tmp`，不是运行时依赖）。

| 检查 | 命令 / 结果 |
|---|---|
| 全单元与分支数据 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-prefix-full.coverage -m unittest discover -s tests/unit`：116/116 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v`：77/77 PASS |
| 行/分支覆盖 | `/private/tmp/bugmaster-prefix-full-coverage.json`：`bugmaster_core` 行 948/948、分支 390/390；`action_journal.py` 行 285/285、分支 132/132，均 100% |
| Catalog / Benchmark / 品牌 | `scripts/validate_catalog.py` PASS；`scripts/validate_benchmark.py` 结构 PASS（场景未执行）；`scripts/check_branding.py` PASS |
| Release 门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-prefix-full-coverage.json`：No-Go，功能清单未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 缺少执行证据 |
| GitHub Actions | [Run 44448388986](https://github.com/naodeng/bugmaster/actions/runs/44448388986)：PR #5 实现提交的 CI 全部步骤通过；CI 检查行覆盖，分支覆盖来自本地 coverage.py 记录 |
| Diff 空白 | `git diff --check`：PASS |

## 未覆盖能力

此方法只证明当前本地日志在结构、状态转换和哈希链层面包含指定前缀。日志哈希不能证明事件由可信来源产生或描述真实外部结果。尚未把 CheckpointStore、SessionStore 与正确 Journal 身份串接成可信恢复验证器；未对账预算、核验当前授权、执行恢复或崩溃断点注入，也未验证 Windows、真实 API/Browser、双宿主或 50 个 Benchmark 场景。整体 Release 维持 **No-Go**；PR 为草稿，R3 变更须独立安全审查后再合并。
