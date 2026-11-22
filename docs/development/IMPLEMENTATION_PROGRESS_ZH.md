# BugMaster 工程实施进度矩阵

**更新日期：** 2026-11-22
**当前状态：** PR #1–#7 已合入 `main`。PR #8 head `21ed1b9281566bb28c72f1708d40ad84cd6dce3e` 修复 Session 与 Journal ID 绑定，Actions Runs `44983187716`、`44983456594` 均成功。PR #9 最新 head `69b72003237e281f81a99f45c358f90478e63239` 的 Actions Run `44986287358` 成功；CodeX 通用复审在代码 head `d904e4d` 未发现重大问题，Security AI 复审仍待结果。PR #10 当前整合代码提交 `7eb6f1a40b165e43080f0ba167c3389fd0d5e6ae`（tree `af0e751902f230ef5e8035a51c845f5d14ab8ace`）包含最新 PR #9 基线；本地 macOS / Python 3.12.16：430/430 单元、82/82 契约、1/1 安全测试，生产行/分支覆盖 2,150/2,150 与 770/770（均 100%）。PR #10 代码/证据 head `8bbc2c3` 的 Actions Run `44986603312` 全部通过；CodeX 复审请求待返回。PR #8/#9 已合入 main；PR #10 原先整合在特性分支，当前通过 PR #11 提交到 main。此处为 2026-11-22 历史快照，PR 实时状态见 GitHub。Q15=D：每个 PR 做 Codex 代码扫描，R2/R3 另做安全扫描；所有者查看后手动合并。V-2 至 V-6 仍待验证，完整产品 Release No-Go。

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
| W6 | Action Journal、Session/Checkpoint 持久化与安全恢复 | 部分实现 | PR #3–#7 已合入 `main`；PR #8–#10 均属 R3。PR #8 修复 Session–Journal ID 不匹配问题；PR #9 当前 head `69b7200` 纳入该修复及 dispatch/Finding/replay fail-closed 改动，Actions Run `44986287358` 全部成功。PR #10 整合代码提交 `7eb6f1a40b165e43080f0ba167c3389fd0d5e6ae` 包含最新 PR #9 基线，保留待对账枚举与进程崩溃验证；本地 430/430 单元、82/82 契约、1/1 安全、生产 2,150/2,150 语句及 770/770 分支均 PASS；代码/证据 head `8bbc2c3` 的 Actions Run `44986603312` 全部成功。PR #11 的代码/安全扫描结果与所有者手动合并状态见 GitHub；V-2 至 V-6 仍待验证。可信授权、事件来源真实性、预算对账和安全恢复授权未实现。
| W7 | Finding、跨入口去重与报告 | 待实现 | 需 Oracle、来源、E3+ 证据和剩余风险追踪 |
| W8 | 回归建议 | 待实现 | 只输出建议，不自动修改/提交测试代码 |
| W9 | 50 场景 Benchmark | 计划中 | 需真实运行、隔离 Ground Truth 和 G0–G3 对照 |
| W10 | Codex 与 Claude Code 双宿主验证 | 未验证 | 需两宿主的真实安装和 API/Browser 权限测试 |
| W11 | 发布治理 | 未实施 | Q15 扫描证据、Q16 双人批准和供应链证据缺失；No-Go |

## 质量状态

| 门禁 | 当前状态 | 说明 |
|---|---|---|
| 品牌与 Skill 命名扫描 | PASS | `python3 scripts/check_branding.py`；命名契约包含 4 项 Skill ID 检查 |
| Catalog/Registry | PASS | `python3 scripts/validate_catalog.py` |
| Benchmark Manifest | PASS（结构） | `validate_benchmark.py` 明确提示场景未执行 |
| GitHub Actions | PR #8/#9/#10 当前已验证 heads PASS | PR #8 Runs `44983187716`、`44983456594`；PR #9 Run `44986287358`；PR #10 code/evidence head `8bbc2c3` Run `44986603312` 均成功 |
| 单元测试 | PR #8/#9/#10 当前本地树 PASS | PR #8 408/408；PR #9 最新整合树 408/408；PR #10 最新整合树 430/430。PR #10 Journal/Session/Checkpoint 恢复定向测试 22/22；覆盖 JSON：`/private/tmp/bugmaster-pr10-final.json` |
| R3 安全测试 | PR #8/#9 Actions 与 PR #10 本地及 Actions PASS，1/1 | PR #9 Run `44986287358`、PR #10 Run `44986603312` 均成功；Q15=D 要求 R3 变更有 Codex 安全扫描并由项目所有者查看后手动合并 |
| 契约测试 | PR #8 79/79；PR #9/#10 当前整合树 82/82，均 PASS | Python 3.12 + `jsonschema[format-nongpl]==4.26.0`；PR #10 远端 Actions 待核对 |
| 当前生产 Python 行/分支覆盖率 | PR #8/#9/#10 最新本地树 PASS，100% / 100% | PR #8 2,148/2,148 语句、772/772 分支；PR #9 2,145/2,145、768/768；PR #10 2,150/2,150、770/770。分别统计行/分支，不代表业务功能覆盖 |
| 业务功能覆盖率 >60% | 未达成 | 目前没有真实业务执行证据 |
| 核心 Happy / Negative / Edge | 未达成 | 需每个核心功能有三类实际通过证据 |
| Release | No-Go | 全量功能、真实 Benchmark、双宿主和独立审批均未完成 |

本轮 PR #10 最新整合代码 tree `af0e751902f230ef5e8035a51c845f5d14ab8ace` 使用覆盖 JSON `/private/tmp/bugmaster-pr10-final.json` 运行 `PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr10-final.json`，结果按预期为 No-Go：Feature Inventory 未冻结、真实业务覆盖未超过 60%，核心 Feature 的 Happy/Negative/Edge 执行证据缺失。Benchmark 只校验清单结构，50 个场景未执行。

初始验证的命令与实际输出记录在 [基线验证记录](2026-11-18_INITIAL_BASELINE_VERIFICATION_ZH.md)。Scope 风险 helper、本地 OpenAPI 静态发现 CLI、Scope/Approval/Action Schema、Session Schema、R2 缺少可信审批网关时拒绝派发和 W6-04 重放门禁的 RED/GREEN/REFACTOR/VERIFY 证据分别见 [范围与风险门禁 TDD 记录](2026-11-18_SCOPE_GATE_TDD_ZH.md)、[OpenAPI 发现 TDD 记录](2026-11-18_OPENAPI_DISCOVERY_TDD_ZH.md)、[Scope Schema TDD 记录](2026-11-18_SCOPE_SCHEMA_TDD_ZH.md)、[Approval 与 Action Schema TDD 记录](2026-11-18_APPROVAL_ACTION_SCHEMA_TDD_ZH.md)、[Session Schema TDD 记录](2026-11-19_SESSION_SCHEMA_TDD_ZH.md)、[R2 门禁 TDD 记录](2026-11-18_R2_GATE_TDD_ZH.md)、[Session Revision 持久化 TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md)、[Checkpoint 跨存储引用 TDD 记录](2026-11-19_CHECKPOINT_REFERENCE_VALIDATION_TDD_ZH.md)和[回放门禁 fail-closed TDD 记录](2026-11-19_REPLAY_GATE_FAIL_CLOSED_TDD_ZH.md)。

11 个独立包的离线构建/闭包/摘要核验见 [Standalone 打包验证记录](2026-11-18_STANDALONE_PACKAGING_VERIFY_ZH.md)。

## 执行顺序

1. 运行基线静态检查、单元/契约测试与当前质量门禁，记录真实输出。
2. 选定 W0/W1 中尚未实现的首个安全关键行为，先写并运行失败测试，再实现最小代码。
3. 每一轮更新本矩阵和独立中文 TDD 记录；不得将内部纵向切片作为缩水 MVP 对外发布。

