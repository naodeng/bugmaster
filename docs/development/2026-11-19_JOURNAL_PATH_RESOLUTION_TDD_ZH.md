# W6 ActionJournal 确定性路径解析 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6；`F-RECOVERY`；`TDD-ACT-009`

**风险：** R3；独立 Security Reviewer 审查前不得合并。

**实现提交：** `4bc2dc0b18ed8523f51fb8f5c171437ea40cd12d`；PR [#8](https://github.com/naodeng/bugmaster/pull/8) 当前 open/ready，基于 PR #7 `codex/journal-id-binding`，尚未合并。

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

当前只解决 Journal 路径选择和本地文件类型/软链接保护。拥有相同本地权限的主体仍可改写 Journal 内容；尚无事件真实性、当前授权校验、预算与 Journal 消费对账、权威只读 reconciliation、恢复授权、工具层执行绑定或八断点崩溃注入。Windows、真实 API/Browser、Codex/Claude 双宿主和 50 个 Benchmark 场景均未验证。PR #8 当前 open/ready，合并仍需独立安全审查；整体 Release 仍为 **No-Go**。

## 交叉审核修复（PR #8）

### RED

- 根路径回归：先构造相对路径 Store，再切换工作目录；13 项定向测试中 1 项失败，证明 Store 保留相对路径并在新工作目录重新解析。
- 只读读取和历史缺失：Store 定向测试另有 2 项失败，分别证实 `open()` 会对已有目录重新 `chmod`，以及规范 Journal 文件缺失时会返回空 Journal；即使旁边存在旧的调用方自选路径日志，也没有错误提示。
- FIFO 路径：在临时 POSIX FIFO 上为读取、追加增加非阻塞断言；ActionJournal 41 项定向测试中 2 项因缺少 `O_NONBLOCK` 断言失败，防止测试本身挂住。

### GREEN / REFACTOR

- Store 构造时将根目录固定为绝对路径。
- 将用途明确分开：`initialize()` 负责显式创建新的规范空 Journal 和私有目录；`open()` 只读打开已存在的规范 Journal，不创建目录或改权限，并在目录/文件缺失时失败关闭。`ActionJournal` 的 `require_existing` 标记也会在检查与打开之间文件消失时拒绝空历史。没有自动迁移旧的调用方自选路径日志。
- Journal 读取使用非阻塞只读描述符、普通文件校验和共享锁；追加使用非阻塞读写描述符，并在 `fchmod` 或读事件之前拒绝 FIFO/目录等非普通文件。
- CheckpointReferenceValidator 的测试夹具改用显式 `initialize()` 写入测试 Journal；验证器继续调用只读 `open()`。

### VERIFY

实现提交：`8b9bfec5fff1252d58e450a71a30d6c175085580`。修复后 ActionJournal 41/41、ActionJournalStore 14/14、CheckpointReferenceValidator 15/15 单测 PASS；Event Schema 契约 2/2 PASS；`git diff --check` PASS。全单元、全契约和 100% 行/分支覆盖会在 PR #10 集成后重新运行。

## CI 覆盖门禁复查（2026-11-19）

PR #8 首次推送后 Actions Run [44486235780](https://github.com/naodeng/bugmaster/actions/runs/44486235780) 的单元与契约步骤通过，但精确行覆盖门禁失败：`covered_lines=1178`、`num_statements=1193`。失覆盖位于 Store 的错误处理分支（路径检查、Journal 文件创建/同步、存储根和中间目录类型）以及 Journal 读取的安全打开错误映射。此前的定向正向路径测试没有执行这些边界。

### RED / GREEN

- 在 PR #8 中补充 9 项边界行为测试：Journal 拒绝安全打开错误；Store 将文件路径检查、创建、文件同步和目录同步错误映射为领域错误；拒绝非普通文件、不可用根目录及软链接存储目录。
- 测试不修改生产实现。补齐后 ActionJournal/ActionJournalStore 定向测试 64/64 PASS；这些断言逐一命中原先未执行的处理路径。

### VERIFY

- 隔离克隆：`/private/tmp/bugmaster-review-fixes-20261119`；分支：`codex/journal-path-resolution`；Python 3.12；coverage.py 7.13.3；测试依赖位于 `/private/tmp/bugmaster-review-venv`。
- `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-pr8-final.coverage -m unittest discover -s tests/unit`：177/177 PASS。
- `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/contracts`：77/77 PASS。
- `coverage report --data-file=/private/tmp/bugmaster-pr8-final.coverage --include='bugmaster_core/*'`：1193/1193 语句、474/474 分支，均为 100%。
- 当前 PR #8 head 的 Actions 重跑待提交后确认；Release 仍为 No-Go。该门禁是单元代码行覆盖，不是业务功能覆盖。
