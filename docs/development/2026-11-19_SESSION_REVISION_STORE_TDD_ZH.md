# W6 Session Revision 持久化 TDD 记录

**日期：** 2026-11-19
**Workstream / 义务：** W6-01 Session Persistence；`F-RECOVERY`；`TDD-ACT-004`
**风险：** R3；合并前需要独立 Security Reviewer。
**实现提交：** `7d2e1957dc417146ed9559e75f04e9c694a3ebbb`（初版存储提交 `2e2101015d0ab062ed7b9a7a0301ba729bb6679b`）；草稿 PR [#3](https://github.com/naodeng/bugmaster/pull/3)，叠加于 Session Schema PR #2，尚未合并。

## Oracle 与范围

沿用 `docs/zh-CN/03-contracts.md` 中 Session / Checkpoint 不可变引用和恢复前核对要求。每个 Session revision 单独、不可覆盖地持久化；写入需校验版本化 Session Schema；并发追加必须基于调用者读取的当前 revision；恢复读取必须拒绝损坏、缺号或互相矛盾的历史。

本切片不证明 Approval 来源真实，不把预算与 Action Journal 对账，不写 Checkpoint，不批准恢复，也不代表安全重放、exactly-once 或工具层授权已经完成。SessionStore 需要调用方提供 Schema validator；存储目录与锁使用 POSIX 行为，Windows 尚未验证。

## RED

起始时 `SessionStore` 模块不存在。首轮 19 项单元测试因缺少模块而失败；2 项 Session Schema 集成测试同样因缺少模块失败。之后补齐存储与历史转换用例。

权限审查发现初版会把调用方拥有的根目录权限从 `0750` 改成 `0700`。新增 `test_store_does_not_change_caller_owned_root_permissions` 后实测失败（实际 `0700`，期望保留 `0750`），证明实现改动了调用方目录权限。

读取历史的审查发现已存 revision 各自通过 Schema 校验仍不够：revision 1 的 `journalId` 被改写为另一个合法字符串后，`read_latest()` 未拒绝。新增 `test_read_fails_closed_when_persisted_history_breaks_immutable_identity`，先得到 `SessionCorruptionError not raised`，作为明确的 RED 证据。之后检查发现宽松测试 validator 下，重复或倒退的同一 Scope revision 会因数组长度增长而被当作新 Scope history；新增 `test_scope_history_rejects_duplicate_and_backward_revisions`，先得到 `SessionStoreError not raised`。

## 复审修复：尾部截断、路径边界与只读读取

**日期：** 2026-11-19
**实现与测试提交：** `d2777e9`

### RED

先增加尾部 revision 缺失、复用 revision 号重置预算、悬空 revisions 软链接、会话目录软链接、只读锁权限及相对存储根工作目录变化的行为测试。实现前运行：

```text
python3.12 -m unittest discover -s tests/unit -p test_session_store.py -v
```

42 项中 5 项失败、1 项报错，分别暴露旧版本被当成最新、预算状态可回退、软链接路径被接受、只读锁不能读取和相对根随工作目录变化。

### GREEN / REFACTOR

每个 Session 写入独立 `session.head`，记录 Session ID、已提交 revision 和该 revision 的 SHA-256；读取会核对 head 与实际最新文件，尾部文件缺失或内容不符时失败关闭。读取先用 `lstat` 检查根目录及受控子目录，再以只读锁读取，不创建锁或改文件权限。构造 Store 时固定绝对根路径。

复审补充了 head 丢失、head 与 revisions 不一致、head 损坏及发布失败清理用例；这些用例覆盖新的错误路径，不代表所有测试均在同一轮 RED 阶段新增。

### VERIFY

环境：macOS、Python 3.12.16；`jsonschema[format-nongpl]==4.26.0`、`coverage==7.13.3`。
- SessionStore 定向单测：49/49 PASS。
- 全单元测试：105/105 PASS。
- 全合同测试：75/75 PASS。
- `bugmaster_core` 行覆盖：832/832（100%）；分支覆盖：354/354（100%）。
- `git diff --check`：PASS。

head 记录可发现 revision 尾部文件单独丢失或修改；它不是外部签名，无法证明整个 Session 目录未被整体回滚或同时删除。

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

## CodeX Security Review 修复：目录竞态、历史完整性与追加恢复

**日期：** 2026-11-19

**Workstream / 义务：** W6-01 Session Persistence；`F-RECOVERY`；`TDD-ACT-004`
**复审：** PR #3 head `73dbf6fad5a26ea539f04a991c35bd8948af9234` 的 CodeX review 留下 3 项发现；修复后 head `cccf6cd39cec59320f4ee54115741abdf52bb037` 的复审又发现超长 Session ID 会生成不可读 head。随后沿同一崩溃路径发现首次创建也可能遗留无法重试的 revision 1。当前本地均已修复；最后一轮变更、新 head、Security Review 与 GitHub Actions 结果待推送后补录。

### RED

先加入三个行为测试，再针对原实现运行：

```text
python -m unittest \
  tests.unit.test_session_store.SessionStoreTests.test_read_latest_uses_the_directory_that_owns_the_acquired_lock \
  tests.unit.test_session_store.SessionStoreTests.test_head_binds_every_historical_revision \
  tests.unit.test_session_store.SessionStoreTests.test_uncommitted_revision_after_head_write_failure_is_recoverable -v
```

3 项中 2 项失败、1 项报错：锁定后替换 `sessions` 目录会读到攻击者的预算（预期 12，实际 0）；改写早期 revision 后没有被 head 检出；head 发布失败留下的下一 revision 使后续读取报 `SessionCorruptionError`，重试无法恢复。

随后 CodeX 对新 head 的常规复审发现：长度为 1,000 的 Session ID 可通过 Schema 与 Store 校验，但产生的 `session.head` 超过读取上限。新增 `test_long_session_id_keeps_the_persisted_head_readable` 后先得到 `SessionCorruptionError: Session revision head is too large`，随后再实现修复。

再新增 `test_create_recovers_initial_revision_after_head_publication_failure`，模拟 revision 1 已发布而 head 发布失败；原实现重试 `create()` 时得到 `SessionCorruptionError: Session revision head is missing`。这是沿 CodeX 的崩溃一致性发现补出的相邻边界。

### GREEN / REFACTOR

- 根目录、`sessions`、Session 和 `revisions` 均通过目录描述符逐级打开；锁、head、revision 读取及发布都相对已打开的目录描述符完成。这样替换路径名或软链接不会把已锁定的 Store 操作重定向到另一目录。读锁使用 `O_NONBLOCK` 后再检查文件类型，避免 FIFO 在检查前阻塞。
- `session.head` 除最新 revision 摘要外，再绑定从 revision 1 开始的规范化完整历史摘要。读取任一历史版本都会重新计算整条摘要链，早期内容被改写时失败关闭。
- 追加若已发布一个连续、合法的下一 revision，但 head 发布失败，读取仍返回最后已提交版本；下一次追加校验这唯一的待提交 revision 后清理并重试。缺号、多余、非法或状态转换不合法的文件仍失败关闭。
- 将 head 读取上限设为 Session 最大文档体积加固定元数据余量；head 只重复有界的 `sessionId` 和定长摘要。该上限与 Store 可接受的 Session 文档大小一致，长度 1,000 的 ID 可创建、读取并追加；超出上限的持久化 head 仍在读取正文前拒绝。
- 若首次创建已耐久发布唯一的 revision 1、但尚未发布 head，下一次 `create()` 会读取并验证该初始 revision，恢复 head；相同创建请求可安全重试成功。存在其他文件、无效内容或不符合 revision 1 序号的状态仍失败关闭。

### VERIFY（本地；远端结果待补）

环境：macOS、Python 3.12.16；coverage.py 7.13.3；测试依赖位于 `/private/tmp/bugmaster-review-venv`。

| 检查 | 结果 |
|---|---|
| SessionStore 单元 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_session_store`：66/66 PASS |
| 全单元及覆盖率采集 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/session-pr3-final-v6.coverage -m unittest discover -s tests/unit`：122/122 PASS |
| 全合同 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/contracts -v`：75/75 PASS |
| `bugmaster_core` 行覆盖 | 959/959（100%） |
| `bugmaster_core` 分支覆盖 | 378/378（100%） |
| `git diff --check` | PASS |
| 远端状态 | Actions [Run 44524216279](https://github.com/naodeng/bugmaster/actions/runs/44524216279) 在上一 head `1db75b6` 通过；其后的首次创建恢复补强及验证已在本地完成。最终 head 的 CodeX 复审、Security Review 与 Actions 待推送后复核 |

本修复只保护相对于当前 head 可重算的存储历史完整性，不引入外部签名或防止整个存储目录被回滚；已有文档中关于 Session/Journal 对账、审批真实性及 Release No-Go 的范围说明仍适用。

## 未覆盖的产品能力

100% 单元行覆盖不是业务功能覆盖，也不是 BLK-03 完成证据。Checkpoint 持久化、崩溃断点注入、Windows 实现、进程/主机恢复、Approval 真实性验证、预算与 Journal 对账、可信只读核验及恢复授权仍未实现或未验证。未执行任何真实 API/Browser 目标测试、50 个 Benchmark 场景或双宿主验证。完整 Release 维持 **No-Go**；本 R3 PR 不得在缺少独立安全审查时合并。

## 独立安全与工程复审补充

**日期：** 2026-11-19
**复审范围：** PR #3 当前本地完整差异；W6-01 / `F-RECOVERY` / `TDD-ACT-004`；R3。

### RED

独立 Security Review 与 Engineering Review 交叉检查后，针对新发现分别新增回归测试并确认旧实现失败：

- 根目录检查后被替换成软链接、首次 revision 恢复请求与孤立数据不一致、已有数据丢失锁时追加会重建新锁、根路径末级 `..` 别名无法读取既有 Session、`_fsync_directory(Path)` 堆叠兼容，以及根/子目录 `fsync` 失败后的重试没有补同步父目录。
- 空 Session 目录在首次锁创建前被读取、旧版遗留的空 `revisions/` 无锁状态不能重试、锁并发创建时未重开锁、读取为并发首次提交误报损坏、深层 JSON 与超长整数把解析异常泄漏给调用方、超长历史读取累积全部 revision，以及进程中断遗留临时文件未清理。
- 通过故障注入覆盖 `mkdir`、目录重开、目录扫描、fsync 与锁打开错误；并修正一项并发锁失败测试，明确断言三次 `open()`，避免只测试首次打开失败造成假阳性。

### GREEN / REFACTOR

- 首次创建恢复先比对磁盘 revision 1 与本次请求的规范字节，再发布 head；请求不一致时保留孤立状态，不能替请求确认另一份 Session。
- 读写均先打开现有锁；只允许空目录，或仅含真实且为空的旧版 `revisions/` 目录时新建锁，并以 `O_EXCL` 处理并发初始化。已有数据缺锁仍失败关闭。锁初次打开未命中时检查目录；如果 revisions 扫描已看到并发发布的数据，会再打开锁并等待 `flock` 后读取。
- 写入重试会重新同步已有根路径分量和子目录的父目录；目录创建及重开失败转换为 Store 层异常。保留 `_fsync_directory(Path)` 供叠加 PR #4 的 CheckpointStore 使用，SessionStore 内部使用描述符版本。
- 只规范化根路径的末级 `..`；普通末级路径仍以 `O_NOFOLLOW` 打开，避免检查后被替换为软链接。revision 历史逐个扫描、校验并滚动摘要，只保留当前、前一和请求 revision，限制长历史读取内存。深层或整数过长的 JSON 统一映射为 `SessionCorruptionError`；下次独占写入时只清理匹配格式的普通临时文件并同步目录。

### VERIFY（本地最终差异；远端 head 待更新）

环境：macOS；Python 3.12.16；coverage.py 7.13.3；合同依赖位于 `/private/tmp/bugmaster-jsonschema`。

| 检查 | 命令 / 结果 |
|---|---|
| 全单元及分支采集 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/session-pr3-final-v15.coverage -m unittest discover -s tests/unit`：156/156 PASS |
| 合同测试 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/contracts`：75/75 PASS |
| 单元生产代码行覆盖 | `bugmaster_core` 1,045/1,045（100%） |
| 单元生产代码分支覆盖 | `bugmaster_core` 406/406（100%）；与行覆盖分开报告 |
| Release quality gate | Coverage 检查通过；整体 **No-Go**，原因仍是 Feature Inventory 未冻结、业务覆盖与核心 Happy/Negative/Edge 执行证据不足。本 PR 不声称 Release GO |
| 独立 Security Reviewer（CodeX 安全角色） | 最新复审无待修复发现；覆盖锁重开竞态、无锁数据隔离及旧目录兼容 |
| 独立 Engineering Reviewer | 最新复审无待修复发现；实测空目录竞态可线性化，进行中的首次提交会等待 writer lock 后读取 |
| `git diff --check` | PASS |
| GitHub Actions / GitHub 常规 CodeX Review / GitHub Security Review | 本地最终差异尚未推送；推送后须对新 head 重新核实 Actions、常规 review 与 Security review，再决定合并 |

这份本地复审结论不替代新远端 head 的 CI、GitHub review 状态或 Release 级审计。PR #3 保持未合并，直到新 head 的远端门禁与安全审查复核完成。

## GitHub Linux 覆盖率诊断跟进

**日期：** 2026-11-19

PR #3 head `5d398bb761233453c94cfa4d53d932a56e17e866` 的 Actions [Run 44533110359](https://github.com/naodeng/bugmaster/actions/runs/44533110359) 中，156 项单测和 75 项合同测试均通过；Ubuntu 26.04 / Python 3.12 的单元行覆盖率为 1,044/1,045（99.90%），因此 CI 按 100% 门槛失败。macOS 上相同 1,045 行全部覆盖，当前差异表明有一处平台执行路径尚未覆盖。

为让下一次 CI 失败能直接给出文件和未覆盖行，先扩展 `WorkflowCoverageGateTests`，断言失败报告包含缺失行；旧 workflow 在新测试下得到预期 RED。随后更新合同 workflow 的失败信息以输出 `coverage.json` 中各文件的 `missing_lines`，不改变 100% 门槛。`python -m unittest tests.contracts.test_quality_gate -v`：5/5 PASS；`git diff --check`：PASS。

首个诊断 head `0770f07ba08fabc7fda70a0aec4d860221eeafd2` 的 [Run 44534395315](https://github.com/naodeng/bugmaster/actions/runs/44534395315) 未创建 job。检查发现 YAML 普通标量中的 Python 字典冒号带空格会破坏 workflow 解析；本地 Ruby Psych 首次解析得到语法错误，移除冒号后的空格后解析通过，合同门禁回归仍为 5/5 PASS。

修正格式后的 head `0e76caeb514688b19682f5a6d9c35c43fbac636f` 在 [Run 44535020463](https://github.com/naodeng/bugmaster/actions/runs/44535020463) 正常执行至覆盖率门禁，报告唯一未覆盖行是 `bugmaster_core/session_store.py:780`（`00000001.json` 后出现额外目录项时拒绝恢复）。根据前一检查点的控制流和 Linux `scandir` 的无序枚举，这项两 revision 防护测试会先遇到 `00000002.json` 并在行 778 返回，因此没有覆盖行 780；这是测试依赖目录顺序造成的平台差异，未发现生产行为缺陷。将该测试的目录项顺序固定为名称升序后，目标测试 1/1、全单元 156/156、全合同 75/75 PASS；本机 `bugmaster_core` 行覆盖 1,045/1,045（100%）、分支覆盖 406/406（100%），`git diff --check` PASS。修正后的覆盖率 CI、安全复审和常规 CodeX review 仍待新 head 验证；PR #3 暂不合并。
