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
| Oracle（预期行为判定依据） | `.bugmaster/oracles/<id>/revisions/` | ID + `revision`（版本号）+ `canonical record digest`（规范记录摘要）；记录预期行为和来源指纹，尚未认证来源与作者身份 |
| Evidence（证据） | 元数据 + `content-addressed artifact`（按内容摘要寻址的制品） | EV ID + 制品 SHA-256（内容摘要）+ Oracle/Journal 引用；校验本地字节完整性和引用关系，来源真实性仍未验证 |
| Candidate Assessment（候选评估） | 嵌入 Candidate（候选记录）版本 | Candidate ID + revision（版本号）；只表示筛选结果；拒绝需可信反证审核 |
| Candidate（候选记录） | `<root>/candidates/<sha256(candidateId)>/revisions/` | 本地不可变元数据版本；评估结果仍是暂定状态 |
| Finding（缺陷记录） | `<root>/findings/<sha256(findingId)>/revisions/` + `metadata.head`（最新版本指针） | 只保存本地元数据，不生成报告或索引 |
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

Candidate/Finding Schema（数据结构规则）描述未来完整状态枚举；当前本地存储只接受 Candidate 决策 `candidate`、`needs_review` 和暂定的 `duplicate`，以及 Finding 状态 `hypothesis`、`observed`、`suspected` 和 `needs_review`。接入可信验证与所需真人审核前，存储会阻止 Candidate `rejected`，也会阻止 Finding `confirmed`、`rejected`、`duplicate`、`resolved` 和 `reopened`。

## 缺陷确认准入

Confirmed 需要有效且适用的 Oracle、真实且可追溯的执行证据、明确的预期违反、环境/因果排查、没有阻断级矛盾、至少 E3 的门禁评估，以及策略要求时的真实人工 Review。E4 独立复核不作为普遍强制条件。偶现无法再次复现不自动推翻可信原始证据。Evidence Level 与 Severity/Confidence 完全独立。

## 候选筛选与反馈

Candidate Assessment Schema 为未来可信 Host verifier 流程保留 `rejected`；当前 `assess_candidate()` helper 只输出 `candidate`、`needs_review` 或 `duplicate`，并且不接受调用方传入的 verifier 回调。可信 Host verifier 接入前，结构有效的反证仍保持 `needs_review`，并标记来源尚未验证。自述的 `validated` 或来源验证标志不能作为自动拒绝的依据。模型意见不能单独拒绝。E3+ 违规证据与反证冲突时必须转 `needs_review`。`candidate-assessment-rejected.json` 仅用于验证 Schema 结构，不是运行时输出。

`candidate` 和 `duplicate` 是基于调用方所给记录的本地暂定筛选结果。helper 不认证来源标志，也不通过规范存储核验 `duplicateOf`。Host 在把这些结果当作权威状态，或据此抑制/汇总记录前，必须核验来源真实性和被引用的 Candidate。Candidate Assessment 始终被 Confirmed Gate 阻断。

跨表面去重只关联目标、业务对象、操作、Oracle 和违规签名均相同的候选。表面字段不参与该身份，因此 API（应用程序接口）与 Browser（浏览器）观测可以关联且不重复计数。人工反馈以事件列表追加，并绑定 Candidate revision（候选记录版本）和证据引用。helper（辅助函数）仍只返回更新后的内存值；元数据存储是独立 API（应用程序接口），尚未接入候选评估、去重或报告。下方的本地绑定校验器也未接入 Candidate Assessment。

## Candidate/Finding 元数据持久化

`CandidateStore` 和 `FindingStore` 默认校验对应 JSON Schema（JSON 数据结构规则），并在配置的私有目录下追加不可变版本文件。存储使用 ID 的哈希值选择每条记录的独立目录；每条记录有 POSIX（类 Unix 操作系统接口）文件锁、包含最新版本和历史摘要的当前指针，以及基于 `expected_revision`（预期当前版本）的乐观并发检查。版本和指针通过私有临时文件、`fsync`（将数据同步到磁盘）及不可覆盖的版本发布方式写入。读取时会重新校验完整版本历史；遇到缺失或孤立版本、未知目录项、软/硬链接、不安全所有者、已有文件权限不私有、可检测到的扩展 ACL（访问控制列表）、非规范 JSON、Schema 校验失败或摘要不匹配时，都会 fail-closed（失败时保持阻断）。不存在的配置根目录会以仅所有者访问权限创建；已存在的根目录必须本来就是私有目录，存储不会擅自修改其权限。子级记录目录在核验所有者与 ACL 后，写入时可收紧为仅所有者访问；读取时拒绝权限不私有的目录。已有文件权限不安全时始终拒绝且不修改权限。

Candidate revision（候选记录版本）嵌入 Candidate Assessment（候选评估），并要求两者的 ID、版本、观测表面、Pattern（缺陷模式）、Oracle（预期行为判定依据）引用、证据引用、误报检查、审核要求和可选去重身份保持一致。审核事件必须引用同一 Candidate 和该记录已经存在的版本；事件 ID 不能重复，事件中的 Evidence ID（证据标识）必须存在于事件所引用的确切版本中。Candidate 不能将自身列为重复项。这些检查只校验引用关系，不认证审核人身份，也不证明真人实际审核过。身份字段在版本间不能变化；证据引用、误报检查和审核事件不能删除或重排。Finding（缺陷记录）中的 Candidate、表面、Action（动作）和 Evidence（证据）引用也只能追加。Candidate 的证据引用只保存 Evidence ID；Finding 的证据引用还包含 SHA-256 摘要和字节长度。两者都不保存 Evidence 原件字节。存储不核验外部引用，不认证来源声明或审核人身份，不抑制重复项，也不把任何状态接入 Confirmed Gate（缺陷确认门禁）。已保存的审核人 ID 或审核决定只是未经验证的声明，不能证明真人实际审核过。发布过程被中断时不会自动恢复；后续读取会因孤立版本或临时项而阻断，直至由操作者处理。Windows 行为尚未验证。

摘要链可以发现局部或不一致修改，无法抵御拥有整个根目录写权限的本地用户重算全部摘要或恢复完整的旧目录。调用方不得将 Evidence（证据）原文或 Base64（文本编码格式）证据内容放入描述性自由文本。存储会把这些字段当作普通文本，不会检查其中是否嵌入了证据内容。

每条 Finding 中的 Evidence ID 必须唯一；即使重复 ID 携带不同摘要或字节长度，也会被拒绝。

## Oracle（预期行为判定依据）与 Evidence（证据）数据校验

`Oracle Schema`（预期行为判定依据数据结构规则）v1.0 记录 `revision`（版本号）、预期行为描述、目标/功能适用范围，以及来源字节的 SHA-256（内容摘要）和长度。`Evidence Schema`（证据数据结构规则）v1.0 记录证据制品的媒体类型、SHA-256（内容摘要）和长度、精确的 Oracle ID、`revision`（版本号）、`canonical record digest`（规范记录摘要），以及 `Action Journal`（动作日志）结果事件的 Session（会话）、Journal（动作日志）、Action ID（动作标识）、结果引用、序号和事件摘要。E0–E4 是证据等级标签，此校验器不会独立核验等级。

`bugmaster_core.provenance.verify_provenance()` 会重新计算给定 Oracle 来源和 Evidence 制品的摘要，匹配规范化 Oracle 记录摘要，然后要求具体的 `ActionJournal` 实例校验完整本地事件链并返回所引用的结果事件。摘要、引用不一致或结果不可读取时，都会 `fail-closed`（失败时保持阻断）。返回结果只说明本地内容完整、引用对应：SHA-256（内容摘要算法）是内容指纹，Journal（动作日志）哈希链不是数字签名。Oracle 作者身份、证据采集过程、事件来源和外部事实仍未认证；结果明确保持来源真实性未验证，并阻断 `Confirmed Finding`（已确认缺陷记录）门禁。这一阶段只增加 Schema（数据结构规则）和内存校验器，尚未实现持久化、可信适配器、签名身份或门禁接入。

## 审批与恢复

批准必须绑定规范化动作、目标、参数摘要、环境、Scope Revision、风险等级、次数和有效期。模型自填 `approved` 不具备身份效力。R2 修改操作需要真实授权与可实施的工具层控制；R3 默认阻断。恢复前记录 Action Intent，对结果未知的副作用首先只读核查；可信只读核验器尚未接入，因此当前重放 helper 对所有请求 fail-closed；不能承诺外部系统 Exactly Once；预算与已消费审批不得在恢复时重置。

`ActionJournal.actions_needing_reconciliation()` 返回本地日志状态仍未解决的 Action ID 元组，供恢复流程逐项检查。它只提供诊断视图，不验证外部副作用、不授权重放；Journal 缺失或校验失败时会拒绝读取。

Scope JSON Schema 按目标记录 `in_scope`、`pending_authorization` 或 `out_of_scope`，并保存非秘密身份/环境引用、风险上限、有限动作预算，以及每个 `in_scope` 目标的审批引用。该引用本身不是授权证据；派发前授权网关必须验证真实审批记录及其与当前 Scope Revision 的绑定。v0.1 不允许将 Android、iOS 或未知表面标记为可执行。

Approval 和 Action Schema 记录 Scope/Action 引用、Scope Revision、目标、环境、规范化操作与参数摘要、风险、次数、有效期及生命周期状态。在宿主核验来源事件和动作绑定前，引用字段仍是不可信数据；当前 helper 在真实网关实现前拒绝 R2，R3 不能进入已派发或已完成状态。

每条 Action Journal Event 使用 Schema v1.1，必须同时绑定 `sessionId` 和稳定的 `journalId`；读取器拒绝身份不匹配或含重复 JSON 键的记录。`ActionJournalStore` 将这对身份映射到 `<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl`，逐级以 no-follow 目录相对方式打开配置根及其祖先，校验可信所有者和私有模式位（包括文件系统根目录），并在 macOS 上拒绝扩展 ACL。它只规范化由 root 所有且目标符合预期的 macOS `/tmp`、`/var` 系统别名；其他祖先软链接会失败关闭。`initialize()` 通过每个 Session 共用的锁与 Session 发布串行化；只有在该 Session 尚无持久化 revision 时，才创建并同步新的私有 Journal。revision 持久化后，它只重新打开已有 Journal，文件或存储路径缺失时失败关闭。不安全的既有文件会被拒绝且权限保持原样。`open()` 同样要求安全文件已存在，绝不创建或修复路径。返回的 Journal 实例会固定 Session 目录描述符，并在每次读取和追加前重新检查该目录的 ACL。Checkpoint 引用验证会逐级验证存储根的可信祖先，再把同一个根目录描述符传给 Checkpoint/Session 快照，并据此相对打开规范 Journal、校验其前缀。这样固定了本地路径选择与声明 ID 的关系，但不认证文件内容、事件来源或外部事实。缺少 `journalId` 的 v1.0 事件会被拒绝；本轮不提供迁移，也不会原地改写旧文件。

## 实现顺序

先冻结 JSON Schema 与统一枚举，再实现交叉引用校验、状态机、Evidence Gate 和恢复门禁。结构检查与语义评审分层，不能以 LLM 自评替代确定性验证。
