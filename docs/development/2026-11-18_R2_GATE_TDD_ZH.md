# R2 缺少可信网关时拒绝派发：TDD 记录

**日期：** 2026-11-18
**Workstream：** W5 工具安全
**Feature：** `F-AUTH`
**风险：** R2 变更操作；本切片不连接任何目标系统。

## RED

在 `tests/contracts/test_contracts.py` 新增 `test_r2_self_asserted_fields_never_substitute_for_trusted_gateway`。输入同时声称审批已批准、来源已验证、动作摘要与 Scope Revision 相符，策略也声称 `enforcement="enforced"`；测试要求当前仓库缺少可信审批网关时仍拒绝派发。

执行 `python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py' -k self_asserted -v`：失败。实际 `can_dispatch` 返回 `True`，暴露了普通字典自述字段被当作可信来源与强制执行证明的问题。

## GREEN

在 `scripts/validate_gates.py` 中保留 R3 阻断，并将 R2 在此实现阶段固定拒绝。只有能从可信宿主/网关获得经过验证、并绑定具体 Scope Revision 与规范化 Action 的证明后，才可以实现 R2 放行；输入文档中的 `provenanceVerified` 或 `enforcement` 字段不能代替证明。

同步更新已有 R2 契约测试：无论策略字段声称 advisory 还是 enforced，都不得由当前纯数据 helper 放行。

## REFACTOR

保留 R0/R1 的既有逻辑和 R3 的显式拒绝；没有引入新的网关抽象，也没有对外宣称 R2 已支持。正式能力边界写入代码注释与进度表。

## VERIFY

| 检查 | 命令 / 环境 | 结果 |
|---|---|---|
| RED 回归 | `python3.12 -m unittest discover -s tests/contracts -p 'test_contracts.py' -k self_asserted -v` | RED，原实现错误放行 |
| 授权相关契约 | 同上，去掉 `-k` | PASS，11/11 |
| 单元测试 | Python 3.12：`python -m unittest discover -s tests/unit -v` | PASS，12/12 |
| 全量契约 | Python 3.12 + `jsonschema==4.26.0`：`python -m unittest discover -s tests/contracts -v` | PASS，26/26 |
| 品牌扫描 | `python3.12 scripts/check_branding.py` | PASS |

本切片不解除 R2 阻断；当前 R2/R3 不能执行。Release 仍为 **No-Go**，真实审批网关和工具层强制测试仍是 W5 阻断工作。
