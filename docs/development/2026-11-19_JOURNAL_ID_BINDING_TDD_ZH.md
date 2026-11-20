# W6 ActionJournal 稳定身份绑定 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6；`F-RECOVERY`；`TDD-ACT-008`

**风险：** R3；独立 Security Reviewer 审查前不得合并。

**实现提交：** `215a1e831b24bb3b20ca99121e3063f184edbe02`；草稿 PR [#7](https://github.com/naodeng/bugmaster/pull/7)，基于 PR #6 `codex/checkpoint-reference-validation`，尚未合并。

## 需求、Oracle 与边界

每条持久化 Action Journal Event 必须绑定 Session 和稳定 Journal 身份。读取器应拒绝身份不匹配的日志；Checkpoint 引用验证还应要求 Session 声明的 Journal ID 与调用方传入 Journal 对象一致。Schema 负责结构约束，真实存储单测负责身份与事件链行为。

本轮把 Event Schema 提升到 v1.1，新增必需 `journalId`；ActionJournal 默认身份为 `journal-<sessionId>`，也允许调用方指定，并在写入/读取期间使用同一只读身份。v1.0 事件没有 Journal ID，会被拒绝读取且文件不被改写；本轮没有提供迁移。

这里的身份绑定仅验证 Journal 自报身份与 Session 文档相同。Journal 文件路径仍由调用方选择；本轮不证明 ID 到路径的来源真实性，不验证外部事件真实性、授权、预算对账或恢复安全，也不提供 Safe Resume。

## RED

先在真实临时文件系统测试中为 ActionJournal 增加身份写入、显式身份读取匹配/不匹配、显式空 ID 拒绝及身份属性不可变断言。运行 ActionJournal 定向测试时，37 项中的新增身份断言按预期失败，指出构造器/事件没有稳定 Journal 身份或该身份可被重新赋值。

随后新增 Event Schema v1.1 契约断言。运行 `tests/contracts/test_journal_schema.py` 时，2 项中的新断言失败：生成事件缺少 `journalId`，版本仍为旧值。

最后为 `CheckpointReferenceValidator` 增加 Session `journalId` 与传入 Journal 不匹配的真实存储测试。实现前该用例失败，因为验证器接受了身份不一致的对象。上述失败均发生在对应生产变更前。

## GREEN / REFACTOR

ActionJournal 现在在初始化时固定 `journal_id`，省略参数时使用 `journal-<sessionId>`；Event v1.1 的哈希链载荷包含 `journalId`，读取期间检查每个事件均与读取器身份相同。身份以只读属性公开。`CheckpointReferenceValidator` 另比较最新 Session 的 `journalId` 和传入 Journal 的 `journal_id`。

初版实现的全量分支覆盖发现一个身份非空检查分支未覆盖。审查后确认该条件由构造器约束和紧随其后的不相等检查完全蕴含；删除冗余判断，并先增加身份属性不可变的回归断言、运行得到 RED，再完成该结构简化。没有放宽测试断言。

## VERIFY

环境：macOS/POSIX；Python 3.12；coverage.py 7.13.3；契约测试使用 `jsonschema[format-nongpl]==4.26.0`。测试工具安装在 `/private/tmp`，没有加入产品运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| ActionJournal 定向单测 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py'`：38/38 PASS |
| Checkpoint 引用定向单测 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_checkpoint_reference_validator.py'`：13/13 PASS |
| Event Schema 契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -p 'test_journal_schema.py'`：2/2 PASS |
| 全单元与分支数据 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-journal-identity-full.coverage -m unittest discover -s tests/unit`：133/133 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：77/77 PASS |
| 行 / 分支覆盖 | `bugmaster_core`：990/990 语句、414/414 分支，均 100%；`action_journal.py`：295/295 语句、138/138 分支；`checkpoint_reference_validator.py`：32/32 语句、18/18 分支。独立报告行与分支覆盖，不以行覆盖代替分支覆盖 |
| 项目静态检查 | `scripts/validate_catalog.py`、`scripts/validate_benchmark.py`、`scripts/check_branding.py` 均 PASS；Benchmark 仅验证清单结构，50 个场景未执行；`git diff --check` PASS |
| GitHub Actions | [Run 44452742738](https://github.com/naodeng/bugmaster/actions/runs/44452742738)：单元、契约、行覆盖、Catalog、Benchmark 结构与品牌步骤全部成功 |
| Release 门禁 | **No-Go**：功能义务清单未冻结，真实业务功能执行覆盖率未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失 |

GitHub Actions 对该提交执行行覆盖门禁；本地分支覆盖报告为 100%。AI 编写的身份断言使用真实临时存储验证身份与拒绝行为，没有只断言调用次数或内部实现细节。

## 后续缺口

当前 `CheckpointReferenceValidator` 仍接收调用方构造的 ActionJournal，故无法证明文件路径由 Session `journalId` 唯一解析。恢复授权、动作级审批真实性、预算与 Journal 消费对账、权威只读副作用 reconciliation、文件系统故障注入、工具层执行绑定及八个崩溃断点仍未实现。没有运行真实 API/Browser、Windows、双宿主或 50 个 Benchmark 场景。写作本节时 PR #7 仍为草稿，之后已标为 ready；整体 Release 仍为 **No-Go**。

## 交叉审核修复（PR #7）

### RED

新增真实文件重开用例，使用合法的稳定 `journalId="journal\u2028\u0085identity"` 写入事件，再实例化新的读取器验证恢复状态和前缀。旧版 `str.splitlines()` 将 JSON 字符串中的 U+2028、U+0085 当作记录分隔符，定向测试在读取器构造时失败，报 `JournalCorruptionError: journal contains invalid JSON`（39 项中 1 项错误）。

### GREEN / VERIFY

改为按 JSONL 实际分隔符 LF 拆分记录，且去掉已由完整性检查确认的最终 LF；Unicode 行分隔字符留在 JSON 字符串内部。实现提交 `17359297f6e5388468498f545a9465360cdc4754`。修复后 ActionJournal 定向测试 39/39 PASS，Event Schema 契约 2/2 PASS，`git diff --check` PASS。该段是原始 PR 分支历史证据，不表示后续集成已完成。

## 2026-11-20 集成复审与修复验证

前文记录的是原始 PR #7 分支，不能代表当前集成状态。PR #6 已合入 `main`，merge commit 为 `c67af41c6aa2e74688bb289fb2ec6d3355fc861e`；远端 PR #7 head `81144137601b2a93a1e26293a25930bbe5b90bf1` 仍以旧 PR #6 分支为 base，旧 Actions Run `44486229369` 仅作为旧源码历史证据。以下验证使用继承 PR #6 merge tree 的隔离集成候选；推送后仍需重新等待远端 CI 和同一最终 head 的独立复审。

### 复审发现与 RED

独立安全角色针对原 PR #7 head 标出三项 P1 和两项 P2：重复 JSON 键允许 `journalId` 二义性；分开读取 Checkpoint/Session 会混合不同目录快照；按路径打开并先 `fchmod` 可能修改软链接目标；构造器接受无法 UTF-8 编码的 ID；缺少真实 v1.0 日志不变性回归。以下失败证据由 Python 3.12、macOS/POSIX 隔离副本产生；旧实现 SHA 均为原 PR #7 head `81144137601b2a93a1e26293a25930bbe5b90bf1`。`-k` 为 unittest discovery 的测试名过滤参数。

| RED 测试 ID | 命令（均以 `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit` 为前缀） | 旧实现失败证据 |
|---|---|---|
| `ActionJournalRecoveryTests.test_rejects_duplicate_journal_id_in_later_event_before_prefix_read` | `-p 'test_action_journal.py' -k duplicate_journal_id -v` | `AssertionError: JournalCorruptionError not raised` |
| `ActionJournalRecoveryTests.test_append_rejects_a_journal_symlink_before_changing_its_target` | `-p 'test_action_journal.py' -k symlink_before_changing -v` | 软链接目标模式被改为 `0600`；断言实际 `384` (`0600`)，预期 `420` (`0644`) |
| `CheckpointReferenceValidatorTests.test_rejects_journal_id_from_a_replaced_session_snapshot` | `-p 'test_checkpoint_reference_validator.py' -k replaced_session_snapshot -v` | `AssertionError: CheckpointReferenceError not raised` |
| `ActionJournalRecoveryTests.test_rejects_an_unencodable_journal_id_before_file_creation` | `-p 'test_action_journal.py' -k unencodable_journal_id -v` | `AssertionError: JournalError not raised` |
| `ActionJournalRecoveryTests.test_rejects_an_unencodable_session_id_before_file_creation` | `-p 'test_action_journal.py' -k unencodable_session_id -v` | `AssertionError: JournalError not raised` |
| `ActionJournalRecoveryTests.test_rejects_appending_to_a_late_appearing_v1_journal_without_mutation` | `-p 'test_action_journal.py' -k late_appearing_v1_journal -v` | 原始日志模式被改为 `0600`；断言实际 `384` (`0600`)，预期 `420` (`0644`) |

Event Schema 的首次身份版本断言在 PR #6 merge SHA `c67af41c6aa2e74688bb289fb2ec6d3355fc861e` 上先失败。环境为相同 macOS/POSIX、Python 3.12，命令为 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -p 'test_journal_schema.py' -k journal_id_is_required -v`，测试 ID `JournalSchemaTests.test_journal_id_is_required_and_v1_0_is_not_valid`，失败输出 `AssertionError: '1.0' != '1.1'`。以上 RED 用例在生产改动前运行；v1.0 仅拒绝且不变的重开/追加回归都保留在最终候选中。

身份、Schema、快照测试先于本轮生产实现运行。生产实现保留 PR #6 的目录描述符快照与 PR #5 的唯一 JSON 对象解析、安全无链接打开、身份复核和“先完整校验、后改文件模式”顺序。Event v1.1 现在要求 `journalId`；Checkpoint 验证器在同一 Session 快照中比较最新 Session 的 `journalId` 与配置的 Journal 对象 `journal_id`；构造器提前拒绝空 ID，以及无法 UTF-8 编码的 Session/Journal ID。调用方仍选择 Journal 路径，这项检查不证明 ID 到路径的真实性。

### GREEN / REFACTOR / VERIFY

首次完整覆盖检查发现两个生产分支缺少用例：事件 `journalId` 与读取器 ID 不匹配、显式空 ID。增加有效哈希事件身份不匹配和空 ID 建文件前拒绝测试后，全量测试与覆盖再次运行。最终隔离候选环境为 macOS/POSIX、Python 3.12、coverage.py 7.13.3；`jsonschema[format-nongpl]==4.26.0` 从 `/private/tmp/bugmaster-jsonschema` 加载，仅用于契约测试。

| 检查 | 命令 / 结果 |
|---|---|
| ActionJournal 定向单测 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v`：80/80 PASS |
| 全单元测试与分支采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-pr7-integrated.coverage -m unittest discover -s tests/unit`：268/268 PASS |
| 全契约测试 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：79/79 PASS |
| R3 安全测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/security`：1/1 PASS |
| 行与分支覆盖 | `bugmaster_core`：1457/1457 语句、540/540 分支，均 100%；Event / Checkpoint 跨存储新增路径包含在内 |
| Catalog / Benchmark / 品牌 | `scripts/validate_catalog.py`、`scripts/validate_benchmark.py`、`scripts/check_branding.py`：PASS；Benchmark 只检查清单结构，未执行场景 |
| Release 质量门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr7-integrated-coverage.json`：预期 **No-Go**；功能义务清单未冻结、真实业务覆盖未超过 60%，且核心功能 Happy/Negative/Edge 执行证据缺失 |
| 远端 CI / PR 复审 | 集成候选尚未推送；NOT_RUN。原 PR head 的既有检查/复审不能代替新 head 验证 |

以上本地测试及覆盖数据证明当前声明范围内的代码路径，不证明完整功能验收、真实 API/Browser 执行、Safe Resume、50 个 Benchmark 执行或发布批准。最终集成 commit SHA 与其 GitHub Actions Run 应在推送后补录。
