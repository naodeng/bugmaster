# Action 待对账枚举与进程崩溃注入 TDD 记录

**日期：** 2026-11-19<br>
**Workstream / 义务：** W6 安全恢复；`F-RECOVERY` / `TDD-ACT-011`<br>
**风险：** R3（恢复诊断；不授权执行）<br>
**实现提交：** `8129838d0165115a78bf7435f1cdced7fa3de601`<br>
**崩溃注入测试提交：** `72157f7e9d8df73f324d8432555d16e3ac1ef988`<br>
**PR：** [#10](https://github.com/naodeng/bugmaster/pull/10)，基于 PR #9<br>
**状态：** PR #10 原 head `ae3ac3f74237a96c5f6db8944f2a46338bef9213` 已先后合入 PR #9 当前代码基线。PR #9 的 C-1 修复随 head `21ed1b9` 进入其整合提交 `d2d2d6123b3c549fea93e3a393d55660516de9bc`；PR #10 最终代码整合提交 `7eb6f1a40b165e43080f0ba167c3389fd0d5e6ae` 包含该修复与 fail-closed gate，tree `af0e751902f230ef5e8035a51c845f5d14ab8ace`。文档同步 merge 提交 `a0e339481406f716ba0433247167448ecabd54be` 纳入 PR #9 最新文档 head `69b72003237e281f81a99f45c358f90478e63239`。本地 macOS / Python 3.12.16 验证 430/430 单元、82/82 契约、1/1 安全测试，生产行/分支覆盖 2,150/2,150 与 770/770（均 100%）；PR #10 最新 head Actions 与 CodeX 复审待推送后核对。独立真人 Q15 Security Review 仍未签署。只读枚举和崩溃注入不提供可信外部核验、恢复授权或真实 API/Browser 执行。

## 需求与边界

W6 要求 Journal/安全恢复、未知副作用对账和崩溃故障注入。Journal 已有单个 Action 的恢复状态查询，但恢复进程没有 API 枚举所有尚待核查的 Action。SessionStore 与 CheckpointStore 使用临时文件及 hard link 发布不可变数据，本轮补充进程退出注入来核查这些发布阶段。Action 枚举必须来自完整校验后的本地 Journal 状态；本地日志、哈希链与对账引用都不能证明外部事实。

本切片新增 `ActionJournal.actions_needing_reconciliation()`，按 Action 首次写入顺序返回状态仍需对账的 ID 元组。它不验证外部副作用、不认证对账声明，也不授权重放；`can_replay()` 继续对所有请求 fail-closed。预算计数时点和真实观察器未在本次推断或实现。

## RED

先加入 10 个 Journal 子进程退出故障注入场景，覆盖准备/派发/结果事件的部分写入、事件写完但未同步、同步后退出、未知结果、未验证对账声明、枚举顺序及已记录完成结果。定向运行 10/10 PASS，说明现有 Journal 对这些进程退出状态已经采取保守处理。

随后增加枚举接口行为测试，并在生产代码修改前运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_action_journal_crash_recovery.py' -k recovery_can_enumerate -v
```

结果：按预期失败，`AttributeError: 'ActionJournal' object has no attribute 'actions_needing_reconciliation'`。

另新增 SessionStore 5 个、CheckpointStore 4 个崩溃注入点：临时文件部分写入、发布 hard link 前、发布后目录同步前、目录同步后临时文件清理前；SessionStore 还覆盖 `session.head` 已同步的提交点。首次执行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p 'test_store_crash_recovery.py' -v
```

结果 6/8；2 个 Checkpoint 场景的注入夹具先命中了首次创建 `checkpoints/` 子目录的同步，而不是记录发布后的同步。预先建立目标目录后重跑同一命令为 8/8 PASS；没有生产代码缺陷或放宽断言。

## GREEN

实现只读枚举：重读并验证本地 Journal，再用现有 `_needs_reconciliation` 状态判定返回 Action ID 元组。损坏日志仍抛出既有 `JournalCorruptionError`；不完整、不可信或恢复声明状态仍不会被转成可重放。SessionStore/CheckpointStore 的 9 个注入场景验证了已发布记录可完整读回，发布前中断不会暴露记录且允许重试；这部分只增加验证，没有修改既有存储实现。

## REFACTOR

保持最小 API，不添加外部核验器、批准状态或 Session 预算计算。同步英文和中文合同说明，注明 API 的诊断性质与失效关闭行为。总计 19 个进程崩溃场景使用子进程 `os._exit` 模拟应用进程突然退出，不等价于断电、内核崩溃、文件系统故障或 Windows 验证。

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

合入 PR #8 覆盖边界测试后的历史全量验证基于提交 `301c7e79ab325a64d2bc935131900beb6bdc530d`：198 项单测、78 项契约和 1196/1196 语句、474/474 分支均通过。PR #10 Actions [Run 44487187776](https://github.com/naodeng/bugmaster/actions/runs/44487187776) 验证代码与测试 head `8f498d38d81c4fe8127c5c35759f27eb7ceffb32`；后续 docs-only head `ffe52dc6…` 对应 Run `44488992365`。两次均基于旧 PR #9 提交 `f69c61b8…`，只作为历史证据，不证明当前 PR #9/#10 叠加树。

| 检查 | 命令 / 结果 |
|---|---|
| Journal/Session/Checkpoint 崩溃恢复 | `/private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_action_journal_crash_recovery tests.unit.test_store_crash_recovery -v`：21/21 PASS；包含 10 个 Journal、5 个 Session、4 个 Checkpoint 进程退出点 |
| ActionJournal 与 ActionJournalStore | `/private/tmp/bugmaster-review-venv/bin/python -m unittest tests.unit.test_action_journal tests.unit.test_action_journal_store -v`：64/64 PASS |
| 全单元与覆盖数据 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-pr10-final.coverage -m unittest discover -s tests/unit`：198/198 PASS；`PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage json --data-file=/private/tmp/bugmaster-pr10-final.coverage -o /private/tmp/bugmaster-pr10-final-coverage.json` 生成质量门禁输入 |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m unittest discover -s tests/contracts -v`：78/78 PASS |
| 行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python -m coverage report --data-file=/private/tmp/bugmaster-pr10-final.coverage --include='bugmaster_core/*'`：1196/1196 语句、474/474 分支，均为 100%；无排除项 |
| 品牌 / Catalog / Benchmark | `/private/tmp/bugmaster-review-venv/bin/python scripts/check_branding.py`、`/private/tmp/bugmaster-review-venv/bin/python scripts/validate_catalog.py`、`/private/tmp/bugmaster-review-venv/bin/python scripts/validate_benchmark.py` 均 PASS；Benchmark 仅结构检查，场景未执行 |
| 发布门禁 | `PYTHONDONTWRITEBYTECODE=1 /private/tmp/bugmaster-review-venv/bin/python scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-final-coverage.json` 按预期 NO-GO：义务清单未冻结，真实功能覆盖与核心 Happy/Negative/Edge 证据缺失 |
| GitHub Actions | PR #10 旧基线代码/测试 head [Run 44487187776](https://github.com/naodeng/bugmaster/actions/runs/44487187776)：PASS，但不覆盖当前 PR #9 基线；PR #9 最新 docs head Run `44908476017` 成功。PR #10 新整合 head Actions 待推送后验证 |
| 补丁格式 | `git diff --check`：PASS |

崩溃模拟仍只覆盖应用进程 `os._exit`；不代表断电、内核崩溃、文件系统失效、真实外部副作用或 Windows 行为。PR #10 仍需独立 R3 Security Reviewer 审核。

## PR #9 最新基线整合复验（2026-11-22）

交叉审核确认 PR #10 旧 head 落后当前 PR #9，GitHub 标记 `dirty`；旧 Actions 不覆盖当前叠加树。以远端 PR #9 head `c8f0f6e061ed55909e656b30a125d5f9cf2042d3` 的 tree `df2c515215dc3228957475a430be16eb37121221` 为基线整合 PR #10 的变更，同时保留 PR #9 的 Journal 路径、目录描述符、ACL 和 fail-closed replay hardening。

最新基线复验首先新增「Journal 文件缺失时不得返回空列表」测试。RED 测试-only tree `251cfa25f4c7861f83d3dcaff3809fe812ea54ad` 基于上述 PR #9 基线和 PR #10 现有枚举实现，但不包含缺失文件 guard；在 Python 3.12.16/macOS POSIX 环境运行 `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest tests.unit.test_action_journal_crash_recovery.ActionJournalCrashRecoveryTests.test_enumeration_fails_closed_when_journal_is_missing -v`，按预期失败：`AssertionError: JournalCorruptionError not raised`。随后让 `actions_needing_reconciliation()` 在完整加载后检查已验证的文件身份；缺少规范 Journal 时抛出既有 `JournalCorruptionError`，同一测试 1/1 PASS。崩溃测试注入器也改为识别成功发布的硬链接、`session.head` 替换和目标目录同步；此前 PR #8 的目录 fd 同步、Session 锁和 `os.link(..., src_dir_fd=..., dst_dir_fd=...)` 使旧注入点不能命中预期发布阶段。没有改变 SessionStore/CheckpointStore 生产逻辑。

环境：隔离本地克隆 `/private/tmp/bugmaster-pr10-integrated`，macOS POSIX，Python 3.12.16；`coverage.py` 和 `jsonschema` 从 `/private/tmp` 加载。合并后本地完整验证：

| 检查 | 命令 / 结果 |
|---|---|
| Journal/Session/Checkpoint 恢复定向测试 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest tests.unit.test_action_journal_crash_recovery tests.unit.test_store_crash_recovery -v`：22/22 PASS |
| 全单元与覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema:/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr10-integrated.coverage -m unittest discover -s tests/unit`：428/428 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v`：80/80 PASS |
| R3 安全测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/security -v`：1/1 PASS |
| 生产行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage json --data-file=/private/tmp/bugmaster-pr10-integrated.coverage -o /private/tmp/bugmaster-pr10-integrated.json`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage report --data-file=/private/tmp/bugmaster-pr10-integrated.coverage --include='bugmaster_core/*,scripts/*'`：2146/2146 语句、772/772 分支，100%，无排除项 |
| 品牌 / Catalog / Benchmark manifest | `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/check_branding.py`、`PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/validate_catalog.py`、`PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/validate_benchmark.py`：均 PASS；Benchmark 只查结构，50 场景未执行 |
| Diff 格式 | `git diff --check`：PASS |
| Release Gate | `scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-integrated.json`：按预期 NO-GO；功能义务清单未冻结、真实业务覆盖未超过 60%，核心 Happy/Negative/Edge 证据缺失 |

完整本地整合验证对应 tree `badb6af5f651f646d9c5f6137cb826c46bd64efd`，已由远端提交 `911f62def6331def4918a2ab8d5286794e3876a3` 固定；该提交第一父提交为 PR #10 原 head `ffe52dc6c523e2eb4503d0d9a979dde515659fef`，第二父提交为 PR #9 当前 head `c8f0f6e061ed55909e656b30a125d5f9cf2042d3`。该 head 已推送。随后文档 head `f44d8628cc48886d25baa896951b1e25626ad962` 的 GitHub Actions [Run 81](https://github.com/naodeng/bugmaster/actions/runs/44977659359) 全部成功；Codex 通用审查对该 head 未发现重大问题。三种交叉审核角色对整合代码/测试快照无未解决发现。GitHub CodeX Security Review 请求未产生状态或结果，不能视为通过；所有 PR #3–#10 仍需独立人工 R3 Security Reviewer，AI 复核不构成 Q15 签署。

## 2026-11-22：接入最新 PR #9 fail-closed 基线

PR #9 在原 PR #10 基线提交 `c8f0f6e` 之后新增了对 R0/R1 自述 Scope claim 与自述 Evidence claim 的拒绝逻辑，并补充相应契约负例。PR #10 原 head `ae3ac3f` 因而不再基于最新 PR #9 head。为保留现有分支提交与审查轨迹，本次以普通 merge 将 PR #9 head `84e7dee9838f4123b2aec181a93f4d4ebf85d9c3` 合入 PR #10，生成整合提交 `b7e98a5c6ab6aec8ad860ee390d9e62a78d5d2d6`，tree `f4c12afa7bc8e9127e9b5c80720df6062a26f45b`。没有改动 PR #10 的 Action 枚举或进程崩溃恢复实现。

环境：macOS POSIX，Python 3.12.16；JSON Schema 与 coverage 依赖从 `/private/tmp` 加载。验证结果：

| 检查 | 命令 / 结果 |
|---|---|
| Journal / Session / Checkpoint 恢复定向测试 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest tests.unit.test_action_journal_crash_recovery tests.unit.test_store_crash_recovery -v`：22/22 PASS |
| 全单元与覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema:/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr10-latest.coverage -m unittest discover -s tests/unit`：428/428 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：82/82 PASS |
| R3 安全测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/security -v`：1/1 PASS |
| 生产行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage json --data-file=/private/tmp/bugmaster-pr10-latest.coverage -o /private/tmp/bugmaster-pr10-latest.json`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage report --data-file=/private/tmp/bugmaster-pr10-latest.coverage --include='bugmaster_core/*,scripts/*'`：2,143/2,143 语句、768/768 分支，分别统计且均 100%，无遗漏项。 |
| Catalog / 品牌 / Benchmark manifest | `python3.12 scripts/validate_catalog.py`、`python3.12 scripts/check_branding.py`、`python3.12 scripts/validate_benchmark.py`：均 PASS；Benchmark 只校验结构，50 个场景未执行 |
| Release Gate | `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-latest.json`：按预期 NO-GO，原因包括 Feature Inventory 未冻结、真实业务覆盖不超过 60%、核心 Happy/Negative/Edge 执行证据缺失 |

PR #10 代码/证据 head `8bbc2c3` 的 GitHub Actions Run `44986603312` 全部通过。CodeX 通用与安全辅助复审已在该 head 请求，结果待返回；旧 head 上的 AI review 不代表当前整合代码。任何模型结论和 CI 均不替代独立真人 Q15 Security Reviewer 签署。

## 2026-11-22：接入含 PR #8 C-1 的最新 PR #9 基线

PR #9 最新代码树已包含 PR #8 Session–Journal ID 绑定修复及自身的 fail-closed Scope/Evidence gate。PR #10 原始分支曾基于更早的 PR #9 head；本次整合代码提交 `7eb6f1a40b165e43080f0ba167c3389fd0d5e6ae` 纳入该最新代码树，tree `af0e751902f230ef5e8035a51c845f5d14ab8ace`。后续文档同步 merge `a0e339481406f716ba0433247167448ecabd54be` 纳入 PR #9 最新证据 head `69b72003237e281f81a99f45c358f90478e63239`。PR #10 的 Action 枚举、缺失日志 guard 和进程崩溃验证实现未修改。

环境：macOS POSIX，Python 3.12.16；JSON Schema 与 coverage 依赖从 `/private/tmp` 加载。代码树 `af0e751` 的本地验证：

| 检查 | 命令 / 结果 |
|---|---|
| Journal / Session / Checkpoint 恢复定向 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest tests.unit.test_action_journal_crash_recovery tests.unit.test_store_crash_recovery -v`：22/22 PASS；另行运行 Session–Journal mismatch 回归 1/1 PASS |
| 全单元与覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema:/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr10-final.coverage -m unittest discover -s tests/unit`：430/430 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：82/82 PASS |
| R3 安全测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/security -v`：1/1 PASS |
| 生产行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage json --data-file=/private/tmp/bugmaster-pr10-final.coverage -o /private/tmp/bugmaster-pr10-final.json`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage report --data-file=/private/tmp/bugmaster-pr10-final.coverage --include='bugmaster_core/*,scripts/*'`：2,150/2,150 语句、770/770 分支，分别统计且均 100%，无遗漏项 |
| Catalog / 品牌 / Benchmark manifest | `python3.12 scripts/validate_catalog.py`、`python3.12 scripts/check_branding.py`、`python3.12 scripts/validate_benchmark.py`：PASS；50 个 Benchmark 场景未执行 |
| Release Gate | `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-final.json`：按预期 NO-GO，Feature Inventory 未冻结、业务覆盖未超过 60%、核心 Happy/Negative/Edge 证据缺失 |

PR #9 head `69b7200` 对应 Actions Run `44986287358` 全部通过；PR #10 当前整合 head 的 Actions 与 CodeX 通用/安全复审待远端核对。独立真人 Q15 Security Reviewer 仍未签署，模型结论和 CI 均不能替代签署。

## 2026-11-22：补齐人工复核指出的 PR #10 枚举与 store-backed 崩溃覆盖

PR #10 合入 PR #9 新 head `be7884511d034d85358f6c3d4599796b37b8a092`，整合提交为 `0ab902673f1e4734b1509db2bfafa1a5960d0777`；本次测试提交为 `4aaafd4eb32cfeb09de73133a10f5aeba811e667`。本轮只增加测试，没有改变生产行为。审查报告指出这些路径此前缺少测试，故不伪造生产行为 RED；新增真实文件系统和子进程场景后验证其结果。

### 新增覆盖

- **store-backed 崩溃恢复：** 子进程通过 `ActionJournalStore.open()` 打开与持久 Session `journalId` 相符的 Journal，在 `dispatched` 事件 fsync 后以 `os._exit(71)` 退出。父进程重新通过 Store 打开，枚举到未决 action，并确认不能再次 dispatch。
- **空 Journal 枚举：** 对零字节 Journal 明确断言当前结果为 `()`。这只固定空历史的现有语义；同 UID 截断/篡改仍属于已声明威胁模型，测试不声称检测该操作。若产品要求抵抗同 UID 篡改，需要单独设计并审查 genesis/head 记录。
- **失败态风险枚举：** 对失败的 R0 Action 断言终态且不枚举；对失败的 R1 Action 断言需要对账且进入枚举。

### VERIFY

环境：macOS / Darwin，Python 3.12.16。

| 检查 | 结果 |
|---|---|
| Journal 崩溃恢复定向测试 | `test_action_journal_crash_recovery.py`：15/15 PASS；包含 store-backed 子进程崩溃、零字节、失败 R0/R1 枚举 |
| 全量单元 / 契约 / 安全 | 单元 437/437、契约 82/82、安全 1/1 PASS |
| 行 / 分支覆盖 | `bugmaster_core/` 与 `scripts/` 共 2,159/2,159 语句、768/768 分支，分别统计，均 100%；覆盖 JSON：`/private/tmp/bugmaster-pr10-human-review.json` |
| macOS ACL / 清单检查 | 完整单元与验证器套件在 Darwin 执行，原生 `chmod +a` ACL 测试通过；Catalog、Benchmark manifest 结构、品牌扫描与 `git diff --check` PASS。50 个 Benchmark 场景未执行 |
| Release Gate | **NO-GO（预期）**：Feature Inventory 未冻结、业务覆盖未超过 60%、核心 Happy/Negative/Edge 执行证据缺失 |
| 远端 CI / Q15 | 新整合 head 推送后仍须核验远端 Actions；用户提供的报告是 REQUEST CHANGES 结论，不是 GitHub Q15 APPROVE，不能记录为已签署 |

V-2/V-3/V-5 仍为未证实的平台 ACL、DoS/root 祖先及 legacy 可达性事项；本轮没有把它们扩大成确认漏洞。V-4 的同 UID 篡改威胁也未改变。最终是否通过 R3 Q15 仍需独立真人在修复后的 head 上复核并正式批准。

## Q15 项目所有者修订（2026-11-22）

本记录中“独立真人 Q15 Security Review 尚未签署”“仍需独立真人审核”等文字，记录的是当时的 Q15=B 规则和历史状态。项目所有者已于 2026-11-22 将 Q15 修订为 D：每个 PR 由 Codex 进行代码扫描；R2/R3 改动另做安全扫描；所有者查看结果后手动合并，不要求独立真人 Q15 审核或签署。此修订只更新 PR 门禁，不改变 Q16 的公开发布双人授权，也不代表本地崩溃测试覆盖真实目标、外部副作用或 Release 验收。

本次合并候选的代码/安全扫描结果与准确 commit 记录在对应 PR 描述中；该描述不作为 Q16 真人发布批准。
