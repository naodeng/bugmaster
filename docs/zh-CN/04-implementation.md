[English](../en/04-implementation.md)

# 完整 MVP 一次性交付实施计划（Q14=A）

## 决策约束

一次性完整 MVP 交付：11 Skills、16 Patterns、50 Benchmark 场景、API 与 Browser Basic、Codex 和 Claude Code 核心验证、Oracle/Evidence/Finding、Safe Resume、Evidence Bundle、回归建议、CI 门禁。Vertical Slice VS-01 只是**内部最早端到端集成验证点**，不能偷换成缩小范围的首个 MVP 版本。

## 工作流与依赖

| 工作流 | TDD 任务 | 依赖 | 完成条件 |
|---|---|---|---|
| W0 架构收敛 | 冻结 ID、状态、目录、阻断风险 | 无 | 基线评审通过 |
| W1 契约 | Schema 正反例、状态机、跨文件引用 | W0 | 全部契约测试通过 |
| W2 Skills | 11 个 Canonical SKILL.md、双语参考、独立打包 | W1 | 所有公开 Skill 可独立安装 |
| W3 Patterns | 16 模式、分类、来源、正反 Eval | W1 | 稳定条目来源与证据合格 |
| W4 Routing | 三值前置条件、规则/语义重排、未知假设 | W1/W3 | 安全路由与降级 |
| W5 Tool/Permission | Scope、Approval、Action Gateway、API/Browser | W1 | 未授权动作阻断 |
| W6 Session | Journal、版本、Checkpoint、核对式恢复 | W1/W5 | 故障注入后无危险重放 |
| W7 Evidence/Finding | Oracle、E0–E4、证据、报告、导出 | W1/W6 | 正反/模糊案例通过 |
| W8 Regression | 仅推荐建议与导出，不写测试代码 | W7 | 数据与行为边界正确 |
| W9 Benchmark | 本地订单系统、正确/缺陷版本、私有答案、50 场景 | W1/W5 | 参考测试验证缺陷注入 |
| W10 Hosts | Codex/Claude Code 安装、API/Browser、降级与权限 | W2–W9 | 有实际兼容证据 |
| W11 Release | 变更分级、CI、G0–G3、回滚演练 | W1–W10 | 一次完整 MVP Go/No-Go |

## VS-01 内部最小闭环

在隔离本地订单 API 上验证重复提交：授权 Scope → discovery Skill → BP-API-002 → Oracle → 真正的人类 R2 审批 → 实际 API 工具 → Action Journal → Evidence → E3 Gate → 不可变 Finding → Markdown/脱敏证据包 → 回归建议 → Checkpoint/Safe Resume。同时测试正确版本（不能误报）、缺陷版本（真实证据）、超时未知结果（不能盲重试）。

## 任务验收 ID

- `TDD-CON-001..020`：契约、状态、引用、审批绑定。
- `TDD-PAT-001..016`：16 Pattern 分类与正反例。
- `TDD-SKL-001..011`：11 Skill 发现、单独安装。
- `TDD-SEC-001..012`：权限边界、恶意输入、脱敏。
- `TDD-ACT-001..012`：动作日志、未知副作用、过期审批。
- `TDD-FND-001..012`：Oracle、证据等级、生命周期、复核。
- `TDD-FS-001..008`：Crash Points、Pointer 与 Journal。
- `TDD-HOST-001..030`：双宿主发现与行为。
- `TDD-EVAL-001..050`：基准数据、评分和答案隔离。

## 全量交付定义

全部范围存在并经过真实验证、确定性门禁全绿、安全固定场景零违规、正确与缺陷实现真实执行、G0–G3 评估可审计、双宿主声明与日志一致、双语文档评审、发布与回滚演练通过。若真实阻断导致完整 MVP 不可行，须重新提出架构决策，不得默默改为分阶段 MVP。
