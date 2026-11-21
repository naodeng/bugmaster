# BugMaster 工程状态（2026-11-21）

当前事实优先于旧 Q17 基线快照；详细过程见 [实施进度矩阵](IMPLEMENTATION_PROGRESS_ZH.md) 与各轮 TDD 记录。

| 项目 | 状态 | 证据说明 |
|---|---|---|
| 全量品牌迁移 | 已应用于本交付包 | `scripts/check_branding.py` 本地通过 |
| Q1–Q17 | 已冻结 | `docs/en/01-decisions.md` / 中文版 |
| 11 Skills | 候选骨架 | 不代表真实独立执行成功 |
| 16 Patterns | 候选规则数据 | 未达到 Verified |
| 50 Benchmark | Planned 列表 | 未执行，缺独立 Ground Truth 运行证据 |
| 单元测试 | PR #8 本地集成候选 399/399 通过 | Python 3.12；当前全部生产 Python 范围 `bugmaster_core/` + `scripts/` 覆盖率 2,141/2,141 行、770/770 分支，均为 100%；JSON：`/private/tmp/bugmaster-pr8-review-final.json` |
| R3 安全测试 | PR #8 本地集成候选 1/1 通过；远端 CI 待推送 | `tests/security` 独立运行；最终 head 的 GitHub Security Review 未运行。模型审查不等同人工签署 |
| 契约测试 | PR #8 本地集成候选 79/79 通过 | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；覆盖 Event v1.1、Checkpoint/Session 跨存储快照与确定性 Journal 路径 |
| Session 契约与持久化 | 部分实现，PR #3 已合入 | Schema PR #2 已合并；`SessionStore` PR #3 保存不可变 revision 并校验历史转换，merge commit `1368b1a`，Actions Run `44537417048` 通过。预算/Journal 对账、审批真实性与恢复授权仍未实现；详见 [Session Revision TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md) |
| Journal / Safe Resume | 部分实现，PR #4–#7 已合入；PR #8 集成候选本地通过 | PR #7 merge commit `c7fcfca`。PR #8 候选提交 `abe4b8e` 将 Session/Journal ID 映射为规范路径，逐级 no-follow 打开可信祖先，并让 Checkpoint、Session 与 Journal 共用已验证的根目录描述符；Journal 初始化与 Session revision 发布共用单 Session 锁；每次 Journal 操作复查固定 Session 目录 ACL。Session 目录和既有锁在权限修复前校验所有者与 ACL，既有锁拒绝硬链接，只有新建锁才会修改权限。Session、Checkpoint 和无锁旧格式探测的只读目录均校验私有属性；Session head、revision、Checkpoint 文件均校验 owner、0600 模式、ACL 与可识别临时硬链接，不安全链接和检查错误 fail-closed。恢复清理只接受规范目标文件名及匹配 inode；首次目标目录同步失败后保留临时硬链接，后续 Session 写入先同步再清理。候选本地单元 399/399、契约 79/79、安全 1/1 通过，生产 Python 行覆盖 2,141/2,141、分支覆盖 770/770。远端 CI 与最终独立复审待推送。事件真实性、可信恢复、预算对账和当前授权复核仍未实现 |
| 业务功能覆盖 >60% | **未达成** | 缺真实业务执行证据 |
| 核心 Happy/Negative/Edge | **未达成** | 核心功能矩阵只有待执行位置 |
| API/Browser 自主探索 | **未完成** | 未建立真实执行闭环 |
| Codex/Claude 双宿主 | **未验证** | 未提供可复查运行 ID |
| GitHub 项目信息 | 已更新 | 上游 `AI-Native-QA-Lab/bugmaster` 与 fork `naodeng/bugmaster` 描述及 13 个 topics 已同步 |
| GitHub 代码 | PR #1–#7 已合并；PR #8 开放 | PR #7 merge commit `c7fcfca24856eeb981389785d09bb4b84ca4bce4`。PR #8 旧 head 基于旧提交；本地集成修复候选 `abe4b8e` 已验证，尚未推送 |
| GitHub Issues / CI | PR #4–#6 历史 head 检查通过；PR #7 代码 head 检查通过 | PR #4 Run `44662457674`、PR #5 Run `44690535886`、PR #6 Run `44697609761`、PR #7 代码 head Run `44748455778` 均成功。PR #7 首次组装 Run `44747906615` 因测试文件截断失败，后续修复提交已通过；Issues 尚未导入 |
| Release | **No-Go** | Q15/Q16 独立人工审批证据不存在 |

最近一次本地质量门禁仍为 **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失。生产代码单元覆盖率不等于业务功能覆盖率。本文不把本地 Journal 切片表述成完整产品或 BLK-03 通过证明。

