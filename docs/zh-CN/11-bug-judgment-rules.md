# 缺陷判定规则：Pattern → Oracle → Evidence Gate

[English](../en/11-bug-judgment-rules.md) · [产品说明](../../PRODUCT.zh-CN.md)

## 三层判断
1. **Pattern（缺陷模式）**：指出应该探索什么高风险现象；匹配模式本身不构成 Bug。
2. **Oracle（预期判据）**：从明确需求、OpenAPI、经确认的业务规则或状态机决定正确行为；没有规则时只形成待确认假设。
3. **Validation Gate（证据门禁）**：要求实际授权执行、工具来源证据、可追溯状态、因果/环境复核和必要审批，才能达到 E3 的 Confirmed。

| 测试对象 | 典型规则 | 判定依据 |
|---|---|---|
| API | 状态码/字段、空与缺失、边界、幂等、状态持久化 | 具体 API 契约与状态证据 |
| Web UI | 表单、导航、刷新、重复点击、UI/API 一致性 | UI 规范/真实浏览器动作/关联 API |
| 业务流程 | 优惠券、金额精度、非法状态迁移 | 明确的业务不变量和权威状态 |
| APP | v0.1 仅分类，不可执行 | 后续迭代 |

API 入口发现的问题不一定是 API 层根因；Web 上观察到异常也未必是前端问题。分别保存 testSurface、observedLayer、failureType、suspectedComponent、rootCauseStatus。

候选筛选与 Finding 确认分开。helper 输出的 `candidate` 与 `duplicate` 是基于调用方所给记录的本地暂定筛选结果；它不认证来源标志，也不通过规范存储核验重复引用。Host 在把结果当作权威状态，或据此抑制/汇总记录前，必须核验来源真实性与被引用的 Candidate。Candidate Assessment 始终被 Confirmed Gate 阻断。

Schema 为未来可信 Host verifier 流程保留 `rejected`；当前 helper 不会输出该状态，也不接受调用方传入 verifier 回调。可信 Host verifier 接入前，反证保持 `needs_review`；自述来源标志不能授权自动拒绝。证据缺失或结构无效、规则模糊、证据弱、环境不稳或观察矛盾时也继续 Review。人工反馈须绑定候选 revision 和证据；没有可信宿主审核记录时，反馈不能作为已认证批准。

## 规则在哪看
- `patterns/taxonomy.json` 分类；`patterns/<domain>/<pattern-id>/pattern.json` 单条规则；`registry/capabilities.json` Skill 路由。
- 正式规则应补齐适用条件、反例排除、业务 Oracle 来源、具体实验、证据、误报防护，并对正常/缺陷实现执行 Eval；当前 16 条仍是 Candidate。
