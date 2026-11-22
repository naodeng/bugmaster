# W6 未知结果 Action 重放门禁 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6；`F-RECOVERY`；`TDD-ACT-010`

**风险：** R3；未知副作用恢复边界，独立 Security Reviewer 审查前不得合并。

**实现提交：** `91e79ee1857f7e986f97431d850a1e2b6faa0037`；草稿 PR [#9](https://github.com/naodeng/bugmaster/pull/9)，基于 PR #8 `codex/journal-path-resolution`，尚未合并。

## 需求与 Oracle

`scripts/validate_gates.py` 的 `can_replay()` 原先仅凭输入字典中 `reconcilerVerified=True`、`newAuthorizationValid=True` 和 `outcome=reconciled-not-executed` 返回可重放。仓库并未接入可信只读 reconciliation verifier 或当前授权门禁；调用方自报布尔值不是信任根，不能解锁未知外部副作用。Oracle 来自冻结的恢复不变量：未知结果必须经权威只读对账后才可能考虑重放；当前没有可信核验器，因此必须 fail-closed。

本切片只阻断当前辅助门禁的重放允许结果。它不实现 reconciliation、重新授权或安全恢复，也不声称任何外部动作已执行。

## RED

先新增 `test_self_asserted_reconciliation_cannot_authorize_replay`，向原函数传入全部为真的 `reconcilerVerified` 与 `newAuthorizationValid` 字段。实现前运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py' -k self_asserted_reconciliation_cannot_authorize_replay -v
```

测试失败：`AssertionError: True is not false`，明确证明普通字典中的自报字段当前可以开放重放。检查原测试后发现它还要求上述输入返回 True，与“没有可信核验器，不可盲目重放”的已冻结不变量冲突；在实现前移除该错误正向期望，并保留单独负例来约束 fail-closed 行为。

**2026-11-21 复核补充：** 原始 RED 记录未保存该次运行的 Git SHA。为补足可复现证据，在生产代码基线 `99fe47e808a01c6b9964a3da38a59a506de16bc9` 上重建仅含该合同测试变更的测试专用提交 `0c607ae10b9f2742a31ebc702ec9b82954c99de1`；测试文件内容取自实现提交 `91e79ee1857f7e986f97431d850a1e2b6faa0037`，未改动生产代码。环境为 macOS/POSIX、Python 3.12.16，工作目录 `/private/tmp/bugmaster-pr9-red`。运行上方命令的输出为 `Ran 1 test`、`FAILED (failures=1)`，断言仍为 `AssertionError: True is not false`。这是针对旧生产代码的补充重现，不冒充 2026-11-19 原始运行快照。

## GREEN / REFACTOR

`can_replay()` 在可信只读 verifier 和当前授权门禁接入前固定返回 False，并注明调用方布尔字段不能授权重放。没有添加模拟的可信状态、签名或 verifier 参数，也没有扩大到真实工具执行。

## VERIFY

环境：macOS；Python 3.12；契约测试依赖 `jsonschema[format-nongpl]==4.26.0` 位于 `/private/tmp`。

| 检查 | 命令 / 结果 |
|---|---|
| 重放门禁合同 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py'`：12/12 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：78/78 PASS |
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-replay-gate.coverage -m unittest discover -s tests/unit`：145/145 PASS |
| 核心语句/分支覆盖 | `/private/tmp/bugmaster-replay-gate-coverage.json`：`bugmaster_core` 1060/1060 语句、428/428 分支（100%）。该数字只描述已声明核心模块范围；新增 helper 的行为由合同测试直接验证 |
| Catalog / Benchmark / 品牌 / Diff | Catalog PASS；Benchmark 清单结构 PASS（50 场景未执行）；品牌扫描 PASS；`git diff --check` PASS |
| Release 门禁 | **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%、核心功能 Happy/Negative/Edge 执行证据缺失 |
| GitHub Actions | [Run 44457678961](https://github.com/naodeng/bugmaster/actions/runs/44457678961)：单元、契约、行覆盖、Catalog、Benchmark 结构与品牌步骤全部成功 |

## 最新 PR #8 基线整合验证（2026-11-21）

验证对应代码与测试树提交 `42850bb49401a4090e0c8dc21ad2cdd4e0306bca`，其双亲为 PR #9 原 head `7a69db0e37eb7dc13b0324329208dbbdf346093e` 与最新 PR #8 head `58a601aa1dfa9639b38d9f9c6b0a62d9dbee2a4d`。以下本地命令在该提交树上重跑；本节在验证后补录，随后只变更开发记录文档。

环境：macOS/POSIX、Python 3.12.16；测试依赖 `jsonschema[format-nongpl]==4.26.0` 与 `coverage==7.13.3` 位于 `/private/tmp`。

| 检查 | 命令 / 结果 |
|---|---|
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit`：406/406 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：80/80 PASS |
| R3 安全测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/security`：1/1 PASS |
| 全单元与分支覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr9-integrated.coverage -m unittest discover -s tests/unit`：406/406 PASS |
| 生产行/分支覆盖 | `PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage report --data-file=/private/tmp/bugmaster-pr9-integrated.coverage`：2,141/2,141 行、770/770 分支，均为 100%；JSON：`/private/tmp/bugmaster-pr9-integrated.json` |
| 品牌 / Catalog / Benchmark | `python3.12 scripts/check_branding.py`、`python3.12 scripts/validate_catalog.py`、`python3.12 scripts/validate_benchmark.py`：均 PASS；Benchmark 只验证清单结构，50 场景未执行 |
| Release 门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr9-integrated.json`：exit 1 / **No-Go**，功能清单未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 执行证据缺失 |
| GitHub Actions | [Run 44907692817](https://github.com/naodeng/bugmaster/actions/runs/44907692817)：提交 `42850bb` 的单元 406 项中 402 通过、4 项 macOS ACL enforcement 测试在 Ubuntu 跳过；契约 80/80、安全 1/1、100% 行覆盖断言、Catalog、Benchmark 结构及品牌检查均通过 |

## 后续缺口

可信只读 reconciliation verifier、当前授权真实性/修订绑定、预算与 Journal 消费对账、未知结果的权威状态来源以及安全恢复流程仍未实现。不能因为此 helper 当前全部拒绝重放，就把 W6 或 BLK-03 标记完成。Release 维持 **No-Go**。

## 2026-11-22 复核 V-1：调用方自述字段不得打开派发与 Finding 门禁

### 审查范围

复核报告指出，`can_replay()` 已经恒拒绝，但 `can_dispatch()` 仍会因普通字典中的 `scopeValidated=True` 放行 R0/R1；`eligible_confirmed()` 也会因输入字典同时自称 E3、Oracle 已验证、执行来源/完整性已验证和因果检查通过而返回 eligible。仓库没有这三个 helper 的生产调用方，也没有可信 Scope、Approval 或 Evidence verifier。本修复不伪造 verifier，只让这些尚未接入可信验证器的辅助门禁保持 fail-closed。

### RED

- 新增 `test_self_asserted_scope_claim_cannot_dispatch_r0_or_r1`，分别用 R0、R1 和 `scopeValidated=True` 重现放行；新增 `test_self_asserted_evidence_cannot_confirm_without_a_trusted_verifier`，让 Finding、Tool Evidence 与 Oracle 的所有字段都由输入字典自述为有效。
- 在生产代码仍处于 PR #9 原 head `c8f0f6e061ed55909e656b30a125d5f9cf2042d3` 时，运行：
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py' -v`
  结果 **RED**：14 项测试中 3 个断言失败；R0、R1 的 `can_dispatch()` 都错误返回 True，`eligible_confirmed()` 也错误返回 True。

### GREEN / REFACTOR

- `can_dispatch()` 在可信 Scope/Approval verifier 接入前对所有风险等级恒返回 False。调用方传入的普通 `action`、`approval`、`policy` 字典不能证明授权或强制执行。
- `eligible_confirmed()` 在可信 Evidence/Oracle verifier 接入前始终带有 `trusted-evidence-verifier-unavailable` 阻断原因；其他质量原因仍按原逻辑收集。所有自述字段都为真时也不会确认 Finding。
- 保留现有函数签名与返回结构；`can_replay()` 继续恒返回 False。本轮没有增加生产调用方，也没有实现真实 verifier、派发或恢复。

### VERIFY

**代码/测试提交：** `e9e336b77e8e3ffb5aa42109857b8d7d436af27b`。环境：macOS / Darwin、Python 3.12.16。

| 检查 | 命令 / 结果 |
|---|---|
| Script 工具定向单测 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/unit -p 'test_script_tools.py' -v`：11/11 PASS |
| Finding/派发/重放合同 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py' -v`：14/14 PASS |
| 全量单元与覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr9-v1.coverage -m unittest discover -s tests/unit`：406/406 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/contracts`：82/82 PASS |
| 独立安全套件 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 -m unittest discover -s tests/security`：1/1 PASS |
| 行覆盖 / 分支覆盖 | `coverage report --data-file=/private/tmp/bugmaster-pr9-v1.coverage --include='bugmaster_core/*,scripts/*'`：2,138/2,138 语句、766/766 分支，分别统计，均为 100%；无未覆盖生产行或分支 |
| Catalog | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 scripts/validate_catalog.py`：PASS |
| Benchmark manifest / 品牌 / Diff | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 scripts/validate_benchmark.py` 与 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 scripts/check_branding.py` 均 PASS；`git diff --check` PASS。Benchmark 只验证清单结构，50 场景未执行 |
| Release 质量门禁 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage:/private/tmp/bugmaster-jsonschema /private/tmp/bugmaster-review-venv/bin/python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr9-v1.json`：exit 1 / **NO-GO（预期）**；功能义务清单未冻结、实测业务覆盖未超过 60%，且核心 Feature 缺少 Happy/Negative/Edge 实测证据 |
| GitHub Actions | [Run 44983997546](https://github.com/naodeng/bugmaster/actions/runs/44983997546) 在 PR #9 代码 head `e9e336b77e8e3ffb5aa42109857b8d7d436af27b` 上全部成功：单元、契约、安全、覆盖采集与 100% 行覆盖断言、Catalog、Benchmark manifest 结构、品牌检查均 PASS |
| Q15 / 合并 | PR #9 属 R3；独立真人 Security Reviewer 的正式 Q15 签署仍未记录。fail-closed helper、AI 审查与自动化门禁均不能替代签署 |

覆盖 JSON：`/private/tmp/bugmaster-pr9-v1.json`。本地结果不代表真实 API/Browser 执行、可信授权或恢复已实现；Release 仍为 **No-Go**。

## 2026-11-22：接入 PR #8 最新 Journal 身份绑定修复

PR #8 的最新 head `21ed1b9281566bb28c72f1708d40ad84cd6dce3e` 修复了 `ActionJournalStore.initialize()` 未将 Store Journal ID 与已持久化 Session `journalId` 绑定的问题。PR #9 原先停留在旧 PR #8 基线 `58a601a`；本次将最新 PR #8 head 合入 PR #9，生成提交 `d2d2d6123b3c549fea93e3a393d55660516de9bc`（tree `00f2b6ae995279fa6bf1d7e40dd5a1d8c209cc55`），保留 V-1 fail-closed 代码和负例测试。

环境：macOS / Darwin，Python 3.12.16。最新整合树验证：

| 检查 | 命令 / 结果 |
|---|---|
| Journal ID 绑定与 SessionStore 定向 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest tests.unit.test_action_journal_store.ActionJournalStoreTests.test_initialize_rejects_journal_id_mismatch_for_an_existing_session tests.unit.test_session_store -v`：131/131 PASS |
| 全单元与覆盖采集 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema:/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core,scripts --data-file=/private/tmp/bugmaster-pr9-current.coverage -m unittest discover -s tests/unit`：408/408 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：82/82 PASS |
| R3 安全测试 | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/security -v`：1/1 PASS |
| 生产行 / 分支覆盖 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage json --data-file=/private/tmp/bugmaster-pr9-current.coverage -o /private/tmp/bugmaster-pr9-current.json`；`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage report --data-file=/private/tmp/bugmaster-pr9-current.coverage --include='bugmaster_core/*,scripts/*'`：2,145/2,145 语句、768/768 分支，分别统计且均 100% |
| Catalog / 品牌 / Benchmark | `python3.12 scripts/validate_catalog.py`、`python3.12 scripts/check_branding.py`、`python3.12 scripts/validate_benchmark.py`：PASS；50 个 Benchmark 场景未执行 |
| Release Gate | `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr9-current.json`：按预期 NO-GO，Feature Inventory 未冻结、真实业务覆盖不足、核心 Happy/Negative/Edge 证据缺失 |

PR #9 整合代码 tree `00f2b6ae995279fa6bf1d7e40dd5a1d8c209cc55` 的 Actions Run `44985928795`（最新证据 head `d904e4d`）全部通过。CodeX 通用与安全辅助审查请求已提交至 d904e4d，结果待返回；旧 head 上的 AI 结论不代表当前代码。独立真人 Q15 Security Reviewer 仍未签署，V-2 至 V-6 继续标记为待验证证据或威胁模型问题。

## 2026-11-22：接入 PR #8 open() 绑定与 fail-closed gate 修复

PR #8 新 head `907f03ef017ac438f2f0dd82732789ce59257cbe` 增加公开 `ActionJournalStore.open()` 的 Session `journalId` 绑定，并让 PR #8 自身的 dispatch、replay、confirmed Finding gates 在可信验证器接入前失败关闭。PR #9 原先基于 PR #8 head `21ed1b9`；本次合入新基线，生成整合提交 `4dac5546ce2533442ce8c8afb24b4084e4e3dc38`。冲突文件按 PR #8 最终行为合并，并保留 PR #9 的全自述 replay 契约负例。

环境：macOS / Darwin，Python 3.12.16。当前整合树本地验证：

| 检查 | 结果 |
|---|---|
| 全量单元 / 契约 / 安全 | 单元 412/412、契约 82/82、安全 1/1 PASS |
| 行 / 分支覆盖 | `bugmaster_core/` 与 `scripts/` 共 2,154/2,154 语句、766/766 分支，分别统计，均 100%；覆盖 JSON：`/private/tmp/bugmaster-pr9-remediation.json` |
| 原生 macOS ACL / 清单检查 | 完整单元与验证器测试在 Darwin 上运行；其中 `chmod +a` ACL 用例实际执行。Catalog、Benchmark manifest 结构、品牌扫描及 `git diff --check` PASS；Benchmark 场景未执行 |
| Release Gate | **NO-GO（预期）**：Feature Inventory 未冻结、业务覆盖未超过 60%、核心 Happy/Negative/Edge 执行证据缺失 |
| 远端 CI | 新 PR #8/#9 head 的 Actions **待运行/核验**；本地结果不代表远端 CI 或真人 Q15 批准 |

PR #9 对 `can_dispatch()`、`can_replay()` 与 `eligible_confirmed()` 的增量仍保持 fail-closed。报告中的 V-2、V-3、V-5 为未证实的平台证据/DoS/legacy 可达性事项，V-4 属同 UID 威胁模型与测试覆盖事项，V-6 需按最终远端 head 核对 macOS 执行证据；本节不把它们记为已确认跨用户漏洞。
