# BugMaster v0.1 完整最小可行产品（Minimum Viable Product，MVP）实施顺序（中文）

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
| W10 | 双宿主 | 先比较 Codex Computer Use、ego-browser、agent-browser、Playwright CLI（命令行接口）/MCP（模型上下文协议）等浏览器工具，并记录本地优先（local-first）、证据留存、隔离与权限取舍；再做 Codex 和 Claude Code 实际安装，验证 API（应用程序接口）/Browser（浏览器）能力及权限/兼容矩阵；BLK-01/06；不新增 BugMaster Skill（技能包）或 Agent Runtime（智能体运行时） |
| W11 | 发布治理 | Q15 Codex 代码/安全扫描记录、Tag/Attestation、Q16 双人发行批准、恢复演练；BLK-07 |

## W5 授权来源边界与停止条件

- **调研基线：** 2026-11-25 的 [Codex 宿主审批边界调研](2026-11-25_W5_CODEX_HOST_APPROVAL_BOUNDARY_RESEARCH_ZH.md)显示，普通 MCP（模型上下文协议）审批只门控宿主工具调用；BugMaster 无法从调用结果验证本次动作的真人授权。实验性 `userVerification`（设备用户验证）路由按当前官方源码仅接受特定宿主自有 Apps（宿主集成应用）服务；当前安装的 Codex Desktop 协议和界面尚未核实。
- **当前门禁：** `scripts/validate_gates.py` 中的 `can_dispatch()` 对所有风险等级均拒绝。W5-01 授权来源 Spike（阻断验证项）保持未解决；没有批准放宽门禁或实现可放行的宿主适配。
- **依赖停止条件：** 在项目所有者确认已验证的宿主集成来源，或另行审议并批准 BugMaster 自有签名服务设计前，暂停依赖 W5-01 授权来源的 W5-02 与 W6-01。来源、签名和审批生命周期设计都尚未获批。
- **真人审查边界：** 按 Q15（逐 PR 代码扫描及适用的安全扫描）先由 Codex 完成代码与安全审查，再由项目所有者确认并手动合并。若具体改动确实要求独立真人审查，先单列审查对象、依据和影响，与项目所有者讨论；Codex 审查不代替真人签署。Q16（正式发布双人授权）仍要求两名不同人员。

## 阻断 Spikes
BLK-01 独立安装；BLK-02 动作权限强制；BLK-03 Crash Consistency；BLK-04 证据真伪；BLK-05 Ground Truth 隔离；BLK-06 双宿主 Browser scope；BLK-07 全链路。每个 Spike 的 Red/GREEN/反例/环境证据需纳入 `docs/development/` 中文记录。

## 首个完整纵向路径（内部，不是缩小的 MVP）
本地订单系统：仅提供 URL/OpenAPI→发现订单端点→冻结允许范围→授权重复创建操作→有/无 Bug 对照→验证权威订单状态→生成 E3 Finding→输出 Session Report/单项报告；遇到未知写入结果必须停止重放。完成后同样标准扩展全部冻结范围。

## 发布 Go/No-Go
覆盖率和所有核心三类用例只是必要条件，仍需完整 11/16/50/2 hosts、真实执行、Q15 扫描记录和 Q16 发布授权。Q15 不要求独立真人 PR 签署。公开发布当前 No-Go。
