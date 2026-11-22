# BugMaster 工程状态（2026-11-22）

当前事实优先于旧 Q17 基线快照；详细过程见 [实施进度矩阵](IMPLEMENTATION_PROGRESS_ZH.md) 与各轮 TDD 记录。

| 项目 | 状态 | 证据说明 |
|---|---|---|
| 全量品牌迁移 | 已应用于本交付包 | `scripts/check_branding.py` 本地通过 |
| Q1–Q17 | 已冻结 | `docs/en/01-decisions.md` / 中文版 |
| 11 Skills | 候选骨架 | 不代表真实独立执行成功 |
| 16 Patterns | 候选规则数据 | 未达到 Verified |
| 50 Benchmark | Planned 列表 | 未执行，缺独立 Ground Truth 运行证据 |
| 单元测试 | PR #8/#9/#10 当前整合树本地 PASS | PR #8 408/408；PR #9 408/408；PR #10 最新整合树 430/430，崩溃恢复定向 22/22。Python 3.12；PR #10 code/evidence head `8bbc2c3` Actions Run `44986603312` 成功 |
| R3 安全测试 | PR #8/#9 Actions 与 PR #10 本地及 Actions 均 1/1 PASS | `tests/security` 独立运行；PR #10 Run `44986603312` 成功。CI 结果不代表 Q15 扫描结论；现行流程按准确 PR head 记录 Codex 代码/适用的安全扫描，由项目所有者查看后手动合并 |
| 契约测试 | PR #8 79/79；PR #9/#10 本地 82/82 | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；PR #9 Run `44986287358`、PR #10 Run `44986603312` 成功 |
| Session 契约与持久化 | 部分实现，PR #3 已合入（Q15 分类 R3） | Schema PR #2 已合并；`SessionStore` PR #3 保存不可变 revision 并校验历史转换，merge commit `1368b1a`，Actions Run `44537417048` 通过。预算/Journal 对账、审批真实性与恢复授权仍未实现；详见 [Session Revision TDD 记录](2026-11-19_SESSION_REVISION_STORE_TDD_ZH.md) |
| Journal / Safe Resume | 部分实现；W6-05 PR #11 已合入 `main` | `main` 合并提交 `f97ca8f` 包含待对账 Action 枚举与进程崩溃验证。V-2 至 V-6 仍是待验证证据/威胁模型事项；可信授权、事件来源真实性、预算对账与安全恢复授权仍未实现 |
| 业务功能覆盖 >60% | **未达成** | 缺真实业务执行证据 |
| 核心 Happy/Negative/Edge | **未达成** | 核心功能矩阵只有待执行位置 |
| API/Browser 自主探索 | **未完成** | 未建立真实执行闭环 |
| Codex/Claude 双宿主 | **未验证** | 未提供可复查运行 ID |
| GitHub 项目信息 | 已更新 | 上游 `AI-Native-QA-Lab/bugmaster` 与 fork `naodeng/bugmaster` 描述及 13 个 topics 已同步 |
| GitHub 代码 | PR #1–#9、#11 已合并到 `main`；PR #10 只合入过中间功能分支 | 最新 `main` 为 `f97ca8fb002f17e51986b91269a3df0556cd63a6`；PR #10 的 merge commit `1f974bc` 不在 `main` 历史中，但其 W6 代码不在当前 Candidate Assessment 差异范围内。Candidate Assessment 与 Q15 文档改动从最新 `main` 重建，待本轮扫描和合并。Q15 由 CodeX 做代码扫描，R2/R3 加做安全扫描，项目所有者查看后手动合并，不要求独立真人 PR 签署 |
| GitHub Issues / CI | PR #8/#9/#10 当前验证 head 检查成功 | PR #8 Runs `44983187716` / `44983456594`、PR #9 Run `44986287358`、PR #10 Run `44986603312` 成功。Issues 尚未导入 |
| Release | **No-Go** | 业务与 Benchmark 验收证据未完成；Q16 双人发布授权与供应链证据尚未完成。Q15 真人 PR 签署不是发布阻断项 |

最近一次本地质量门禁仍为 **No-Go**：功能义务清单未冻结、真实业务覆盖未超过 60%，核心功能 Happy/Negative/Edge 执行证据缺失。生产代码单元覆盖率不等于业务功能覆盖率。本文不把本地 Journal 切片表述成完整产品或 BLK-03 通过证明。

