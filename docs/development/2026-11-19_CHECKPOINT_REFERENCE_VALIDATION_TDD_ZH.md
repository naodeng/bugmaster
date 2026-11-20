# W6 Checkpoint 跨存储引用校验 TDD 记录

**日期：** 2026-11-19

**复审更新：** 2026-11-20

**Workstream / 义务：** W6-02 Safe Resume；`F-RECOVERY`；`TDD-ACT-007`

**风险：** R3；独立 Security Reviewer 已复审当前本地候选，未发现 P1/P2。最终远端 head 和 Actions 尚待更新。

**初始实现提交：** `891885826ad4f392cecd6a21fa80d94ca00092e6`。PR [#6](https://github.com/naodeng/bugmaster/pull/6) 当前开放（非草稿）；旧 head `e5c443c` 仍以已合并 PR #5 的旧栈分支为 base。2026-11-20 复审修正后的最终提交 SHA 与 Actions 将在后续证据中补记。

## Oracle 与范围

Checkpoint Schema 要求引用正整数 Session revision、Scope revision 和 Journal 序号/哈希锚点；Session revision 保存不可变 Scope history 与 Checkpoint 引用。恢复前必须校验交叉引用，但哈希不能单独证明数据来源或外部事件真实性。

本切片新增 `CheckpointReferenceValidator`，使用实际 CheckpointStore、SessionStore 和 ActionJournal，校验：同一 Session 与 Session/Checkpoint 共同根目录；Checkpoint 已持久化；其 Session revision 存在；Scope 锚点存在于该 revision；最新 Session revision 登记了该 Checkpoint；传入 Journal 对象包含匹配的有效前缀。

交叉引用单测为隔离本切片行为，向真实 Store 注入接受文档的测试 validator；Session/Checkpoint Schema 结构由现有契约测试另行校验。本轮没有声称这些交叉引用单测重新执行 JSON Schema 校验。

这里传入的 Journal 对象由调用方选择；当前 ActionJournal 没有持久化的 `journalId` 到路径映射，因此本验证器不能证明它就是 Session `journalId` 指向的文件。它也不做来源认证、当前授权核验、预算与 Journal 对账或恢复决策；不是 Safe Resume 或 BLK-03 完成证明。

## RED

以下是 2026-11-19 原始 PR head 的历史记录；新复审回归的 RED/GREEN 证据见文末 2026-11-20 补记。

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

## 原始 VERIFY（2026-11-19，旧基线）

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

## 原始未覆盖能力（旧基线）

尚未验证 Session `journalId` 与实际 Journal 文件路径的绑定、事件来源和外部事实真实性、当前授权、预算剩余量与 Journal 消费量对账、未知副作用的权威只读对账、恢复过程或八个文件系统崩溃断点。未运行 Windows、真实 API/Browser、双宿主或 50 个 Benchmark 场景。整体 Release 维持 **No-Go**。

## 2026-11-20 独立复审修复与当前候选

复审以已合入 PR #5 的 `main`（`59945424f5528645afd7ba725801dfe769f48591`）为验证基线，不沿用旧 head `e5c443c` 的 144 单测、77 契约测试和旧覆盖数据。

### RED

1. **Session 快照混读：** 新增真实 POSIX 临时目录回归。测试在读取 Checkpoint 后将同一 Session ID 的目录 A 换成目录 B；A 的 Session 未登记 Checkpoint，B 登记了同 ID 但保存不同 Checkpoint。旧实现把 A 的 Checkpoint 与 B 的历史拼接后错误接受。命令：

   `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_checkpoint_reference_validator.py' -k mixed_from_different_session_snapshots -v`

   RED：1 项失败，输出 `AssertionError: CheckpointReferenceError not raised`。

2. **Schema 整值语义：** 新增真实 Checkpoint 与 Session Schema 的跨存储契约测试，Checkpoint 中 `sessionRevision=1.0`、`scopeRevision=1.0`、`journalSequence=0.0)。旧实现将 `1.0` 传给只接受 Python `int` 的 `SessionStore.read_revision`，实测以 `SessionStoreError: revision must be a positive integer` 失败。Journal 前缀 PR #5 已在当前 main 中把整值序号按 Schema 语义规范化。

3. **安全打开能力检查：** 新增从 Validator 入口临时移除 `os.O_NONBLOCK` 的测试。旧入口绕过 `CheckpointStore._locked`，未在打开锁前拒绝缺失能力，RED 暴露底层 `AttributeError`。

### GREEN / REFACTOR

- `CheckpointStore._read_locked(storage, checkpoint_id, filename)` 只在调用方持有共享 Session 锁时读取 Checkpoint。
- Validator 先验证 Checkpoint ID 并计算文件名，再通过 `CheckpointStore._locked(create_directories=False)` 做平台安全能力检查并获取一次锁；Checkpoint、锚定 Session revision、最新 Session revision 都使用同一份 storage 目录描述符读取。A/B 目录替换后只会读到 A 的 Checkpoint 与 A 的 Session 历史，随后因 A 未登记而拒绝。
- Schema 接受的整值浮点 `sessionRevision` 在调用 SessionStore 内部整数接口前规范化；分数、布尔和非正值仍失败关闭。
- 将原有“两个 Session 读取间目录被移除”的测试改成“验证前 Session revision 缺失”负例。新实现以一次完整、已校验的 Session 快照为准；目录在快照返回后变化不改变这次快照的含义。验证器不执行恢复，调用方仍须在任何恢复决策前重新校验状态。
- Validator 定向单测 17/17 PASS；Checkpoint Schema 定向契约测试 11/11 PASS。

### VERIFY

环境：macOS/POSIX；Python 3.12.16；coverage.py 7.13.3；契约依赖 `jsonschema[format-nongpl]==4.26.0` 位于 `/private/tmp`，不是运行时依赖。

| 检查 | 结果 |
|---|---|
| 全单元 | 257/257 PASS；`python3.12 -m unittest discover -s tests/unit -v` |
| 全契约 | 78/78 PASS；`PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v` |
| R3 安全套件 | 1/1 PASS；`python3.12 -m unittest discover -s tests/security -v` |
| 行/分支覆盖 | `bugmaster_core` 1,437/1,437 行、532/532 分支（100% / 100%）；JSON：`/private/tmp/bugmaster-pr6-main-coverage.json`。仅为 GATE-U100 初始样例范围 |
| Catalog / Benchmark / 品牌 | PASS；Benchmark 仅结构校验，50 个场景未执行 |
| Release 门禁 | **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 证据缺失 |
| 独立安全复审 | PASS；最新本地候选无 P1/P2 |
| GitHub Actions | 当前复审候选尚未推送，待最终 head 的 Actions 运行 |

本地检查不代表完整产品 Go，也不替代远端 CI、真实 API/Browser、双宿主或 50 场景 Eval。Session `journalId` 与 Journal 路径绑定、权威 Scope/事件真实性、当前授权和预算核验、未知副作用只读对账及恢复流程仍未实现；此切片不是 Safe Resume 或 BLK-03 完成证明。

