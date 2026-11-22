# BugMaster 工程实施进度矩阵

**更新日期：** 2026-11-21
**当前状态：** PR #1–#7 已合入 `main`，PR #7 merge commit 为 `c7fcfca24856eeb981389785d09bb4b84ca4bce4`。PR #8（W6-03）远端仍是基于旧 head 的开放 PR；本地隔离候选提交 `abe4b8e025402d5c0ec9b96ff68eabbdbb964b08` 基于当前 main 集成基线，并修复原三项安全评论及多轮独立复审问题。本轮再关闭两个 P2：恢复清理按 Session revision / Checkpoint ID 核对规范发布文件名及 inode；首次发布目录同步失败时保留临时硬链接，并在后续 Session 写入中同步后清理。最新本地验证为单元 399/399、契约 79/79、安全 1/1 通过；生产 Python（`bugmaster_core/` + `scripts/`）行覆盖 2,141/2,141、分支覆盖 770/770。覆盖 JSON：`/private/tmp/bugmaster-pr8-review-final.json`。候选尚未推送；同一最终 head 的独立复审和远端 CI 未运行。完整产品仍为 Release No-Go。

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
| W5 | R0–R3 动作级授权 | 部分实现 | R0/R1 基础 helper 已 fail-closed；无可信网关时 R2 现在 fail-closed；真实网关、审批摘要和修订绑定仍待实现 |
| W6 | Action Journal、Session/Checkpoint 持久化与安全恢复 | 部分实现 | PR #3–#7 已合入 `main`。当前 PR #8 候选新增确定性 `ActionJournalStore` 路径映射；使用 no-follow 目录描述符、固定根快照、检查可信祖先/私有模式与 macOS ACL、同步重试目录项，并在缺失历史或存在不安全既有文件时失败关闭。Journal 初始化和 Session revision 发布通过公开的 Session 锁上下文串行化；目录和既有锁的所有者/ACL/硬链接检查先于权限修改，只有新建锁才会 `fchmod`。Session 临时恢复只接受从记录身份推导出的规范目标文件名和同 inode；首次发布 `fsync` 失败会保留临时链接供下次写入恢复。最新候选单元 399/399、契约 79/79、安全 1/1、本地生产代码行/分支覆盖均 100%；Release 质量门禁仍因业务功能证据不足为 No-Go。远端 CI 与最终独立复审待推送后完成。事件来源真实性、可信 Safe Resume、权威 Scope、授权与预算对账仍未实现。 |
| W7 | Finding、跨入口去重与报告 | 待实现 | 需 Oracle、来源、E3+ 证据和剩余风险追踪 |
| W8 | 回归建议 | 待实现 | 只输出建议，不自动修改/提交测试代码 |
| W9 | 50 场景 Benchmark | 计划中 | 需真实运行、隔离 Ground Truth 和 G0–G3 对照 |
| W10 | Codex 与 Claude Code 双宿主验证 | 未验证 | 需两宿主的真实安装和 API/Browser 权限测试 |
| W11 | 发布治理 | 未实施 | Q15 独立审查、Q16 双人批准和供应链证据缺失；No-Go |

## 质量状态

| 门禁 | 当前状态 | 说明 |
|---|---|---|
| 品牌与 Skill 命名扫描 | PASS | `python3 scripts/check_branding.py`；命名契约包含 4 项 Skill ID 检查 |
| Catalog/Registry | PASS | `python3 scripts/validate_catalog.py` |
| Benchmark Manifest | PASS（结构） | `validate_benchmark.py` 明确提示场景未执行 |
| GitHub Actions | PR #4–#7 历史 head 检查通过；PR #8 最终 head NOT_RUN | PR #4 Run `44662457674`、PR #5 最终 head Run `44690535886`、PR #6 最终文档 head Run `44697609761`、PR #7 代码 head Run `44748455778` 均成功。PR #8 整合候选还未推送 |
| 单元测试 | PR #8 本地集成候选 PASS，399/399 | Python 3.12；全部生产 Python 范围 `bugmaster_core/` + `scripts/` 行覆盖 2141/2141、分支覆盖 770/770，均为 100%；覆盖 JSON：`/private/tmp/bugmaster-pr8-review-final.json` |
| R3 安全测试 | PR #8 本地集成候选 PASS，1/1 | `python3.12 -m unittest discover -s tests/security`；远端 CI 待推送后执行，不并入单元覆盖率分母 |
| 契约测试 | PR #8 本地集成候选 PASS，79/79 | Python 3.12 + `jsonschema[format-nongpl]==4.26.0`；覆盖 Event v1.1、跨存储快照与确定性 Journal 路径 |
| 当前生产 Python 行/分支覆盖率 | PR #8 本地集成候选 PASS，100% / 100% | `bugmaster_core` + `scripts` 共 2141/2141 行、770/770 分支；JSON：`/private/tmp/bugmaster-pr8-review-final.json`。行/分支口径分开报告，不等于业务功能覆盖 |
| 业务功能覆盖率 >60% | 未达成 | 目前没有真实业务执行证据 |
| 核心 Happy / Negative / Edge | 未达成 | 需每个核心功能有三类实际通过证据 |
| Release | No-Go | 全量功能、真实 Benchmark、双宿主和独立审批均未完成 |

本轮 PR #8 候选使用完整生产 Python 覆盖 JSON `/private/tmp/bugmaster-pr8-review-final.json` 运行 release quality gate，结果仍为 No-Go：代码行覆盖门禁通过，但功能清单未冻结、真实功能覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行矩阵缺证据。W6 本地状态机单测不作为真实业务功能执行证据。Benchmark 脚本仅验证清单结构，未运行 50 个场景。

初始验证的命令与实际输出记录在 [基线验证记录](2026-11-18_INITIAL_BASELINE_VERIFICATION_ZH.md)。Scope 风险 helper、本地 OpenAPI 静态发现 CLI、Scope/Approval/Action Schema、Session Schema 和 R2 缺少可信审批网关时拒绝派发的 RED/GREEN/REFACTOR/VERIFY 证据分别见 [范围与风险门禁 TDD 记录](2026-11-18_SCOPE_GATE_TDD_ZH.md)、[OpenAPI 发现 TDD 记录](2026-11-18_OPENAPI_DISCOVERY_TDD_ZH.md)、[Scope Schema TDD 记录](2026-11-18_SCOPE_SCHEMA_TDD_ZH.md)、[Approval 与 Action Schema TDD 记录](2026-11-18_APPROVAL_ACTION_SCHEMA_TDD_ZH.md)、[Session Schema TDD 记录](2026-11-19_SESSION_SCHEMA_TDD_ZH.md)、[R2 门禁 TDD 记录](2026-11-18_R2_GATE_TDD_ZH.md)、[Session Revision 持久化 TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md)和[Checkpoint 跨存储引用 TDD 记录](2026-11-19_CHECKPOINT_REFERENCE_VALIDATION_TDD_ZH.md)。

11 个独立包的离线构建/闭包/摘要核验见 [Standalone 打包验证记录](2026-11-18_STANDALONE_PACKAGING_VERIFY_ZH.md)。

## 执行顺序

1. 运行基线静态检查、单元/契约测试与当前质量门禁，记录真实输出。
2. 选定 W0/W1 中尚未实现的首个安全关键行为，先写并运行失败测试，再实现最小代码。
3. 每一轮更新本矩阵和独立中文 TDD 记录；不得将内部纵向切片作为缩水 MVP 对外发布。

