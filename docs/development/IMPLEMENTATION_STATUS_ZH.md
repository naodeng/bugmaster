# BugMaster 工程状态（2026-11-19）

当前事实优先于旧 Q17 基线快照；详细过程见 [实施进度矩阵](IMPLEMENTATION_PROGRESS_ZH.md) 与各轮 TDD 记录。

| 项目 | 状态 | 证据说明 |
|---|---|---|
| 全量品牌迁移 | 已应用于本交付包 | `scripts/check_branding.py` 本地通过 |
| Q1–Q17 | 已冻结 | `docs/en/01-decisions.md` / 中文版 |
| 11 Skills | 候选骨架 | 不代表真实独立执行成功 |
| 16 Patterns | 候选规则数据 | 未达到 Verified |
| 50 Benchmark | Planned 列表 | 未执行，缺独立 Ground Truth 运行证据 |
| 单元测试 | 198/198 通过 | Python 3.12；`bugmaster_core` 为 1196/1196 语句与 474/474 分支覆盖 |
| 契约测试 | 78/78 通过 | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；含 SessionStore、CheckpointStore Schema 集成测试和 replay gate 负例 |
| Session 契约与持久化 | 部分实现 | Schema 提交 `aaa5564`；`SessionStore` 审查修复后 400/400 语句与 160/160 分支覆盖。PR #3 P1 已修复：缺少 `session.head` 或修订历史会失败关闭，不能以同一 Session ID 重置预算。预算/Journal 对账、审批真实性与恢复授权仍未实现。按 Q15 W6-01 归为 R3，独立安全审查前不合并 |
| Checkpoint 持久化 | 部分实现 | `CheckpointStore` 审查修复后 185/185 语句、60/60 分支覆盖。PR #4 P2 已修复：只读读取逐层拒绝软链接并使用无目录修改的共享锁。只持久化结构记录，不验证外部引用或授权恢复；R3 变更须独立 Security Reviewer，详见 [Checkpoint TDD 记录](2026-11-19_CHECKPOINT_STORE_TDD_ZH.md) |
| Journal / Safe Resume | 部分实现 | Journal 有 append/fsync、状态校验、哈希链、未决 Action 阻断和 Checkpoint 前缀核验（PR #5）；PR #6/#7 校验跨存储引用和 Session/Journal ID；PR #7 修正 LF-only JSONL 分隔，保留合法 Unicode 行分隔字符；PR #8 的 `ActionJournalStore` 固定绝对根路径，显式 `initialize()` 新日志，只读 `open()` 读取规范日志并在缺失时失败关闭，也拒绝软链接/FIFO；PR #9 将 `can_replay()` 改为在可信 verifier 接入前恒拒绝；PR #10 增加完整有序的待对账 Action ID 枚举和 19 个 Journal/SessionStore/CheckpointStore 进程退出检查。Event v1.0 和此前调用方自选路径日志均不会被隐式迁移。可信恢复验证器、预算对账、HTTP/Browser 网关及审批真实性认证仍未实现。PR #5–#10 均为 R3，独立安全审查前不合并 |
| 业务功能覆盖 >60% | **未达成** | 缺真实业务执行证据 |
| 核心 Happy/Negative/Edge | **未达成** | 核心功能矩阵只有待执行位置 |
| API/Browser 自主探索 | **未完成** | 未建立真实执行闭环 |
| Codex/Claude 双宿主 | **未验证** | 未提供可复查运行 ID |
| GitHub 项目信息 | 已更新 | 上游 `AI-Native-QA-Lab/bugmaster` 与 fork `naodeng/bugmaster` 描述及 13 个 topics 已同步 |
| GitHub 代码 | 本轮修复已推送；PR #1–#10 open/ready | PR #1–#10 均未合并且逐层叠加；没有已废弃或重复 PR 可安全关闭。PR #3 P1、PR #4 P2 inline threads 已回复并解决；其余交叉审核发现已补充测试或修复 |
| GitHub Issues / CI | 当前代码/测试 head Actions 全部 PASS | Runs [44486194925](https://github.com/naodeng/bugmaster/actions/runs/44486194925), [44486207106](https://github.com/naodeng/bugmaster/actions/runs/44486207106), [44486210063](https://github.com/naodeng/bugmaster/actions/runs/44486210063), [44486216357](https://github.com/naodeng/bugmaster/actions/runs/44486216357), [44486219511](https://github.com/naodeng/bugmaster/actions/runs/44486219511), [44486223458](https://github.com/naodeng/bugmaster/actions/runs/44486223458), [44486229369](https://github.com/naodeng/bugmaster/actions/runs/44486229369), [44487177211](https://github.com/naodeng/bugmaster/actions/runs/44487177211), [44487182796](https://github.com/naodeng/bugmaster/actions/runs/44487182796), [44487187776](https://github.com/naodeng/bugmaster/actions/runs/44487187776) 均成功。PR #1–#2 为 R2，需要独立 Quality Reviewer；PR #3–#10 为 R3，需要独立 Security Reviewer。当前没有独立人工 Approve；Issues 尚未导入 |
| Release | **No-Go** | Q15/Q16 独立人工审批证据不存在 |

最近一次本地质量门禁仍为 **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失。`bugmaster_core` 单元覆盖率不等于业务功能覆盖率。本文不把本地 Checkpoint 引用校验表述成完整产品或 BLK-03 通过证明。
