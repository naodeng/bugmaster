# Candidate Assessment 增量实现 TDD 记录

**日期：** 2026-11-22
**工作流：** W3 / W7 / W9；对应既有 Feature ID `F-FINDING`、`F-DEDUP`、`F-BENCHMARK`。本记录不新增 Feature Inventory 分母或正式 TDD ID。
**验证基线 HEAD：** `336ce6277f0965c36fcbe61fbb90f50ea01ea2bf`
**实现提交：** `6f122d1`（基于 PR #10 合并分支 `1f974bc` 重放）

## 变更范围

- 增加 `Candidate Assessment` Schema 和纯本地筛选 helper；Schema 决策允许 `candidate`、`needs_review`、`rejected`、`duplicate`，不会生成 `confirmed`。2026-11-22 所有者复核后，当前运行时仅输出 `candidate`、`needs_review` 或 `duplicate`；Schema 的 `rejected` 仅为未来 Host verifier 集成保留。
- 固定拒绝原因码；候选输入格式错误、误报检查不确定、证据冲突、环境不稳定或 Oracle/Evidence 来源未验证时 fail-closed。
- 初始实现曾用调用方传入的 `oracle_verifier` 与 `evidence_verifier` 回调控制 `rejected`；经安全复核发现调用方可自行提供恒真回调。所有者已决定在可信 Host verifier 集成前关闭自动 `rejected`；当前 API 不接受调用方 verifier 回调，结构有效的反证会保持 `needs_review`。
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
| 正常行为反证只有 `provenanceVerified=true` 时曾错误得到 `rejected` | 初始实现添加 Evidence verifier 回调；2026-11-22 安全复核发现调用方可自带回调，所有者决定移除回调入口并关闭自动拒绝 |
| `oracle.status="validated"` 加调用方自带的恒真回调曾足以自动拒绝 | 当前 helper 不接受 verifier 回调；结构反证始终产生 `needs_review` 和来源未验证原因码，直到可信 Host verifier 接入 |
| 未知误报检查值 `probably_clear` 曾被忽略并得到 `candidate` | 仅识别固定结果枚举；未知、格式错误或非对象检查输出 `needs_review`，并从输出结构剔除无效记录 |
| 重复 Candidate 在需要人工复核时被提前排除，人工审核计数为 0 | 先统计人工审核工作量，再将重复项排除出缺陷 Precision/Recall 分母 |
| Review Event 的布尔 revision、重复 Evidence 引用和指向其他 Candidate 的既有事件未被拒绝 | 严格校验 Revision 类型、Evidence 唯一性及追加前历史绑定；仅追加同一 Candidate revision 的反馈 |
| Schema 时间戳负例最初因未启用 FormatChecker 未被识别 | 契约测试启用 JSON Schema `FormatChecker`，`reviewedAt` 非 RFC3339 时间值被拒绝 |

## VERIFY

运行环境：工作树根目录；Python 3.12 临时验证环境 `/private/tmp/bugmaster-candidate-check`；验证依赖未写入产品运行时依赖。

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

固定复核基线：`origin/main`，提交 `f97ca8fb002f17e51986b91269a3df0556cd63a6`；复核范围为该基线到当前 `develop` 工作树的完整差异（含暂存文件）。

| 检查 | 结果 | 证据与边界 |
|---|---|---|
| CodeX 代码扫描：Standards / Spec | PASS | 两轴均未发现未解决的代码规范违规或需求实现缺陷。Standards 指出的 VERIFY 证据缺口已在本表补记。 |
| CodeX 安全扫描 | PASS（源码审查） | 未发现当前可确认的漏洞；重点检查 Candidate 输入、Oracle/Evidence 来源、拒绝决策、Review Event 和 Confirmed Gate。此项为只读源码扫描，未执行目标代码。 |
| 本地全量单元、契约、安全测试与覆盖率 | NOT_RUN | 当前本机沙箱无法同时强制安全审查要求的累计磁盘配额等隔离限制，因此没有在本机执行目标测试代码。提交后的 GitHub Actions 必须对准确 PR head 执行这些工作流；其结果在 PR 记录。 |
| 本地差异空白检查 | PASS | `git diff --cached --check`，当前工作树；未报告空白错误。 |
| PR Actions | PENDING | 尚未在远端 PR head 执行。仅在准确 head 的所需 Actions 全部成功后合并。 |

扫描命令的固定点与结论按本节记录；GitHub Actions 的提交 SHA、Run 链接和结果在 PR 中补充。Release Gate 仍按真实业务覆盖和执行证据单独判定，现有 Release 状态保持 No-Go。
