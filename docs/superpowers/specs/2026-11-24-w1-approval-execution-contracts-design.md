# W1-02 审批与执行契约绑定校验设计

- **日期：** 2026-11-24
- **状态：** 实现及最新修复后的全量验证完成；Ponytail（精简代码审查）发现方法名末尾行终止符问题，三轮 Codex 安全复核发现 Approval 时间、Action.createdAt 和 SHA-256 摘要末尾行终止符问题，均已修复并增加回归用例。最终代码复核与安全复扫完成；复核结果和边界见 TDD 记录。本文件与校验结果都不构成授权证明。
- **工作流 / 功能义务：** W1-02 / `F-AUTH`。
- **基线：** PR #15 合并提交 `d578c61e9ed6b28bad236b2f5c33524df98805bb`。

## 目的

在不执行动作、不授予权限的前提下，校验 Scope（授权范围）、Action（动作）和 Approval（审批）记录之间的结构绑定，避免彼此矛盾的记录被误认为相互匹配。校验结果只表达“记录之间是否一致”，不表达“动作已获授权”。

## 现状与约束

- Scope、Action、Approval 已有 JSON Schema（JSON 数据结构规则），其中包含范围版本、目标、环境、身份、风险、动作摘要、参数摘要与审批有效时间字段。
- Action 与 Approval 对 `method`（方法）的正则约束目前不一致；本切片会将 Approval 约束对齐到 Action，避免合法 Action 方法无法通过审批 Schema。
- JSON Schema 的 `date-time` 格式需要启用 `FormatChecker`（格式检查器）才会被 `jsonschema` 实际校验；本切片会在生产校验边界启用它。
- `bugmaster_core.scope.action_allowed()` 仅允许当前规则覆盖的 R0/R1 条件；R2/R3 仍拒绝。
- `scripts/validate_gates.py` 中的 `can_dispatch()` 对所有风险等级都拒绝派发；仓库没有可认证审批人、审批来源或执行控制的可信宿主网关。
- 普通输入字段、`approvalRef`、摘要和 `enforcementRef` 都不能证明审批来源真实，也不能证明目标系统已强制执行控制。

## 比较过的做法

1. **纯契约绑定校验（已选）：** 校验各记录字段、引用及时间关系的一致性；不认证来源、不授权、不派发。与现有 fail-closed（失败时保持阻断）边界相符，能为后续网关提供可复用的一致性检查。
2. **可信宿主证明接口：** 定义由宿主提供的审批身份、来源事件和强制执行证明接口，但暂不接入具体宿主。其接口形状取决于目标宿主实际能提供的身份和执行证明，当前仓库没有这些证据来源。
3. **实际授权与派发网关：** 消费审批并放行 R0/R1/R2 动作。它会改变目标系统权限和副作用边界，必须先单独讨论宿主身份、撤销、时钟、审批消费、动作级授权及独立真人安全复核要求；不属于本设计。

## 范围

- 对 Scope、Action、Approval 先执行 JSON Schema 校验，再执行跨记录绑定校验。生产校验使用 Draft 2020-12 校验器和 `FormatChecker`；运行环境必须安装提供日期时间格式实现的依赖，不能只在测试环境启用。`date-time` 格式错误在跨记录比较前拒绝。
- Action 与 Scope 的绑定规则：
  - Action 的 `scopeId`、`scopeRevision`、`environmentRef` 必须分别与 Scope 的 `scopeId`、`revision`、`environmentRef` 相同。
  - Action 的 `targetRef` 和 `surface` 必须唯一匹配 Scope 中一个目标；缺失或匹配多个目标均返回不一致。
  - Action 的 `risk` 必须是 `Scope.allowedRisks` 中的枚举值。此处按现有 v1.0 显式列表做成员比较，不按风险名称推导排序；成员关系只表示记录约束，不授予执行权。
  - 只有 `decision=in_scope` 的目标可与 Action 形成一致绑定。`pending_authorization` 和 `out_of_scope` 目标可以单独保留在 Scope 中，但 Action 指向它们时返回不一致，且不会因审批引用改变目标决定。
- Scope Approval（范围审批）绑定规则：
  - 每个 `decision=in_scope` 的目标必须有 `approvalRef`，且该引用必须对应 `kind=scope`、`status=approved` 的 Approval。
  - `Scope target.approvalRef` 必须等于 Approval 的 `approvalId`；Approval 的 `scopeId`、`scopeRevision`、`targetRef`、`environmentRef` 和 `identityRef` 必须分别匹配目标引用及其所属 Scope。类型错误、拒绝状态或任一字段不匹配均返回不一致。
  - `pending_authorization` 和 `out_of_scope` 可没有审批引用；若提供引用，仍须等于对应 Approval 的 `approvalId`，解析为 `kind=scope` 并绑定相同 Scope、目标、环境和身份。该引用不能把目标升级为 `in_scope`。
- Action Approval（动作审批）绑定规则：
  - 对 Action Schema 规定必须含 `approvalRef` 的 R2 状态，`Action.approvalRef` 必须等于对应 Approval 的 `approvalId`，且该记录为 `kind=action`、`status=approved`。
  - 核对 `approvalId`、`scopeId`、`scopeRevision`、`targetRef`、`environmentRef`、`identityRef`、`actionDigest`、`method`、`parameterDigest`、`risk` 和 `count`。其中 `identityRef` 必须等于绑定 Scope 的执行身份；`actionDigest` 必须等于 `Action.intentDigest`。
  - `proposed` 等 Schema 不要求审批引用的状态可以不带 `approvalRef`；若提供引用，仍检查 `Action.approvalRef` 是否等于 Approval 的 `approvalId`，并核对引用类型及全部绑定字段。仅在 Schema 要求审批的状态下，`status=approved` 是一致性前提。
- Action 的 `createdAt` 与 Approval 的 `issuedAt` / `expiresAt` 均先按 RFC 3339 `date-time` Schema 格式校验，再用严格解析器检查完整字符串；Approval 的 `expiresAt` 必须晚于 `issuedAt`。本切片不比较当前时间，也不将 Action 的 `createdAt` 当作授权/派发时间：Action Schema 没有状态转换时间，不能据此证明动作发生在审批有效期内。当前时间有效性与可信事件时间绑定留给未来可信网关。
- Action 内部约束由 Action Schema 单独负责，不在绑定校验器中重复实现：R0 只读、R1 变更动作要求 `enforcementRef`、R3 禁止进入执行态。`enforcementRef` 仍只是字段声明，不能证明宿主实际执行控制。
- Approval 的 `method` 模式调整为与 Action 一致的 `^[A-Z][A-Z0-9_-]*$`，并在两份 Schema 中显式拒绝回车、换行和 Unicode（统一码）行分隔符，避免 `$` 结束锚点接受末尾行终止符；契约测试覆盖数字、下划线、连字符及行终止符，不扩大 Action 已接受的方法范围。Action 与 Approval 的 SHA-256 摘要模式也显式拒绝相同行终止符，防止结束锚点将带换行的 64 位十六进制文本视为合法摘要。
- 返回只描述一致性的 `bindingConsistent`（绑定一致）和排序去重后的 `reasonCodes`（原因码）；包括 `schema-invalid`、`scope-action-mismatch`、`scope-target-missing`、`scope-target-ambiguous`、`target-not-in-scope`、`scope-approval-missing`、`scope-approval-mismatch`、`scope-approval-not-approved`、`approval-reference-ambiguous`、`action-approval-missing`、`action-approval-mismatch`、`risk-not-allowed`、`approval-time-invalid`。不返回 `authorized`（已授权）、`trusted`（可信）或 `dispatchAllowed`（允许派发）字段，也不修改输入。
- 对动作摘要只比较 Action 与 Approval 中的摘要是否相同。本数据模型不包含原始参数，无法在本层重新计算并证明摘要对应的实际动作内容。
- Approval 按 `targetRef` 绑定，不单独绑定 `surface`。若未来可信网关需要区分同一目标引用下不同测试表面的审批，须先评估扩充审批字段或禁止该类重复目标；当前纯契约校验不作为授权依据。

原因码含义：

| 原因码 | 含义 |
|---|---|
| `schema-invalid` | Scope、Action 或 Approval 未通过 JSON Schema（JSON 数据结构规则）或日期时间格式校验 |
| `scope-action-mismatch` | Action 的 Scope 标识、修订号或环境与 Scope 不一致 |
| `scope-target-missing` / `scope-target-ambiguous` | 没有唯一的 `targetRef`（目标引用）与 `surface`（测试表面）组合 |
| `target-not-in-scope` | Action 匹配的 Scope 目标尚未纳入授权范围 |
| `scope-approval-missing` / `scope-approval-mismatch` / `scope-approval-not-approved` | 范围审批引用无法解析、类型或绑定字段不符、或必需状态不是 approved（已批准） |
| `approval-reference-ambiguous` | 同一审批标识对应多条记录，引用无法唯一解析 |
| `action-approval-missing` / `action-approval-mismatch` | 动作审批引用无法解析，或审批类型、状态、动作字段与 Action 不一致 |
| `risk-not-allowed` | Action 风险不在 Scope 显式允许的风险清单中 |
| `approval-time-invalid` | Approval 的过期时间不晚于签发时间 |

这些原因码只解释一致性检查结果，不代表风险等级或动作可执行。

## 不在本范围

不认证审批人或来源事件，不验证签名、撤销状态或宿主控制，不判定审批相对于当前时间是否有效，不对账或消费预算，不改变 `can_dispatch()` / `action_allowed()` 的放行结果，不调用 HTTP/浏览器/其他目标工具，不接入 Browser Adapter（浏览器适配器）、Evidence/Finding Gate（证据/缺陷确认门禁）或 Agent Runtime（智能体运行时），也不修改冻结的 Q1–Q17。

## 验收与审查

- 先为正向绑定、Scope/Action 审批类型与状态错误、执行身份不匹配、各跨记录字段不匹配、目标缺失/重复/未纳入范围、风险不在清单、缺失审批、伪造的自述字段、无效时间格式/区间、方法模式兼容性及摘要末尾行终止符写 RED（先失败）测试。
- R0/R1/R3 的记录内约束由 Schema 契约测试验证；绑定校验测试验证 Schema 失败会阻止进入跨记录比较，避免复制一套风险状态规则。
- 在有效绑定记录存在时，`can_dispatch()` 对 R0/R1/R2/R3 仍全部拒绝；校验通过不能成为执行授权。
- 新增生产函数达到仓库要求的 100% 单元测试行覆盖；运行相关单测、契约测试、安全测试及适用门禁，并记录实际结果。
- PR 由 Codex 完成代码审查与安全审查，项目所有者最终确认并手动合并。任何需要独立真人安全审查、或需要真实宿主身份/动作权限的后续范围，先另行讨论。
