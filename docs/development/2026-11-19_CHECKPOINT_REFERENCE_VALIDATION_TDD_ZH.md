# W6 Checkpoint 跨存储引用校验 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6-02 Safe Resume；`F-RECOVERY`；`TDD-ACT-007`

**风险：** R3；合并前需要独立 Security Reviewer。

**实现提交：** `891885826ad4f392cecd6a21fa80d94ca00092e6`；草稿 PR [#6](https://github.com/naodeng/bugmaster/pull/6)，以 Journal 前缀 PR #5 的 `codex/journal-prefix-checkpoint` 为 base，尚未合并。

## Oracle 与范围

Checkpoint Schema 要求引用正整数 Session revision、Scope revision 和 Journal 序号/哈希锚点；Session revision 保存不可变 Scope history 与 Checkpoint 引用。恢复前必须校验交叉引用，但哈希不能单独证明数据来源或外部事件真实性。

本切片新增 `CheckpointReferenceValidator`，使用实际 CheckpointStore、SessionStore 和 ActionJournal，校验：同一 Session 与 Session/Checkpoint 共同根目录；Checkpoint 已持久化；其 Session revision 存在；Scope 锚点存在于该 revision；最新 Session revision 登记了该 Checkpoint；传入 Journal 对象包含匹配的有效前缀。

交叉引用单测为隔离本切片行为，向真实 Store 注入接受文档的测试 validator；Session/Checkpoint Schema 结构由现有契约测试另行校验。本轮没有声称这些交叉引用单测重新执行 JSON Schema 校验。

这里传入的 Journal 对象由调用方选择；当前 ActionJournal 没有持久化的 `journalId` 到路径映射，因此本验证器不能证明它就是 Session `journalId` 指向的文件。它也不做来源认证、当前授权核验、预算与 Journal 对账或恢复决策；不是 Safe Resume 或 BLK-03 完成证明。

## RED

先新增 11 个真实临时文件系统测试，覆盖有效非空/空 Journal 锚点、已登记和未登记 Checkpoint、缺失 Session revision、缺失 Scope 锚点、错误 Journal 前缀、跨 Session/存储根混用、Checkpoint 锚定旧 Session revision、Journal 损坏传播。

命令：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_checkpoint_reference_validator.py' -v
```

实现前 11/11 测试按预期失败：测试 helper 捕获模块缺失并报告 `CheckpointReferenceValidator` 不存在，而非导入异常或 fixture 错误。

GREEN 后检查发现读取 Session 锚定 revision 与最新登记之间，Session 目录可能被外部移除。针对这一边界增加第 12 个测试；先移除 `latest_session is None` 的保护，测试失败并指出泄漏了 `TypeError`，而非领域错误。随后补上 fail-closed 的 `CheckpointReferenceError` 检查。

## GREEN / REFACTOR

`CheckpointReferenceValidator.validate(checkpoint_id)` 先读取结构校验后的 Checkpoint，再读取其精确 Session revision，检查 Scope history 项；随后读取最新 Session revision，要求 `checkpointRefs` 登记该 ID，最后调用 `ActionJournal.matches_prefix`。缺失/不一致引用抛 `CheckpointReferenceError`；存储损坏和 Journal 链损坏的底层异常继续传播，阻止验证成功。

代码复查后保留直接、只读的跨存储顺序；不添加恢复动作、预算计算、授权旁路或额外抽象。定向测试最终 12/12 通过。

## VERIFY

环境：macOS/POSIX；Python 3.12；coverage.py 7.13.3；契约测试使用 `jsonschema[format-nongpl]==4.26.0`（测试依赖位于 `/private/tmp`，不是运行时依赖）。

| 检查 | 命令 / 结果 |
|---|---|
| 全单元与分支数据 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-reference-full.coverage -m unittest discover -s tests/unit`：128/128 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：77/77 PASS |
| 行/分支覆盖 | `/private/tmp/bugmaster-reference-full-coverage.json`：`bugmaster_core` 行 978/978、分支 406/406；`checkpoint_reference_validator.py` 行 30/30、分支 16/16，均 100% |
| Catalog / Benchmark / 品牌 | `scripts/validate_catalog.py` PASS；`scripts/validate_benchmark.py` 结构 PASS（场景未执行）；`scripts/check_branding.py` PASS |
| Release 门禁 | `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-reference-full-coverage.json`：No-Go，功能清单未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 缺少执行证据 |
| GitHub Actions | [Run 44450205158](https://github.com/naodeng/bugmaster/actions/runs/44450205158)：PR #6 实现提交全部 CI 步骤通过；CI 检查行覆盖，本地另测分支覆盖 |
| Diff 空白 | `git diff --check`：PASS |

## 未覆盖能力

尚未验证 Session `journalId` 与实际 Journal 文件路径的绑定、事件来源和外部事实真实性、当前授权、预算剩余量与 Journal 消费量对账、未知副作用的权威只读对账、恢复过程或八个文件系统崩溃断点。未运行 Windows、真实 API/Browser、双宿主或 50 个 Benchmark 场景。整体 Release 维持 **No-Go**；PR 为草稿，R3 变更需独立安全审查后再合并。
