[English](../en/07-release.md)

# MVP / v1.0 路线图、发布门禁与回滚

## Q14=A：完整 MVP 一次性交付

v0.1 作为**唯一完整 MVP 发布目标**，包括 11 Skills、16 Patterns、50 场景、双宿主核心验证、API + Browser Basic、证据与审批、Session 恢复、报告与回归建议、治理门禁。VS-01 不另行作为缩水后的 MVP 发布。

## Go / No-Go

1. 静态、契约、安全固定场景所有阻断测试通过。
2. 所有公开 Skill 均可独立安装并包含 Pattern 闭包，构建摘要正确。
3. Stable/Verified Pattern 来源、正反 Eval 合规；Candidate 明确标注。
4. 本地订单 Demo 正确/缺陷变体经独立参考测试验证。
5. 实际执行 API 和 Browser 路径，不能接受编造的执行证据。
6. E3 / 人工 Review、文件故障恢复、未知副作用核对与 Safe Resume 通过。
7. Codex/Claude Code 兼容声明有真实 Run ID，不默默降级。
8. 固定 50 场景 Eval 和 G0–G3 对照报告、指标阈值校准与审批。
9. 固定源码 Commit、资产 Digest、许可、双语文档和人工发布审批齐全。
10. 回滚演练不删除 `.bugmaster/`，旧程序不兼容新 Schema 时只读或拒绝写入。

真实阻断未解决则 No-Go；不能擅自把 Q14=A 改成分阶段缩小范围。必要时发起新架构决策。

## 后续版本（仍需后续决策）

v0.2 并发/数据一致性，v0.3 深化浏览器，v0.4 Pattern 治理，v0.5 复现，v0.6 PR 风险，v0.7 AI/RAG/Agent，v0.8 多宿主/模型评估，v0.9 可选数据交换，v1.0 稳定公开契约与质量成熟度。Q9 不会被后续版本自动变更为写测试代码。

## 回滚原则

固定版本恢复、保留用户 Finding/Evidence/Session、能力禁用优先于越权执行。数据库式不可逆数据迁移不在 MVP；文件 Schema 变更也不承诺任意逆向恢复。
