# Candidate Assessment 增量实现 TDD 记录

**日期：** 2026-11-22
**工作流：** W3 / W7 / W9；对应既有 Feature ID `F-FINDING`、`F-DEDUP`、`F-BENCHMARK`。本记录不新增 Feature Inventory 分母或正式 TDD ID。
**历史功能初始基线：** `336ce6277f0965c36fcbe61fbb90f50ea01ea2bf`
**本轮 PR 基线：** `f97ca8fb002f17e51986b91269a3df0556cd63a6`（`origin/main`）
**实现来源：** 原始实现提交 `6f122d1` 位于 `develop@513c107d4d51aa8b8359261ab340d4f1c3383c00` 的提交历史中；最终 PR 从 `main` 重新应用文件差异，不迁移原分支历史。`1f974bc` 不是该 `main` 基线的祖先；本 PR 不包含 W6 Journal 生产代码或相关测试的差异。

## 变更范围

- 增加 `Candidate Assessment` Schema 和纯本地筛选 helper；Schema 决策允许 `candidate`、`needs_review`、`rejected`、`duplicate`，不会生成 `confirmed`。2026-11-22 所有者复核后，当前运行时仅输出 `candidate`、`needs_review` 或 `duplicate`；Schema 的 `rejected` 仅为未来 Host verifier 集成保留。
- 固定拒绝原因码；缺少/结构无效的 Oracle 或 Evidence、误报检查不确定、证据冲突及环境不稳定时转 `needs_review`。
- `candidate` 与 `duplicate` 是根据调用方输入作出的本地暂定筛选结果。当前 helper 不认证 Oracle/Evidence 来源标志，也不从规范存储验证 `duplicate_of`；Host 在确认来源或据此抑制/汇总记录前必须完成这些校验。任何 Candidate Assessment 均不能通过 Confirmed Gate。
- 初始实现曾用调用方传入的 `oracle_verifier` 与 `evidence_verifier` 回调控制 `rejected`；经安全复核发现调用方可自行提供恒真回调。所有者已决定在可信 Host verifier 集成前关闭自动 `rejected`；当前 API 不接受调用方 verifier 回调，结构有效的反证会保持 `needs_review`。
- Review Event 追加到 Candidate revision 并绑定证据引用；本实现只更新内存副本，不认证 `reviewerId`，不提供持久化或签名身份。
- 指标分别记录候选 Precision/Recall、错误拒绝、模糊 Oracle、重复关联和人工审核时长；没有真实 Ground Truth / 工时数据时不输出正式 Eval 结论。
- 将 7 个现有 Benchmark 场景标记候选评估关注点，50 个场景仍为 `planned`，未增加总量。
- 调研真人审核责任边界与浏览器工具候选；没有接入或运行任何外部浏览器。
- 统一实施规范与治理文档中的并行开发冲突，明确一个功能 PR 完成审批并合并后再开始下一项。

## RED → GREEN

**历史证据说明：** 下表中初始功能阶段的行为描述来自当时开发记录；当前仓库未保留全部原始失败日志、测试命令、环境和精确 SHA，因此这些行只作为历史问题与实现摘要，不算可复核的 RED 证据，也不据此声称初始开发的 TDD 记录完整。本轮 PR 审查发现的缺陷均补了测试优先的 RED/GREEN 记录。

| RED 证据 | GREEN 修复与验证 |
|---|---|
| `test_candidate_assessment_cannot_be_confirmed` 在门禁缺少 Candidate Assessment 隔离时失败：候选输入被 `eligible_confirmed()` 接受 | 在 Confirmed Gate 拒绝含 `candidateAssessment` 的记录；`test_contracts.py` 13 项通过 |
| malformed `candidateAssessment` 为字符串或 `null` 时，旧 Gate 仍可能把记录当作 Confirmed Finding | 按该字段是否存在阻断，并增加两种错误序列化负例 |
| Benchmark 映射测试因 `assessmentFocus` 缺失失败（实际为 `None`，预期 `candidate-positive`） | 在既有 7 个场景加入筛选关注点；对应契约测试 14 项通过，清单仍为 50 项 |
| 正常行为反证只有 `provenanceVerified=true` 时曾错误得到 `rejected` | 初始实现添加 Evidence verifier 回调；2026-11-22 安全复核发现调用方可自带回调，所有者决定移除回调入口并关闭自动拒绝 |
| `oracle.status="validated"` 加调用方自带的恒真回调曾足以自动拒绝 | 当前 helper 不接受 verifier 回调；结构反证始终产生 `needs_review` 和来源未验证原因码，直到可信 Host verifier 接入 |
| PR #12 代码审查：候选自己的 `evidenceRefs` 同时链接 E3+ `violated` 与 `satisfied` 观测，但未传单独 `counter_evidence` 时仍得到 `candidate`；Review Event 引用单独链接的 counter-evidence 时因尚未合并引用而抛出 `review-event-evidence-invalid` | 新增 `test_conflicting_observations_in_candidate_evidence_require_review` 与 `test_review_event_can_reference_counterevidence`；先合并全部证据引用再校验 Review Event，并将候选自身已链接的满足观测纳入冲突判定 |
| 未知误报检查值 `probably_clear` 曾被忽略并得到 `candidate` | 仅识别固定结果枚举；未知、格式错误或非对象检查输出 `needs_review`，并从输出结构剔除无效记录 |
| 重复 Candidate 在需要人工复核时被提前排除，人工审核计数为 0 | 先统计人工审核工作量，再将重复项排除出缺陷 Precision/Recall 分母 |
| Review Event 的布尔 revision、重复 Evidence 引用和指向其他 Candidate 的既有事件未被拒绝 | 严格校验 Revision 类型、Evidence 唯一性及追加前历史绑定；仅追加同一 Candidate revision 的反馈 |
| Schema 时间戳负例最初因未启用 FormatChecker 未被识别 | 契约测试启用 JSON Schema `FormatChecker`，`reviewedAt` 非 RFC3339 时间值被拒绝 |

### 本轮 PR 评论修复的可复核 RED/GREEN 证据

- **RED 固定点：** `f97ca8fb002f17e51986b91269a3df0556cd63a6`；当时仅测试文件有未提交改动，生产代码未改。
- **RED 环境与命令：** Python 3.12.16；`python3.12 -m unittest discover -s tests/unit -p 'test_candidate_assessment.py' -k conflicting_observations_in_candidate_evidence -k review_event_can_reference_counterevidence -v`。
- **RED 结果：** `test_conflicting_observations_in_candidate_evidence_require_review` 失败（实际 `candidate`，预期 `needs_review`）；`test_review_event_can_reference_counterevidence` 抛出 `ValueError: review-event-evidence-invalid`；共 2 项，1 failure、1 error。
- **GREEN 环境与命令：** 同一 Python 3.12.16 临时干净工作树，生产修复后重复同一命令；2/2 PASS。
- **GREEN 回归：** Candidate Assessment 单测 45/45 PASS；Schema 契约 11/11 PASS。完整验证见 VERIFY 表。

### 最终代码审查追加发现的 RED/GREEN

- **RED 固定点：** `fa1a7d5fc4e51f072fcb0598088f8ac798e602f3`；仅测试文件有未提交改动。
- **RED 环境与命令：** Python 3.12.16；`/private/tmp/bugmaster-candidate-check/bin/python -m unittest discover -s tests/unit -p 'test_candidate_assessment.py' -k candidate_quality_rejects_unknown_values -v` — `TypeError: unhashable type: 'list'`。同环境执行 `... -k review_event_rejects_invalid_review_record_shape -v`，两种非法 review 对象均未抛出预期 `ValueError`。
- **GREEN：** 先校验评分枚举输入为字符串，并要求 review 对象精确包含布尔 `required` 与 `events`；上述两个定向测试各 1/1 PASS，Candidate Assessment 单测 46/46 PASS，Schema 契约 11/11 PASS。

## REFACTOR

- Review Event 历史复用 `append_review_event()` 的绑定、时间戳和引用校验路径；没有为这一小段确定性 helper 增加额外抽象。
- 合并 PR #10 后的目标单测与契约测试分别为 474/474 与 96/96 PASS；本轮安全修复的定向单元与 Schema 契约复跑为 40/40 与 11/11 PASS。
- 本轮两个 PR 评论修复仅调整证据引用合并次序及候选证据冲突判断，没有引入新的抽象；修复后 45 项 Candidate Assessment 单测通过。

## VERIFY

运行环境：Python 3.12 临时验证环境 `/private/tmp/bugmaster-candidate-check`；`PY=/private/tmp/bugmaster-candidate-check/bin/python`；验证依赖未写入产品运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| Candidate 初始单测与核心覆盖率（基线 `336ce627`） | `python -m coverage run --branch --source=bugmaster_core -m unittest discover -s tests/unit` — PASS，182/182；`coverage report -m` — `bugmaster_core` 1272/1272 语句、544/544 分支；Candidate Assessment 212/212 语句、116/116 分支 |
| Candidate 初始契约测试（基线 `336ce627`） | `python -m unittest discover -s tests/contracts` — PASS，92/92 |
| Benchmark 结构 | `python scripts/validate_benchmark.py` — PASS；输出明确为 `NOT executed` |
| Patch whitespace | `git diff --check` — PASS |
| Release Quality Gate | `python scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-candidate-coverage.json` — NO-GO：Feature Inventory 未冻结/无验证执行记录、业务功能覆盖未超过 60%、核心 `F-*` 缺少 Happy/Negative/Edge 执行证据 |
| PR #10 基线整合后复核 | `python -m coverage run --branch --source=bugmaster_core -m unittest discover -s tests/unit` — PASS，474/474；`coverage report -m` — 2198/2198 语句、824/824 分支；Candidate Assessment 212/212 语句、116/116 分支；`python -m unittest discover -s tests/contracts` — PASS，96/96 |
| 品牌、Catalog、Benchmark 与差异检查 | `scripts/check_branding.py`、`scripts/validate_catalog.py`、`scripts/validate_benchmark.py` 和 `git diff origin/codex/replay-gate-fail-closed...HEAD --check` — PASS；Benchmark 场景明确为 NOT executed |
| 整合后 Release Quality Gate | `python scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-candidate-final-coverage.json` — NO-GO：Feature Inventory 未冻结、真实业务覆盖未超过 60%、核心 `F-*` 的 Happy/Negative/Edge 执行证据缺失 |

行覆盖和分支覆盖都达到 100%，不代表业务功能覆盖达到门槛。没有运行 API/Browser 真目标、50 个正式 Benchmark 或双宿主集成。Q15 按项目所有者 2026-11-22 的决定执行 CodeX 代码扫描及 R2/R3 安全扫描；不要求独立真人 Q15 签署。

## 真人审核结论与边界

- Q7 的 Finding Review 是策略条件式，不要求所有 Candidate 都等待真人。Oracle 模糊、可信证据冲突或策略要求时转 Review。
- Q3 的 R2 动作级授权属于目标系统操作许可，不等同于 PR Reviewer。
- Q15 项目所有者决定：每个 PR 做 CodeX 代码扫描；R2/R3 变更加做安全扫描；所有者查看结果后手动合并，不要求独立真人 Q15 签署。
- Q16 的 RI/IRR 双人批准只用于公开发布，不是每个 PR 的额外审核。远端 GitHub 分支保护与实际身份验证本轮未核验。

更完整的风险分类与工具比较见 [真人审核边界与浏览器工具调研](2026-11-22_BROWSER_TOOLING_AND_HUMAN_REVIEW_ASSESSMENT_ZH.md)。

## 剩余工作与风险

- 实现真实、可信的 Host Oracle/Evidence verifier 之前，自动拒绝保持关闭；当前 helper 不是 Evidence Gate 的完整实现。
- Candidate/Finding 的不可变持久化、人工身份认证、Review 签署与证据留存尚未实现。
- 7 个 Benchmark 仍未执行；需要隐藏 Ground Truth 的真实 API/Browser 运行及错误拒绝/漏报统计。
- Browser 工具比较是公开文档调研；未在相同隔离环境测试安装、安全策略、会话隔离、证据导出或恢复表现。
- 全仓库 Release Gate 仍为 No-Go；不能以单测覆盖率代替业务功能覆盖或发布审核。

## 2026-11-22 所有者决策与安全修复

项目所有者选择：可信 Host verifier 接入前关闭自动 `rejected`。安全复核发现 `assess_candidate()` 曾允许调用方传入任意 Oracle/Evidence verifier 回调；恒真回调可将调用方自述的反证转为 `rejected`。仓库没有生产调用方或真实 verifier，未发现该路径能生成 Confirmed Finding，但当前接口会过度声称反证可信。

### RED → GREEN

| RED | GREEN |
|---|---|
| `python3.12 -m unittest discover -s tests/unit -p 'test_candidate_assessment.py' -k caller_supplied_verifiers -v`：2 项行为失败；恒真调用方回调得到 `rejected`，且回调参数未被拒绝 | 移除公开 helper 的调用方 verifier 参数；反证总是附带来源未验证原因并停留在 `needs_review`；Schema 保留 `rejected` 供未来 Host 集成，静态 rejected JSON 仅作为 Schema fixture |

### 定向验证

- Python 3.12 Candidate Assessment 单元：40/40 PASS。
- 临时验证环境 `/private/tmp/bugmaster-candidate-check` 的 Candidate Assessment Schema 契约：11/11 PASS。
- Q15 当前规则：对准确 PR head 执行 CodeX 代码扫描；R2/R3 再执行安全扫描；项目所有者查看后手动合并，不要求独立真人 Q15 签署。Q16 两人正式发布授权保持不变。

### 合入前复核与验证状态

固定复核基线：`origin/main`，提交 `f97ca8fb002f17e51986b91269a3df0556cd63a6`；PR 候选从该基线重建为独立分支，最终 head 与 Actions 链接在 PR body 中记录。此前 `develop` 的 PR #10 merge commit `1f974bc` 不属于该基线历史；W6 Journal 生产文件与崩溃测试的基线差异为空。

| 检查 | 结果 | 证据与边界 |
|---|---|---|
| CodeX 代码扫描（预修复 head `cfcec1b`） | FINDINGS_FIXED，待最终复扫 | Spec 发现 extra `identity` 可导致输出违反 Schema，以及非列表 `reviewEvents` 被静默丢弃；后续按 RED → GREEN 修复。分支 ancestry 检查确认 `1f974bc` 不是基线 `f97ca8f` 的祖先；最终 PR 已从 `f97ca8f` 重建，避免带入原分支提交历史。 |
| CodeX 安全扫描（预修复 head `cfcec1b`） | 无已确认安全漏洞 | 源码扫描确认 `candidate` / `duplicate` 只是暂定结果，不绕过 Confirmed Gate；未来 Host 需核验来源与规范重复引用。此项为只读扫描，未执行目标代码。 |
| 本地全量单元、契约、安全测试与覆盖率（code fix commit `b6c029bec4c96b8e085887fc10a42d1e8f470abd`） | PASS | Python 3.12.16 临时环境 `/private/tmp/bugmaster-candidate-check`。命令：`$PY -m unittest discover -s tests/unit`、`$PY -m unittest discover -s tests/contracts`、`$PY -m unittest discover -s tests/security`，结果分别 484/484、96/96、1/1 PASS。覆盖：`COVERAGE_FILE=/private/tmp/bugmaster-final-clean.coverage $PY -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit`，之后运行 `coverage json -o /private/tmp/bugmaster-final-clean-coverage.json`、`coverage report -m` 和 100% 行断言，结果 2377/2377 行、878/878 分支。Catalog、Benchmark Manifest、Branding 与 `git diff --check` 均 PASS；Benchmark 明确为 NOT executed。 |
| 本地差异空白检查 | PASS | `git diff --check`，修复工作树；未报告空白错误。 |
| PR #12 首次 Actions（head `bc40b929`，Run `45012754683`） | FAIL（覆盖率） | 单元 477 项运行、4 项跳过且无失败；契约 96/96、security 1/1 通过。覆盖率为 2374/2375 行、877/878 分支；唯一缺行为 `scripts/validate_gates.py:7`。后续清单步骤因门禁失败而跳过。 |
| 覆盖率修复（head `d65f5b4`，Run `45013082076`） | PASS | 增加 unit 行为断言覆盖 `candidateAssessment: null` 的字段存在分支。单元 478 项运行、4 项跳过且无失败；契约 96/96、安全 1/1、行覆盖率门禁及 Catalog/Benchmark/Branding 均通过。该工作流当时未将分支百分比打印到日志。 |
| 分支覆盖率报告（head `cfcec1b`，Run `45013316053`） | PASS | 单元 478 项运行、4 项跳过；契约 96/96、安全 1/1；行覆盖 `2375/2375`、分支覆盖 `878/878`。Catalog、Benchmark Manifest、Branding 均 PASS。 |
| Malformed input RED（head `d17c219`，Run `45014132903`） | RED（预期） | unit 480 项运行，新增两项均按预期失败：额外 identity 字段仍进入输出，非列表 `reviewEvents` 被静默忽略。其他测试流程因单测失败跳过。 |
| Schema identity / review history 修复后的 Actions（head `513c107d4d51aa8b8359261ab340d4f1c3383c00`，Run `45014768396`） | PASS（非最终 PR head） | Python 3.12；单元 481 项运行、4 项跳过；契约 96/96、安全 1/1；行覆盖 2376/2376、分支覆盖 878/878；Catalog、Benchmark Manifest、Branding 均 PASS。该运行不包含本轮 PR 评论修复。 |
| PR #12 审查评论 RED（临时干净分支基线 `f97ca8fb002f17e51986b91269a3df0556cd63a6`，仅测试文件有未提交测试改动） | RED（预期） | `python3.12 -m unittest discover -s tests/unit -p 'test_candidate_assessment.py' -k conflicting_observations_in_candidate_evidence -k review_event_can_reference_counterevidence -v` — 2 项失败：第一项得到 `candidate` 而非 `needs_review`；第二项抛出 `ValueError: review-event-evidence-invalid`。 |
| PR #12 审查评论 GREEN（同一临时分支，生产修复后） | PASS | 同一 Python 3.12 命令 — 2/2 PASS；完整 Candidate Assessment 单测 45/45 PASS；Schema 契约 11/11 PASS；`git diff --check` PASS。 |
| 首轮 CodeX Spec 扫描发现项（head `fa1a7d5`） | FIXED | unhashable `groundTruth` / `decision` 会抛出 `TypeError`；Review Event 追加会保留 Schema 无效的 `review` 对象。均在 `b6c029b` 修复，新增负例并通过 full unit/coverage。 |
| CodeX Security 扫描（head `fa1a7d5`） | PASS，无已确认漏洞 | 只读源码扫描；Candidate Assessment 结果保持暂定，counter-evidence 不自动拒绝，也不能通过 Confirmed Gate。Host 来源认证、规范重复引用验证及 reviewer 身份认证仍待集成；最终 head 复扫待完成。 |
| 当前开发记录、最终 PR Actions 和 CodeX 双扫描 | PENDING | 历史 RED 原始证据未完整保留，已如实标注为历史摘要；当前 PR 评论及代码扫描发现均有可复核 RED/GREEN。最终 Actions 与双扫描需绑定最终 PR head 后再合并。 |

扫描命令的固定点与结论按本节记录；本 PR 由 `main@f97ca8f` 重建，不包含 `1f974bc` 作为祖先提交。PR 最终 head 的 GitHub Actions 与 Q15 扫描结果须在本记录补充。Release Gate 仍按真实业务覆盖和执行证据单独判定，现有 Release 状态保持 No-Go。
