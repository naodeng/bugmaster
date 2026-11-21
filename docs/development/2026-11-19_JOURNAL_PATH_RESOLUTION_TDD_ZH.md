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
| Checkpoint 引用定向单测 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/unit -p 'test_checkpoint_reference_validator.py'`：15/15 PASS |
| 全单元与分支数据 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-journal-path-final.coverage -m unittest discover -s tests/unit`：145/145 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/contracts`：77/77 PASS |
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
- 测试修复提交：`af71416ba5eea6c2dca1869d4714063bda9ba225`。
- `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-pr8-final.coverage -m unittest discover -s tests/unit`：177/177 PASS。
- `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/contracts`：77/77 PASS。
- `coverage report --data-file=/private/tmp/bugmaster-pr8-final.coverage --include='bugmaster_core/*'`：1193/1193 语句、474/474 分支，均为 100%。
- 修复后 PR #8 Actions [Run 44487177211](https://github.com/naodeng/bugmaster/actions/runs/44487177211) 通过；单元与契约检查、行覆盖门禁及静态结构检查成功。Release 仍为 No-Go。该门禁是单元代码行覆盖，不是业务功能覆盖。

## 2026-11-20 基于当前 main 的集成复审

旧 PR #8 head `b14fac80d7dd8af3d321e781148e10ca7e495cb4` 的 base `81144137601b2a93a1e26293a25930bbe5b90bf1` 比当前 `main` 合并提交 `c7fcfca24856eeb981389785d09bb4b84ca4bce4` 落后 39 个提交。隔离候选已用当前 main 的 ActionJournal、SessionStore、CheckpointStore、验证器和测试作为基线，再叠加 W6-03；没有用 PR #8 旧副本覆盖 PR #7 已合并的目录描述符、单快照和完整 Journal 测试加固。以下证据来自 macOS/POSIX、Python 3.12 的集成候选。开始整合时，PR #8 远端 head 为 `b14fac8`，三个原 Codex 安全评论尚未解决。

### RED

- PR #8 独立安全审查报告了三个可复现问题：读取和追加未固定目录描述符，根路径祖先替换后可重定向 Journal；Store 返回的 `require_existing=True` 被追加逻辑忽略，缺失文件可被重新创建并重置序号；只读 `open()` 接受非私有目录和 `0666` 文件。对应回归断言现在覆盖根祖先/Session 目录替换、缺失 Journal 后追加，以及目录/文件所有者与权限。
- 覆盖审计初次发现 ActionJournal 新增描述符分支的 8 行与 3 个分支未执行。补充故障注入后，临时移除“元数据检查失败时关闭重复 FD”的修复，再运行 `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_store.py' -k closes_duplicate_when_descriptor_metadata_fails -v`，用例失败：`AssertionError: OSError not raised`，证明重复 FD 泄漏。

### GREEN / REFACTOR

- `ActionJournalStore` 逐级打开根目录祖先和规范 Journal 目录，使用 `O_NOFOLLOW` 与目录相对文件操作。祖先必须由 root/当前用户拥有；组/其他用户可写的祖先被拒绝，sticky 临时目录例外。Store 根目录、`journals`、Session 目录与 Journal 文件必须由当前用户拥有且权限私有。返回的 `ActionJournal` 将 Session 目录描述符固定在实例中，所有读取和追加均相对该描述符进行。
- `open()` 只读取已经存在的规范 Journal，不创建目录、不修复权限；若已打开目录或文件缺失、不安全或权限变化，则失败关闭。Store-backed 追加遇到已消失 Journal 时不会重建空历史。验证器要求 `ActionJournalStore`，在 CheckpointStore 共享锁和同一 Session 目录快照中读取引用，并从 Session `journalId` 确定规范 Journal 路径。
- 同一回归用例在修复后 PASS。另补充非普通 pinned descriptor、复制 FD 的元数据错误与关闭、pinned 目录权限变化和 append 打开错误的真实系统调用测试。

### Standards / Spec / Security 交叉复审新增问题

- Spec 与 Security 复审发现 `_resolved_root` 先 `realpath` 根目录父路径会隐藏任意祖先软链接；标准 macOS `/tmp`、`/var` 别名经证据确认必须保留。新增 `test_initialize_rejects_a_symlinked_storage_root_ancestor`，旧实现 RED：`ActionJournalStoreError not raised`。
- Security 复审发现目录项 `fsync` 失败后重试会把已存在目录误当成已同步，Journal 文件项也有相同问题。`test_initialize_retries_parent_sync_after_failed_root_sync` 和 `test_initialize_retries_parent_sync_after_failed_journal_file_sync` 在旧实现 RED：重试记录中分别缺少 root parent 和 Journal parent 的同步。
- Security 复审发现硬链接检查发生在 `fchmod` 之后。`test_initialize_rejects_a_hardlinked_file_without_changing_its_mode` 在旧实现 RED：外部链接权限从 `0644` 变为 `0600`，断言为 `384 != 420`。既有的非私有普通文件也需要在修改前拒绝。
- Security 复审发现 Checkpoint / Session 快照锁释放后再按路径打开 Journal 会跨越根目录替换。`test_validates_journal_from_the_pinned_session_root_snapshot` 在旧实现 RED：`canonical Journal storage path is missing`，因为验证器错误地走到替换后的根。
- Security 复审还确认 macOS 扩展 ACL 可独立于 `0700` / `0600` 模式位授予访问。新增文件和目录 ACL 负例，旧实现分别以 `JournalCorruptionError not raised`、`ActionJournalStoreError not raised` 失败。

### 交叉复审修复

- 根路径只对由 root 所有且目标固定为 `/private/tmp`、`/private/var` 的 macOS 系统别名做显式规范化；其余路径由 no-follow 打开逐级校验。Journal 根比较使用 Store 构造时固定的路径值，不在验证时重新解析可变路径。
- CheckpointReferenceValidator 先通过 `ActionJournalStore._open_root_directory(create=False)` 逐级验证根及其祖先，再将同一个根目录描述符传入 Checkpoint/Session 共享锁快照；SessionStore 复制该描述符，JournalStore 也从该快照描述符相对打开 Journal。Journal 随后固定 Session 目录描述符并验证前缀，避免不可信祖先及快照后的根目录替换重定向读取。
- Store writer 每次初始化/重试都会同步每一级目录项；Journal 文件初始化每次也同步其父目录。任一目录同步失败时初始化失败，后续重试重新同步已有目录项。
- 已有 Journal 必须是单链接、当前用户所有、私有模式且无扩展 ACL；不再修复既有文件权限。只有刚创建的文件才 `fchmod(0600)`。macOS ACL 查询错误失败关闭，任意扩展 ACL 被拒绝。
- Standards 复审还指出最终验证记录需要有可追溯的覆盖生成命令、RED 输出和精确提交 SHA。本地代码/测试快照 SHA 与运行证据记于下表；推送后仍需核对远端 head、Actions 与该 head 上的独立审查。启发式重复代码意见保留为 review note，不影响安全或规范门禁。
- 后续 Security 复审发现 Journal 已打开后，Session 目录可被追加扩展 ACL，而固定目录描述符后续操作只检查 owner/mode。新增真实 macOS ACL 与注入查询错误两项用例，RED 均为 `JournalCorruptionError not raised`；`ActionJournal._open_parent()` 现每次读取/追加前复查当前固定目录的 ACL，存在 ACL 或查询失败时拒绝操作。
- 后续 Security 复审发现验证器把 SessionStore 提供的根目录描述符直接交给 JournalStore；SessionStore 自身的祖先遍历虽 no-follow，但不校验可信 owner、写权限或扩展 ACL。新增组可写祖先和 macOS ACL 祖先用例，RED 均为 `ActionJournalStoreError not raised`。验证器现先通过 JournalStore 的可信祖先遍历打开根目录，再把同一根目录描述符传给 Checkpoint/Session 快照及 Journal；Session、Checkpoint 和 Journal 因此从同一 inode 快照读取。另加缺失根目录错误映射用例，移除映射时 RED 为原始 `FileNotFoundError` 泄漏。
- Spec 复审指出绝对路径遍历没有校验文件系统根目录自身的可信 owner/mode/ACL。新增根目录信任用例，旧实现 RED：`ActionJournalStoreError not raised`；现先检查 `/` 的 owner、写权限与扩展 ACL，再打开下级目录。
- Standards 复审指出 Session 已持久化后若 Journal 缺失，`initialize()` 会静默重建空日志。新增真实 SessionStore + 删除 Journal 用例，旧实现 RED：`JournalCorruptionError not raised`，且文件被重新创建；仅当 revision 数为零时才创建 Journal，有已提交 Session revision 时只打开既有 Journal，缺失时失败关闭。涉及快照的单元与契约夹具调整为先初始化 Journal、再持久化 Session。首次全契约运行暴露一个仍使用旧顺序的契约夹具，失败为 `FileNotFoundError: 'journals'`；调整顺序后契约 79/79 PASS。
- GATE-U100 审计确认随项目交付的七个 `scripts/` 工具也属于需单测的生产 Python。把统计范围扩展至 `bugmaster_core/` + `scripts/` 后，先运行的 354 项单元覆盖审计报告 1974/1991 行、695/702 分支；新增脚本 CLI、Standalone 构建、品牌扫描、质量门禁与 Finding/Replay/派发门禁行为测试，覆盖分母没有排除行或缩减。随后全量覆盖达到 1991/1991 行与 702/702 分支。

### VERIFY

| 检查 | 命令 / 结果 |
|---|---|
| ActionJournal + ActionJournalStore 定向单测 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/unit -p 'test_action_journal*.py'`：153/153 PASS |
| Checkpoint 引用定向单测 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/unit -p 'test_checkpoint_reference_validator.py'`：26/26 PASS |
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/unit`：358/358 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/contracts`：79/79 PASS |
| 独立安全套件 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/security`：1/1 PASS |
| 全单元覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr8-review8.coverage -m unittest discover -s tests/unit`：358/358 PASS |
| 覆盖 JSON | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m coverage json --data-file=/private/tmp/bugmaster-pr8-review8.coverage -o /private/tmp/bugmaster-pr8-review8.json`：PASS |
| 行覆盖 / 分支覆盖 | coverage.py 7.13.3，`bugmaster_core/` + `scripts/` 共 1991/1991 语句、702/702 分支，均为 100%；行与分支分开统计 |
| Catalog / Benchmark / 品牌 | `scripts/validate_catalog.py` PASS；`scripts/validate_benchmark.py` 清单结构 PASS（场景未执行）；`scripts/check_branding.py` PASS |
| Release 质量门禁 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr8-review8.json`：按预期 `NO-GO`；Feature Inventory 未冻结/为空、功能覆盖未超过 60%，且所有核心 Feature 缺少 Happy/Negative/Edge 实测记录 |
| 当前代码测试快照 | `28a3802d01e8e3df5f1e36e32ad1c832f7e30b51`；本表测试与覆盖命令在此提交执行。该 SHA 是本地可复核快照，尚非远端 PR head |
| 远端 CI 与最终审查 | **NOT_RUN**：候选尚未推送；推送后需在同一最终 head 确认 Actions、Standards、Spec 与 Security 审查 |
| Release 门禁 | **No-Go**：业务义务清单未冻结，真实业务覆盖未超过 60%，核心 Happy/Negative/Edge 和 50 个 Benchmark 场景没有实际执行证据 |

`/private/tmp/bugmaster-pr8-review8.coverage` 和 `/private/tmp/bugmaster-pr8-review8.json` 保存本机覆盖数据。测试依赖位于 `/private/tmp`，不是 BugMaster 运行时依赖。模型或本地测试结果不代表人工发布签署，也不证明 Journal 事件来源、事实真实性或安全恢复。

## 2026-11-21 Journal 初始化与 Session 发布并发复审

### RED

- Security 复审在代码/测试快照 `f75fef64b997d9586ec60c3344be36c634761bf5` 上发现初始化生命周期竞态：`initialize()` 检查 Session revision 后、创建 Journal 前，SessionStore 可能发布 revision，随后缺失 Journal 仍被重建。
- 将并发回归测试移植到该旧生产代码快照并执行：
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_store.py' -k serializes_journal_creation_with_session_publication -v`
  结果 **RED**：`AssertionError: True is not false`；Session 创建在 Journal 初始化暂停期间完成。
- 新增脚本工具测试中的“凭输入自述字段允许派发、确认 Finding 或重放”正向断言未构成 PR #8 的可信验证。依 Security 复审意见移除这些放行断言，只保留拒绝路径；可信 replay/reconciliation 与当前授权属于后续 W6-04 / PR #9 的范围，不在本 PR 声称实现。

### GREEN / REFACTOR

- `ActionJournalStore.initialize()` 现在以 SessionStore 的同一 per-Session 排他锁检查 revision 并创建 Journal，使 Journal 初始化与 Session revision 发布串行化。若 revision 已存在，缺失的 Journal 文件或存储路径映射为 `JournalCorruptionError` 并失败关闭；仅在 revision 数为零时才创建新 Journal。
- 为并发回归使用 Events 暂停 Journal 文件创建，再启动真实 `SessionStore.create()`；验证 Session 发布在 Journal 初始化释放锁前不能完成。新增缺失存储路径错误映射测试。
- 定向与全量单元测试通过。新脚本测试不依赖调用方自报 provenance/reconciliation/approval 布尔值作为成功依据。

### VERIFY

**代码/测试快照：** `470c180d620687020f067da5dc405e84e093bdfc`。该 SHA 是基于当前 `main` 集成基线的本地复核提交，不是 GitHub PR head；本节的全量检查均在该代码与测试树执行。

| 检查 | 命令 / 结果 |
|---|---|
| 全量单元与覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr8-review9.coverage -m unittest discover -s tests/unit`：361/361 PASS |
| 覆盖 JSON / 行与分支 | `coverage json --data-file=/private/tmp/bugmaster-pr8-review9.coverage -o /private/tmp/bugmaster-pr8-review9.json`：PASS；coverage.py 7.13.3，`bugmaster_core/` + `scripts/` 行 1,989/1,989、分支 706/706，分别为 100% |
| 契约 / 安全套件 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/contracts`：79/79 PASS；同环境 `-m unittest discover -s tests/security`：1/1 PASS |
| Catalog / Benchmark / 品牌 / 差异 | `scripts/validate_catalog.py` PASS；`scripts/validate_benchmark.py` 清单结构 PASS（场景未执行）；`scripts/check_branding.py` PASS；`git diff --check` PASS |
| Release 门禁 | 使用 `/private/tmp/bugmaster-pr8-review9.json` 运行 `scripts/quality_gate.py --mode release`：预期 **NO-GO**，Feature Inventory 未冻结、实测功能覆盖未超过 60%，核心 Happy/Negative/Edge 无证据；50 个 Benchmark 场景未执行 |
| GitHub CI 与最终复审 | **NOT_RUN**：本地候选尚未推送；最终远端 head 的 Actions 与 Standards、Spec、Security 复审仍待同一 head 上完成 |

覆盖 JSON：`/private/tmp/bugmaster-pr8-review9.json`。单元行/分支覆盖不代表业务功能覆盖。独立模型审查也不等同 R3 所要求的真实人工 Security Reviewer 签署。

## 2026-11-21 Session 锁与 ACL 副作用复审

本轮继续处理 PR #8 的三个旧 CodeX 线程，并落实新的 Security / Standards 复审意见。工作区为 `/private/tmp/bugmaster-pr8-review`；不修改主工作树。

### RED

- 安全复审发现 Session 初始化会在检查 ACL 前修复既有私有目录权限；既有锁文件也可能是指向外部文件的硬链接，旧逻辑会先 `fchmod(0600)` 再检查，产生仓库目录外的权限副作用。硬链接回归用例在修复前失败：外部文件从 `0644` 变成 `0600`，模式断言为 `384 != 420`。既有锁与目录 ACL 用例在修复前未拒绝 ACL。
- 并发复审发现原测试只等待线程启动并固定等待 100 ms；线程若尚未运行，测试可能误报串行化成功。该计时窗口不能证明 Session 写者实际尝试获取被 Journal 初始化持有的锁。
- Standards 复审指出 Journal Store 读取 SessionStore 的私有 storage 字典和 revision 读取 helper，会把跨组件协调绑定到实现细节。
- Security 与 Spec 复审进一步发现只读 Session / Checkpoint 快照未验证 `sessions`、Session 和 `revisions` 目录的权限及 ACL。第一轮 Session 回归针对修复前代码提交 `cab555dceeba41671383457454dda6c85c80645a`（最终记录见其后代 `a8208a2355151389c1decb86284eb47d6a8fda2b`），环境为 macOS/POSIX、Python 3.12。运行 `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/unit -p 'test_session_store.py' -k read_rejects -v`，两项新增用例 RED：宽松 Session 目录模式时 `SessionCorruptionError not raised`，模拟扩展 ACL 时 `failure is None`；筛选中的四个既有相关用例通过。
- 后续复审找到两个遗漏分支。测试专用提交 `25ecf31acb546f26556850357f1c38f929dcdb73`（基于生产代码 `aebfe11e30604d256054c4a17e587474fb566d5a`）保存了新增回归。Python 3.12 环境下，Checkpoint 命令 `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/unit -p 'test_checkpoint_store.py' -k read_rejects_checkpoint_directory -v` 中，`test_read_rejects_checkpoint_directory_acl_without_repair` 与 `test_read_rejects_checkpoint_directory_with_another_owner` RED，输出均为 `AssertionError: CheckpointCorruptionError not raised`；`test_read_rejects_checkpoint_directory_with_insecure_permissions` 与 `test_read_rejects_checkpoint_directory_with_owner_only_nondefault_mode` PASS。无锁空 revisions 命令 `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/unit -p 'test_session_store.py' -k empty_revisions -v` 中，`test_read_rejects_empty_revisions_directory_acl_without_lock` 与 `test_read_rejects_nonprivate_empty_revisions_directory_without_lock` RED，输出均为 `AssertionError: SessionCorruptionError not raised`；两个合法空目录用例 PASS。
- 后续 Security 复审发现 Session head、revision 与 Checkpoint 文件读取未检查文件 owner、ACL 和外部硬链接。测试专用提交 `df71c75cf21d8f15023ab630c848a72b6f969ff7`（父提交 `c3bfc5197830b4be091366b357a3a352ecc258c0`，生产代码为 `34247354af608d80abd41f81cbc67dc6c0b2bb83`）新增 9 个拒绝用例：`test_read_rejects_checkpoint_file_acl_without_repair`、`test_read_rejects_checkpoint_file_owned_by_another_user`、`test_read_rejects_checkpoint_file_hard_link_without_repair`、`test_read_rejects_session_head_acl`、`test_read_rejects_session_head_owned_by_another_user`、`test_read_rejects_session_head_hard_link`、`test_read_rejects_revision_file_acl`、`test_read_rejects_revision_file_owned_by_another_user`、`test_read_rejects_revision_file_hard_link`；另有 `test_read_accepts_checkpoint_file_linked_to_its_crash_temporary` 与 `test_read_accepts_revision_linked_to_its_crash_temporary` 两个正例。

  环境为 macOS/POSIX、Python 3.12.16。对旧实现运行：

  ```sh
  PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest \
    tests.unit.test_checkpoint_store.CheckpointStoreTests.test_read_rejects_checkpoint_file_acl_without_repair \
    tests.unit.test_checkpoint_store.CheckpointStoreTests.test_read_rejects_checkpoint_file_owned_by_another_user \
    tests.unit.test_checkpoint_store.CheckpointStoreTests.test_read_rejects_checkpoint_file_hard_link_without_repair \
    tests.unit.test_checkpoint_store.CheckpointStoreTests.test_read_accepts_checkpoint_file_linked_to_its_crash_temporary \
    tests.unit.test_session_store.SessionStoreTests.test_read_rejects_session_head_acl \
    tests.unit.test_session_store.SessionStoreTests.test_read_rejects_session_head_owned_by_another_user \
    tests.unit.test_session_store.SessionStoreTests.test_read_rejects_session_head_hard_link \
    tests.unit.test_session_store.SessionStoreTests.test_read_rejects_revision_file_acl \
    tests.unit.test_session_store.SessionStoreTests.test_read_rejects_revision_file_owned_by_another_user \
    tests.unit.test_session_store.SessionStoreTests.test_read_rejects_revision_file_hard_link \
    tests.unit.test_session_store.SessionStoreTests.test_read_accepts_revision_linked_to_its_crash_temporary
  ```

  输出为 `Ran 11 tests`、`FAILED (failures=9)`。Checkpoint 三个负例分别输出 `AssertionError: CheckpointCorruptionError not raised`；Session head/revision 六个负例分别输出 `AssertionError: SessionCorruptionError not raised`；两个崩溃临时硬链接正例 PASS。
- 测试专用提交 `b265d411d7976862b647a15a73f9fb3f7c40bab4`（父提交 `df71c75cf21d8f15023ab630c848a72b6f969ff7`；基线生产代码仍为 `34247354af608d80abd41f81cbc67dc6c0b2bb83`）又加入 `test_read_fails_closed_when_revision_acl_inspection_fails` 与 `test_read_fails_closed_when_revision_temporary_links_cannot_be_inspected`。环境为 macOS/POSIX、Python 3.12.16；在旧生产代码上运行 `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_session_store.SessionStoreTests.test_read_fails_closed_when_revision_acl_inspection_fails tests.unit.test_session_store.SessionStoreTests.test_read_fails_closed_when_revision_temporary_links_cannot_be_inspected`，输出为 `Ran 2 tests`、`FAILED (failures=2)`；模拟 ACL 查询与 pinned Session 目录扫描失败时，旧实现均未抛出 `SessionCorruptionError`。
- Spec 复核发现 Checkpoint 发布在 link 成功、临时项 unlink 前崩溃时，reader 会安全接受 `.checkpoint-*` 硬链接，但后续写入的临时文件清理白名单未包含该前缀。测试专用提交 `b633461cc39c7edaa1c7d4b222f7e460329dd5de`（父提交 `18d43c9133a829d254f6f1a12ec9dcb546172aea`，生产代码基线 `a18807e04c081849b6f3a1d8f81a7b11c2fec970`）新增 `test_session_write_cleans_interrupted_checkpoint_temporary_link`。环境为 macOS/POSIX、Python 3.12.16；旧代码 RED 命令为 `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_session_store.SessionStoreTests.test_session_write_cleans_interrupted_checkpoint_temporary_link`，输出 `Ran 1 test`、`FAILED (failures=1)`，断言 `AssertionError: True is not false`（下一次 Session 写入后临时链接仍存在）。
- 安全复核发现若进程在 Checkpoint 正式链接创建后、`checkpoints/` 目录同步前崩溃，下一次 Session 写入会删除临时链接并只同步 Session 目录，可能丢失未持久化的正式链接。测试专用提交 `2d97b4f10eee00adfb67183530f7d2e32870560a` 与 `638fc9cdf5898fcd09ac56698bf25f3422c23a03`（旧代码基线 `39352801aa7782030b8b739ff50515308d753903`）新增 `test_session_write_preserves_checkpoint_link_when_directory_sync_fails` 和 `test_session_write_preserves_revision_link_when_directory_sync_fails`。macOS/POSIX、Python 3.12.16 执行 `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_session_store.SessionStoreTests.test_session_write_preserves_checkpoint_link_when_directory_sync_fails tests.unit.test_session_store.SessionStoreTests.test_session_write_preserves_revision_link_when_directory_sync_fails`，输出 `Ran 2 tests`、`FAILED (failures=2)`：Checkpoint 路径报 `AssertionError: SessionStoreError not raised`；revision 路径报 `AssertionError: False is not true`，证明临时链接已在目标目录同步前被删除。
- 测试专用提交 `9589d519be2199fa651df831bf72c9d404e0c1cc`（父提交 `638fc9cdf5898fcd09ac56698bf25f3422c23a03`，旧代码基线仍为 `39352801aa7782030b8b739ff50515308d753903`）增加四个拒绝不确定链接状态的用例：`test_session_write_rejects_checkpoint_temp_without_checkpoint_directory`、`test_session_write_rejects_checkpoint_temp_without_canonical_link`、`test_session_write_rejects_linked_head_temporary`、`test_session_write_rejects_checkpoint_temp_with_extra_hard_link`。环境为 macOS/POSIX、Python 3.12.16；在旧代码基线上运行以下 RED 命令，输出 `Ran 4 tests`、`FAILED (failures=4)`，每项均为 `AssertionError: SessionStoreError not raised`：

  ```sh
  PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_without_checkpoint_directory \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_without_canonical_link \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_linked_head_temporary \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_with_extra_hard_link
  ```
- 安全复审随后发现两个 P2：恢复清理把任意同 inode 目标目录项（例如 `backup.json`）当成正式发布项；首次写入在 `link()` 成功、目标目录 `fsync()` 失败后会由 `finally` 删除唯一恢复链接。测试专用提交 `305334806a6069b983b4bb3865696f8e2fb1126d` 基于生产代码 `0152593968bfdb7a220f627826ee99590a164bba` 新增规范名称与首次发布同步失败用例。RED 命令：

  ```sh
  PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_with_noncanonical_name \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_revision_temp_with_noncanonical_name \
    tests.unit.test_session_store.SessionStoreTests.test_revision_first_publication_sync_failure_preserves_temporary_link \
    tests.unit.test_checkpoint_store.CheckpointStoreTests.test_first_publication_sync_failure_preserves_temporary_link
  ```

  macOS/POSIX、Python 3.12.16 输出 `Ran 4 tests`、`FAILED (failures=4)`：Checkpoint 非规范名称未抛错；revision 非规范名称下临时项被删除；revision 与 Checkpoint 首次发布失败后临时硬链接数均为 `0`（期望 `1`）。

### GREEN / REFACTOR

- 将 macOS 扩展 ACL descriptor 检查抽到 `bugmaster_core.filesystem_security`，由 Session 与 Action Journal 存储共用。Session 私有目录在权限修复前校验目录类型、所有者和 ACL；既有 `session.lock` 在加锁及权限变更前校验普通文件、当前用户、单链接、无组/其他/特殊权限位和无扩展 ACL。ACL 查询失败时失败关闭；仅本次创建的锁才执行 `fchmod(0600)`。新建目录失败时仅清理本次创建的目录项。
- `SessionStore.lock_revisions()` 作为公开锁上下文，在持有同一 Session 排他锁时提供已提交 revision 数。`ActionJournalStore.initialize()` 在该上下文内检查 Session 生命周期并创建/打开 Journal，避免首次 Session 发布与 Journal 初始化竞态，也不再读取 SessionStore 私有结构。
- 并发测试现在通过真实文件描述符尝试 `flock(LOCK_EX | LOCK_NB)`，必须观测到锁被阻塞，才继续断言发布尚未完成；不再依赖固定 sleep 时长。
- 新增外部硬链接权限保持、既有锁/目录 ACL、owner/mode/ACL 查询错误及目录创建清理故障测试。没有通过放宽断言处理失败。
- `_open_child_directory()` 对所有标记为私有的目录（包括 `create=False` 只读路径）统一验证目录类型、所有者、私有权限位及 ACL；只在 `create=True` 写路径允许权限修复并执行 `fchmod(0700)`。SessionStore 与 CheckpointStore 的手工旧格式测试夹具改为明确创建 `0700` 目录；Checkpoint FIFO 故障注入按文件 inode 限定，避免伪造 Session 目录元数据。
- `CheckpointStore._read_locked()` 现在也以 `private=True` 打开 Checkpoint 目录，保留既有精确 `0700` 模式检查并补上所有者/ACL 校验；SessionStore 在缺少锁且扫描空 `revisions/` 的恢复分支也传入 `private=True`，在判断空 Session 前拒绝不安全目录。Checkpoint owner/ACL 与空 revisions mode/ACL 四个新负例均由 RED 变为 GREEN。
- Session head、revision 与 Checkpoint 文件读取现在共用私有文件检查：只接受当前用户拥有、普通文件、精确 `0600` 模式且无扩展 ACL 的记录；ACL 查询失败会映射为领域损坏错误并 fail-closed。head 必须只有一个链接；revision/Checkpoint 允许唯一额外链接仅当 pinned Session 目录中存在同 inode、命名匹配本 Store 临时文件前缀的崩溃遗留项，其他外部硬链接、无法检查目录和不匹配链接均拒绝。两个合法崩溃临时硬链接正例通过，9 个文件级 owner/ACL/hardlink 负例以及 2 个元数据检查故障用例均由 RED 变为 GREEN。
- Session 临时文件清理规则纳入精确命名的 `.checkpoint-<32位小写十六进制>` 项；后续持有 Session 排他锁的写操作会删除崩溃遗留链接，同时保留 Checkpoint 规范记录。新增清理回归从 RED 转为 GREEN。
- Session 临时文件清理按文件内容推导规范目标名：revision 内容通过持久化 Session 校验后取 revision 序号；Checkpoint 校验 Session ID 与非空 checkpoint ID 后按 SHA-256 映射名称。临时文件以 no-follow 打开并校验 owner、模式、ACL、设备号、inode、链接数、大小、换行和规范 JSON；只对精确规范文件名执行 `stat(..., follow_symlinks=False)`，要求同设备/inode，再先同步目标目录并删除临时链接。目标缺失、非规范名称、inode 不匹配、额外链接、无法检查或同步失败都会保留临时项并中止写入。
- Revision 与 Checkpoint 写入器在成功 `link()` 后标记发布状态；目标目录 `fsync()` 失败时 `finally` 保留临时链接。之后的 Session 写入会先重试目标目录同步，再清理临时项；revision 测试继续执行第二次 append 并验证 revision 2 正常读回，Checkpoint 测试也验证恢复清理后记录仍可读。验证使用真实文件系统 hardlink 与注入的 `fsync` 错误，没有声称执行了断电测试。
- 覆盖率补充测试验证了被替换的临时 inode、链接计数变化、临时文件在检查期间增长、过大/截断/非法/非规范 JSON 及无效 Checkpoint 身份均 fail-closed；另验证规范目标路径的 inode 不匹配会保留临时项。此组补充只覆盖已有安全错误路径，没有新增产品行为。
- GREEN 定向命令（Python 3.12.16，macOS/POSIX）执行 Checkpoint/Session 临时清理、目录同步失败保留、缺失或非规范目标、额外硬链接、首发同步失败重试及上述失效文件路径；输出 `Ran 13 tests`、`OK`。

  ```sh
  PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_cleans_interrupted_checkpoint_temporary_link \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_preserves_checkpoint_link_when_directory_sync_fails \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_without_checkpoint_directory \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_without_canonical_link \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_with_noncanonical_name \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_revision_temp_with_noncanonical_name \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_linked_head_temporary \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_rejects_checkpoint_temp_with_extra_hard_link \
    tests.unit.test_session_store.SessionStoreTests.test_session_write_preserves_revision_link_when_directory_sync_fails \
    tests.unit.test_session_store.SessionStoreTests.test_revision_first_publication_sync_failure_preserves_temporary_link \
    tests.unit.test_checkpoint_store.CheckpointStoreTests.test_first_publication_sync_failure_preserves_temporary_link \
    tests.unit.test_session_store.SessionStoreTests.test_interrupted_checkpoint_publication_rejects_invalid_temporary_files \
    tests.unit.test_session_store.SessionStoreTests.test_interrupted_publication_rejects_canonical_path_inode_mismatch
  ```

### VERIFY

**代码/测试快照：** `abe4b8e025402d5c0ec9b96ff68eabbdbb964b08`。测试专用 RED 提交为 `df71c75cf21d8f15023ab630c848a72b6f969ff7`、`b265d411d7976862b647a15a73f9fb3f7c40bab4`、`b633461cc39c7edaa1c7d4b222f7e460329dd5de`、`2d97b4f10eee00adfb67183530f7d2e32870560a`、`638fc9cdf5898fcd09ac56698bf25f3422c23a03`、`9589d519be2199fa651df831bf72c9d404e0c1cc` 和 `305334806a6069b983b4bb3865696f8e2fb1126d`。

| 检查 | 命令 / 结果 |
|---|---|
| 全量单元与覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage erase --data-file=/private/tmp/bugmaster-pr8-review-final.coverage && PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr8-review-final.coverage -m unittest discover -s tests/unit`：399/399 PASS |
| 覆盖 JSON | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage json --data-file=/private/tmp/bugmaster-pr8-review-final.coverage -o /private/tmp/bugmaster-pr8-review-final.json`：PASS；2,141/2,141 行、770/770 分支，分别统计，均为 100% |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/contracts`：79/79 PASS |
| 独立安全套件 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/security`：1/1 PASS |
| Catalog / Benchmark / 品牌 / Diff | Python 3.12 执行 `scripts/validate_catalog.py`、`scripts/validate_benchmark.py`、`scripts/check_branding.py` 均 PASS；Benchmark 仅验证清单结构（场景未执行）；`git diff --check` PASS |
| Release 质量门禁 | `scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr8-review-final.json`：**NO-GO**；单元覆盖通过；阻断项仍为功能清单未冻结、实测功能覆盖未超过 60% 和所有核心 Feature 缺少 Happy/Negative/Edge 执行证据 |
| 远端 CI / 最终独立审查 | **NOT_RUN**：本地最终代码/文档尚未推送；R3 人工 Security Reviewer 签署也未获得，模型交叉审查不替代该签署 |

`/private/tmp/bugmaster-pr8-review-final.json` 是本机覆盖证据，不是业务功能覆盖。50 个 Benchmark 场景未执行，远端 CI 与同一最终 head 上的独立审查尚未完成，Release 仍为 **No-Go**。
