# Approval 与 Action JSON Schema：TDD 记录

**日期：** 2026-11-18
**Workstream：** W1 数据契约 / W5 授权绑定
**实现范围：** `schemas/approval.schema.json`、`schemas/action.schema.json` 及契约样例。Schema 只验证结构，不执行动作或证明审批真实。

## RED

先分别新增 `tests/contracts/test_approval_schema.py` 与 `tests/contracts/test_action_schema.py`，覆盖有效 Scope/Action Approval、规范化 Action、R0/R1/R2/R3 行为边界、摘要绑定、过期格式、未知字段和引用缺失。

Approval 首次执行退出码 5：`schemas/approval.schema.json` 尚不存在。补入 Schema 后，6 项通过、时间戳负例失败：安装的基础 `jsonschema` 没有启用 `date-time` 检查，`FormatChecker` 对未知格式按规范不报错。检查依赖 metadata 后发现需要可选格式实现；因此 CI 和本地规范改为固定 `jsonschema[format-nongpl]==4.26.0`，启用 RFC3339 校验，再次执行 7/7 通过。

Action 首次执行退出码 5：`schemas/action.schema.json` 尚不存在。失败来自计划内 Schema 缺失，非测试或导入错误。

## GREEN

新增 Approval 与 Action Schema 以及 4 个示例：`scope-approval.json`、`action-approval.json`、`action-readonly.json`、`action-r2-authorized.json`。

- Approval 分 `scope` / `action` 两类。均绑定 Scope ID/Revision、目标、环境、执行身份、审批人引用、宿主来源事件引用、签发与到期时间；R2 Action Approval 额外绑定规范化 Action 摘要、参数摘要、方法和次数。拒绝记录必须说明原因；Action Approval 的风险仅接受 R2。
- Action 必须有 Session/Action/sequence、目标表面、方法、参数与意图 SHA-256、环境、Scope 修订、风险、变更分类、次数和创建时间。
- R0 只能只读；R1 变更动作达到执行状态时需要 enforcement 引用；R2 变更动作达到授权/执行状态时需要 Approval 引用；R3 和 Android/iOS/unknown 不得进入 dispatched/completed 状态。
- Schema 禁止写入 `provenanceVerified` 一类自我声明字段。所有审批/强制引用都只是指针，运行时仍必须检查可信宿主事件与精确绑定。

## REFACTOR

将时间戳格式检查纳入明确的 test-only extra，而不是只保留 Schema `format` 注解；补充 Scope → Approval 与 Action → Approval fixture 关联断言，避免示例间 ID、目标、摘要或修订漂移。没有改变已确认风险策略。

## VERIFY

| 检查 | 命令 / 环境 | 结果 |
|---|---|---|
| Approval Schema | Python 3.12 + `jsonschema[format-nongpl]==4.26.0` | PASS，7/7 |
| Action Schema | Python 3.12 + `jsonschema[format-nongpl]==4.26.0` | PASS，11/11 |
| R2 Gate | `test_r2_self_asserted_fields_never_substitute_for_trusted_gateway` | RED：原 helper 错误放行；修复后 PASS |
| 单元测试 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit -v` | PASS，12/12 |
| 契约全量 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v` | PASS，45/45 |
| 品牌、Catalog、Benchmark Manifest | 对应 `scripts/check_branding.py`、`validate_catalog.py`、`validate_benchmark.py` | PASS；Benchmark 仅结构验证，未实际执行 |

真实 R2 网关仍未实现，当前 helper 明确拒绝所有 R2。Release 仍为 **No-Go**。
