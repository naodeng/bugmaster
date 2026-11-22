# BugMaster 工程状态（2026-11-22）

当前事实优先于旧 Q17 基线快照；详细过程见 [实施进度矩阵](IMPLEMENTATION_PROGRESS_ZH.md) 与各轮 TDD 记录。

| 项目 | 状态 | 证据说明 |
|---|---|---|
| 全量品牌迁移 | 已应用于本交付包 | `scripts/check_branding.py` 本地通过 |
| Q1–Q17 | 已冻结 | `docs/en/01-decisions.md` / 中文版 |
| 11 Skills | 候选骨架 | 不代表真实独立执行成功 |
| 16 Patterns | 候选规则数据 | 未达到 Verified |
| 50 Benchmark | Planned 列表 | 未执行，缺独立 Ground Truth 运行证据 |
| 单元测试 | PR #10 最新 PR #9 基线本地 428/428 通过；新 head Actions 待验证 | Python 3.12.16；PR #8/#9 Ubuntu Actions 的 4 项跳过仅支持 macOS ACL enforcement。完整命令与输出见 [Action 待对账枚举 TDD 记录](2026-11-19_ACTION_RECONCILIATION_ENUMERATION_TDD_ZH.md) |
| R3 安全测试 | PR #10 最新基线本地 1/1 通过；新 head Actions 待验证 | `tests/security` 独立运行；Q15 独立人工 Security Reviewer 尚未签署；模型审查不等同人工签署 |
| 契约测试 | PR #10 最新基线本地 80/80 通过；新 head Actions 待验证 | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；覆盖 Event v1.1、Checkpoint/Session 跨存储快照、确定性 Journal 路径、replay gate 和待对账枚举 |
| 生产代码行 / 分支覆盖率 | PR #10 最新基线本地 100% / 100%；新 head Actions 待验证 | `bugmaster_core/` + `scripts/`：2146/2146 语句、772/772 分支，无排除项；JSON：`/private/tmp/bugmaster-pr10-integrated.json`。行/分支覆盖不等于业务功能覆盖 |
| Session 契约与持久化 | 部分实现，PR #3 已合入（Q15 分类 R3） | Schema PR #2 已合并；`SessionStore` PR #3 保存不可变 revision 并校验历史转换，merge commit `1368b1a`，Actions Run `44537417048` 通过。预算/Journal 对账、审批真实性与恢复授权仍未实现；详见 [Session Revision TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md) |
| Journal / Safe Resume | 部分实现，PR #4–#7 已合入；PR #8–#10 开放 | PR #7 merge commit `c7fcfca`。PR #8 head `58a601a` 将 Session/Journal ID 映射为规范路径并验证可信祖先、目录描述符和 ACL。PR #9 当前 head `c8f0f6e` 的 `can_replay()` 在可信只读 verifier 和当前授权门禁接入前恒返回 False。PR #10 增加有序待对账 Action 枚举；缺失 Journal 现在抛出 `JournalCorruptionError`。最新 PR #9 基线整合树本地 428/428 单元、80/80 契约、1/1 安全；生产行/分支 2146/2146、772/772（100%）。新 head Actions 待推送后验证。PR #8–#10 属 R3，Q15 独立人工安全审查仍未完成。事件真实性、可信恢复、预算对账和当前授权复核仍未实现 |
| 业务功能覆盖 >60% | **未达成** | 缺真实业务执行证据 |
| 核心 Happy/Negative/Edge | **未达成** | 核心功能矩阵只有待执行位置 |
| API/Browser 自主探索 | **未完成** | 未建立真实执行闭环 |
| Codex/Claude 双宿主 | **未验证** | 未提供可复查运行 ID |
| GitHub 项目信息 | 已更新 | 上游 `AI-Native-QA-Lab/bugmaster` 与 fork `naodeng/bugmaster` 描述及 13 个 topics 已同步 |
| GitHub 代码 | PR #1–#7 已合并；PR #8/#9 开放；PR #10 正在更新基线 | PR #10 原 head `ffe52dc6` 基于过期 PR #9 SHA `f69c61b8`，GitHub 标记 dirty。已在 PR #9 当前 head `c8f0f6e` 完成本地整合和复验，更新后的远端提交待推送 |
| GitHub Issues / CI | PR #8 Run `44904668163`、PR #9 latest docs Run `44908476017` 成功；PR #10 新整合 head Actions pending | PR #4 Run `44662457674`、PR #5 Run `44690535886`、PR #6 Run `44697609761`、PR #7 Run `44748455778`、PR #8 Run `44904668163`、PR #9 docs head Run `44908476017` 成功。PR #10 旧 Run `44488992365` 不覆盖当前 PR #9 基线。Issues 尚未导入 |
| Release | **No-Go** | 业务与 Benchmark 验收证据未完成；Q15 独立人工安全审查和 Q16 双人批准证据缺失 |

最近一次本地质量门禁仍为 **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失。生产代码单元覆盖率不等于业务功能覆盖率。本文不把本地 Journal 切片表述成完整产品或 BLK-03 通过证明。

