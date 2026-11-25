# W1-03 Schema 引用完整性与版本兼容契约设计

- **日期：** 2026-11-25
- **状态：** 实现、验证与 Codex 代码/聚焦安全扫描通过；项目所有者已于 2026-11-25 指示继续推进 PR（拉取请求）。后续按 `develop` → `main` 单 PR 流程审阅和手动合并，合并前不启动下一片。
- **工作流 / 功能义务：** W1-03 / `TDD-CON-012..020`。
- **风险：** R2；依 Q15 进行 Codex 代码扫描与安全扫描。此范围不要求独立真人安全审查。
- **基线：** PR #20 合并提交 `42f9b5d`；开发分支 `develop` 已与个人 fork 的 `main` 同步。

## 目的

为仓库内 JSON Schema（JSON 数据结构规则）建立统一的本地引用注册表与版本入口契约，避免某一校验器遗漏跨文件 `$ref`（规则引用）、引用 URI（统一资源标识符）拼写错误后尝试远程解析，或不同规则对 `schemaVersion`（契约版本）的要求不一致。

本切片只验证规则文件及规则之间的 `$ref` 图。业务记录中的 `approvalRef`、`oracleRef`、`evidenceRefs`、`actionRefs` 等数据引用仍由各自契约绑定器或存储负责；JSON Schema 引用完整不代表业务记录存在、来源可信或有权限。

## 范围与规则

- 所有 `schemas/*.schema.json` 必须使用 Draft 2020-12（JSON Schema 标准版本），且使用全仓唯一的绝对、无片段 `$id`（规则标识）；重复检查统一协议/主机名大小写，并折叠 HTTP（超文本传输协议）/HTTPS（安全超文本传输协议）默认端口。
- 每份 Schema 必须在 `required` 中要求 `schemaVersion`，并通过 `const` 将其固定为 `主版本号.次版本号` 字符串。
- 加载时先校验所有 Schema，再将顶层与嵌套 `$id` 资源注册到本地 `Registry`（注册表），随后按每个 Schema 子规则的有效基准 URI 解析 `$ref` 与 `$dynamicRef`。本地 JSON Pointer（JSON 指针）和跨文件引用必须均能解析到有效的 Schema 或布尔 Schema；`default` 等普通数据字段中的对象不作为 Schema 子规则扫描。
- 对 URI 等价但字面拼写不同的引用，仅为已知本地资源添加精确别名；注册表没有网络检索回调。目标不在本地 Schema 集合中、引用路径不存在或 URI 无法解析时，抛出 `SchemaRegistryError` 并阻止调用方继续使用校验器。
- `contract_binding` 与 Candidate/Finding（候选记录/缺陷记录）本地存储复用 `get_schema_validator()`，不再各自维护外部 Schema 注册特例。
- 记录只接受各自 Schema 固定的 `schemaVersion`。没有隐式迁移，不宣称不同版本之间自动向后兼容；新增支持版本须单独新增/修改 Schema 和迁移决策。

## 选择与边界

选用封闭本地注册表，而不是允许 `$ref` 临时访问网络。当前 Candidate Schema 曾以 HTTPS URI 引用 Candidate Assessment Schema；运行时只有一个存储入口显式注册该依赖，其他入口与全仓引用图缺少统一完整性检查。统一注册表让全部校验器遵循同一闭包，并避免外部 Schema 变动影响本地校验结果。

本切片不更改 Schema 字段、ID、业务状态、数据落盘格式或业务记录引用规则；不认证 Oracle（预期行为判定依据）、Evidence（证据）、Approval（审批）或 Reviewer（审核人）；不授权动作、不开放 `can_dispatch()`、不接入 Browser（浏览器）运行时或 Confirmed Gate（缺陷确认门禁），也不提供历史记录迁移。

## 验收

- 现有 12 份 Schema 的唯一 ID、固定版本、Draft 2020-12 结构以及所有本地 `$ref` 均通过注册表检查。
- 正向夹具通过跨文件 `$ref` 校验；本地指针缺失、指向非 Schema 值的引用、外部 URI 未注册、带片段或 URI 等价的重复 ID、版本字段缺失/未固定/格式错误、Schema 结构非法、JSON 文件不可解析等负例均被拒绝。
- 元数据存储的既有校验器读取故障仍被包装成 `MetadataStoreError` 并失败关闭。
- `validate_contract_bindings()` 和 Candidate/Finding 存储现有测试保持通过；验证记录区分单测、契约、安全检查、覆盖率与发布门禁。
- Codex 代码与安全复核没有未解决问题后，再由项目所有者确认并手动合并；若复核揭示独立真人审查需求，另行讨论，不将 Codex 复核冒充真人审查。

## 文档

技术规则同步到 `docs/en/03-contracts.md` 与 `docs/zh-CN/03-contracts.md`；仓库用途说明同步到 `README.md` 与 `README.zh-CN.md`。本设计不改变冻结的 Q1–Q17。
