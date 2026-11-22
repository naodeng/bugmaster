# BugMaster v0.1 完整 MVP 实施顺序（中文）

## 开发分解（全部必须验收）
| W | 模块 | 实际实施与强 TDD 路径 |
|---|---|---|
| W0 | 开发基线 | 文件名/品牌一致性 Red 测试→迁移和双语文档→静态/结构 Gate |
| W1 | 数据契约 | Scope、Surface、Feature、Oracle、Finding、Evidence、Journal JSON Schema；对非法输入先写 Negative tests |
| W2 | 11 Skills | 基于仅 URL/OpenAPI 触发的探索流程；独立安装、可执行 Eval；先失败契约与宿主测试 |
| W3 | 16 Patterns | 每条 Pattern 的适用/排除、真实 Oracle、实验、反例、证据、来源；真实缺陷/正常实现对照 |
| W4 | 路由与自主循环 | 只读发现→范围授权→风险排序→三值过滤→工具执行→更新假设；超时/预算/拒绝负例 |
| W5 | 权限执行 | 真正 API/Browser 动作级 R0–R3 强制门禁、审批 digest 校验与禁用越界；BLK-02 |
| W6 | 安全恢复 | append-only Journal、Checkpoint、unknown-result 对账、崩溃故障注入；BLK-03 |
| W7 | 发现与报告 | 确认可追溯 Bug、跨入口去重、Feature Coverage、Session Summary、中英文 Finding 报告与 Redaction |
| W8 | 回归建议 | 基于 Confirmed Finding 给可执行测试建议但不修改测试代码 |
| W9 | Benchmark | 50 场景 real-run correct/defect/ambiguous 变体，隔离 Ground Truth，G0–G3 对照；BLK-05 |
| W10 | 双宿主 | 先比较 Codex Computer Use、ego-browser、agent-browser、Playwright CLI/MCP 等浏览器工具并记录 local-first / 证据 / 隔离 / 权限取舍，再做 Codex 和 Claude Code 实际安装、API/Browser 与权限/兼容矩阵；BLK-01/06；不新增 BugMaster Skill 或 Agent Runtime |
| W11 | 发布治理 | 风险独立审核、Tag/Attestation、双人发行批准、恢复演练；BLK-07 |

## 阻断 Spikes
BLK-01 独立安装；BLK-02 动作权限强制；BLK-03 Crash Consistency；BLK-04 证据真伪；BLK-05 Ground Truth 隔离；BLK-06 双宿主 Browser scope；BLK-07 全链路。每个 Spike 的 Red/GREEN/反例/环境证据需纳入 `docs/development/` 中文记录。

## 首个完整纵向路径（内部，不是缩小的 MVP）
本地订单系统：仅提供 URL/OpenAPI→发现订单端点→冻结允许范围→授权重复创建操作→有/无 Bug 对照→验证权威订单状态→生成 E3 Finding→输出 Session Report/单项报告；遇到未知写入结果必须停止重放。完成后同样标准扩展全部冻结范围。

## 发布 Go/No-Go
覆盖率和所有核心三类用例只是必要条件，仍需完整 11/16/50/2 hosts、真实执行和独立签署。未创建 Github 仓库，当前 No-Go。
