# BugMaster 工程实施进度矩阵

**更新日期：** 2026-11-25
**当前状态：** PR #15 已合并到 `main`（合并提交 `d578c61`）；W1-02 已提交至 `develop`，提交 `069b1a7d30cf8cc461dbeee988758c5b1991ed1f`，并通过 [PR #16](https://github.com/naodeng/bugmaster/pull/16) 提交至 `main`，等待项目所有者审阅并手动合并。Ponytail（精简代码审查）及三轮 Codex 安全复核发现四项行终止符输入问题，均已修复并补充回归测试。最新修复后的全量测试、覆盖率和质量检查通过；最终代码复核无可执行缺陷，最终安全复核无代码问题，发现的设计文档计数歧义已更正。PR 合并前暂停后续开发。本切片只判断记录一致性，不认证来源或审核人，不授权、不派发，也不修改 `can_dispatch()` 的全风险拒绝行为。安全复核为 AI 源码复核，并非独立真人审查。W7 原始 Evidence Blob（证据原件字节）存储、可信来源适配器、浏览器运行时和真实基准评测仍未完成；完整产品仍为 Release No-Go（暂不发布）。

## 仓库审计摘要

- 当前开发工作树：`/Users/inaodeng/.codex/worktrees/w5-scope-action-gateway/bugmaster`，活动分支 `develop`，本地与远端 head 为 `069b1a7`。PR #15 已合并到 `origin/main` 的 `d578c61`。W1-02 最新修复后的全量测试、覆盖率与质量扫描、代码复核和安全复核均已完成；安全复核未发现代码问题。PR [#16](https://github.com/naodeng/bugmaster/pull/16) 已开放，等待项目所有者审阅和手动合并；该 PR 合并前不开始下一个实现切片。
- GitHub 上游：`AI-Native-QA-Lab/bugmaster`；个人项目 fork：`naodeng/bugmaster`。两者均为公开仓库，当前连接具有管理员权限。
- 仓库简介与 13 个主题标签的同步、起始提交 `cef3cb5` 推送到个人 fork（分叉仓库），均为早期历史记录；PR #13 合并提交 `5c640a21` 是治理基线，当前 `develop` 已包含 PR #15 和 W1-02 设计；W1-02 实现已由 PR #16 推送。
- 当前代码来源：用户提供的 `/Users/inaodeng/Downloads/bugmaster 2/`（128 个文件）。该 v1.1 基线采用 11 个 Discovery / Validation / Reporting（发现/验证/报告）Skill ID；旧 v1.0 的 `hunt-*` 目录不导入。
- 现有实现仍是工程起点：`bugmaster_core` 已有严格表面/范围门禁与本地 OpenAPI（开放 API 描述格式）3 静态发现；没有 URL（统一资源定位符）/Browser（浏览器）动态发现或真实 API（应用程序接口）/浏览器执行闭环。
- 16 个 Patterns 属于候选规则，50 个 Benchmark 属于计划清单；不能据此声称真实验证完成。
- 本机默认 Python 为 3.9.6；仓库 CI（持续集成）指定 Python 3.12。本轮使用 Python 3.12；固定版 `jsonschema[format-nongpl]==4.26.0`（JSON Schema 验证器）和 `coverage.py`（覆盖率工具）安装在 `/private/tmp/bugmaster-provenance-test-deps`。Candidate/Finding 存储的默认校验器依赖 `jsonschema`；该依赖由仓库开发与 CI 环境安装，产品完整打包仍未完成。
- W6 文件锁使用 POSIX `fcntl`，Windows 兼容性未验证。W6 实现及其审查修正在早期提交中推送到个人 fork；该事实不代表本轮代码已推送。

## W0–W11 进度

| 工作流 | 目标 | 状态 | 验收证据 / 下一步 |
|---|---|---|---|
| W0 | 开发基线与品牌/Skill 名称统一 | 本地检查通过 | `check_branding.py`、`validate_catalog.py`、Skill 命名契约通过；基线提交 `cef3cb5` 已推送到 fork |
| W1 | Scope（授权范围）、Surface（测试表面）、Feature（功能）、Oracle（预期行为判定依据）、Finding（缺陷记录）、Evidence（证据）、Journal（动作日志）数据契约 | 部分实现；W1-02 已进入 PR #16，等待合并 | 已有 Scope、Feature Inventory（功能清单）、Approval（审批）、Action（动作）、Event（事件）、Checkpoint（检查点）、Session（会话）、Oracle（预期行为判定依据）/Evidence（证据）和 Candidate Assessment（候选评估）契约；`validate_contract_bindings()` 完成 Scope/Action/Approval Schema（数据结构规则）校验及跨记录字段绑定。最新测试、覆盖与代码/安全复核通过。结果不认证来源/审核人、不授权或派发。Evidence 原件持久化、可信来源校验及 Confirmed Gate（缺陷确认门禁）仍未实现 |
| W2 | 11 个独立 Skill（技能包） | 本地闭包验证通过 | 11 个包均含规范 Skill/Pattern（缺陷模式）闭包且 Manifest（清单）摘要一致；Codex/Claude 干净安装和真实 Eval（评测）未验证 |
| W3 | 16 个 Bug Pattern（缺陷模式） | 候选规则 | 需适用/排除条件、Oracle（预期行为判定依据）、反例和真实对照评测 |
| W4 | 风险路由与有界自主探索 | 部分实现 | `scripts/discover_openapi.py` 可从本地 OpenAPI（开放 API 描述格式）3 JSON 输出稳定 ID 和 JSON Pointer（JSON 指针）来源清单；URL（统一资源定位符）/Browser（浏览器）发现、风险路由与动态执行仍待实现 |
| W5 | R0–R3 风险级别动作授权 | fail-closed（失败时保持阻断） | `scripts/validate_gates.py` 的 `can_dispatch()` 对所有风险等级恒拒绝。W1-02 的绑定一致结果不构成授权；真实范围解析、可信审批网关、审批时效与身份认证、宿主执行控制仍待实现 |
| W6 | Action Journal（动作日志）、Session（会话）/Checkpoint（检查点）持久化与安全恢复 | 部分实现 | 早期 PR #9 与 PR #11 已合入个人仓库 `main`；PR #11 增加待对账 Action（动作）枚举与进程崩溃验证。V-2 至 V-6 仍待核验。可信授权、事件来源真实性、预算对账和安全恢复授权未实现。 |
| W7 | Finding（缺陷记录）、跨入口去重与报告 | 部分实现：候选评估 + Oracle/Evidence 绑定 + Candidate/Finding 元数据存储 | Candidate Assessment（候选评估）辅助函数仍只生成 `candidate`、`needs_review` 或暂定 `duplicate`。PR #14 已加入 Oracle（预期行为判定依据）来源字节、Evidence（证据）制品摘要、精确 Oracle 版本与 Action Journal（动作日志）结果引用绑定；本切片实现提交 [`1a86eea`](https://github.com/naodeng/bugmaster/commit/1a86eeabffad401df3f5e1f484c856e548a10360) 新增 Candidate（候选记录）/Finding（缺陷记录）私有本地元数据持久化、不可变修订和摘要链。以上仍不认证来源/审核人、不保存证据原件字节、不验证外部引用、不抑制规范重复项，也不解锁 `Confirmed Gate`（缺陷确认门禁）；报告、真实可信来源适配器和审核身份认证仍待实现 |
| W8 | 回归建议 | 待实现 | 只输出建议，不自动修改/提交测试代码 |
| W9 | 50 场景 Benchmark（基准评测） | 计划细化，仍未执行 | 保持 50 总数；7 个既有 API（应用程序接口）/UI（用户界面）场景映射候选正例、可信正常反证、模糊 Oracle、模型与执行矛盾、错误拒绝风险、人工反馈、跨表面去重；Manifest（清单）仍为 `planned`（计划中），需隔离 Ground Truth（真实结论）并进行 G0–G3 对照实验 |
| W10 | Codex 与 Claude Code 双宿主验证 | 未验证 | W10-02 首项交付为浏览器工具比较与选型记录；满足 W5-02/W7-02/W9-02 依赖后，再跑两宿主真实安装和 API（应用程序接口）/Browser（浏览器）权限测试 |
| W11 | 发布治理 | 部分实施 | PR #13 已确立 Q15（逐 PR 代码扫描、R2/R3 变更增加安全扫描）与项目所有者手动确认/合并；Q16（正式发布双人授权）和供应链证据仍待落实。完整 Release（正式发布）为 No-Go（暂不发布） |

## 质量状态

| 门禁 | 当前状态 | 说明 |
|---|---|---|
| 品牌与 Skill 命名扫描 | PASS（通过） | `python3 scripts/check_branding.py`；命名契约包含 4 项 Skill ID 检查 |
| Catalog（目录）/Registry（注册表） | PASS（通过） | `python3 scripts/validate_catalog.py` |
| Benchmark Manifest（基准评测清单） | PASS（结构） | `validate_benchmark.py` 明确提示场景未执行 |
| PR #15 合并前 W7 定向单元测试 | PASS（通过，33/33 + 83/83） | `test_provenance.py` 与 `test_action_journal.py`；只代表当时两个定向测试文件 |
| W7 历史 Candidate/Finding 存储定向单元测试 | PASS（通过，83/83） | `tests/unit/test_metadata_store.py`；含校验器不可变性、身份/审核事件/证据绑定、整数归一化和本地文件系统边界 |
| W7 历史 Candidate Assessment 定向单元测试 | PASS（通过，59/59） | `tests/unit/test_candidate_assessment.py`；含规范 ID 拒绝、嵌套引用处理和审核事件绑定 |
| PR #15 合并前 W7 完整单元测试 | PASS（通过，615/615） | Python 3.12，固定测试依赖位于 `/private/tmp/bugmaster-provenance-test-deps`；不是当前 W1-02 验证 |
| PR #15 合并前 W7 Schema 契约测试 | PASS（通过，129/129） | Python 3.12 + `jsonschema[format-nongpl]==4.26.0`；包含 Candidate/Finding Schema；不是当前 W1-02 验证 |
| PR #15 合并前 W7 安全测试 | PASS（通过，1/1） | `tests/security`；不代替 Q15 源码安全扫描，也不是当前 W1-02 验证 |
| PR #15 合并前 W7 行/分支覆盖 | PASS（通过，100% / 100%） | `bugmaster_core` 与 `scripts`：3057/3057 语句、1096/1096 分支；覆盖数据 `/private/tmp/bugmaster-w7-finding-metadata-final.coverage`；不是当前 W1-02 验证 |
| 本分支发布质量门禁 | NO-GO（预期） | `quality_gate.py --mode release`：功能清单未冻结、业务覆盖未超过 60%、核心功能缺少 Happy（成功）/Negative（失败）/Edge（边界）场景的执行证据；不是本切片测试失败 |
| PR #13 合并前验证（历史） | PASS | 准确 head `d6602dd`：单元 488/488、契约 96/96、安全测试 1/1、行/分支覆盖 2384/2384 与 880/880；Actions Run `45019266106` 全部通过。这些结果不包含当前 W7 改动 |
| PR #13 Q15 代码/安全扫描（历史） | PASS | PR 描述记录的 Codex 代码复扫与安全复核针对 `d6602dd`；属于 AI 扫描结果，不代表独立真人安全复核，也不覆盖当前 W7 改动 |
| PR #14 GitHub 拉取请求 / GitHub Actions（自动化检查） | PASS（通过，已合并） | [PR #14](https://github.com/naodeng/bugmaster/pull/14)；[运行 #116](https://github.com/naodeng/bugmaster/actions/runs/45107658770) 单元、契约、安全、覆盖率、目录、基准清单结构与品牌校验全部成功；合并提交 `e594946ca4d823c044897c000c1975a7301631c7` |
| PR #14 Q15 Codex 代码扫描/安全复核 | PASS（历史） | 扫描针对 PR #14；静态 AI 安全复核不代表独立真人审查，也不覆盖当前 Candidate/Finding 切片 |
| W7 Candidate/Finding 历史定向单元/契约测试 | PASS（通过） | 存储单测 83/83、候选评估单测 59/59、全量契约 129/129；证据见 [W7 元数据持久化 TDD 记录](2026-11-23_W7_CANDIDATE_FINDING_METADATA_TDD_ZH.md) |
| W7 Candidate/Finding 历史 Q15 代码/安全审查 | PASS（历史） | `codex review --uncommitted` 未发现可执行缺陷；需求与编码规范双轴复核及聚焦安全复核未发现阻断项；结果只针对 W7 变更 |
| W7 切片独立真人安全复核 | 未进行 | W7 未认证来源或审核人、未改动作授权或 Confirmed Gate；后续跨入上述边界时，按项目所有者要求先单独讨论真人复核范围 |
| W1-02 最新修复前全量验证 | PASS（通过，非最终） | 单元 638/638、契约 132/132、安全 1/1；`bugmaster_core` 与 `scripts` 行/分支覆盖 100%（3157/3157 条语句，1150/1150 条分支）；不含 Action.createdAt 新增回归用例 |
| W1-02 最新修复后验证 | PASS（通过） | 单元 639/639、契约 134/134、安全 1/1；行/分支覆盖 3159/3159 与 1152/1152（均 100%）；品牌、目录和 Benchmark（基准评测）结构扫描通过；Release（正式发布）门禁按预期 NO-GO，详见 [W1-02 契约绑定 TDD 记录](2026-11-25_W1_APPROVAL_EXECUTION_BINDING_TDD_ZH.md) |
| 当前 W1-02 代码/安全复核 | PASS（通过） | Codex 代码复核未发现可执行缺陷；最终安全复核未发现代码问题，文档计数歧义已修复。Approval 不绑定 surface（测试表面）的目标粒度作为未来可信网关设计事项记录。Codex 安全复核不是独立真人审查。详见 [W1-02 契约绑定 TDD 记录](2026-11-25_W1_APPROVAL_EXECUTION_BINDING_TDD_ZH.md) |
| W1-02 发布质量门禁 | NO-GO（预期） | 真实功能清单尚未冻结，功能执行证据未超过 60%，核心功能缺少实际 Happy（成功）/Negative（失败）/Edge（边界）场景；不影响本切片定向实现测试通过，产品仍不可发布 |
| 历史单元测试与覆盖率 | 仅作历史参考 | 早期 PR #10 / Candidate Assessment 整合结果为 474/474、96/96 和 100% 行/分支覆盖；基线与范围均不同于当前 W7 工作树，不作为本轮门禁 |
| 业务功能覆盖率 >60% | 未达成 | 目前没有真实业务执行证据 |
| 核心 Happy（成功）/Negative（失败）/Edge（边界）场景 | 未达成 | 每个核心功能都需这三类场景的实际通过证据 |
| Release | No-Go | 全量功能、真实 Benchmark、双宿主和独立审批均未完成 |

历史发布质量门禁记录：PR #10 整合代码树 `af0e751902f230ef5e8035a51c845f5d14ab8ace` 使用覆盖 JSON `/private/tmp/bugmaster-pr10-final.json` 运行 `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-final.json`，结果为 No-Go（不满足发布门槛）：Feature Inventory（功能清单）未冻结、真实业务覆盖未超过 60%，核心 Feature（功能）的 Happy（成功）/Negative（失败）/Edge（边界）场景执行证据缺失。该历史 Benchmark（基准评测）仅检查清单结构，50 个场景未执行。

初始验证的命令与实际输出记录在 [基线验证记录](2026-11-18_INITIAL_BASELINE_VERIFICATION_ZH.md)。Scope 风险辅助函数、本地 OpenAPI 静态发现 CLI（命令行工具）、Scope/Approval/Action Schema、Session Schema、R2 缺少可信审批网关时拒绝派发和 W6-04 重放门禁的 RED/GREEN/REFACTOR/VERIFY 证据分别见 [范围与风险门禁 TDD 记录](2026-11-18_SCOPE_GATE_TDD_ZH.md)、[OpenAPI 发现 TDD 记录](2026-11-18_OPENAPI_DISCOVERY_TDD_ZH.md)、[Scope Schema TDD 记录](2026-11-18_SCOPE_SCHEMA_TDD_ZH.md)、[Approval 与 Action Schema TDD 记录](2026-11-18_APPROVAL_ACTION_SCHEMA_TDD_ZH.md)、[Session Schema TDD 记录](2026-11-19_SESSION_SCHEMA_TDD_ZH.md)、[R2 门禁 TDD 记录](2026-11-18_R2_GATE_TDD_ZH.md)、[Session Revision 持久化 TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md)、[Checkpoint 跨存储引用 TDD 记录](2026-11-19_CHECKPOINT_REFERENCE_VALIDATION_TDD_ZH.md)、[回放门禁 fail-closed TDD 记录](2026-11-19_REPLAY_GATE_FAIL_CLOSED_TDD_ZH.md)、[Candidate Assessment（候选评估）](2026-11-22_CANDIDATE_ASSESSMENT_TDD_ZH.md) 和 [Oracle/Evidence 本地绑定切片](2026-11-23_W7_ORACLE_EVIDENCE_PROVENANCE_TDD_ZH.md)。人工审核与浏览器工具调研见 [审核边界与浏览器工具调研](2026-11-22_BROWSER_TOOLING_AND_HUMAN_REVIEW_ASSESSMENT_ZH.md)。

11 个独立包的离线构建/闭包/摘要核验见 [Standalone 打包验证记录](2026-11-18_STANDALONE_PACKAGING_VERIFY_ZH.md)。

## 执行顺序

1. 运行基线静态检查、单元/契约测试与当前质量门禁，记录真实输出。
2. PR #15 已合并。W1-02 已通过 PR #16 从 `develop` 提交至 `main`；等待项目所有者审阅并手动合并，合并前暂停后续开发，不叠加第二个 PR。实现证据见 [W1-02 契约绑定 TDD 记录](2026-11-25_W1_APPROVAL_EXECUTION_BINDING_TDD_ZH.md)。
3. W1-02 合并后继续浏览器探索工具调研：先完善人工审核边界与浏览器工具对照文档，再按 W5/W7/W9 依赖评估隔离 Order Demo（订单演示项目）同场对照和运行时实现。凡涉及真实来源认证、审核身份、动作授权或 Confirmed Gate（缺陷确认门禁）的变更，先与项目所有者讨论是否需独立真人安全复核。
4. 每次只推进一个功能 PR；每轮更新本矩阵和独立中文 TDD 记录。不得将内部纵向切片作为缩水 MVP 对外发布。

