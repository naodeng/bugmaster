# Candidate Assessment 增量实现 TDD 记录

**日期：** 2026-11-22
**工作流：** W3 / W7 / W9；对应既有 Feature ID `F-FINDING`、`F-DEDUP`、`F-BENCHMARK`。本记录不新增 Feature Inventory 分母或正式 TDD ID。
**验证基线 HEAD：** `336ce6277f0965c36fcbe61fbb90f50ea01ea2bf`
**工作树状态：** 本轮修改尚未提交；上述 SHA 是验证前基线，不代表本轮实现提交。

## 变更范围

- 增加 `Candidate Assessment` Schema 和纯本地筛选 helper；决策只允许 `candidate`、`needs_review`、`rejected`、`duplicate`，不会生成 `confirmed`。
- 固定拒绝原因码；候选输入格式错误、误报检查不确定、证据冲突、环境不稳定或 Oracle/Evidence 来源未验证时 fail-closed。
- `rejected` 必须有同一有效 Oracle 下的 E3+ 正常行为反证，并由可信 `oracle_verifier` 与 `evidence_verifier` 回调同时确认。仓库尚无真实 Oracle/Evidence adapter；任一 verifier 缺失或拒绝时只转 `needs_review`。测试中的 verifier 是测试替身，不是产品真实性证明。
- Review Event 追加到 Candidate revision 并绑定证据引用；本实现只更新内存副本，不认证 `reviewerId`，不提供持久化或签名身份。
- 指标分别记录候选 Precision/Recall、错误拒绝、模糊 Oracle、重复关联和人工审核时长；没有真实 Ground Truth / 工时数据时不输出正式 Eval 结论。
- 将 7 个现有 Benchmark 场景标记候选评估关注点，50 个场景仍为 `planned`，未增加总量。
- 调研真人审核责任边界与浏览器工具候选；没有接入或运行任何外部浏览器。
- 统一实施规范与治理文档中的并行开发冲突，明确一个功能 PR 完成审批并合并后再开始下一项。

## RED → GREEN

| RED 证据 | GREEN 修复与验证 |
|---|---|
| `test_candidate_assessment_cannot_be_confirmed` 在门禁缺少 Candidate Assessment 隔离时失败：候选输入被 `eligible_confirmed()` 接受 | 在 Confirmed Gate 拒绝含 `candidateAssessment` 的记录；`test_contracts.py` 13 项通过 |
| malformed `candidateAssessment` 为字符串或 `null` 时，旧 Gate 仍可能把记录当作 Confirmed Finding | 按该字段是否存在阻断，并增加两种错误序列化负例 |
| Benchmark 映射测试因 `assessmentFocus` 缺失失败（实际为 `None`，预期 `candidate-positive`） | 在既有 7 个场景加入筛选关注点；对应契约测试 14 项通过，清单仍为 50 项 |
| 正常行为反证只有 `provenanceVerified=true` 时错误得到 `rejected`；测试期望未认证来源转 `needs_review` | 加入可信 `evidence_verifier` 回调及 `EVIDENCE_PROVENANCE_UNVERIFIED` 原因码；无回调/回调拒绝时不自动拒绝 |
| `oracle.status="validated"` 的输入声明加一个正向 Evidence verifier 曾足以自动拒绝 | 加入可信 `oracle_verifier` 回调及 `ORACLE_PROVENANCE_UNVERIFIED` 原因码；Oracle 与 Evidence 两个来源都必须可信 |
| 未知误报检查值 `probably_clear` 曾被忽略并得到 `candidate` | 仅识别固定结果枚举；未知、格式错误或非对象检查输出 `needs_review`，并从输出结构剔除无效记录 |
| 重复 Candidate 在需要人工复核时被提前排除，人工审核计数为 0 | 先统计人工审核工作量，再将重复项排除出缺陷 Precision/Recall 分母 |
| Review Event 的布尔 revision、重复 Evidence 引用和指向其他 Candidate 的既有事件未被拒绝 | 严格校验 Revision 类型、Evidence 唯一性及追加前历史绑定；仅追加同一 Candidate revision 的反馈 |
| Schema 时间戳负例最初因未启用 FormatChecker 未被识别 | 契约测试启用 JSON Schema `FormatChecker`，`reviewedAt` 非 RFC3339 时间值被拒绝 |

## VERIFY

运行环境：工作树根目录；Python 3.12 临时验证环境 `/private/tmp/bugmaster-candidate-check`；验证依赖未写入产品运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| Unit + 核心覆盖率 | `python -m coverage run --branch --source=bugmaster_core -m unittest discover -s tests/unit` — PASS，182/182；`coverage report -m` — `bugmaster_core` 1272/1272 语句、544/544 分支；Candidate Assessment 212/212 语句、116/116 分支 |
| Contract | `python -m unittest discover -s tests/contracts` — PASS，92/92 |
| Benchmark 结构 | `python scripts/validate_benchmark.py` — PASS；输出明确为 `NOT executed` |
| Patch whitespace | `git diff --check` — PASS |
| Release Quality Gate | `python scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-candidate-coverage.json` — NO-GO：Feature Inventory 未冻结/无验证执行记录、业务功能覆盖未超过 60%、核心 `F-*` 缺少 Happy/Negative/Edge 执行证据 |

行覆盖和分支覆盖都达到 100%，不代表业务功能覆盖达到门槛。没有运行 API/Browser 真目标、50 个正式 Benchmark、双宿主集成或独立真人审查。

## 真人审核结论与边界

- Q7 的 Finding Review 是策略条件式，不要求所有 Candidate 都等待真人。Oracle 模糊、可信证据冲突或策略要求时转 Review。
- Q3 的 R2 动作级授权属于目标系统操作许可，不等同于 PR Reviewer。
- Q15 的 R3 Security Reviewer 有明确必要性。Q15 目前将 R2 变更也纳入独立 QR；可进一步讨论按影响面收窄，但 Q1–Q17 已冻结，本轮未修改 Q15。
- Q16 的 RI/IRR 双人批准只用于公开发布，不是每个 PR 的额外审核。远端 GitHub 分支保护与实际身份验证本轮未核验。

更完整的风险分类与工具比较见 [真人审核边界与浏览器工具调研](2026-11-22_BROWSER_TOOLING_AND_HUMAN_REVIEW_ASSESSMENT_ZH.md)。

## 剩余工作与风险

- 实现真实、可验证的 Oracle 校验与 Evidence 来源适配器之前，自动拒绝保持关闭；当前 helper 不是 Evidence Gate 的完整实现。
- Candidate/Finding 的不可变持久化、人工身份认证、Review 签署与证据留存尚未实现。
- 7 个 Benchmark 仍未执行；需要隐藏 Ground Truth 的真实 API/Browser 运行及错误拒绝/漏报统计。
- Browser 工具比较是公开文档调研；未在相同隔离环境测试安装、安全策略、会话隔离、证据导出或恢复表现。
- 全仓库 Release Gate 仍为 No-Go；不能以单测覆盖率代替业务功能覆盖或发布审核。
