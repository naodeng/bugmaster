# BugMaster 工程实施进度矩阵

**更新日期：** 2026-11-22
**当前状态：** 2026-11-22 已核验 PR #9、#10 均显示合并。PR #9 合并到 `main`；PR #10 的 base 是 `codex/replay-gate-fail-closed`，本次 fetch 时该分支为 `1f974bc`，`origin/main` 为 `1498b04`，因此 PR #10 目前在该功能分支上、尚未进入 `main`。本地新增 W7 Candidate Assessment 筛选契约/helper，细化 W9 既有场景并完成 W10-02 浏览器工具调研初稿；完整 Finding/Evidence 存储、可信 Evidence Adapter、浏览器运行时和真实 Benchmark 仍未完成。完整产品仍为 Release No-Go。

## 仓库审计摘要

- 当前源仓库：`/Users/inaodeng/Code/bugmaster`。Session Schema 工作树为 `/Users/inaodeng/.codex/worktrees/session-contract/bugmaster`，分支 `codex/session-schema`；本轮 SessionStore 工作树为 `/Users/inaodeng/.codex/worktrees/session-revision-store/bugmaster`，分支 `codex/session-revision-store`，基于 Schema 提交 `808be6d`，初版提交 `2e21010`、Scope 历史修正 `7d2e195`。
- GitHub 上游：`AI-Native-QA-Lab/bugmaster`；个人项目 fork：`naodeng/bugmaster`。两者均为公开仓库，当前连接具有管理员权限。
- 两个仓库的 About 描述与 13 个 topics 已同步；未设置官网链接。基线提交 `cef3cb5` 已推到 fork 的 `origin/main`，尚未向组织上游推送代码。
- 当前代码来源：用户提供的 `/Users/inaodeng/Downloads/bugmaster 2/`（128 个文件）。该 v1.1 基线采用 11 个 Discovery / Validation / Reporting Skill ID；旧 v1.0 的 `hunt-*` 目录不导入。
- 现有实现仍是工程起点：`bugmaster_core` 已有严格表面/范围门禁与本地 OpenAPI 3 静态发现；没有 URL/Browser 动态发现或真实 API/Browser 执行闭环。
- 16 个 Patterns 属于候选规则，50 个 Benchmark 属于计划清单；不能据此声称真实验证完成。
- 当前默认 Python 为 3.9.6；仓库 CI 指定 Python 3.12。测试所需的 `coverage.py` 和 `jsonschema` 使用 Python 3.12，并安装在 `/private/tmp`，未改动系统 Python 或产品运行时依赖。
- 本机默认 Python 为 3.9.6；CI 和契约测试使用 Python 3.12。W6 文件锁使用 POSIX `fcntl`，Windows 兼容性未验证。W6 实现提交 `d317001` 与审查修正 `8376067` 已推送到 fork 的 `origin/main`；未向组织上游推送代码。

## W0–W11 进度

| Workstream | 目标 | 状态 | 验收证据 / 下一步 |
|---|---|---|---|
| W0 | 开发基线与品牌/Skill 名称统一 | 本地检查通过 | `check_branding.py`、`validate_catalog.py`、Skill 命名契约通过；基线提交 `cef3cb5` 已推送到 fork |
| W1 | Scope、Surface、Feature、Oracle、Finding、Evidence、Journal 数据契约 | 部分实现 | Scope、Feature Inventory、Approval、Action、Event、Checkpoint 和 Session JSON Schema 有对应契约测试；Session 仅结构校验，Oracle、Evidence、Finding 等仍待实现；本轮 `TDD-CON-014` 实现提交 `aaa5564` |
| W2 | 11 个独立 Skills | 本地闭包验证通过 | 11 个包均含规范 Skill/Pattern 闭包且 manifest 摘要一致；Codex/Claude 干净安装和真实 Eval 未验证 |
| W3 | 16 个 Bug Patterns | 候选规则 | 需适用/排除、Oracle、反例和真实对照 Eval |
| W4 | 风险路由与有界自主探索 | 部分实现 | `scripts/discover_openapi.py` 可从本地 OpenAPI 3 JSON 输出稳定 ID 和 JSON Pointer 来源清单；URL/Browser 发现、风险路由与动态执行仍待实现 |
| W5 | R0–R3 动作级授权 | 部分实现 | `scripts/validate_gates.py` 的 `can_dispatch()` 在可信 Scope/Approval verifier 接入前对所有风险等级恒拒绝；自述 `scopeValidated` 不再授权。真实 Scope 解析、授权网关、审批摘要和修订绑定仍待实现 |
| W6 | Action Journal、Session/Checkpoint 持久化与安全恢复 | 部分实现 | PR #9 已合并到 `main`；PR #10 已合并到 `codex/replay-gate-fail-closed`，但本次 fetch 的 `origin/main` 尚未包含其提交。PR #10 增加待对账 Action 枚举与进程崩溃验证；独立 Q15 真人签署和 V-2 至 V-6 证据状态仍需单独核验。可信授权、事件来源真实性、预算对账和安全恢复授权未实现。 |
| W7 | Finding、跨入口去重与报告 | 部分实现：候选筛选 helper / schema | Candidate Assessment 只允许 `candidate` / `needs_review` / `rejected` / `duplicate`；拒绝需可信 Oracle + Evidence verifier 回调，未接入时 fail-closed；追加式 Review Event、跨表面身份去重与质量指标已测。Candidate/Finding 持久化、来源认证、签署身份、完整 Oracle/Evidence Gate、报告仍未实现 |
| W8 | 回归建议 | 待实现 | 只输出建议，不自动修改/提交测试代码 |
| W9 | 50 场景 Benchmark | 计划细化，仍未执行 | 保持 50 总数，7 个既有 API/UI 场景映射候选正例、可信正常反证、模糊 Oracle、模型与执行矛盾、错误拒绝风险、人工反馈、跨表面去重；Manifest 仍为 `planned`，需隔离 Ground Truth 和 G0–G3 真实对照 |
| W10 | Codex 与 Claude Code 双宿主验证 | 未验证 | W10-02 首项交付为浏览器工具比较与选型记录；满足 W5-02/W7-02/W9-02 依赖后，再跑两宿主真实安装和 API/Browser 权限测试 |
| W11 | 发布治理 | 未实施 | Q15 独立审查、Q16 双人批准和供应链证据缺失；No-Go |

## 质量状态

| 门禁 | 当前状态 | 说明 |
|---|---|---|
| 品牌与 Skill 命名扫描 | PASS | `python3 scripts/check_branding.py`；命名契约包含 4 项 Skill ID 检查 |
| Catalog/Registry | PASS | `python3 scripts/validate_catalog.py` |
| Benchmark Manifest | PASS（结构） | `validate_benchmark.py` 明确提示场景未执行 |
| GitHub PR / Actions | PR #9 合并到 `main`；PR #10 合并到其功能分支 | 本次 fetch 时 `origin/main=1498b04`、`codex/replay-gate-fail-closed=1f974bc`；PR #10 尚未进入 `main`。此前 Actions Run `44986287358` / `44989084262` 成功记录是历史 CI 证据 |
| 单元测试 | PASS，182/182（本次合并前工作树） | Python 3.12；包含 Candidate Assessment Happy/Negative/Edge、可信拒绝 fail-closed、重复项审核成本用例；整合 PR #10 基线后需复跑 |
| R3 安全测试 | 历史 PR #9/#10 记录 PASS | PR #9 Run `44986287358`、PR #10 Run `44989084262`；独立人工 Q15 审核结论不由 CI 证明 |
| 契约测试 | PASS，92/92（本次合并前工作树） | Python 3.12 + `jsonschema[format-nongpl]==4.26.0`；整合 PR #10 基线后需复跑 |
| 当前核心模块行/分支覆盖率 | PASS，100% / 100%（本次合并前工作树） | `bugmaster_core`：1272/1272 语句、544/544 分支；整合 PR #10 基线后需复跑。行/分支覆盖不等于业务功能覆盖 |
| 业务功能覆盖率 >60% | 未达成 | 目前没有真实业务执行证据 |
| 核心 Happy / Negative / Edge | 未达成 | 需每个核心功能有三类实际通过证据 |
| Release | No-Go | 全量功能、真实 Benchmark、双宿主和独立审批均未完成 |

本轮 PR #10 最新整合代码 tree `af0e751902f230ef5e8035a51c845f5d14ab8ace` 使用覆盖 JSON `/private/tmp/bugmaster-pr10-final.json` 运行 `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-final.json`，结果按预期为 No-Go：Feature Inventory 未冻结、真实业务覆盖未超过 60%，核心 Feature 的 Happy/Negative/Edge 执行证据缺失。Benchmark 只校验清单结构，50 个场景未执行。

初始验证的命令与实际输出记录在 [基线验证记录](2026-11-18_INITIAL_BASELINE_VERIFICATION_ZH.md)。Scope 风险 helper、本地 OpenAPI 静态发现 CLI、Scope/Approval/Action Schema、Session Schema、R2 缺少可信审批网关时拒绝派发和 W6-04 重放门禁的 RED/GREEN/REFACTOR/VERIFY 证据分别见 [范围与风险门禁 TDD 记录](2026-11-18_SCOPE_GATE_TDD_ZH.md)、[OpenAPI 发现 TDD 记录](2026-11-18_OPENAPI_DISCOVERY_TDD_ZH.md)、[Scope Schema TDD 记录](2026-11-18_SCOPE_SCHEMA_TDD_ZH.md)、[Approval 与 Action Schema TDD 记录](2026-11-18_APPROVAL_ACTION_SCHEMA_TDD_ZH.md)、[Session Schema TDD 记录](2026-11-19_SESSION_SCHEMA_TDD_ZH.md)、[R2 门禁 TDD 记录](2026-11-18_R2_GATE_TDD_ZH.md)、[Session Revision 持久化 TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md)、[Checkpoint 跨存储引用 TDD 记录](2026-11-19_CHECKPOINT_REFERENCE_VALIDATION_TDD_ZH.md)、[回放门禁 fail-closed TDD 记录](2026-11-19_REPLAY_GATE_FAIL_CLOSED_TDD_ZH.md) 和 [Candidate Assessment](2026-11-22_CANDIDATE_ASSESSMENT_TDD_ZH.md)。人工 Review 与浏览器工具调研见 [审核边界与浏览器工具调研](2026-11-22_BROWSER_TOOLING_AND_HUMAN_REVIEW_ASSESSMENT_ZH.md)。

11 个独立包的离线构建/闭包/摘要核验见 [Standalone 打包验证记录](2026-11-18_STANDALONE_PACKAGING_VERIFY_ZH.md)。

## 执行顺序

1. 运行基线静态检查、单元/契约测试与当前质量门禁，记录真实输出。
2. W7 下一步先实现并验证真实 Evidence adapter / Oracle provenance，再接入持久化 Candidate/Finding；否则拒绝结论始终保持人工复核。浏览器工具先在隔离 Order Demo 做同场对照，不先引入多套 Runtime。
3. 按单 PR 顺序完成当前工作、Review、审批与合并后再开始后续功能；每轮更新本矩阵和独立中文 TDD 记录。不得将内部纵向切片作为缩水 MVP 对外发布。

