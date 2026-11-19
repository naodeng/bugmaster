# W6 ActionJournal 确定性路径解析 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6；`F-RECOVERY`；`TDD-ACT-009`

**风险：** R3；独立 Security Reviewer 审查前不得合并。

**实现提交：** `4bc2dc0b18ed8523f51fb8f5c171437ea40cd12d`；草稿 PR [#8](https://github.com/naodeng/bugmaster/pull/8)，基于 PR #7 `codex/journal-id-binding`，尚未合并。

## 需求、Oracle 与边界

Checkpoint 引用验证必须根据共同存储根、Session ID 及已验证 Session 中的 `journalId` 读取 Journal。调用方不能为同一身份任意挑选另一文件。路径映射固定为：

```text
<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl
```

确定性映射解决本地调用路径选择问题，不认证文件内容，也不证明 Journal 事件来源或外部事实真实性。文件仍可被拥有该本地用户权限的主体修改；本切片不增加授权、预算对账或安全恢复能力。

## RED

先新增 6 个 `ActionJournalStore` 单测，运行时 6/6 以明确的能力缺失断言失败：新模块尚不存在。再为 `CheckpointReferenceValidator` 新增任意路径负例，运行时以“需要 stable-ID Journal store”的断言失败。之后依据覆盖审计补充边界断言：

- 软链接 storage root 被接受时，测试失败：`ActionJournalStoreError not raised`。
- 移除根目录创建错误映射时，`NotADirectoryError` 泄漏，预期的领域错误未产生。
- 移除普通文件检查时，目录形式的 Journal 路径泄漏 `IsADirectoryError`，未产生 `JournalCorruptionError`。
- 移除 `CheckpointReferenceValidator` 的 Store 类型门禁时，任意 ActionJournal 路径导致 `AttributeError`，测试未得到所需的 `CheckpointReferenceError`。
- 新增根目录、Session ID、Journal ID 不可变断言时，3 个子断言均失败，因为公开字段可直接赋值。

以上每个后续边界保护均通过临时移除对应代码条件复现失败；恢复保护后再运行 GREEN。未以放宽断言解决失败。

## GREEN / REFACTOR

新增 `ActionJournalStore`，用 Session ID 与 Journal ID 的 SHA-256 计算私有目录和文件名；验证器要求传入该 Store、检查 Session ID 与根目录一致，并在读取最新 Session 后比较其 `journalId`，再通过 Store 打开规范路径核验 Checkpoint 的 Journal 前缀。Store 的 root、Session ID 和 Journal ID 作为只读属性公开。

Store 创建/检查私有目录，并拒绝根目录或中间目录软链接。ActionJournal 读取时使用平台支持的 `O_NOFOLLOW`，拒绝软链接目标和非普通文件；追加时也使用 `O_NOFOLLOW`。路径映射本身和哈希链仍不提供内容真实性。

## VERIFY

环境：macOS/POSIX；Python 3.12；coverage.py 7.13.3；契约测试使用 `jsonschema[format-nongpl]==4.26.0`。测试依赖位于 `/private/tmp`，不是产品运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| ActionJournalStore 定向单测 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_store.py'`：10/10 PASS |
| Checkpoint 引用定向单测 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_checkpoint_reference_validator.py'`：15/15 PASS |
| 全单元与分支数据 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-journal-path-final.coverage -m unittest discover -s tests/unit`：145/145 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：77/77 PASS |
| 行 / 分支覆盖 | `/private/tmp/bugmaster-journal-path-final-coverage.json`：`bugmaster_core` 1060/1060 语句、428/428 分支；`action_journal.py` 301/301 语句、140/140 分支；`action_journal_store.py` 59/59 语句、10/10 分支；`checkpoint_reference_validator.py` 37/37 语句、20/20 分支，全部 100% |
| Catalog / Benchmark / 品牌 / Diff | `scripts/validate_catalog.py` PASS；`scripts/validate_benchmark.py` 清单结构 PASS（场景未执行）；`scripts/check_branding.py` PASS；`git diff --check` PASS |
| Release 门禁 | **No-Go**：功能义务清单未冻结、真实业务覆盖率未超过 60%、所有核心功能的 Happy/Negative/Edge 执行证据缺失；50 个 Benchmark 场景未执行 |
| GitHub Actions | [Run 44455794738](https://github.com/naodeng/bugmaster/actions/runs/44455794738)：单元、契约、行覆盖、Catalog、Benchmark 结构与品牌步骤全部成功 |

AI 编写的路径断言针对真实临时文件系统和实际文件打开行为；没有声称真实 API/Browser 执行。

## 后续缺口

当前只解决 Journal 路径选择和本地文件类型/软链接保护。拥有相同本地权限的主体仍可改写 Journal 内容；尚无事件真实性、当前授权校验、预算与 Journal 消费对账、权威只读 reconciliation、恢复授权、工具层执行绑定或八断点崩溃注入。Windows、真实 API/Browser、Codex/Claude 双宿主和 50 个 Benchmark 场景均未验证。PR #8 保持草稿；整体 Release 仍为 **No-Go**。
