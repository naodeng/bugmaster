[English](../en/03-contracts.md)

# 统一契约与状态机

## 权威数据与版本

| 实体 | 权威位置 | 约束 |
|---|---|---|
| Skill | `skills/<name>/SKILL.md` | 唯一 Canonical，单 Skill 分发闭包完整 |
| Pattern | `patterns/<category>/<id>/pattern.json` | 稳定 ID / Revision；来源与正反例 |
| Capability | `registry/capabilities.json` | 仅引用存在的 Skill/Pattern |
| Feature Inventory | 本地 CLI 输出 | 来源引用 + 稳定 Feature ID；只表示发现，不表示授权或执行 |
| Scope | `.bugmaster/scopes/<id>.json` | 审批引用仍须由可信网关核验 |
| Approval | Scope/Action 引用的审批记录 | Approval ID + Scope Revision；宿主验证来源事件与精确意图绑定 |
| Action | Session Action Journal | 事前写意图；未知执行结果禁止重放 |
| Oracle | `.bugmaster/oracles/` 不可变版本 | 来源、适用条件、有效性 |
| Evidence | 元数据 + 内容哈希 Artifact | 哈希证明完整性，不单独证明真实性 |
| Finding | 不可变 Revision + `current.json` | 报告/索引由权威数据生成 |
| Review | 真实审核记录 | 绑定 Finding、Oracle 和证据摘要 |
| Session | 不可变版本 + Journal + Checkpoint | 单写者；恢复重新核查权限 |
| Regression Recommendation | 不可变版本 | 只提供建议，不写测试代码 |
| Eval Run | 不可变运行记录 | 隔离 Ground Truth |

## 统一状态枚举

- Finding：`hypothesis`, `observed`, `suspected`, `needs_review`, `confirmed`, `rejected`, `duplicate`, `resolved`, `reopened`。
- Evidence：`E0`, `E1`, `E2`, `E3`, `E4`。
- Reproduction：`not_attempted`, `reproduced`, `not_reproduced`, `intermittent`, `blocked`, `unknown`。
- Review：`not_required`, `pending`, `approved`, `rejected`, `expired`。
- Session：`created`, `ready`, `running`, `paused`, `recovering`, `completed`, `failed`, `blocked`, `cancelled`。
- Action：`proposed`, `authorized`, `prepared`, `dispatched`, `completed`, `failed`, `outcome_unknown`, `reconciled_completed`, `reconciled_not_executed`, `needs_review`, `rejected`, `cancelled`。
- Recovery：`safe`, `restricted`, `needs_reconciliation`, `blocked`。
- Pattern：`candidate`, `reviewed`, `verified`, `deprecated`。
- Regression Recommendation：`draft`, `needs_review`, `approved`, `rejected`, `exported`, `superseded`, `archived`。

## 缺陷确认准入

Confirmed 需要有效且适用的 Oracle、真实且可追溯的执行证据、明确的预期违反、环境/因果排查、没有阻断级矛盾、至少 E3 的门禁评估，以及策略要求时的真实人工 Review。E4 独立复核不作为普遍强制条件。偶现无法再次复现不自动推翻可信原始证据。Evidence Level 与 Severity/Confidence 完全独立。

## 审批与恢复

批准必须绑定规范化动作、目标、参数摘要、环境、Scope Revision、风险等级、次数和有效期。模型自填 `approved` 不具备身份效力。R2 修改操作需要真实授权与可实施的工具层控制；R3 默认阻断。恢复前记录 Action Intent，对结果未知的副作用首先只读核查；可信只读核验器尚未接入，因此当前重放 helper 对所有请求 fail-closed；不能承诺外部系统 Exactly Once；预算与已消费审批不得在恢复时重置。

Scope JSON Schema 按目标记录 `in_scope`、`pending_authorization` 或 `out_of_scope`，并保存非秘密身份/环境引用、风险上限、有限动作预算，以及每个 `in_scope` 目标的审批引用。该引用本身不是授权证据；派发前授权网关必须验证真实审批记录及其与当前 Scope Revision 的绑定。v0.1 不允许将 Android、iOS 或未知表面标记为可执行。

Approval 和 Action Schema 记录 Scope/Action 引用、Scope Revision、目标、环境、规范化操作与参数摘要、风险、次数、有效期及生命周期状态。在宿主核验来源事件和动作绑定前，引用字段仍是不可信数据；当前 helper 在真实网关实现前拒绝 R2，R3 不能进入已派发或已完成状态。

Action Journal 事件 Schema v1.1 要求每个事件同时绑定 `sessionId` 和 `journalId`；读取器会拒绝与配置 Session 或 Journal 身份不一致的事件流。`ActionJournalStore` 根据存储根目录、Session ID 和 Journal ID 确定唯一文件路径，`CheckpointReferenceValidator` 只通过该映射读取 Journal。v1.0 日志不含 Journal ID，会被拒绝且不会修改；当前未实现迁移。确定性本地路径、身份字段与哈希链不能证明事件来源或外部事实真实性。

## 实现顺序

先冻结 JSON Schema 与统一枚举，再实现交叉引用校验、状态机、Evidence Gate 和恢复门禁。结构检查与语义评审分层，不能以 LLM 自评替代确定性验证。
