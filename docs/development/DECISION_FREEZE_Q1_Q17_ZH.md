# BugMaster 已确认决策 Q1–Q17（中文冻结摘要）

| 编号 | 选择 | 约束 |
|---|---|---|
| Q1 | A | 独立 Skill Bundle，不自建 Agent Runtime |
| Q2 | A | 完全独立安装，不依赖其他 QA 仓库 |
| Q3 | B | Hybrid Discovery，实际工具级 R0–R3 控制 |
| Q4 | B | API-first + Browser Basic |
| Q5 | B | 集中版本化 Pattern Catalog |
| Q6 | B | 三值规则过滤+有边界语义重排+降级 |
| Q7 | B | E0–E4 证据等级、有效 Oracle、人工 Review |
| Q8 | B | Finding SSOT + 独立 Evidence Blob，Local-first |
| Q9 | A | 仅回归建议，不生成或提交测试代码 |
| Q10 | B | 50 个真实执行 Eval，G0–G3 对照 |
| Q11 | B | 基于证据的质量治理 |
| Q12 | B | Portable Core + Codex-first / Claude Code 验证 |
| Q13 | B | Session/Action Journal/Checkpoint/Safe Resume |
| Q14 | A | 全量 11 Skills、16 Patterns、50 场景、双宿主，一次性 MVP |
| Q15 | D | Codex 对每个 PR 做代码扫描；R2/R3 还做安全扫描；项目所有者查看结果后手动合并，不要求真人签署 |
| Q16 | B | 发起人与独立复审者两人发布授权 |
| Q17 | A | GitHub-first 实际工程实施 |

附加确认：品牌全量迁移为 BugMaster，旧项目品牌无别名；测试对象范围选择 B（维持 API + Browser Basic，APP 只预留）；加入 Test Surface/Scope Discovery、业务 Oracle、跨入口归因去重与 Session 汇总报告，不扩大 Q14 范围；开发过程中文、公开技术文档英中互链、强 TDD、100% 单元行覆盖、业务功能有效覆盖 >60%、核心功能 Happy/Negative/Edge 三类实际测试。
