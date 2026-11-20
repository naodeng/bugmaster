# W6 Action Journal Checkpoint 前缀核验 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6-02 Safe Resume；`F-RECOVERY`；`TDD-ACT-006`

**风险：** R3；独立 Security Reviewer 已复审当前本地候选，未发现 P1/P2；更新远端 head 后仍需通过 Actions。

**初始实现提交：** `b108b7c7f12d14a3f11d3a9f49fdd843afd2f8d1`；PR [#5](https://github.com/naodeng/bugmaster/pull/5) 当前开放。PR #4 已合入 `main`（merge `6c5d519`）；本地复审修复尚未推送，更新 PR 前会核对远端 head 并同步到 `main` 基线。

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

## 独立安全复核与追加 TDD

独立 Security Reviewer 对旧 head `fa0d2201` 发现四项可复现问题：重复 JSON 键可能被静默折叠；FIFO 读取会阻塞、悬空软链接会被视作空 Journal；`splitlines()` 会错误拆分字符串中的 U+2028/U+2029；深层 JSON、超长整数和未配对代理字符会泄漏底层异常。复核确认 `matches_prefix()` 不派发动作或放宽重放权限；上述风险都在其复用的持久化读取边界。

### RED

先增加真实文件回归测试，再运行 ActionJournal 定向套件。复现包括：后续事件的重复字段仍让早期锚点返回 `True`；FIFO 子进程在 2 秒内超时；悬空及有效软链接被跟随；合法 Unicode 分隔符写入后无法重读；目录、10,000 层 JSON、5,000 位整数与未配对代理字符未统一成 `JournalCorruptionError`。加固深层 JSON 用例后，Python 3.12 实际抛出 `RecursionError: maximum recursion depth exceeded while decoding a JSON array`；超长整数抛出 `ValueError: Exceeds the limit (4300 digits)`。

### GREEN / REFACTOR

- JSON 解码通过 `object_pairs_hook` 在所有对象层级拒绝重复键；仅按写入器使用的 LF 切分 JSONL。
- `_load_current()` 用 `O_NONBLOCK | O_NOFOLLOW` 打开路径，以 `fstat()` 拒绝 FIFO、目录和其他非普通文件；仅真正缺失的路径仍表示空 Journal。
- 将 JSON 解码和哈希规范编码中的 `ValueError`、`RecursionError` 与 Unicode 编码错误包装为带 `__cause__` 的 `JournalCorruptionError`。
- 定向 ActionJournal 测试 43/43 PASS，覆盖首轮四项复核发现。

### 第二轮安全 / 契约复审

复核修复后，Security Reviewer 又发现：追加路径仍可能跟随实例创建后的末级软链接并修改目标文件权限；父目录经祖先软链接重定向后，实例可能切换到另一份 Journal。Spec Reviewer 还发现 JSON Schema `integer` 接受 `1.0`，但 matcher 原先只接受 Python `int`，导致结构有效的 Checkpoint 无法核验。

先补四个回归行为，再执行：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v
```

RED 结果：47 项中 3 项失败、1 项报错；分别观察到追加后目标文件权限变成 `0600`、父目录删除仍返回空锚点、父级软链接重定向后 matcher 接受了另一份日志，以及 `1.0` 被 `JournalError` 拒绝。

GREEN 将 Journal 父目录的 `(st_dev, st_ino)` 固定在实例上，并使用 `dir_fd` 打开日志；追加采用 `O_NOFOLLOW | O_NONBLOCK`，先检查普通文件再改权限。父目录消失或身份变化时失败关闭。`matches_prefix()` 将 Schema 允许的有限整值浮点数规范化为 Python 整数；分数、布尔和负数仍拒绝。定向 ActionJournal 测试 47/47 PASS。

### 第三轮安全复审：目录持久化与日志身份

独立 Security Reviewer 发现三个问题：第一次创建 Journal 子目录后父目录 `fsync` 失败，另一个新实例可能把它误当作已持久化；同一实例已观察到的日志被删除后会被视作空 Journal 并从序号 1 重建；硬链接通过普通文件检查后可能在解析失败前把其他文件权限改成 `0600`。

先补四个真实文件系统回归：父目录同步失败后重建实例必须重新同步祖先、已观察日志被删除或替换必须失败关闭、硬链接目标的权限与内容不变。RED 复现四项失败。GREEN 将路径锚定到根目录并固定已观察目录组件身份；每个实例首次追加时同步完整目录链，失败后可重试；记录并核对日志文件 `(st_dev, st_ino)`，删除或替换已观察文件时拒绝重建；在任何权限修改前拒绝多链接文件。读写描述符在解锁失败时也保证关闭。定向 ActionJournal 套件随后通过。

### 第四轮安全复审：锁等待中的目录项变化

独立复审发现日志可能在打开描述符后、取得 `flock(LOCK_EX)` 前被替换，或在等待期间新增硬链接。先新增三项测试并确认均 RED：读取旧 inode 后仍接受锚点、追加写入已从路径移走的 inode、等待锁时新增长链接后仍写入。

GREEN 在获取锁后用固定 `parent_fd` 检查当前目录项仍是已打开的普通文件、inode 相同且链接数为 1；读完后和追加 `fsync` 后再核对。针对读/写期间替换路径和等待期间新增硬链接的三个用例均通过。

### 第五轮安全复审：父目录被替换

最后一轮独立安全复审指出，日志文件 inode 检查不能检测锁等待期间整个父目录被移走、同名新目录被创建。先增加两项确定性测试，分别在读取和追加等待锁时移动真实父目录；两项均按预期 RED，旧实现会从已脱离配置路径的目录读取或写入。

GREEN 在锁后和读写返回前重新遍历固定目录身份链，并比较当前路径父目录 inode 与操作持有的 `parent_fd`。两条回归均转为 PASS；最终 Security Reviewer 复核确认之前发现均关闭，当前候选无 P1/P2。追加路径仍拒绝末级软链接、FIFO、非普通文件和硬链接。

## VERIFY

环境：macOS/POSIX；Python 3.12；coverage.py 7.13.3；契约测试使用 `jsonschema[format-nongpl]==4.26.0`（测试依赖位于 `/private/tmp`，不是运行时依赖）。

| 检查 | 命令 / 结果 |
|---|---|
| ActionJournal 定向单元 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest tests.unit.test_action_journal`：71/71 PASS |
| 全单元 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit`：239/239 PASS |
| 全契约 / R3 安全套件 | Python 3.12.16：合同 77/77 PASS；`tests/security/` 1/1 PASS（不计入单元覆盖率分母） |
| 行/分支覆盖 | coverage.py 7.13.3：`bugmaster_core/` 行 1,393/1,393、分支 508/508（100% / 100%）；这只是 GATE-U100 初始样例范围。JSON 报告：`/private/tmp/bugmaster-pr5-coverage-final.json` |
| Catalog / Benchmark / 品牌 | `python3.12 scripts/validate_catalog.py` PASS；`python3.12 scripts/validate_benchmark.py` 结构 PASS（场景未执行）；`python3.12 scripts/check_branding.py` PASS |
| Release 门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr5-coverage-final.json`：No-Go；功能清单未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 缺少执行证据（预期门禁结果） |
| 独立 R3 安全复审 | PASS：独立 Security Reviewer 对当前 ActionJournal 候选未发现 P1/P2 |
| GitHub Actions | 本地候选验证通过；更新 PR #5 的远端 head 后仍待 Actions |
| Diff 空白 | `git diff --check`：PASS |

## 未覆盖能力

此方法只证明当前本地日志在结构、状态转换和哈希链层面包含指定前缀。日志哈希不能证明事件由可信来源产生或描述真实外部结果。尚未把 CheckpointStore、SessionStore 与正确 Journal 身份串接成可信恢复验证器；未对账预算、核验当前授权、执行恢复或崩溃断点注入，也未验证 Windows、真实 API/Browser、双宿主或 50 个 Benchmark 场景。整体 Release 维持 **No-Go**；PR #5 仍须通过更新后 GitHub Actions 才可合并。
