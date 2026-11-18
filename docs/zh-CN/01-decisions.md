[English](../en/01-decisions.md)

# 架构决策登记簿

状态：已在对话中确认；尚未在 GitHub 实施或提交。

| ID | Choice | 决策 |
|---|---|---|
| Q1 | A | Skill Bundle；不自建执行引擎/UI |
| Q2 | A | 完全独立于 Awesome QA Skills |
| Q3 | B | 混合模式：指导/辅助/有界自动 |
| Q4 | B | API 优先 + 基础浏览器 |
| Q5 | B | 集中模式库 + 引用 |
| Q6 | B | 规则筛选 + Agent 语义重排 |
| Q7 | B | 证据分级与验证门禁 |
| Q8 | B | 结构化 Finding + Markdown + 证据包 |
| Q9 | A | 只给回归建议，不写测试代码 |
| Q10 | B | 可执行证据驱动基准 |
| Q11 | B | 风险分级质量治理与发布门禁 |
| Q12 | B | 可移植核心；Codex 优先，Claude Code 验证 |
| Q13 | B | 版本化会话、日志与安全恢复 |
| Q14 | A | 完整 MVP 一次交付；垂直切片仅为内部集成检查点 |

ADR-014：一次交付完整 MVP。Vertical Slice 不构成分阶段缩减 MVP。若宿主缺少可强制的权限边界，应禁用有界自动执行，而不是降低安全要求。


## Q16 — 正式发布授权

**B：双人发布授权。** RI 发起，另一名真实独立的 IRR 对固定 Commit、Manifest Digest、产物来源和质量证据签署批准后，受保护 CI 才能发布。Q14=A 完整 MVP 一次性交付范围不变。详见 ADR-016。

## Q17 — 工程实施位置

**A — GitHub-first**。GitHub 仓库尚不可访问时先准备可导入的本地工程资产，不得宣称已经提交。完整 v0.1 MVP 仍一次性交付。
