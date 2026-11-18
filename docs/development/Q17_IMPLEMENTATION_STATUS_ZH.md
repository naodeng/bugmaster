> 历史 Q17 状态记录；以 `docs/development/IMPLEMENTATION_STATUS_ZH.md` 为最新状态准据。

# Q17 工程实施记录

Q17=A GitHub-first 已确认；当前 GitHub 目标 `AI-Native-QA-Lab/BugMaster` 未查到可访问仓库，且本会话 GitHub 连接器不提供创建仓库操作，因此以下文件仍为**本地源码候选**，未提交 GitHub，也没有建立任何 Issue。

## 事实与验收状态

- Q1–Q17 决策：A,A,B,B,B,B,B,B,A,B,B,B,B,A,B,B,A。
- 计划完整 MVP：11 Skills、16 Patterns、50 Eval、2 宿主。均保持在发布验收范围。
- 已准备：11 份基础 SKILL.md 及中文摘要，16 个 Candidate Pattern 元数据，Registry，确定性保守 Gate、Standalone 打包器、10 个单元/契约测试、50 项 **planned** Benchmark Manifest、CI 预检、W0–W11 Issue 导入清单。
- 未实现：真正的 HTTP/Browser 受控 Action Gateway、Session Journal 强持久化、完整 E0–E4 Gate、Finding 版本化、真实订单 Demo 与注入缺陷、50 个可执行 Benchmark、Codex/Claude Code 实际安装验证、双人发布保护。
- 未验证：所有宿主安全强制、GitHub Environment/Ruleset、真实评估质量指标及发布状态。

## 关键 Spike

| ID | 目标 | 当前状态 |
|---|---|---|
| BLK-01 | 独立安装闭包 | 仅本地打包器测试；宿主验证待做 |
| BLK-02 | Tool Gateway 权限硬约束 | 仅保守授权判定单测；工具拦截待做 |
| BLK-03 | Journal/Pointer 故障恢复 | 待做 |
| BLK-04 | 真实证据来源验证 | 模型自述拒绝单测；工具来源待做 |
| BLK-05 | Ground Truth 隔离 | 待做 |
| BLK-06 | Browser 越界/交互适配 | 待做 |
| BLK-07 | 端到端完整集成 | 待做 |

## GitHub 首次导入

1. 在组织 `AI-Native-QA-Lab` 中创建 `BugMaster`（需仓库创建权限）。
2. 将本目录作为初始化候选提交到**新分支**；由 Q15 Reviewer 审核后合并，而非绕过审核写 main。
3. 使用 `docs/development/Q17_GITHUB_IMPORT_BACKLOG.csv` 导入 Issues，先创建 W0–W11 Epics 再建立依赖。
4. 启用受保护分支、最小权限 CI；发布工作流保持 No-Go，直到 Q16 真实双人签署机制验证。
5. 执行真实 Codex/Claude Code 安装与安全测试；不得将计划测试误标为已完成。

## 开发验证命令

```bash
python -m unittest discover -s tests -v
python scripts/validate_catalog.py
python scripts/validate_benchmark.py
python scripts/build_standalone.py --skill discover-api-idempotency-defects
```

**Q14=A 不变：完整 MVP 一次正式发布。** 这些只是启动资产，不是已完成 MVP。
