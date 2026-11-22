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
| Candidate Assessment | Candidate revision 中的 `candidateAssessment` | 只表示筛选结果；不能是 `confirmed`；拒绝必须关联反证 |
| Finding | 不可变 Revision + `current.json` | 报告/索引由权威数据生成 |
| Review | 真实审核记录 | 绑定 Finding、Oracle 和证据摘要 |
| Session | 不可变版本 + `ActionJournalStore` + Checkpoint | Session 身份确定本地 Journal 路径；恢复门禁仍独立 |
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

## 候选筛选与反馈

候选评估只允许 `candidate`、`needs_review`、`rejected` 和 `duplicate`，不能表示 `confirmed`。固定原因码说明 Oracle/证据缺失、Oracle/证据来源尚未验证、环境不稳定、误报检查不确定、观察相互矛盾、重复关联、策略要求人工复核或存在可信反证。拒绝必须有绑定同一已验证 Oracle 的 E3+ 工具执行证据，并表明实际行为符合预期；还必须由可信 Oracle 与 Evidence verifier 回调同时确认来源。自述的 `validated` 或来源验证标志不能作为依据；未提供两个可信 verifier 时必须保持 `needs_review`。模型意见不能单独拒绝。E3+ 违规证据与反证冲突时必须转 `needs_review`。

跨表面去重只关联目标、业务对象、操作、Oracle 和违规签名均相同的候选。表面字段不参与该身份，因此 API 与 Browser 观测可以关联且不重复计数。人工反馈以事件列表追加，并绑定 Candidate revision 和证据引用。当前 helper 只返回更新后的内存值；本次改动没有实现不可变 Candidate/Finding 持久化或证据来源真实性校验。

## 审批与恢复

批准必须绑定规范化动作、目标、参数摘要、环境、Scope Revision、风险等级、次数和有效期。模型自填 `approved` 不具备身份效力。R2 修改操作需要真实授权与可实施的工具层控制；R3 默认阻断。恢复前记录 Action Intent，对结果未知的副作用首先只读核查；可信只读核验器尚未接入，因此当前重放 helper 对所有请求 fail-closed；不能承诺外部系统 Exactly Once；预算与已消费审批不得在恢复时重置。

`ActionJournal.actions_needing_reconciliation()` 返回本地日志状态仍未解决的 Action ID 元组，供恢复流程逐项检查。它只提供诊断视图，不验证外部副作用、不授权重放；Journal 缺失或校验失败时会拒绝读取。

Scope JSON Schema 按目标记录 `in_scope`、`pending_authorization` 或 `out_of_scope`，并保存非秘密身份/环境引用、风险上限、有限动作预算，以及每个 `in_scope` 目标的审批引用。该引用本身不是授权证据；派发前授权网关必须验证真实审批记录及其与当前 Scope Revision 的绑定。v0.1 不允许将 Android、iOS 或未知表面标记为可执行。

Approval 和 Action Schema 记录 Scope/Action 引用、Scope Revision、目标、环境、规范化操作与参数摘要、风险、次数、有效期及生命周期状态。在宿主核验来源事件和动作绑定前，引用字段仍是不可信数据；当前 helper 在真实网关实现前拒绝 R2，R3 不能进入已派发或已完成状态。

每条 Action Journal Event 使用 Schema v1.1，必须同时绑定 `sessionId` 和稳定的 `journalId`；读取器拒绝身份不匹配或含重复 JSON 键的记录。`ActionJournalStore` 将这对身份映射到 `<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl`，逐级以 no-follow 目录相对方式打开配置根及其祖先，校验可信所有者和私有模式位（包括文件系统根目录），并在 macOS 上拒绝扩展 ACL。它只规范化由 root 所有且目标符合预期的 macOS `/tmp`、`/var` 系统别名；其他祖先软链接会失败关闭。`initialize()` 通过每个 Session 共用的锁与 Session 发布串行化；只有在该 Session 尚无持久化 revision 时，才创建并同步新的私有 Journal。revision 持久化后，它只重新打开已有 Journal，文件或存储路径缺失时失败关闭。不安全的既有文件会被拒绝且权限保持原样。`open()` 同样要求安全文件已存在，绝不创建或修复路径。返回的 Journal 实例会固定 Session 目录描述符，并在每次读取和追加前重新检查该目录的 ACL。Checkpoint 引用验证会逐级验证存储根的可信祖先，再把同一个根目录描述符传给 Checkpoint/Session 快照，并据此相对打开规范 Journal、校验其前缀。这样固定了本地路径选择与声明 ID 的关系，但不认证文件内容、事件来源或外部事实。缺少 `journalId` 的 v1.0 事件会被拒绝；本轮不提供迁移，也不会原地改写旧文件。

## 实现顺序

先冻结 JSON Schema 与统一枚举，再实现交叉引用校验、状态机、Evidence Gate 和恢复门禁。结构检查与语义评审分层，不能以 LLM 自评替代确定性验证。
