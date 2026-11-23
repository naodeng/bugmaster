# BugMaster 工程实施进度矩阵

**更新日期：** 2026-11-23
**当前状态：** PR #13（候选评估与 Q15 治理）已合并到个人仓库 `naodeng/bugmaster` 的 `main`，合并提交为 `5c640a21`。当前 W7 Oracle（预期行为判定依据）/Evidence（证据）数据结构与本地绑定切片已在独立工作分支实现。单元、契约、安全测试及行/分支覆盖均已通过；Codex 代码扫描没有发现可执行缺陷。本轮 PR 尚未建立，等待提交到远端供项目所有者确认。该切片不认证来源，也不接入自动 `rejected`（拒绝）或 `Confirmed Gate`（缺陷确认门禁）。持久化、可信来源适配器、浏览器运行时和真实基准评测仍未完成，完整产品仍为 Release No-Go（暂不发布）。

## 仓库审计摘要

- 当前开发工作树：`/Users/inaodeng/.codex/worktrees/w7-evidence-oracle/bugmaster`，分支 `codex/w7-evidence-oracle-provenance`，远端 `origin` 指向个人仓库 `naodeng/bugmaster`，HEAD 为 PR #13 合并提交 `5c640a21`。GitHub 查询确认个人仓库和组织上游均无未合并 PR。完成实现验证、Q15（代码扫描门禁）及适用的安全扫描后，交项目所有者确认并手动合并，再开始下一项；不叠加未合并功能分支。
- GitHub 上游：`AI-Native-QA-Lab/bugmaster`；个人项目 fork：`naodeng/bugmaster`。两者均为公开仓库，当前连接具有管理员权限。
- 仓库简介与 13 个主题标签的同步、起始提交 `cef3cb5` 推送到个人 fork（分叉仓库），均为早期历史记录；当前开发基线以 PR #13 合并提交 `5c640a21` 为准，未向组织上游推送本轮代码。
- 当前代码来源：用户提供的 `/Users/inaodeng/Downloads/bugmaster 2/`（128 个文件）。该 v1.1 基线采用 11 个 Discovery / Validation / Reporting（发现/验证/报告）Skill ID；旧 v1.0 的 `hunt-*` 目录不导入。
- 现有实现仍是工程起点：`bugmaster_core` 已有严格表面/范围门禁与本地 OpenAPI（开放 API 描述格式）3 静态发现；没有 URL（统一资源定位符）/Browser（浏览器）动态发现或真实 API（应用程序接口）/浏览器执行闭环。
- 16 个 Patterns 属于候选规则，50 个 Benchmark 属于计划清单；不能据此声称真实验证完成。
- 本机默认 Python 为 3.9.6；仓库 CI（持续集成）指定 Python 3.12。本轮使用 Python 3.12；固定版 `jsonschema[format-nongpl]==4.26.0`（JSON Schema 验证器）和 `coverage.py`（覆盖率工具）安装在 `/private/tmp/bugmaster-provenance-test-deps`，仅用于测试，未改动产品运行时依赖。
- W6 文件锁使用 POSIX `fcntl`，Windows 兼容性未验证。W6 实现及其审查修正在早期提交中推送到个人 fork；该事实不代表本轮代码已推送。

## W0–W11 进度

| Workstream | 目标 | 状态 | 验收证据 / 下一步 |
|---|---|---|---|
| W0 | 开发基线与品牌/Skill 名称统一 | 本地检查通过 | `check_branding.py`、`validate_catalog.py`、Skill 命名契约通过；基线提交 `cef3cb5` 已推送到 fork |
| W1 | Scope（授权范围）、Surface（测试表面）、Feature（功能）、Oracle（预期行为判定依据）、Finding（缺陷记录）、Evidence（证据）、Journal（动作日志）数据契约 | 部分实现 | Scope、Feature Inventory（功能清单）、Approval（审批）、Action（动作）、Event（事件）、Checkpoint（检查点）、Session（会话）及本分支 Oracle/Evidence 数据结构规则已有契约测试；新增本地绑定校验只检查来源/制品字节摘要、Oracle 版本和 Journal 结果引用，不认证来源。Finding 持久化与可信来源校验仍待实现 |
| W2 | 11 个独立 Skill（技能包） | 本地闭包验证通过 | 11 个包均含规范 Skill/Pattern（缺陷模式）闭包且 Manifest（清单）摘要一致；Codex/Claude 干净安装和真实 Eval（评测）未验证 |
| W3 | 16 个 Bug Pattern（缺陷模式） | 候选规则 | 需适用/排除条件、Oracle（预期行为判定依据）、反例和真实对照评测 |
| W4 | 风险路由与有界自主探索 | 部分实现 | `scripts/discover_openapi.py` 可从本地 OpenAPI（开放 API 描述格式）3 JSON 输出稳定 ID 和 JSON Pointer（JSON 指针）来源清单；URL（统一资源定位符）/Browser（浏览器）发现、风险路由与动态执行仍待实现 |
| W5 | R0–R3 风险级别动作授权 | 部分实现 | `scripts/validate_gates.py` 的 `can_dispatch()` 在可信 Scope/Approval 验证器接入前对所有风险等级恒拒绝；自述 `scopeValidated` 不再授权。真实范围解析、授权网关、审批摘要和修订绑定仍待实现 |
| W6 | Action Journal（动作日志）、Session（会话）/Checkpoint（检查点）持久化与安全恢复 | 部分实现 | 早期 PR #9 与 PR #11 已合入个人仓库 `main`；PR #11 增加待对账 Action（动作）枚举与进程崩溃验证。V-2 至 V-6 仍待核验。可信授权、事件来源真实性、预算对账和安全恢复授权未实现。 |
| W7 | Finding（缺陷记录）、跨入口去重与报告 | 部分实现：候选评估 + Oracle/Evidence 数据结构规则与本地绑定校验 | Candidate Assessment（候选评估）只输出 `candidate`（候选）、`needs_review`（需要复核）或 `duplicate`（重复）；`rejected`（拒绝）保留给未来 Host verifier（宿主可信验证器），不接受调用方 verifier callback（验证回调）。本分支新增 Oracle 来源字节、Evidence 制品摘要、精确 Oracle `revision`（版本号）和 Action Journal（动作日志）结果事件绑定；匹配结果仍标记来源真实性未验证，`Confirmed Gate`（缺陷确认门禁）保持阻断。Candidate（候选记录）/Finding（缺陷记录）持久化、真实可信来源适配器、签署身份、完整证据门禁和报告仍未实现 |
| W8 | 回归建议 | 待实现 | 只输出建议，不自动修改/提交测试代码 |
| W9 | 50 场景 Benchmark（基准评测） | 计划细化，仍未执行 | 保持 50 总数；7 个既有 API（应用程序接口）/UI（用户界面）场景映射候选正例、可信正常反证、模糊 Oracle、模型与执行矛盾、错误拒绝风险、人工反馈、跨表面去重；Manifest（清单）仍为 `planned`（计划中），需隔离 Ground Truth（真实结论）并进行 G0–G3 对照 |
| W10 | Codex 与 Claude Code 双宿主验证 | 未验证 | W10-02 首项交付为浏览器工具比较与选型记录；满足 W5-02/W7-02/W9-02 依赖后，再跑两宿主真实安装和 API（应用程序接口）/Browser（浏览器）权限测试 |
| W11 | 发布治理 | 部分实施 | PR #13 已确立 Q15（逐 PR 代码扫描、R2/R3 变更增加安全扫描）与项目所有者手动确认/合并；Q16（正式发布双人授权）和供应链证据仍待落实。完整 Release（正式发布）为 No-Go（暂不发布） |

## 质量状态

| 门禁 | 当前状态 | 说明 |
|---|---|---|
| 品牌与 Skill 命名扫描 | PASS（通过） | `python3 scripts/check_branding.py`；命名契约包含 4 项 Skill ID 检查 |
| Catalog（目录）/Registry（注册表） | PASS（通过） | `python3 scripts/validate_catalog.py` |
| Benchmark Manifest（基准评测清单） | PASS（结构） | `validate_benchmark.py` 明确提示场景未执行 |
| 本分支定向单元测试 | PASS（通过，33/33 + 83/83） | `test_provenance.py` 与 `test_action_journal.py`；仅代表这两个定向测试文件通过 |
| 本分支完整单元测试 | PASS（通过，523/523） | Python 3.12，固定测试依赖路径位于 `/private/tmp` |
| 本分支 Schema 契约测试 | PASS（通过，105/105） | Python 3.12 + `jsonschema[format-nongpl]==4.26.0` |
| 本分支安全测试 | PASS（通过，1/1） | `tests/security`；不代替 Q15 源码安全扫描 |
| 本分支全量行/分支覆盖 | PASS（通过，100% / 100%） | `bugmaster_core` 与 `scripts`：2535/2535 语句、930/930 分支 |
| PR #13 合并前验证（历史） | PASS | 准确 head `d6602dd`：单元 488/488、契约 96/96、安全测试 1/1、行/分支覆盖 2384/2384 与 880/880；Actions Run `45019266106` 全部通过。这些结果不包含当前 W7 改动 |
| PR #13 Q15 代码/安全扫描（历史） | PASS | PR 描述记录的 Codex 代码复扫与安全复核针对 `d6602dd`；属于 AI 扫描结果，不代表独立真人安全复核，也不覆盖当前 W7 改动 |
| 本轮 GitHub PR / Actions | 未建立 PR | PR #13 已合并；2026-11-23 查询个人 fork 和组织上游均无开放 PR。本轮分支尚未推送，因此没有远端 CI 结果 |
| 本轮 Q15 Codex 代码扫描 | PASS（通过） | `codex review --uncommitted` 未发现可执行缺陷；扫描复跑单测、契约和安全测试 |
| 本轮安全复核 | PASS（静态 AI 复核） | 复核范围为本地数据校验和日志绑定；复核者未运行测试，测试状态见上方单独记录 |
| 独立真人安全复核 | 未进行 | 本切片不处理来源认证、动作授权或缺陷确认；来源真实性仍未验证且缺陷确认门禁保持阻断。后续适配器、签名或门禁改动前，再与项目所有者单独讨论真人复核要求 |
| 历史单元测试与覆盖率 | 仅作历史参考 | 早期 PR #10 / Candidate Assessment 整合结果为 474/474、96/96 和 100% 行/分支覆盖；基线与范围均不同于当前 W7 工作树，不作为本轮门禁 |
| 业务功能覆盖率 >60% | 未达成 | 目前没有真实业务执行证据 |
| 核心 Happy / Negative / Edge | 未达成 | 需每个核心功能有三类实际通过证据 |
| Release | No-Go | 全量功能、真实 Benchmark、双宿主和独立审批均未完成 |

历史发布质量门禁记录：PR #10 整合代码 tree `af0e751902f230ef5e8035a51c845f5d14ab8ace` 使用覆盖 JSON `/private/tmp/bugmaster-pr10-final.json` 运行 `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-final.json`，结果为 No-Go（不满足发布门槛）：Feature Inventory（功能清单）未冻结、真实业务覆盖未超过 60%，核心 Feature（功能）的 Happy/Negative/Edge（成功/失败/边界场景）执行证据缺失。该历史 Benchmark（基准评测）仅检查清单结构，50 个场景未执行。

初始验证的命令与实际输出记录在 [基线验证记录](2026-11-18_INITIAL_BASELINE_VERIFICATION_ZH.md)。Scope 风险辅助函数、本地 OpenAPI 静态发现 CLI（命令行工具）、Scope/Approval/Action Schema、Session Schema、R2 缺少可信审批网关时拒绝派发和 W6-04 重放门禁的 RED/GREEN/REFACTOR/VERIFY 证据分别见 [范围与风险门禁 TDD 记录](2026-11-18_SCOPE_GATE_TDD_ZH.md)、[OpenAPI 发现 TDD 记录](2026-11-18_OPENAPI_DISCOVERY_TDD_ZH.md)、[Scope Schema TDD 记录](2026-11-18_SCOPE_SCHEMA_TDD_ZH.md)、[Approval 与 Action Schema TDD 记录](2026-11-18_APPROVAL_ACTION_SCHEMA_TDD_ZH.md)、[Session Schema TDD 记录](2026-11-19_SESSION_SCHEMA_TDD_ZH.md)、[R2 门禁 TDD 记录](2026-11-18_R2_GATE_TDD_ZH.md)、[Session Revision 持久化 TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md)、[Checkpoint 跨存储引用 TDD 记录](2026-11-19_CHECKPOINT_REFERENCE_VALIDATION_TDD_ZH.md)、[回放门禁 fail-closed TDD 记录](2026-11-19_REPLAY_GATE_FAIL_CLOSED_TDD_ZH.md)、[Candidate Assessment（候选评估）](2026-11-22_CANDIDATE_ASSESSMENT_TDD_ZH.md) 和 [Oracle/Evidence 本地绑定切片](2026-11-23_W7_ORACLE_EVIDENCE_PROVENANCE_TDD_ZH.md)。人工审核与浏览器工具调研见 [审核边界与浏览器工具调研](2026-11-22_BROWSER_TOOLING_AND_HUMAN_REVIEW_ASSESSMENT_ZH.md)。

11 个独立包的离线构建/闭包/摘要核验见 [Standalone 打包验证记录](2026-11-18_STANDALONE_PACKAGING_VERIFY_ZH.md)。

## 执行顺序

1. 运行基线静态检查、单元/契约测试与当前质量门禁，记录真实输出。
2. 当前 W7 切片已完成 Oracle/Evidence 数据结构、本地绑定实现、测试、全量覆盖和 Codex 代码扫描。将分支提交到远端并开 PR，供项目所有者确认后手动合并。合并后再单独设计 Evidence adapter（证据适配器）和可信 Oracle provenance（来源可追溯性），之后才进入 Candidate/Finding 持久化。来源未认证期间，自动拒绝和 Confirmed Gate（缺陷确认门禁）始终关闭。浏览器工具按既定依赖顺序先与隔离 Order Demo 做同场对照，再评估运行时实现。
3. 每次只推进一个功能 PR；当前 PR 合并后再开始后续功能。每轮更新本矩阵和独立中文 TDD 记录。不得将内部纵向切片作为缩水 MVP 对外发布。

