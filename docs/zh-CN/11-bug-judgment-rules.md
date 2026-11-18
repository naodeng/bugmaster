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

## 规则在哪看
- `patterns/taxonomy.json` 分类；`patterns/<domain>/<pattern-id>/pattern.json` 单条规则；`registry/capabilities.json` Skill 路由。
- 正式规则应补齐适用条件、反例排除、业务 Oracle 来源、具体实验、证据、误报防护，并对正常/缺陷实现执行 Eval；当前 16 条仍是 Candidate。
