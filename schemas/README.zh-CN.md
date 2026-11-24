[English](README.md)

# 契约 Schema

Schema 使用 JSON Schema Draft 2020-12。契约测试同时校验 Schema 本身与代表性文档。

## 已实现

- `oracle.schema.json`：校验带版本的 `Oracle`（预期行为判定依据）、目标/功能适用范围，以及来源字节的 SHA-256（内容摘要）和长度；不会认证来源或 Oracle 作者。该 `Schema`（数据结构规则）描述记录字段，不证明来源真实。
- `evidence.schema.json` 与 `bugmaster_core.provenance.verify_provenance`：校验 `Evidence artifact`（证据制品）的摘要，以及对 Oracle 版本和本地 `Action Journal`（动作日志）结果事件的精确引用。该辅助函数会检查给定来源/制品的字节、规范化 Oracle 记录摘要和完整本地 Journal 事件链。匹配只证明本地完整性和引用关系；结果仍标记来源真实性为 `unverified`（未验证），`Confirmed Finding`（已确认缺陷记录）门禁为 `blocked`（阻断）。这不是持久化存储、可信适配器、签名器或来源认证器。`ActionJournal.recorded_outcome(action_id)` 返回校验过的本地结果绑定，但不认证事件来源或外部结果。

- `scope.schema.json`：校验带版本的 Scope、逐目标授权决定、已知表面与风险、in-scope 目标的审批引用及有限动作预算。
- `feature-inventory.schema.json`：校验带来源的 Feature Inventory；授权与执行进度保存在独立账本。
- `approval.schema.json`：校验 Scope 或 Action 审批记录、Scope revision 和目标绑定、来源/审批人引用、有效期，以及 R2 所需动作意图字段。
- `action.schema.json`：校验规范化 Action 意图和生命周期状态、R0/R2 变更约束、R2 审批引用、R1 变更强制执行引用，以及不可执行的移动端/未知表面。
- `event.schema.json`：校验 Action Journal v1.1 事件封套，要求同时提供 `sessionId` 与稳定的 `journalId`，并校验 prepared/dispatched/outcome/reconciliation claim 载荷。运行时代码还会核验序号、状态转换、两种身份、RFC3339 时间、重复 JSON 键和 SHA-256 事件链。缺少 `journalId` 的 v1.0 记录会被拒绝；本轮不提供迁移，也不原地改写旧记录。
- `checkpoint.schema.json`：校验 Checkpoint 的不可变 Session revision、Scope revision 与 Journal 序号/哈希锚点，并覆盖空 Journal 边界。它只做结构验证；恢复仍需验证所引用的 revision 和 Journal，并重新核验当前授权与预算。
- `session.schema.json`：校验版本化 Session revision、规范生命周期状态、Scope revision 历史、绑定 Scope revision 的审批引用、预算上限与已用计数，以及 Journal/Checkpoint 引用。引用不构成授权或安全恢复证明。
- `candidate-assessment.schema.json` 与 `bugmaster_core.candidate_assessment`：将候选筛选结果与 Confirmed Finding 分离，校验稳定原因码；人工反馈绑定 Candidate revision 与证据并以事件追加；支持基于确定性业务身份的跨表面去重，并统计精确率、召回率和人工审核工作量。`candidate` 与 `duplicate` 是本地暂定筛选结果；Host 在把它们当作权威状态，或据此抑制/汇总记录前，必须核验来源真实性和规范重复引用。Schema 为未来可信 Host 流程保留 `rejected`，当前 helper 不会输出它，也不接受调用方传入的 verifier 回调；`candidate-assessment-rejected.json` 仅为 Schema 测试夹具。它只是筛选契约和内存 helper，不是 Finding 存储或证据真实性服务。
- `candidate.schema.json`、`finding.schema.json` 与 `bugmaster_core.metadata_store.CandidateStore` / `FindingStore`：按配置的私有目录保存带版本的 Candidate（候选记录）/Finding（缺陷记录）元数据。记录目录由 ID 的 SHA-256 摘要命名；写入使用仅所有者可读写的 POSIX 文件锁、不可变 revision（修订版）文件、当前 head（最新版本指针）、规范 JSON 摘要及乐观版本检查。存储默认执行对应 Schema，也可再执行调用方增加的校验器。它拒绝软链接、硬链接、不安全的所有者、已有文件的不安全权限、macOS 上可检测到的扩展 ACL（访问控制列表）、版本缺口、未登记文件和摘要不匹配。不存在的配置根目录会以仅所有者访问权限创建；已存在的根目录必须本来就是私有目录，存储不会擅自修改其权限。子级记录目录在核验所有者与 ACL 后，写入时可收紧为仅所有者访问。读取时拒绝不符合私有权限要求的目录；已有文件权限不安全时一律拒绝且不修改权限。Candidate 的 `evidenceRefs` 只保存 Evidence ID；Finding 的 `evidenceRefs` 还保存 SHA-256 摘要和字节长度。存储没有专用 Evidence Blob（证据原件）字段或字节存储通路；自由文本字段仍可承载证据原文或 Base64 编码内容，调用方须避免写入。Candidate Assessment（候选评估）身份会与对应 Candidate revision 及顶层 Oracle（判定依据）引用绑定；Candidate 不能将自身列为重复项。审核事件只能引用同一 Candidate 已存在的版本，且事件证据引用必须存在于事件所指的确切版本。存储拒绝 Candidate 的 `rejected`，也拒绝 Finding 的 `confirmed`、`rejected`、`duplicate`、`resolved` 和 `reopened` 状态。本地完整性检查不认证证据来源、来源声明或审核人身份；不会验证外部引用、抑制重复项、接入 Confirmed Gate（缺陷确认门禁）或生成报告。写入中断留下的孤立版本或临时文件会 fail-closed（失败时保持阻断），本切片不自动修复；Windows 行为尚未验证。
- `bugmaster_core.session_store.SessionStore`：将每个通过校验的 Session revision 保存为独立不可变文件，使用私有 Session 目录和 POSIX 文件锁串行化写入，通过同步临时文件后再以不可覆盖方式落盘；拒绝替换、序号缺口、权限错误和不一致的历史转换。`lock_revisions()` 提供已提交数量；新增的 `lock_revision_snapshot()` 会在同一把锁内提供数量和最新 revision，避免 Journal 初始化与首次 Session 发布发生竞争，也防止绑定错误的 Journal ID。只读路径会校验私有目录的所有者、权限与 ACL，且不修改目录；写入路径则先校验所有者与 ACL，再修复权限。既有 Session 锁文件必须仅允许所有者访问、没有扩展 ACL 且没有硬链接。它不会认证 Approval 引用、将预算与 Action Journal 对账，也不授权恢复。Windows 行为尚未验证。
- `bugmaster_core.filesystem_security`：供 Session 与 Action Journal 存储共用的底层 ACL 检查。macOS 上会查询文件描述符的 ACL，无法检查时失败关闭；其他平台通过这项 macOS 专用检查报告没有扩展 ACL。
- `bugmaster_core.checkpoint_store.CheckpointStore`：按 Checkpoint ID 的哈希在私有 Session 目录下持久化通过 Schema 校验的 Checkpoint。它与 SessionStore 共用 POSIX 单 Session 锁，通过同步临时文件和不可覆盖硬链接落盘，并拒绝损坏记录以及所有者、权限或 ACL 不安全的 Checkpoint 目录。读取不会修复已有路径。它不会验证引用的 Session revision、Scope revision 或 Journal head 是否存在或真实，也不授权恢复。Windows 行为尚未验证。
- `bugmaster_core.action_journal.ActionJournal.matches_prefix(sequence, head_hash)`：先校验完整本地 Journal，再比对 Checkpoint 前缀；拒绝重复 JSON 键、软链接、硬链接、FIFO 和非普通文件，固定每一级父目录身份，并在取得锁后及成功返回前复核父目录/日志文件身份。每个实例首次追加前同步完整目录链；已观察到的 Journal 消失或被替换时失败关闭。它按 LF 解析 JSONL，保留字符串内合法的 Unicode 行分隔符，并接受符合 Checkpoint Schema 整数语义的数值。这只验证本地完整性，不证明事件来源、事实真实性、授权或安全恢复。
- `bugmaster_core.action_journal_store.ActionJournalStore`：将 `sessionId` 与 `journalId` 映射到 `<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl`。它以 no-follow 目录相对方式逐级遍历配置根及其祖先，检查可信所有者和私有模式位（包括文件系统根目录），并在 macOS 上拒绝扩展 ACL。它只规范化由 root 所有且目标符合预期的 `/tmp`、`/var` 系统别名；其他祖先软链接失败关闭。`initialize()` 通过每个 Session 共用的锁与 Session 发布串行化；只有在该 Session 尚无持久化 revision 时，才创建并同步新的私有 Journal。revision 持久化后，它只重新打开已有 Journal，文件或存储路径缺失时失败关闭。不安全的既有文件会被拒绝且权限保持原样。`open()` 同样要求安全文件已存在，不会创建或修复路径。返回的 Journal 实例保留 Session 目录描述符，并在每次读取和追加前重新检查该目录的 ACL。
- `bugmaster_core.checkpoint_reference_validator.CheckpointReferenceValidator`：在同一共享锁和目录描述符下读取 Checkpoint 与 Session revision，核对 Scope history 锚点、最新 `checkpointRefs` 登记及 Journal Store 的 `journalId`，先验证存储根的可信祖先，再把同一个根目录描述符传给 Checkpoint/Session 快照，并据此相对打开规范 Journal、验证其前缀。调用方不能为声明 ID 另选路径。这不会认证文件内容、事件来源或外部事实；也不校验权威 Scope 文档、不对账预算、不重新核验授权，也不授权恢复。

`approvalRef`、`enforcementRef` 和 Checkpoint 中的哈希都只是结构/完整性信息。它们不能证明审批人身份、审批真实性/有效期、执行来源或事件真实性。可信授权与恢复验证网关仍未实现；R2 必须由工具层执行审批和控制，R3 仍受独立安全策略约束。

Session Schema 保存结构化历史和计数；`SessionStore` 增加本地不可变 revision 持久化，并检查历史引用与计数是否单调变化。可信恢复验证器仍须验证审批引用真实性，将预算计数与不可变 Scope revision 和 Action Journal 对账，核对 Journal 绑定，并在恢复前重新核验当前授权。JSON Schema 不会比较已用计数与对应上限，可信 Session 恢复验证器尚未实现。

本地 Action Journal 使用受限文件权限、单操作 POSIX 文件锁、追加并 `fsync`，以及保守的恢复状态。事件哈希不证明来源或事实。重启后没有结果的 prepared/dispatched 动作仍保持阻断。调用方提供的只读观察只作为未验证的对账声明保存，不会解锁派发；R1/R2 失败结果也仍保持阻断。`scripts/validate_gates.py` 在可信只读验证器和当前授权门禁实现前拒绝所有重放。

## Candidate/Finding 存储的安全边界

摘要链可以发现局部或不一致修改，无法抵御拥有整个根目录写权限的本地用户重算全部摘要或恢复完整的旧目录。调用方不得将 Evidence（证据）原文或 Base64（文本编码格式）证据内容放入描述性自由文本。存储会把这些字段当作普通文本，不会检查其中是否嵌入了证据内容。Windows 行为尚未验证，扩展 ACL 的直接检查限于 macOS。

每条 Finding 中的 Evidence ID 必须唯一；即使重复 ID 携带不同摘要或字节长度，也会被拒绝。

## 尚未实现的契约

Oracle/Evidence Schema（预期行为判定依据与证据的数据结构规则）与本地绑定校验只是第一阶段契约：目前没有持久化 Evidence Blob（证据原件）存储、可信适配器、来源认证，也未接入 Candidate Assessment（候选评估）或缺陷确认门禁。Candidate/Finding（候选记录/缺陷记录）元数据支持本地持久化，Candidate 中也会保存已绑定的 Candidate Assessment；但存储尚未接入 `assess_candidate()`（候选评估辅助函数）、规范重复项查询、可信工作流或报告流程。Candidate Assessment（候选评估）契约不代表这些实体生命周期已经完成，也不能取代它们；其证据引用和验证标志仍是结构输入。

新增 Oracle/Evidence Schema 结构测试位于 `tests/contracts/test_provenance_schema.py`；它们只检查格式和字段约束，不证明来源真实性。

Skill Manifest（技能清单）、Pattern（缺陷模式）、Catalog（目录）、Capability Registry（能力注册表）、Recovery Decision（恢复决策）、Evidence Blob（证据原件）持久化与可信认证、可信来源 Adapter（适配器）、已签名或已认证的 Review（审核）记录、Report（报告）生成、Regression Recommendation（回归建议）、Eval Manifest（评测清单）和 Release Manifest（发布清单）尚未实现。Candidate（候选记录）/Finding（缺陷记录）现在支持本地元数据持久化，但还没有接入候选评估 helper（辅助函数）、可信工作流或报告；它不代表这些实体的完整生命周期已经完成，也不会授权任何决定。Candidate Assessment（候选评估）契约不代表其他实体已经完成，也不能取代它们。其证据引用和验证标志只是结构输入；可信 Host verifier（宿主验证器）接入前，当前 helper 不会输出 `rejected` 决策。真实可信来源仍依赖对应 Adapter（适配器）。可从 [统一契约](../docs/en/03-contracts.md) 与 [中文统一契约](../docs/zh-CN/03-contracts.md) 中查阅状态和身份约束。当前部分 Schema（数据结构规则）不能被视为完整契约套件已通过。

Oracle、Evidence、Scope、Feature Inventory、Approval、Action、Event、Checkpoint、Session 和 Candidate Assessment Schema 均有 `tests/contracts/` 中的契约测试。Candidate 筛选、Review Event 绑定、拒绝反证和 Benchmark 场景映射由 `tests/unit/test_candidate_assessment.py`、`tests/contracts/test_candidate_assessment_schema.py` 与 `tests/contracts/test_contracts.py` 覆盖；这些测试不能证明证据真实性，也没有运行正式 Eval 场景。Feature Inventory 测试验证 `examples/openapi/orders.json` 的实际 CLI 输出；Event 测试校验实际 Journal 事件（包括 R2 审批引用）；CheckpointStore 持久化由 `tests/unit/test_checkpoint_store.py` 单测和基于 Schema 的契约集成测试覆盖。`CheckpointReferenceValidator` 使用真实本地存储校验 Session revision、Scope history、最新 Session 登记项、Journal ID 确定性路径解析和 Journal 前缀一致性；它不认证 Journal 内容或事件来源，也不验证可信授权、预算对账或恢复授权。SessionStore 持久化由 `tests/unit/test_session_store.py` 和基于 Session Schema 的契约集成测试覆盖；这些测试不运行可信授权、预算对账或恢复流程。

Candidate（候选记录）/Finding（缺陷记录）Schema（数据结构规则）由 `tests/contracts/test_candidate_schema.py` 和 `tests/contracts/test_finding_schema.py` 覆盖；本地版本持久化、摘要校验及安全文件系统边界由 `tests/unit/test_metadata_store.py` 覆盖。这些测试不证明证据来源真实、审核人身份有效，也不运行正式 Eval（评测）场景。

CI 安装固定版本的 `jsonschema[format-nongpl]==4.26.0` 并执行契约套件。Candidate/Finding 存储的默认 Schema 校验器也使用此依赖；可选格式验证器会检查 RFC3339（日期时间格式）字段。低于 Python 3.10 的环境应使用仓库 CI 的 Python 3.12 或兼容环境。

