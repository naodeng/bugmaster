[English](README.md)

# 契约 Schema

Schema 使用 JSON Schema Draft 2020-12。契约测试同时校验 Schema 本身与代表性文档。

## 已实现

- `scope.schema.json`：校验带版本的 Scope、逐目标授权决定、已知表面与风险、in-scope 目标的审批引用及有限动作预算。
- `feature-inventory.schema.json`：校验带来源的 Feature Inventory；授权与执行进度保存在独立账本。
- `approval.schema.json`：校验 Scope 或 Action 审批记录、Scope revision 和目标绑定、来源/审批人引用、有效期，以及 R2 所需动作意图字段。
- `action.schema.json`：校验规范化 Action 意图和生命周期状态、R0/R2 变更约束、R2 审批引用、R1 变更强制执行引用，以及不可执行的移动端/未知表面。
- `event.schema.json`：校验版本化 Action Journal 事件封套和 prepared/dispatched/outcome/reconciliation claim 载荷。运行时代码还会核验序号、状态转换、Session 身份、RFC3339 时间和 SHA-256 事件链。
- `checkpoint.schema.json`：校验 Checkpoint 的不可变 Session revision、Scope revision 与 Journal 序号/哈希锚点，并覆盖空 Journal 边界。它只做结构验证；恢复仍需验证所引用的 revision 和 Journal，并重新核验当前授权与预算。
- `session.schema.json`：校验版本化 Session revision、规范生命周期状态、Scope revision 历史、绑定 Scope revision 的审批引用、预算上限与已用计数，以及 Journal/Checkpoint 引用。引用不构成授权或安全恢复证明。
- `bugmaster_core.session_store.SessionStore`：将每个通过校验的 Session revision 保存为独立不可变文件，使用私有 Session 目录和 POSIX 文件锁串行化写入，通过同步临时文件后再以不可覆盖方式落盘；拒绝替换、序号缺口、权限错误和不一致的历史转换。它不会认证 Approval 引用、将预算与 Action Journal 对账，也不授权恢复。Windows 行为尚未验证。
- `bugmaster_core.checkpoint_store.CheckpointStore`：按 Checkpoint ID 的哈希在私有 Session 目录下持久化通过 Schema 校验的 Checkpoint。它与 SessionStore 共用 POSIX 单 Session 锁，通过同步临时文件和不可覆盖硬链接落盘，并拒绝损坏记录或权限不私有的 Checkpoint 目录。它不会验证引用的 Session revision、Scope revision 或 Journal head 是否存在或真实，也不授权恢复。Windows 行为尚未验证。
- `bugmaster_core.action_journal.ActionJournal.matches_prefix(sequence, head_hash)`：先校验完整本地 Journal，再比对 Checkpoint 前缀；拒绝重复 JSON 键、软链接、硬链接、FIFO 和非普通文件，固定每一级父目录身份，并在取得锁后及成功返回前复核父目录/日志文件身份。每个实例首次追加前同步完整目录链；已观察到的 Journal 消失或被替换时失败关闭。它按 LF 解析 JSONL，保留字符串内合法的 Unicode 行分隔符，并接受符合 Checkpoint Schema 整数语义的数值。这只验证本地完整性，不证明事件来源、事实真实性、授权或安全恢复。
- `bugmaster_core.checkpoint_reference_validator.CheckpointReferenceValidator`：在同一共享锁和目录描述符下读取 Checkpoint、锚定的 Session revision 与最新 Session revision，核对 Scope history 锚点、最新 `checkpointRefs` 登记和本地 Journal 前缀。它不会将 Session 的 `journalId` 绑定到 Journal 路径，不认证事件、不校验权威 Scope 文档、不对账预算、不重新核验授权，也不授权恢复。

`approvalRef`、`enforcementRef` 和 Checkpoint 中的哈希都只是结构/完整性信息。它们不能证明审批人身份、审批真实性/有效期、执行来源或事件真实性。可信授权与恢复验证网关仍未实现；R2 必须由工具层执行审批和控制，R3 仍受独立安全策略约束。

Session Schema 保存结构化历史和计数；`SessionStore` 增加本地不可变 revision 持久化，并检查历史引用与计数是否单调变化。可信恢复验证器仍须验证审批引用真实性，将预算计数与不可变 Scope revision 和 Action Journal 对账，核对 Journal 绑定，并在恢复前重新核验当前授权。JSON Schema 不会比较已用计数与对应上限，可信 Session 恢复验证器尚未实现。

本地 Action Journal 使用受限文件权限、单操作 POSIX 文件锁、追加并 `fsync`，以及保守的恢复状态。事件哈希不证明来源或事实。重启后没有结果的 prepared/dispatched 动作仍保持阻断。调用方提供的只读观察只作为未验证的对账声明保存，不会解锁派发；R1/R2 失败结果也仍保持阻断。可信只读验证器尚未实现。

## 尚未实现的契约

Skill Manifest、Pattern、Catalog、Capability Registry、Recovery Decision、Oracle、Evidence、Finding、Review、Report、Regression Recommendation、Eval Manifest 和 Release Manifest 尚未实现。可从 [统一契约](../docs/en/03-contracts.md) 与 [中文统一契约](../docs/zh-CN/03-contracts.md) 中查阅状态和身份约束。当前部分 Schema 不能被视为完整契约套件已通过。

Scope、Feature Inventory、Approval、Action、Event、Checkpoint 和 Session Schema 均有对应的 `tests/contracts/` 测试。Feature Inventory 测试验证 `examples/openapi/orders.json` 的实际 CLI 输出；Event 测试校验实际 Journal 事件（包括 R2 审批引用）。CheckpointStore 持久化由 `tests/unit/test_checkpoint_store.py` 单测和基于 Schema 的契约集成测试覆盖。CheckpointReferenceValidator 单测使用真实存储和仅供测试使用的文档接受验证器；跨存储 Schema 契约测试使用实际 Checkpoint 与 Session Schema，并验证 Checkpoint 引用字段中的整值 JSON 数字按 Schema 整数语义处理。相关用例检查 Session revision 与 Scope history 引用、最新 Checkpoint 登记和本地 Journal 前缀，但不会把 Session 的 `journalId` 绑定到 Journal 路径、不认证事件、不校验权威 Scope 文档，也不证明可信授权、预算对账或安全恢复。SessionStore 持久化由 `tests/unit/test_session_store.py` 和基于 Session Schema 的契约集成测试覆盖；这些测试不运行可信授权、预算对账或恢复流程。

CI 安装固定版本的测试验证器并执行契约套件。本地使用 Python 3.12，并安装 `jsonschema[format-nongpl]==4.26.0`；可选格式验证器确保 RFC3339 时间字段被执行检查。该依赖仅用于测试，不是 BugMaster 运行时依赖。低于 Python 3.10 的环境应使用仓库 CI 的 Python 3.12 或兼容环境。

