[English](README.md)

# 契约 Schema

Schema 使用 JSON Schema Draft 2020-12。契约测试同时校验 Schema 本身与代表性文档。

## 已实现

- `scope.schema.json`：校验带版本的 Scope、逐目标授权决定、已知表面与风险、in-scope 目标的审批引用及有限动作预算。
- `feature-inventory.schema.json`：校验带来源的 Feature Inventory；授权与执行进度保存在独立账本。
- `approval.schema.json`：校验 Scope 或 Action 审批记录、Scope revision 和目标绑定、来源/审批人引用、有效期，以及 R2 所需动作意图字段。
- `action.schema.json`：校验规范化 Action 意图和生命周期状态、R0/R2 变更约束、R2 审批引用、R1 变更强制执行引用，以及不可执行的移动端/未知表面。
- `event.schema.json`：校验 Action Journal v1.1 事件封套，要求同时提供 `sessionId` 与稳定的 `journalId`，并校验 prepared/dispatched/outcome/reconciliation claim 载荷。运行时代码还会核验序号、状态转换、两种身份、RFC3339 时间、重复 JSON 键和 SHA-256 事件链。缺少 `journalId` 的 v1.0 记录会被拒绝；本轮不提供迁移，也不原地改写旧记录。
- `checkpoint.schema.json`：校验 Checkpoint 的不可变 Session revision、Scope revision 与 Journal 序号/哈希锚点，并覆盖空 Journal 边界。它只做结构验证；恢复仍需验证所引用的 revision 和 Journal，并重新核验当前授权与预算。
- `session.schema.json`：校验版本化 Session revision、规范生命周期状态、Scope revision 历史、绑定 Scope revision 的审批引用、预算上限与已用计数，以及 Journal/Checkpoint 引用。引用不构成授权或安全恢复证明。
- `candidate-assessment.schema.json` 与 `bugmaster_core.candidate_assessment`：将候选筛选结果与 Confirmed Finding 分离，校验稳定原因码和拒绝时的反证引用；人工反馈绑定 Candidate revision 与证据并以事件追加；支持基于确定性业务身份的跨表面去重，并统计精确率、召回率和人工审核工作量。它只是筛选契约和内存 helper，不是 Finding 存储或证据真实性服务。
- `bugmaster_core.session_store.SessionStore`：将每个通过校验的 Session revision 保存为独立不可变文件，使用私有 Session 目录和 POSIX 文件锁串行化写入，通过同步临时文件后再以不可覆盖方式落盘；拒绝替换、序号缺口、权限错误和不一致的历史转换。`lock_revisions()` 提供已提交数量；新增的 `lock_revision_snapshot()` 会在同一把锁内提供数量和最新 revision，避免 Journal 初始化与首次 Session 发布发生竞争，也防止绑定错误的 Journal ID。只读路径会校验私有目录的所有者、权限与 ACL，且不修改目录；写入路径则先校验所有者与 ACL，再修复权限。既有 Session 锁文件必须仅允许所有者访问、没有扩展 ACL 且没有硬链接。它不会认证 Approval 引用、将预算与 Action Journal 对账，也不授权恢复。Windows 行为尚未验证。
- `bugmaster_core.filesystem_security`：供 Session 与 Action Journal 存储共用的底层 ACL 检查。macOS 上会查询文件描述符的 ACL，无法检查时失败关闭；其他平台通过这项 macOS 专用检查报告没有扩展 ACL。
- `bugmaster_core.checkpoint_store.CheckpointStore`：按 Checkpoint ID 的哈希在私有 Session 目录下持久化通过 Schema 校验的 Checkpoint。它与 SessionStore 共用 POSIX 单 Session 锁，通过同步临时文件和不可覆盖硬链接落盘，并拒绝损坏记录以及所有者、权限或 ACL 不安全的 Checkpoint 目录。读取不会修复已有路径。它不会验证引用的 Session revision、Scope revision 或 Journal head 是否存在或真实，也不授权恢复。Windows 行为尚未验证。
- `bugmaster_core.action_journal.ActionJournal.matches_prefix(sequence, head_hash)`：先校验完整本地 Journal，再比对 Checkpoint 前缀；拒绝重复 JSON 键、软链接、硬链接、FIFO 和非普通文件，固定每一级父目录身份，并在取得锁后及成功返回前复核父目录/日志文件身份。每个实例首次追加前同步完整目录链；已观察到的 Journal 消失或被替换时失败关闭。它按 LF 解析 JSONL，保留字符串内合法的 Unicode 行分隔符，并接受符合 Checkpoint Schema 整数语义的数值。这只验证本地完整性，不证明事件来源、事实真实性、授权或安全恢复。
- `bugmaster_core.action_journal_store.ActionJournalStore`：将 `sessionId` 与 `journalId` 映射到 `<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl`。它以 no-follow 目录相对方式逐级遍历配置根及其祖先，检查可信所有者和私有模式位（包括文件系统根目录），并在 macOS 上拒绝扩展 ACL。它只规范化由 root 所有且目标符合预期的 `/tmp`、`/var` 系统别名；其他祖先软链接失败关闭。`initialize()` 通过每个 Session 共用的锁与 Session 发布串行化；只有在该 Session 尚无持久化 revision 时，才创建并同步新的私有 Journal。revision 持久化后，它只重新打开已有 Journal，文件或存储路径缺失时失败关闭。不安全的既有文件会被拒绝且权限保持原样。`open()` 同样要求安全文件已存在，不会创建或修复路径。返回的 Journal 实例保留 Session 目录描述符，并在每次读取和追加前重新检查该目录的 ACL。
- `bugmaster_core.checkpoint_reference_validator.CheckpointReferenceValidator`：在同一共享锁和目录描述符下读取 Checkpoint 与 Session revision，核对 Scope history 锚点、最新 `checkpointRefs` 登记及 Journal Store 的 `journalId`，先验证存储根的可信祖先，再把同一个根目录描述符传给 Checkpoint/Session 快照，并据此相对打开规范 Journal、验证其前缀。调用方不能为声明 ID 另选路径。这不会认证文件内容、事件来源或外部事实；也不校验权威 Scope 文档、不对账预算、不重新核验授权，也不授权恢复。

`approvalRef`、`enforcementRef` 和 Checkpoint 中的哈希都只是结构/完整性信息。它们不能证明审批人身份、审批真实性/有效期、执行来源或事件真实性。可信授权与恢复验证网关仍未实现；R2 必须由工具层执行审批和控制，R3 仍受独立安全策略约束。

Session Schema 保存结构化历史和计数；`SessionStore` 增加本地不可变 revision 持久化，并检查历史引用与计数是否单调变化。可信恢复验证器仍须验证审批引用真实性，将预算计数与不可变 Scope revision 和 Action Journal 对账，核对 Journal 绑定，并在恢复前重新核验当前授权。JSON Schema 不会比较已用计数与对应上限，可信 Session 恢复验证器尚未实现。

本地 Action Journal 使用受限文件权限、单操作 POSIX 文件锁、追加并 `fsync`，以及保守的恢复状态。事件哈希不证明来源或事实。重启后没有结果的 prepared/dispatched 动作仍保持阻断。调用方提供的只读观察只作为未验证的对账声明保存，不会解锁派发；R1/R2 失败结果也仍保持阻断。`scripts/validate_gates.py` 在可信只读验证器和当前授权门禁实现前拒绝所有重放。

## 尚未实现的契约

Skill Manifest、Pattern、Catalog、Capability Registry、Recovery Decision、Oracle、Evidence、完整 Finding 持久化、签署 Review 记录、Report、Regression Recommendation、Eval Manifest 和 Release Manifest 尚未实现。Candidate Assessment 契约不代表这些实体已经完成，也不能取代它们。其证据引用和验证标志只是结构输入；接入可信 Oracle 与 Evidence verifier 前，拒绝逻辑会 fail-closed；真实可信来源仍依赖对应 Adapter。可从 [统一契约](../docs/en/03-contracts.md) 与 [中文统一契约](../docs/zh-CN/03-contracts.md) 中查阅状态和身份约束。当前部分 Schema 不能被视为完整契约套件已通过。

Scope、Feature Inventory、Approval、Action、Event、Checkpoint、Session 和 Candidate Assessment Schema 均有对应的契约测试。Candidate 筛选、Review Event 绑定、拒绝反证和 Benchmark 场景映射由 `tests/unit/test_candidate_assessment.py`、`tests/contracts/test_candidate_assessment_schema.py` 与 `tests/contracts/test_contracts.py` 覆盖；这些测试不能证明证据真实性，也没有运行正式 Eval 场景。Feature Inventory 测试验证 `examples/openapi/orders.json` 的实际 CLI 输出；Event 测试校验实际 Journal 事件（包括 R2 审批引用）；CheckpointStore 持久化由 `tests/unit/test_checkpoint_store.py` 单测和基于 Schema 的契约集成测试覆盖。`CheckpointReferenceValidator` 使用真实本地存储校验 Session revision、Scope history、最新 Session 登记项、Journal ID 确定性路径解析和 Journal 前缀一致性；它不认证 Journal 内容或事件来源，也不验证可信授权、预算对账或恢复授权。SessionStore 持久化由 `tests/unit/test_session_store.py` 和基于 Session Schema 的契约集成测试覆盖；这些测试不运行可信授权、预算对账或恢复流程。

CI 安装固定版本的测试验证器并执行契约套件。本地使用 Python 3.12，并安装 `jsonschema[format-nongpl]==4.26.0`；可选格式验证器确保 RFC3339 时间字段被执行检查。该依赖仅用于测试，不是 BugMaster 运行时依赖。低于 Python 3.10 的环境应使用仓库 CI 的 Python 3.12 或兼容环境。

