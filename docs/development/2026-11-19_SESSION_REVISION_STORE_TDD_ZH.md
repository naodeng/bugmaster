# W6 Session Revision 持久化 TDD 记录

**日期：** 2026-11-19  
**Workstream / 义务：** W6-01 Session Persistence；`F-RECOVERY`；`TDD-ACT-004`
**风险：** R2；合并前需要独立质量审查。  
**实现提交：** `7d2e1957dc417146ed9559e75f04e9c694a3ebbb`（初版存储提交 `2e2101015d0ab062ed7b9a7a0301ba729bb6679b`）；草稿 PR [#3](https://github.com/naodeng/bugmaster/pull/3)，叠加于 Session Schema PR #2，尚未合并。

## Oracle 与范围

沿用 `docs/zh-CN/03-contracts.md` 中 Session / Checkpoint 不可变引用和恢复前核对要求。每个 Session revision 单独、不可覆盖地持久化；写入需校验版本化 Session Schema；并发追加必须基于调用者读取的当前 revision；恢复读取必须拒绝损坏、缺号或互相矛盾的历史。

本切片不证明 Approval 来源真实，不把预算与 Action Journal 对账，不写 Checkpoint，不批准恢复，也不代表安全重放、exactly-once 或工具层授权已经完成。SessionStore 需要调用方提供 Schema validator；存储目录与锁使用 POSIX 行为，Windows 尚未验证。

## RED

起始时 `SessionStore` 模块不存在。首轮 19 项单元测试因缺少模块而失败；2 项 Session Schema 集成测试同样因缺少模块失败。之后补齐存储与历史转换用例。

权限审查发现初版会把调用方拥有的根目录权限从 `0750` 改成 `0700`。新增 `test_store_does_not_change_caller_owned_root_permissions` 后实测失败（实际 `0700`，期望保留 `0750`），证明实现改动了调用方目录权限。

读取历史的审查发现已存 revision 各自通过 Schema 校验仍不够：revision 1 的 `journalId` 被改写为另一个合法字符串后，`read_latest()` 未拒绝。新增 `test_read_fails_closed_when_persisted_history_breaks_immutable_identity`，先得到 `SessionCorruptionError not raised`，作为明确的 RED 证据。之后检查发现宽松测试 validator 下，重复或倒退的同一 Scope revision 会因数组长度增长而被当作新 Scope history；新增 `test_scope_history_rejects_duplicate_and_backward_revisions`，先得到 `SessionStoreError not raised`。

## GREEN / REFACTOR

- 新增 `bugmaster_core/session_store.py`。`create()` 写入 revision 1；`append_revision()` 要求预期 revision 与当前版本一致；`read_latest()` / `read_revision()` 逐个读取独立文件。
- Session ID 映射为 SHA-256 存储目录键，避免将未信任 ID 直接用作路径。Store 不更改调用方根目录权限；它创建的后代目录使用 `0700`，Session lock 与 revision 文件使用 `0600`。
- 使用单 Session POSIX `flock` 串行化读取/追加。写入临时文件后 `fsync`，再以同文件系统硬链接发布目标 revision，拒绝覆盖，并同步目录。读取检查文件类型/权限、规范 JSON、revision 序号、缺号、Schema、引用绑定和相邻 revision 的转换。
- revision 间固定 Schema/session/project/host/environment/创建时间/Journal 身份；Scope、Approval、Checkpoint 引用只允许追加；Scope revision 不可重复，且同一 `scopeId` 的 revision 必须递增；已用预算不可降低；新增预算计数要求新增 Scope history 且从零开始；预算上限变化要求新增 Scope history。
- 发现历史转换不一致时将其报告为 `SessionCorruptionError`。移除了写入代码中的不可达后置检查，减少对成功链接状态的重复维护。

## VERIFY

环境：macOS/POSIX；Python 3.12；coverage.py 7.13.3；契约测试使用 `jsonschema[format-nongpl]==4.26.0`（`/private/tmp/bugmaster-jsonschema`）。测试依赖仅位于 `/private/tmp`，不进入 BugMaster 运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| SessionStore 单元 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit -p 'test_session_store.py' -v`：36/36 PASS |
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-session-revision.coverage -m unittest discover -s tests/unit`：92/92 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v`：75/75 PASS |
| 行覆盖率 | `/private/tmp/bugmaster-session-revision-coverage.json`：`bugmaster_core` 752/752 行，100%；`session_store.py` 320/320 行，100% |
| 分支覆盖率 | `bugmaster_core` 324/324（100%）；`session_store.py` 130/130（100%）。分支结果与行覆盖分开报告 |
| Catalog / Benchmark / 品牌 | `scripts/validate_catalog.py` PASS；`scripts/validate_benchmark.py` 结构 PASS（场景未执行）；`scripts/check_branding.py` PASS |
| Release 门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-session-revision-coverage.json`：No-Go，原因是 Feature Inventory 未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 缺少执行证据 |
| GitHub Actions | [Run 44443870587](https://github.com/naodeng/bugmaster/actions/runs/44443870587)：最终代码提交 `7d2e1957dc417146ed9559e75f04e9c694a3ebbb`，结论 success、所有步骤通过。初版提交 `2e2101015d0ab062ed7b9a7a0301ba729bb6679b` 的 Run `44442603260` 也成功 |
| Diff 空白 | `git diff --check`：PASS |

## 未覆盖的产品能力

100% 单元行覆盖不是业务功能覆盖，也不是 BLK-03 完成证据。Checkpoint 持久化、崩溃断点注入、Windows 实现、进程/主机恢复、Approval 真实性验证、预算与 Journal 对账、可信只读核验及恢复授权仍未实现或未验证。未执行任何真实 API/Browser 目标测试、50 个 Benchmark 场景或双宿主验证。完整 Release 维持 **No-Go**；本 PR 不得在缺少独立 R2 质量审查时合并。
