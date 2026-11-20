# BugMaster 工程状态（2026-11-20）

当前事实优先于旧 Q17 基线快照；详细过程见 [实施进度矩阵](IMPLEMENTATION_PROGRESS_ZH.md) 与各轮 TDD 记录。

| 项目 | 状态 | 证据说明 |
|---|---|---|
| 全量品牌迁移 | 已应用于本交付包 | `scripts/check_branding.py` 本地通过 |
| Q1–Q17 | 已冻结 | `docs/en/01-decisions.md` / 中文版 |
| 11 Skills | 候选骨架 | 不代表真实独立执行成功 |
| 16 Patterns | 候选规则数据 | 未达到 Verified |
| 50 Benchmark | Planned 列表 | 未执行，缺独立 Ground Truth 运行证据 |
| 单元测试 | PR #7 隔离集成候选 268/268 通过 | Python 3.12；`bugmaster_core/` 覆盖率 1,457/1,457 行、540/540 分支，仍只是 GATE-U100 初始样例范围，不代表全项目生产模块 |
| R3 安全测试 | PR #7 隔离集成候选 1/1 通过；远端独立复审待重跑 | `tests/security/` 专项套件已加入 CI 单独执行；PR #7 原 head 的旧安全复审/自动审查不覆盖当前集成候选 |
| 契约测试 | PR #7 隔离集成候选 79/79 通过 | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；覆盖 Event v1.1 和 Checkpoint/Session 跨存储身份检查 |
| Session 契约与持久化 | 部分实现，PR #3 已合入 | Schema PR #2 已合并；`SessionStore` PR #3 保存不可变 revision 并校验历史转换，merge commit `1368b1a`，Actions Run `44537417048` 通过。预算/Journal 对账、审批真实性与恢复授权仍未实现；详见 [Session Revision TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md) |
| Journal / Safe Resume | 部分实现，PR #4–#6 已合入；PR #7 集成中 | PR #6 merge commit `c67af41`。PR #7 旧 head `8114413` 的 Actions 虽通过，但仍基于旧 PR #6 源码；修正版继承 PR #6 安全与快照修复，并增加 Event v1.1 `journalId` 和同快照 ID 比较。最终验证、CodeX 交叉复审和新 Actions 尚待完成。Journal ID 到文件路径的可信绑定、可信恢复、预算对账和当前授权复核仍未实现 |
| 业务功能覆盖 >60% | **未达成** | 缺真实业务执行证据 |
| 核心 Happy/Negative/Edge | **未达成** | 核心功能矩阵只有待执行位置 |
| API/Browser 自主探索 | **未完成** | 未建立真实执行闭环 |
| Codex/Claude 双宿主 | **未验证** | 未提供可复查运行 ID |
| GitHub 项目信息 | 已更新 | 上游 `AI-Native-QA-Lab/bugmaster` 与 fork `naodeng/bugmaster` 描述及 13 个 topics 已同步 |
| GitHub 代码 | PR #1–#6 已合并；PR #7 开放 | PR #6 merge commit `c67af41`。PR #7 仍需从旧 base 集成到最新 `main`，当前候选未推送 |
| GitHub Issues / CI | PR #4–#6 历史 head 检查通过；PR #7 新 head 检查待运行 | PR #4 Run `44662457674`、PR #5 Run `44690535886`、PR #6 Run `44697609761` 均成功。PR #7 旧 head Run `44486229369` 不代表集成修复版已通过；Issues 尚未导入 |
| Release | **No-Go** | Q15/Q16 独立人工审批证据不存在 |

最近一次本地质量门禁仍为 **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失。`bugmaster_core` 单元覆盖率不等于业务功能覆盖率。本文不把本地 Journal 切片表述成完整产品或 BLK-03 通过证明。

