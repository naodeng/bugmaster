# BugMaster 名称一致性与工程验证报告

**日期：2026-11-18**
**状态：命名迁移完成；工程实现仍为开发基线；正式发布 No-Go**

## 范围与迁移决策

- 唯一公开品牌：BugMaster（Bug 大师）；仓库目标 `AI-Native-QA-Lab/bugmaster`。
- 11 个未公开发布的 Skill 身份已统一采用 Discovery / Validation / Reporting 名称，目录、`SKILL.md`、Registry、脚本、README、文档和测试已同步迁移。
- 不保留旧 Skill 名称、旧 Registry 名称和旧品牌兼容别名；`scripts/check_branding.py` 对内容和文件路径执行全仓扫描。
- 稳定业务/质量契约保持不变：16 个 Pattern ID（如 `BP-API-002`）、Finding ID、Q1–Q17 与 ADR 编号。
- 开发过程文档使用中文；项目技术文档英文默认，中文互链。

## 唯一合法 Skill ID 清单

1. `bug-discovery`
2. `discover-business-logic`
3. `discover-boundary-defects`
4. `discover-state-defects`
5. `discover-api-contract-defects`
6. `discover-api-idempotency-defects`
7. `discover-web-interaction-defects`
8. `discover-ui-api-inconsistencies`
9. `bug-validation`
10. `bug-reporting`
11. `bug-regression-recommendation`

## 本地实际执行的检查

| 检查 | 结果 | 说明 |
|---|---|---|
| 品牌及 Skill 名称扫描 | PASS | 路径 + UTF-8 代码/文档内容，含语义遗留前缀 |
| Catalog/Registry 结构 | PASS | 11 个 Skill 对应注册信息与 16 个 Pattern |
| Benchmark Manifest 结构 | PASS | **不等于 50 场景已执行** |
| 单元测试 | 8/8 PASS | 当前最小核心模块 |
| 契约测试 | 18/18 PASS | 含 4 项新增命名一致性测试 |
| 11 个 Skill 本地独立打包 | 11/11 PASS | 仅构建与依赖拷贝，不代表在 Codex/Claude 实际安装有效 |
| 发行门禁 | NO-GO（预期） | 真实覆盖证据、核心 Happy/Negative/Edge、功能覆盖仍缺失 |
| 真实 API/Web 自主探索 | 未验证 | 不能声称已经可供普通用户安装使用 |
| Claude Code/Codex 双宿主 | 未验证 | 后续需要真实主机端到端验证 |

## 发布约束与后续开发

- CI 应继续执行 `scripts/check_branding.py` 和 `tests/contracts/test_skill_naming.py`，任何旧名称复现均阻断。
- 必须按强 TDD 顺序 RED → GREEN → REFACTOR → VERIFY；单元行覆盖 100%，业务功能覆盖严格大于 60%，每个核心功能至少 Happy / Negative / Edge 三类真实通过用例。
- GitHub 目标仓库是否已创建、分支保护、GitHub Actions 实跑与双人发布授权均未在本地证明。
- 不得将这里的迁移检查报告视作已实现的完整 MVP 或发布许可。
