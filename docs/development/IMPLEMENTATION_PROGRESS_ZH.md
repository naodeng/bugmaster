# BugMaster 工程实施进度矩阵

**更新日期：** 2026-11-19
**当前状态：** W6 Action Journal、SessionStore、CheckpointStore、Checkpoint 跨存储引用校验、Journal 身份绑定与路径解析均为局部切片；PR #2–#8 均为草稿且未合并。PR #8 实现提交 `4bc2dc0` 已通过 Actions Run `44455794738`；完整产品仍为 Release No-Go。

## 仓库审计摘要

- 当前源仓库：`/Users/inaodeng/Code/bugmaster`。Session Schema 工作树位于 `/Users/inaodeng/.codex/worktrees/session-contract/bugmaster`、分支 `codex/session-schema`；W6 存储工作树为 `/Users/inaodeng/.codex/worktrees/session-revision-store/bugmaster`，当前分支 `codex/journal-path-resolution`，基于 PR #7 的提交 `6f2bc1d`；PR #8 实现提交 `4bc2dc0`。SessionStore 的实现提交为 `2e21010` / `7d2e195`。
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
| W6 | Action Journal、Session/Checkpoint 持久化与安全恢复 | 部分实现 | `CheckpointReferenceValidator` 校验 Checkpoint、Session revision/Scope history、最新 Session `checkpointRefs`、Journal 前缀及 Session/Journal `journalId` 一致性（PR #6/#7，Actions PASS）；PR #8 的 `ActionJournalStore` 固定绝对根路径，使用显式 `initialize()` 创建新日志、只读 `open()` 读取已有规范日志并在缺失时失败关闭，同时拒绝软链接与非普通文件；Journal 前缀 helper 在 PR #5。事件真实性、可信只读恢复、预算对账、八断点崩溃注入、工具层执行绑定及双宿主验证仍待实现 |
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
| GitHub Actions | PR #1–#8 实现检查通过（均为草稿） | 原 Run `44300382541` 因错误 JSON key 失败；PR #1/#2/#3/#4/#5/#6/#7/#8 最终代码 Run `44304702509` / `44438620887` / `44443870587` / `44446002412` / `44448388986` / `44450205158` / `44452742738` / `44455794738` 均成功。PR #3 文档同步 Run `44444315594`、ID 对齐 Run `44444585372` 也成功。PR #3 为 R2、PR #4–#8 为 R3，仍分别需要独立质量/安全审查 |
| 单元测试 | PASS，145/145 | Python 3.12；SessionStore 36/36、CheckpointStore 19/19、ActionJournal 定向测试 38/38、ActionJournalStore 10/10、CheckpointReferenceValidator 15/15 |
| 契约测试 | PASS，77/77 | Python 3.12 + `jsonschema[format-nongpl]==4.26.0`：包含 SessionStore 与 CheckpointStore Schema 集成测试 |
| 当前核心模块行/分支覆盖率 | PASS，100% / 100% | `bugmaster_core`：1060/1060 语句、428/428 分支；`session_store.py` 320/320 语句、130/130 分支；`checkpoint_store.py` 187/187 语句、60/60 分支；`action_journal.py` 301/301 语句、140/140 分支；`action_journal_store.py` 59/59 语句、10/10 分支；`checkpoint_reference_validator.py` 37/37 语句、20/20 分支。行/分支口径分开报告，不等于业务功能覆盖 |
| 业务功能覆盖率 >60% | 未达成 | 目前没有真实业务执行证据 |
| 核心 Happy / Negative / Edge | 未达成 | 需每个核心功能有三类实际通过证据 |
| Release | No-Go | 全量功能、真实 Benchmark、双宿主和独立审批均未完成 |

本轮使用生成的核心覆盖 JSON 运行 `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-reference-full-coverage.json`，结果仍为 No-Go：功能清单未冻结、真实功能覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行矩阵缺证据。W6 本地状态机单测不作为真实业务功能执行证据。Benchmark 脚本仅验证清单结构，未运行 50 个场景。

初始验证命令与实际输出见 [基线验证记录](2026-11-18_INITIAL_BASELINE_VERIFICATION_ZH.md)。各开发切片的 RED/GREEN/REFACTOR/VERIFY 证据见 [范围与风险门禁](2026-11-18_SCOPE_GATE_TDD_ZH.md)、[OpenAPI 发现](2026-11-18_OPENAPI_DISCOVERY_TDD_ZH.md)、[Scope Schema](2026-11-18_SCOPE_SCHEMA_TDD_ZH.md)、[Approval 与 Action Schema](2026-11-18_APPROVAL_ACTION_SCHEMA_TDD_ZH.md)、[Session Schema](2026-11-19_SESSION_SCHEMA_TDD_ZH.md)、[R2 门禁](2026-11-18_R2_GATE_TDD_ZH.md)、[Session Revision 持久化](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md)、[Checkpoint 持久化](2026-11-19_CHECKPOINT_STORE_TDD_ZH.md)、[Journal 前缀核验](2026-11-19_JOURNAL_PREFIX_MATCH_TDD_ZH.md)、[Checkpoint 跨存储引用校验](2026-11-19_CHECKPOINT_REFERENCE_VALIDATION_TDD_ZH.md)、[Journal 稳定身份绑定](2026-11-19_JOURNAL_ID_BINDING_TDD_ZH.md) 和 [Journal 路径解析](2026-11-19_JOURNAL_PATH_RESOLUTION_TDD_ZH.md)。

11 个独立包的离线构建/闭包/摘要核验见 [Standalone 打包验证记录](2026-11-18_STANDALONE_PACKAGING_VERIFY_ZH.md)。

## 执行顺序

1. 运行基线静态检查、单元/契约测试与当前质量门禁，记录真实输出。
2. 继续 W6：使 Journal 文件位置由 Session 身份与 `journalId` 确定性解析，再处理预算对账与可信只读恢复；每个切片先写并运行失败测试，再实现最小代码。
3. 每一轮更新本矩阵和独立中文 TDD 记录；不得将内部纵向切片作为缩水 MVP 对外发布。
