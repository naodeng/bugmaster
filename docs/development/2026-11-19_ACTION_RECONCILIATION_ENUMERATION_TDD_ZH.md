# Action 待对账枚举与进程崩溃注入 TDD 记录

**日期：** 2026-11-19  
**Workstream / 义务：** W6 安全恢复；`F-RECOVERY` / `TDD-ACT-011`  
**风险：** R3（恢复诊断；不授权执行）  
**实现提交：** `8129838d0165115a78bf7435f1cdced7fa3de601`  
**崩溃注入测试提交：** `72157f7e9d8df73f324d8432555d16e3ac1ef988`
**PR：** [#10](https://github.com/naodeng/bugmaster/pull/10)，基于 PR #9  
**状态：** 本地交叉审核修复已验证；当前代码与测试已推送，PR #10 Actions Run `44487187776` 全步骤通过。只读待对账 Action 枚举，以及 Journal/SessionStore/CheckpointStore 进程崩溃注入不提供可信外部核验、恢复授权或真实 API/Browser 执行。

## 需求与边界

W6 要求 Journal/安全恢复、未知副作用对账和崩溃故障注入。Journal 已有单个 Action 的恢复状态查询，但恢复进程没有 API 枚举所有尚待核查的 Action。SessionStore 与 CheckpointStore 使用临时文件及 hard link 发布不可变数据，本轮补充进程退出注入来核查这些发布阶段。Action 枚举必须来自完整校验后的本地 Journal 状态；本地日志、哈希链与对账引用都不能证明外部事实。

本切片新增 `ActionJournal.actions_needing_reconciliation()`，按 Action 首次写入顺序返回状态仍需对账的 ID 元组。它不验证外部副作用、不认证对账声明，也不授权重放；`can_replay()` 继续对所有请求 fail-closed。预算计数时点和真实观察器未在本次推断或实现。

## RED

先加入 9 个 Journal 子进程退出故障注入场景，覆盖准备/派发/结果事件的部分写入、事件写完但未同步、同步后退出、未知结果、未验证对账声明及已记录完成结果。定向运行 9/9 PASS，说明现有 Journal 对这些进程退出状态已经采取保守处理。

随后增加枚举接口行为测试，并在生产代码修改前运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_crash_recovery.py' -k recovery_can_enumerate -v
```

结果：按预期失败，`AttributeError: 'ActionJournal' object has no attribute 'actions_needing_reconciliation'`。

另新增 SessionStore 与 CheckpointStore 各 4 个崩溃注入点：临时文件部分写入、发布 hard link 前、发布后目录同步前、目录同步后临时文件清理前。首次执行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_store_crash_recovery.py' -v
```

结果 6/8；2 个 Checkpoint 场景的注入夹具先命中了首次创建 `checkpoints/` 子目录的同步，而不是记录发布后的同步。预先建立目标目录后重跑同一命令为 8/8 PASS；没有生产代码缺陷或放宽断言。

## GREEN

实现只读枚举：重读并验证本地 Journal，再用现有 `_needs_reconciliation` 状态判定返回 Action ID 元组。损坏日志仍抛出既有 `JournalCorruptionError`；不完整、不可信或恢复声明状态仍不会被转成可重放。SessionStore/CheckpointStore 的 8 个注入场景验证了已发布记录可完整读回，发布前中断不会暴露记录且允许重试；这部分只增加验证，没有修改既有存储实现。

## REFACTOR

保持最小 API，不添加外部核验器、批准状态或 Session 预算计算。同步英文和中文合同说明，注明 API 的诊断性质与失效关闭行为。总计 17 个进程崩溃场景使用子进程 `os._exit` 模拟应用进程突然退出，不等价于断电、内核崩溃、文件系统故障或 Windows 验证。

## VERIFY

环境：隔离工作树 `/Users/inaodeng/.codex/worktrees/session-contract/bugmaster`，分支 `codex/recovery-observation`；Python 3.12；`coverage.py` 和 `jsonschema` 位于 `/private/tmp`，未修改产品运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| RED 定向测试 | 上述枚举测试命令：因新接口缺失失败，exit 1 |
| Journal 崩溃 / 恢复定向测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_crash_recovery.py' -v`：11/11 PASS，包含 9 个进程退出场景 |
| Session / Checkpoint 崩溃定向测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_store_crash_recovery.py' -v`：8/8 PASS |
| Journal 定向测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v`：38/38 PASS |
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit`：164/164 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：78/78 PASS |
| 行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-recovery-observation-v2.coverage -m unittest discover -s tests/unit`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage json --data-file=/private/tmp/bugmaster-recovery-observation-v2.coverage -o /private/tmp/bugmaster-recovery-observation-v2-coverage.json`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage report --data-file=/private/tmp/bugmaster-recovery-observation-v2.coverage --include='bugmaster_core/*'`：`bugmaster_core` 1063/1063 语句、428/428 分支；`action_journal.py` 304/304 语句、140/140 分支 |
| Catalog / 品牌 / Benchmark | Catalog PASS；品牌扫描 PASS；Benchmark manifest 结构 PASS（50 个场景未执行） |
| 补丁检查 | `git diff --check`：PASS |
| Release Gate | `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-recovery-observation-v2-coverage.json`：按预期 NO-GO；业务功能清单未冻结、业务覆盖率未超过 60%，核心 Happy/Negative/Edge 缺实证 |
| GitHub Actions | [Run `44472202033`](https://github.com/naodeng/bugmaster/actions/runs/44472202033)，含实现提交 `8129838d0165115a78bf7435f1cdced7fa3de601` 与崩溃测试提交 `72157f7e9d8df73f324d8432555d16e3ac1ef988`：单元、契约、行覆盖率断言、Catalog、Benchmark manifest 和品牌检查全步骤成功 |

## 后续门禁

本切片只让恢复流程枚举本地尚待核查的 Action。它不提供 trusted read-only observer、授权网关、预算与 Journal 对账或安全恢复执行；这些能力仍需真实宿主/目标集成及独立 R3 Security Review。业务功能覆盖、核心三类真实执行证据、50 个 Benchmark、双宿主与 Release 均未因此通过。

## 交叉审核修复补充（2026-11-19）

第二轮跨角色审核复查 PR #1–#10 的当前实现，并逐条核对 PR 评论和可执行测试。PR #3 的 P1「修订目录丢失后静默重建并重置预算」与 PR #4 的 P2「只读读取跟随软链接」均已在对应上游切片修复；PR #1 的覆盖率门禁现拒绝 0/0；PR #7 按 LF 分隔 JSONL，保留合法的 U+2028/U+0085 ID；PR #8 的规范 Journal 缺失会失败关闭，读取器不再创建/改权限，且 FIFO 在非阻塞打开后按非普通文件拒绝。

本 PR 的额外复查发现两处验证缺口。第一，崩溃测试使用 no-op Schema validator 和缺少必需字段的最小文档，不能证明真实契约有效；第二，枚举测试只断言一个未决 ID，截断结果仍可能通过。按 RED 顺序改为加载仓库中版本化 Session/Checkpoint Schema、使用完整有效文档，并断言三个未决 ID 的完整顺序元组。SessionStore 新增「revision 已写入但 `session.head` 尚未提交」的失败关闭断言，以及「head 与目录已同步后」可读回的提交点崩溃断言。

### RED

- 第一次以真实 Schema 校验 Session fixture 时失败：缺少规范生命周期字段；补齐字段、时间戳和预算数据后才通过。
- PR #3 的 head 锚点进入叠加分支后，两个旧崩溃断言在无 head 的场景收到 `SessionCorruptionError: Session revision head is missing`，证明原先“revision 已链接即可读取”的预期错误；更新为验证缺失提交标记时失败关闭，并增加 head 已提交后的恢复用例。
- 原枚举恢复场景只包含一个未决 Action，无法识别返回列表被截断；现在先写入多个未决 ID，并断言完整、有序的结果。

### GREEN / VERIFY

环境：隔离克隆 `/private/tmp/bugmaster-review-fixes-20261119`，分支 `codex/recovery-observation`，Python 3.12；测试依赖位于 `/private/tmp/bugmaster-review-venv`。验证的是本地提交，GitHub Actions 尚待推送后运行。

本轮测试提交：`605297156e006e9b6f7f9aacccb4755bc820d62b`。其中包含测试、TDD 记录和进度状态更新；本地全量验证在该测试内容提交前运行，随后只修改了中文证据的命令和路径记录。

合入 PR #8 覆盖边界测试后的全量验证基于提交 `301c7e79ab325a64d2bc935131900beb6bdc530d`：198 项单测、78 项契约和 1196/1196 语句、474/474 分支均通过。PR #10 Actions [Run 44487187776](https://github.com/naodeng/bugmaster/actions/runs/44487187776) 在代码与测试 head `8f498d38d81c4fe8127c5c35759f27eb7ceffb32` 全步骤通过。随后只同步 PR #8 的工作流证据，未改动代码或测试；`git diff --check` 通过。

| 检查 | 命令 / 结果 |
|---|---|
| Journal/Session/Checkpoint 崩溃恢复 | `/private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_action_journal_crash_recovery tests.unit.test_store_crash_recovery -v`：21/21 PASS；包含 10 个 Journal、5 个 Session、4 个 Checkpoint 进程退出点 |
| ActionJournal 与 ActionJournalStore | `/private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_action_journal tests.unit.test_action_journal_store -v`：64/64 PASS |
| 全单元与覆盖数据 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-pr10-final.coverage -m unittest discover -s tests/unit`：198/198 PASS；`PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage json --data-file=/private/tmp/bugmaster-pr10-final.coverage -o /private/tmp/bugmaster-pr10-final-coverage.json` 生成质量门禁输入 |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/contracts -v`：78/78 PASS |
| 行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage report --data-file=/private/tmp/bugmaster-pr10-final.coverage --include='bugmaster_core/*'`：1196/1196 语句、474/474 分支，均为 100%；无排除项 |
| 品牌 / Catalog / Benchmark | `/private/tmp/bugmaster-review-venv/bin/python scripts/check_branding.py`、`/private/tmp/bugmaster-review-venv/bin/python scripts/validate_catalog.py`、`/private/tmp/bugmaster-review-venv/bin/python scripts/validate_benchmark.py` 均 PASS；Benchmark 仅结构检查，场景未执行 |
| 发布门禁 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-final-coverage.json` 按预期 NO-GO：义务清单未冻结，真实功能覆盖与核心 Happy/Negative/Edge 证据缺失 |
| GitHub Actions | PR #10 代码/测试 head [Run 44487187776](https://github.com/naodeng/bugmaster/actions/runs/44487187776)：PASS；PR #1–#9 对应当前代码/测试 head 的工作流也通过，见 [Actions 列表](https://github.com/naodeng/bugmaster/actions) |
| 补丁格式 | `git diff --check`：PASS |

崩溃模拟仍只覆盖应用进程 `os._exit`；不代表断电、内核崩溃、文件系统失效、真实外部副作用或 Windows 行为。PR #10 仍需独立 R3 Security Reviewer 审核。
