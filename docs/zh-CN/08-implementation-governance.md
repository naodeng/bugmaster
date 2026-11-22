[English](../en/08-implementation-governance.md)

# Q15 实施治理：风险分级双人 Review 与完整 MVP Go/No-Go

> ADR-015 · Q15=B · 2026-11-18 · 设计基线 / 未实施 · 来源：Q14 `04-implementation.md`、`BASELINE_REVIEW_ZH.md`、`03-contracts.md` 与 `07-release.md`。

## 0. 不可变范围

Q1–Q15 = **A,A,B,B,B,B,B,B,A,B,B,B,B,A,B**。Q14=A：**唯一完整 v0.1 MVP** 同时交付 11 Skills、16 Patterns、50 Eval 场景、API + Browser Basic、Codex + Claude Code 核心验证、Hybrid Discovery、Routing、审批、Oracle/Evidence/Finding、文件版本与 Safe Resume、Evidence Bundle、仅回归建议、CI/发布门禁。VS-01 是内部集成验证节点，不是公开减配版本。此文件定义计划，不代表通过验收。

## 1. 权限与责任模型（逻辑角色而非既有人员）

| 角色 | 缩写 | 职责 | 可兼任规则 |
|---|---|---|---|
| Integrating Maintainer | IM | 最终集成、依赖/工作流协调、RC 组织及 Go/No-Go 提案 | 可担任 W0–W11 Owner，不可自批 R3 |
| Domain / Quality Reviewer | QR | 业务 Oracle、测试义务、正反 Eval 与质量回归 | R2 必须与变更作者不同；无第二人则保持待审 |
| Independent Security Reviewer | SR | 授权强制、敏感数据、供应链、发布权限、恢复副作用 | R3 必须与作者不同，且有独立审查证据；无人可审则 No-Go |
| Evidence / Benchmark Custodian | EC | 私有 Ground Truth、数据集冻结、运行证据、评分一致性 | 应隔离 Agent 运行权限；可与 QR 兼任但不能泄漏答案 |
| Release Approver | RA | 最终核对发布清单并签署决策 | 默认 IM，但不得替代 R2/R3 的独立审查 |

R0/R1：IM 或授权维护者审核，任何安全敏感变更自动升级 R3；R2：作者之外 QR 审核，IM 合并；R3：SR 独立审核 + IM 集成，RA 根据全量证据决定发布。如果唯一维护者无法取得独立 R3 审核，则不得虚构审核记录；可以继续开发，但公开发布维持 No-Go。AI 只能提出意见，不能充当人工签名者。

## 2. W0–W11：Owner、依赖和 Definition of Done

| Workstream | Accountable | Required reviewer | 依赖 | 可交付工程任务 | DoD / Evidence |
|---|---|---|---|---|---|
| W0 架构收敛 | IM | QR；R3 内容另需 SR | 无 | ADR/ID/状态表/路径统一、风险登记、适用性矩阵 | 决策不冲突、冻结基线记录、BLK 跟踪表 |
| W1 契约 | IM | QR + SR（审批/权限相关） | W0 | 权威 Schema、状态机、跨文件引用、兼容性 | `TDD-CON-001..020` 正反测试、Schema 版本及跨引用证据 |
| W2 Skills | IM | QR | W1 | 11 `SKILL.md`、中英参考、构建依赖闭包 | `TDD-SKL-001..011`、单 Skill 安装、触发反例与降级 |
| W3 Patterns | IM | QR / EC | W1 | 16 Pattern、Taxonomy、来源、许可及测试 | `TDD-PAT-001..016`、正反例与 Pattern 状态合规 |
| W4 Routing | IM | QR | W1,W3 | 三值前提、Rule+Semantic、未知假设、预算 | Routing 合同与负例测试、固定决策轨迹 |
| W5 Tool/Permission | IM | SR（强制） | W1 | Scope、审批绑定、Action Gateway、API/Browser | `TDD-SEC-001..012`；越权动作 0；BLK-02/06 |
| W6 Session | IM | SR + QR | W1,W5 | Journal、版本 Pointer、Checkpoint、核对恢复 | `TDD-ACT-001..012`,`TDD-FS-001..008`；BLK-03 |
| W7 Evidence/Finding | IM | QR + SR（真实性与敏感数据） | W1,W6 | Oracle、E0–E4、报告、不可变修订、Bundle | `TDD-FND-001..012`；伪造证据拒绝；BLK-04 |
| W8 Regression | IM | QR | W7 | 仅建议的 Contract、模板、追踪、导出 | 不写测试代码；建议/已实施状态严格分离 |
| W9 Benchmark | EC | QR + SR（Ground Truth 隔离） | W1,W5 | 正确/缺陷订单 Fixture、50 cases、评分器、G0–G3 | `TDD-EVAL-001..050`、私有答案隔离；BLK-05 |
| W10 Hosts | IM | QR + SR（权限映射） | W2–W9 | Codex / Claude Code 安装、API/Browser/降级 | `TDD-HOST-001..030`、Run IDs；BLK-01/06 |
| W11 Release | RA | QR + SR（R3 项） | W1–W10 | CI、质量报告、资产摘要、版本/回滚演练 | 全量门禁、可审核 Go/No-Go；BLK-07 |

**串行 PR 说明：** 功能实施一次只处理一个 PR。当前 PR 完成开发、验证、Review、所需审批并合并后，才开始下一项功能；不得堆叠功能分支或并行开启实现 PR。工作流依赖仍决定顺序与验收条件，接口冻结不构成并行开发许可。VS-01 的内部验证和完整 MVP 门槛保持不变。

## 3. 七项阻断 Spike（继承 Q14 风险编号）

| Spike | 需要验证的最小实验 | 失败判断 | 退出证据 / 责任 |
|---|---|---|---|
| BLK-01 安装闭包 | 两宿主清洁环境安装独立 `discover-api-idempotency-defects`，离线解析 Pattern/Schema | 任一正式支持宿主引用断裂或版本无法锁定 | 安装日志、产物哈希、环境记录；IM+QR |
| BLK-02 安全执行 | 通过受控入口模拟 R2 未批准、参数审批后变化、工具路径绕过 | 存在未经授权真实副作用或无法强制阻断却声明已受控 | 隔离环境真实阻断日志、能力降级声明；SR |
| BLK-03 崩溃一致性 | 注入 8 个断点（Intent、Dispatch、Response、Artifact、Pointer 等），核对唯一当前版本 | 未知副作用被重放、提交 Pointer 不完整、预算被重置 | 故障注入 Run、Journal、恢复轨迹；IM+SR |
| BLK-04 证据真实性 | 伪造工具回执、替换 Artifact、伪造模型自述执行 | 任一伪造证据可进入 Confirmed | Evidence Gate 对抗案例、摘要及来源核验；QR+SR |
| BLK-05 答案隔离 | Agent 按最大允许文件/命令权限尝试读取私有 Ground Truth | Agent 能读取答案、评分输出暴露缺陷 ID | 容器/目录挂载与访问拒绝记录；EC+SR |
| BLK-06 Browser 跨宿主 | 真正执行 UI+API GP-06/07、重定向及跨域拒绝 | 无真实测试或越界访问未阻断而声称支持 | 两宿主分别提供实测或正式受限能力说明；IM+SR |
| BLK-07 全量集成 | VS-01 正误/超时场景、全量清单及 RC Dry Run | VS 无闭环、任一全量目标缺失 | 完整 RC 验收矩阵与决议；RA+QR |

**阻断语义：** BLK-01–07 对公开完整 v0.1 都是阻断项。某个宿主无法提供强制策略时，可以限定其 Guided 行为，但对 Q12 声称正式支持的目标仍须满足冻结的完整范围；否则必须显式提出变更决策，不能单方面缩水。

## 4. VS-01：内部最早端到端门禁

1. 验证固定的本地订单 API + 正确、缺陷、超时未知三个变体；EC 隔离答案。
2. 读取用户 Scope，登记 `BP-API-002` 与有效 Oracle；R2 动作由真实人工审批；在 Action Journal **持久化意图后**才派发。
3. 工具原始记录经来源核验保存 Evidence；Evidence E3 不自动授予 Confirmed，仍走 G1–G4 与所需 Review。
4. Finding 使用不可变 Revision + Current Pointer；报告/脱敏 Bundle 来源一致；仅生成 Regression Recommendation。
5. 中断后 Safe Resume 不重放未知动作，审批不自动复活；正确版本不误报，缺陷版本有真实发现。

VS-01 失败必须阻断后续全量集成验收，但可持续修复；VS-01 通过绝不等同于完整 MVP Go。

## 5. TDD / Eval 管理

固定编号沿用 Q14：`TDD-CON-001..020`、`TDD-PAT-001..016`、`TDD-SKL-001..011`、`TDD-SEC-001..012`、`TDD-ACT-001..012`、`TDD-FND-001..012`、`TDD-FS-001..008`、`TDD-HOST-001..030`、`TDD-EVAL-001..050`。**编号范围只是计划清单**，没有生成对应测试实现就不能计为通过。W4 和 W8 补充 `TDD-ROUTE-*` 与 `TDD-REG-*`，由 W0 确认不与已有用例重复。

- RED：测试明确失败的证据（对模型行为需多个可复核输入/输出，不只一次随机结果）。
- GREEN：版本、环境、测试记录和真实工具输出。
- REFACTOR：运行影响分析与受影响回归。
- 证据清单：`sourceCommit`, `artifactDigest`, `schemaVersion`, `datasetDigest`, `runId`, `host`, `toolCapabilities`, `reviewer`, `decision`, `knownFailures`。
- 质量测量：缺陷 Recall/Confirmed Precision、错误确认数、Oracle/Evidence 有效性、工具调用和成本；统计分母仅限适用样本，G0–G3 使用相同外部评分器。
- 50 Benchmark 场景沿用 Q10 分组：18 API/Business、12 Browser/UI-API、10 Safety/Approval、6 Fallback/Recovery、4 Oracle/Evidence；不是 50 个已知缺陷。

## 6. GitHub Issue / PR 实施协议

每个 Issue 包含：`Workstream`、`Risk`、`Owner Role`、`Reviewer Role`、`Dependencies`、`Red Test IDs`、`Acceptance Evidence`、`Security Impact`、`DoD`。建议标签 `workstream/W0..W11`、`risk/R0..R3`、`type/contract|skill|pattern|benchmark|adapter|security|release`、`status/blocked|ready|in-progress|review|verified`。

建议优先建立 12 个 Epic（对应 W0–W11），然后展开任务清单。对于 BLK-02、03、04、05、06 的风险控制项设独立 Issue，并以真实日志/Artifact 关闭，不允许仅以“代码已合并”关闭。所有 R2 PR 至少有非作者 QR，R3 PR 必须有独立 SR 审批；Fork PR 不持有密钥。

## 7. Release Go / No-Go 决策表

| Gate | Go 条件 | 当前状态 |
|---|---|---|
| Scope | 11 Skills/16 Patterns/50 cases/2 hosts/API+Browser 全部完成 | 未实现 |
| Contract | 全部阻断级静态、Schema、状态机与引用测试通过 | 未运行 |
| Security | 固定样本未经授权动作、未知副作用盲重放、审批复用 = 0 | 未运行 |
| Evidence | 伪造执行证据拒绝，E3 + 所有适用 Gate 满足方可 Confirmed | 未运行 |
| Eval | 正确/缺陷 Fixture、G0–G3、失败案例、指标分子分母与成本齐全 | 未运行 |
| Compatibility | Codex+Claude Code 的安装/执行声明有实际 Run ID | 未运行 |
| Recovery | 8 故障注入点、损坏文件与版本不兼容安全处理 | 未运行 |
| Release | 双语文档、许可证、可重现产物、回滚演练、Review 证据齐全 | 未完成 |

**决策权限：** IM 汇总 Release Candidate 证据，QR 独立复核领域与 Eval 结果，SR 对 R3 / 安全风险签署，RA 做最后 Go/No-Go。安全阻断未解除、任何要求的审查角色空缺、或关键结果无可验证记录时 **No-Go**；不允许“有条件公开发布”绕过关键门禁。当前为 **Conditional Go for implementation / No-Go for public release**。

## 8. 最小后续决策 Q16（建议）

**独立安全 Reviewer 资源不足时的规则是否允许例外？**
- A：关键变更仅用 AI Review 或同一作者自评（不推荐，与 Q15 双重审核冲突）。
- **B：不可豁免独立 R3 Review；缺少 Reviewer 则暂停公开发布，只继续可安全的研发与测试（推荐）**。
- C：委托外部 Reviewer，依然要求独立证据与明确身份；公开发布在审查完成前阻断。

建议将 Q16 更聚焦于 **Release Execution Authorization（授权维护者实际执行发布操作的职责与签署策略）**，因为 Q15 已要求 R3 独立审核，不应通过下一轮重新开放已确认的安全底线。
