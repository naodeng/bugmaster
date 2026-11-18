# 自主范围发现、测试入口、归因去重与报告契约

[English](../en/12-scope-surfaces-and-reporting.md)

## 用户只给 URL/OpenAPI 时
在授权的只读范围识别路由/端点/参数/业务操作，生成 Feature Inventory（每个候选带来源）、风险排序与待批准 Scope；**不默认自动测试所有发现的域名、登录区或写接口**。确认风险级别、动作预算及隔离环境后，才允许执行对应动作。

三类记录严格分开：`discovered` 只表示功能被观察到；`in_scope/out_of_scope/pending_authorization` 表示授权；`planned/explored/partially_explored/blocked/not_explored` 表示真实测试进度。

当前本地 CLI 可读取 OpenAPI 3 JSON 文件，为每个声明的操作生成稳定 Feature ID，并提供 operation、parameters、requestBody、responses 和有效 security 声明的 JSON Pointer 来源。运行 `python scripts/discover_openapi.py examples/openapi/orders.json --source-ref examples/openapi/orders.json`。这只记录规格声明，不会抓取文档、证明线上端点存在、授予访问权限或发送请求。URL 与 Browser 动态发现尚未实现。

## API/Web/APP
v0.1 仅 REST/JSON/OpenAPI 与 Browser Basic 有执行路由；`android/ios` 仅用于记录未来功能，不能作为已支持能力。测试入口 `testSurface` 不等于问题归属 `observedLayer`；不可确定的根因标 `unknown/suspected`。

## 探索优先级
业务影响 0.30 + 故障风险 0.25 + 复杂度 0.20 + 可观测性 0.15 + 未知度 0.10（候选启发式，应由 Benchmark 调整）。高风险且 Oracle 不确定时，优先澄清业务预期而非宣布 Bug。

## 跨入口去重
同一订单副作用可能由 Browser 和 API 两处观测；用关联业务操作、权威业务状态和因果证据确定 canonical Finding，保留每个入口的独立证据，不能根据两个相似错误提示就强制合并。

## 报告必须覆盖
项目/环境/模式、已发现功能、授权与排除范围、已实际探索/部分/未执行/阻断功能及原因、动作/Pattern/Oracle、已确认和疑似缺陷、归因不确定性、跨入口去重、单个 Bug 复现与证据、剩余风险、回归建议。没有发现 Bug 不能等同测试通过。

## Blind-scope Eval
只给 URL 的 Browser 场景、只给 OpenAPI 的 API 场景、跨域越界阻断、发现新相关功能动态调整范围、Android/iOS 禁止自动路由均应纳入原有 50 个 Benchmark 配额中。
