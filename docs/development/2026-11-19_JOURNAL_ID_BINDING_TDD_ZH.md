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

当前 `CheckpointReferenceValidator` 仍接收调用方构造的 ActionJournal，故无法证明文件路径由 Session `journalId` 唯一解析。恢复授权、动作级审批真实性、预算与 Journal 消费对账、权威只读副作用 reconciliation、文件系统故障注入、工具层执行绑定及八个崩溃断点仍未实现。没有运行真实 API/Browser、Windows、双宿主或 50 个 Benchmark 场景。PR #7 保持草稿；整体 Release 仍为 **No-Go**。

## 交叉审核修复（PR #7）

### RED

新增真实文件重开用例，使用合法的稳定 `journalId="journal\u2028\u0085identity"` 写入事件，再实例化新的读取器验证恢复状态和前缀。旧版 `str.splitlines()` 将 JSON 字符串中的 U+2028、U+0085 当作记录分隔符，定向测试在读取器构造时失败，报 `JournalCorruptionError: journal contains invalid JSON`（39 项中 1 项错误）。

### GREEN / VERIFY

改为按 JSONL 实际分隔符 LF 拆分记录，且去掉已由完整性检查确认的最终 LF；Unicode 行分隔字符留在 JSON 字符串内部。实现提交 `17359297f6e5388468498f545a9465360cdc4754`。修复后 ActionJournal 定向测试 39/39 PASS，Event Schema 契约 2/2 PASS，`git diff --check` PASS。全量测试和覆盖率将在后续集成修复完成后重跑并记录。
