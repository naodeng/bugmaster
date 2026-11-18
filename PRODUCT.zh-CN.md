# BugMaster（Bug 大师）— 产品与完整 MVP 基线

[English](PRODUCT.md) · [中文开发规范](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md)

## 产品目标
BugMaster 是独立、Local-first 的 Agent Skills Bundle，面向有权限的软件系统进行**有边界的自主探索性测试**：没有指定功能点也能发现可测试范围、风险排序、执行真实探索、利用业务 Oracle 与证据验证疑似缺陷、输出可追溯报告。

## 使用路径
1. 用户给 URL、API/OpenAPI 或具体功能；**提供 URL 并不构成授权**。
2. 只在允许边界内进行只读范围发现，形成 Feature Inventory、测试入口与来源证据。
3. 对候选范围按业务影响、故障风险、复杂度、可观测性和不确定性排序，列明已授权/待授权/排除。
4. 在已批准的范围与预算内进行假设→实验→观察→更新循环；R2 操作必须经过可执行授权门禁，R3 默认拒绝。
5. 根据项目明确的需求/API 契约/状态机/业务不变量建立 Oracle；Pattern 仅提出可疑点，不作为 Bug 结论。
6. 证据有效且达到 E3+ 后才能按策略确认 Finding；否则输出 Suspected 或 Needs Review。
7. 输出 Session 探索报告（发现/授权/已探索/未探索的功能、方法、真实动作、问题分组、剩余风险），以及单独的缺陷报告与回归**建议**。

## 范围
- v0.1：REST/JSON/OpenAPI API-first + Browser Basic + 基础 UI/API 一致性，11 Skills、16 Patterns、50 个真实可执行 Benchmark、双宿主正式验证，一次性交付。
- APP：Android/iOS 只保留 Test Surface 分类和未来适配点；**不承诺 v0.1 自动原生 APP 测试**。
- 测试入口不等于责任层：Web UI 观察到 API 错误时，根因可能是网关/后端/数据，无法确认时应标记 `unknown`。
- 相同缺陷跨 API 和 Web 入口只能关联为一个 canonical Finding，保存各自独立证据。
- Local-first 工作目录统一 `.bugmaster/`，仅采用新名称，运行数据不得无审批破坏性重写。

## 测试验收硬约束
**强 TDD：先 Red 失败测试，再 Green 最小实现，再 Refactor，最后 Verify 留痕。**
**单元测试代码行覆盖 100%**；**业务功能有效执行覆盖率严格大于 60%**；**每个核心功能至少 Happy / Negative / Edge 三类真实用例**。缺少实测证据不得视为通过。

## 当前阶段
仅工程骨架及初始契约单测；真实自主探索、双宿主验证、完整 Eval 与公开发布均未完成。状态：开发中 / 发布 No-Go。
