# BugMaster 工程状态（2026-11-21）

当前事实优先于旧 Q17 基线快照；详细过程见 [实施进度矩阵](IMPLEMENTATION_PROGRESS_ZH.md) 与各轮 TDD 记录。

| 项目 | 状态 | 证据说明 |
|---|---|---|
| 全量品牌迁移 | 已应用于本交付包 | `scripts/check_branding.py` 本地通过 |
| Q1–Q17 | 已冻结 | `docs/en/01-decisions.md` / 中文版 |
| 11 Skills | 候选骨架 | 不代表真实独立执行成功 |
| 16 Patterns | 候选规则数据 | 未达到 Verified |
| 50 Benchmark | Planned 列表 | 未执行，缺独立 Ground Truth 运行证据 |
| 单元测试 | PR #8/#9 Actions 各 406 项中 402 通过、4 跳过；PR #9 整合树本地 406/406 通过 | Python 3.12；两次 Ubuntu run 的 4 项跳过测试仅支持 macOS ACL enforcement。PR #9 测试树 SHA `42850bb49401a4090e0c8dc21ad2cdd4e0306bca`；命令、环境和完整结果见 [回放门禁 TDD 记录](2026-11-19_REPLAY_GATE_FAIL_CLOSED_TDD_ZH.md)。生产范围 `bugmaster_core/` + `scripts/` 覆盖率 2,141/2,141 行、770/770 分支，均为 100%；JSON：`/private/tmp/bugmaster-pr9-integrated.json` |
| R3 安全测试 | PR #8/#9 Actions 与 PR #9 整合树本地均 1/1 通过 | `tests/security` 独立运行；Q15 独立人工 Security Reviewer 尚未签署；模型审查不等同人工签署 |
| 契约测试 | PR #8 Actions 79/79 通过；PR #9 整合树本地与 Actions 80/80 通过 | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；覆盖 Event v1.1、Checkpoint/Session 跨存储快照、确定性 Journal 路径和 replay gate 负例 |
| Session 契约与持久化 | 部分实现，PR #3 已合入（Q15 分类 R3） | Schema PR #2 已合并；`SessionStore` PR #3 保存不可变 revision 并校验历史转换，merge commit `1368b1a`，Actions Run `44537417048` 通过。预算/Journal 对账、审批真实性与恢复授权仍未实现；详见 [Session Revision TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md) |
| Journal / Safe Resume | 部分实现，PR #4–#7 已合入；PR #8/#9 开放 | PR #7 merge commit `c7fcfca`。PR #8 当前 head `58a601a` 将 Session/Journal ID 映射为规范路径，逐级 no-follow 打开可信祖先，并让 Checkpoint、Session 与 Journal 共用已验证的根目录描述符；恢复清理只接受规范目标文件名及匹配 inode，首次目标目录同步失败后保留临时硬链接。PR #8 Actions 单元 402 通过、4 项 macOS ACL 测试跳过，契约 79/79、安全 1/1。PR #9 测试树提交 `42850bb49401a4090e0c8dc21ad2cdd4e0306bca` 已接入 PR #8 head `58a601a`，Actions Run `44907692817` 通过：单元 402 通过、4 项平台专用跳过，契约 80/80、安全 1/1；本地 406/406 单元、80/80 契约和 1/1 安全测试通过。PR #9 `can_replay()` 在可信只读 verifier 和当前授权门禁接入前恒返回 False。PR #8/#9 属 R3，Q15 独立人工安全审查仍未完成。事件真实性、可信恢复、预算对账和当前授权复核仍未实现 |
| 业务功能覆盖 >60% | **未达成** | 缺真实业务执行证据 |
| 核心 Happy/Negative/Edge | **未达成** | 核心功能矩阵只有待执行位置 |
| API/Browser 自主探索 | **未完成** | 未建立真实执行闭环 |
| Codex/Claude 双宿主 | **未验证** | 未提供可复查运行 ID |
| GitHub 项目信息 | 已更新 | 上游 `AI-Native-QA-Lab/bugmaster` 与 fork `naodeng/bugmaster` 描述及 13 个 topics 已同步 |
| GitHub 代码 | PR #1–#7 已合并；PR #8/#9 开放 | PR #8 head `58a601aa1dfa9639b38d9f9c6b0a62d9dbee2a4d`；PR #9 测试树提交 `42850bb49401a4090e0c8dc21ad2cdd4e0306bca` 将 PR #8 最新 head 作为第二父提交，GitHub 显示 mergeable |
| GitHub Issues / CI | PR #4–#9 最新检查通过 | PR #4 Run `44662457674`、PR #5 Run `44690535886`、PR #6 Run `44697609761`、PR #7 代码 head Run `44748455778`、PR #8 Run `44904668163`、PR #9 Run `44907692817` 成功；PR #8/#9 单测各 406 项中 402 通过、4 项 macOS ACL 测试跳过；PR #9 契约 80/80、安全 1/1。Issues 尚未导入 |
| Release | **No-Go** | 业务与 Benchmark 验收证据未完成；Q15 独立人工安全审查和 Q16 双人批准证据缺失 |

最近一次本地质量门禁仍为 **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失。生产代码单元覆盖率不等于业务功能覆盖率。本文不把本地 Journal 切片表述成完整产品或 BLK-03 通过证明。

