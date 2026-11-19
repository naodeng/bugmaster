# BugMaster 工程状态（2026-11-19）

当前事实优先于旧 Q17 基线快照；详细过程见 [实施进度矩阵](IMPLEMENTATION_PROGRESS_ZH.md) 与各轮 TDD 记录。

| 项目 | 状态 | 证据说明 |
|---|---|---|
| 全量品牌迁移 | 已应用于本交付包 | `scripts/check_branding.py` 本地通过 |
| Q1–Q17 | 已冻结 | `docs/en/01-decisions.md` / 中文版 |
| 11 Skills | 候选骨架 | 不代表真实独立执行成功 |
| 16 Patterns | 候选规则数据 | 未达到 Verified |
| 50 Benchmark | Planned 列表 | 未执行，缺独立 Ground Truth 运行证据 |
| 单元测试 | 164/164 通过 | Python 3.12；`bugmaster_core` 为 1063/1063 语句与 428/428 分支覆盖 |
| 契约测试 | 78/78 通过 | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；含 SessionStore、CheckpointStore Schema 集成测试和 replay gate 负例 |
| Session 契约与持久化 | 部分实现 | Schema 提交 `aaa5564`、11 项契约测试；`SessionStore` 最终提交 `7d2e195`、36 项定向单测，320/320 行与 130/130 分支覆盖。PR #3 Actions Run `44443870587` 通过；预算/Journal 对账、审批真实性与恢复授权仍未实现。属于 R2，独立质量审查前不合并 |
| Checkpoint 持久化 | 部分实现 | `CheckpointStore` 提交 `ba8bc6a`，19 项定向单测，187/187 行、60/60 分支覆盖；PR #4 Actions Run `44446002412` 通过。只持久化结构记录，不验证外部引用或授权恢复；R3 变更须独立 Security Reviewer，详见 [Checkpoint TDD 记录](2026-11-19_CHECKPOINT_STORE_TDD_ZH.md) |
| Journal / Safe Resume | 部分实现 | Journal 有 append/fsync、状态校验、哈希链、未决 Action 阻断和 Checkpoint 前缀核验（PR #5）；PR #6/#7 校验跨存储引用和 Session/Journal ID；PR #8 的 `ActionJournalStore` 按 Session/Journal ID 确定性解析路径并拒绝软链接/非普通文件；PR #9 将 `can_replay()` 改为在可信 verifier 接入前恒拒绝；PR #10 增加本地待对账 Action ID 枚举和 Journal/SessionStore/CheckpointStore 共 17 个进程崩溃注入场景。Event v1.0 日志 fail-closed 且不改写，无迁移器。可信恢复验证器、预算对账、HTTP/Browser 网关及审批真实性认证仍未实现。PR #5–#10 均为 R3，独立安全审查前不合并 |
| 业务功能覆盖 >60% | **未达成** | 缺真实业务执行证据 |
| 核心 Happy/Negative/Edge | **未达成** | 核心功能矩阵只有待执行位置 |
| API/Browser 自主探索 | **未完成** | 未建立真实执行闭环 |
| Codex/Claude 双宿主 | **未验证** | 未提供可复查运行 ID |
| GitHub 项目信息 | 已更新 | 上游 `AI-Native-QA-Lab/bugmaster` 与 fork `naodeng/bugmaster` 描述及 13 个 topics 已同步 |
| GitHub 代码 | W6 PR #3–#10 已推送 | SessionStore PR #3、CheckpointStore PR #4、Journal 前缀 PR #5、跨存储引用校验 PR #6、Journal ID 绑定 PR #7、路径解析 PR #8、fail-closed replay gate PR #9 和 Action 对账枚举/崩溃注入草稿 [#10](https://github.com/naodeng/bugmaster/pull/10) 均未合并；PR 逐层叠加 |
| GitHub Issues / CI | PR #1–#10 实现检查通过（均为草稿） | PR #1/#2/#3/#4/#5/#6/#7/#8/#9/#10 最终代码 Run `44304702509` / `44438620887` / `44443870587` / `44446002412` / `44448388986` / `44450205158` / `44452742738` / `44455794738` / `44457678961` / `44472202033` 均成功。PR #3 为 R2，PR #4–#10 为 R3，需独立质量/安全审查；Issues 尚未导入 |
| Release | **No-Go** | Q15/Q16 独立人工审批证据不存在 |

最近一次本地质量门禁仍为 **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失。`bugmaster_core` 单元覆盖率不等于业务功能覆盖率。本文不把本地 Checkpoint 引用校验表述成完整产品或 BLK-03 通过证明。
