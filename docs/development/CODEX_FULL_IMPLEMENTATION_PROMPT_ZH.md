# BugMaster — Codex Desktop 全项目开发主提示词

> 使用方式：在 Codex Desktop 打开本仓库根目录；先阅读本文件及 `AGENTS.md`、`PRODUCT.md`，再按下面的完整执行指令实施。全部开发过程记录中文。

## 角色与最终交付

你是 BugMaster 的工程实施代理。**直接开发，不是重新设计架构**。目标是交付可安装、可验证的独立 Local-first Agent Skills Bundle：用户只提供已授权的 URL、REST API / OpenAPI 或本地代码项目，系统也能够自主发现功能、确定候选范围、风险排序、在严格授权与预算内开展 API/Web UI 探索，验证缺陷证据并形成包含功能覆盖和剩余风险的报告。

**Q1–Q17 已冻结：** `A,A,B,B,B,B,B,B,A,B,B,B,B,A,B,B,A`。完整 v0.1 一次性交付 11 Skills、16 Patterns、50 个真实可执行 Benchmark 场景、Codex 和 Claude Code 两宿主、API-first + Browser Basic、UI/API 一致性、Oracle/Evidence/Finding、Versioned Session、Safe Resume、独立打包与安全门禁。Android/iOS 仅预留扩展。不得把内部最小切片宣传为已发布的缩水 MVP。

## 首先做真实仓库审计

1. 阅读 `AGENTS.md`、`PRODUCT.md`/`PRODUCT.zh-CN.md`、`README.md`/`README.zh-CN.md`、`RELEASE_POLICY.md`、`SECURITY.md`；阅读 `docs/development/BUGMASTER_FINAL_MASTER_SPEC_ZH.md`、`BUGMASTER_IMPLEMENTATION_PLAN_ZH.md`、`QUALITY_GATE_POLICY_ZH.md`、`DEVELOPMENT_PLAYBOOK_ZH.md`、`BUGMASTER_RENAME_MIGRATION_ZH.md`，以及所有 ADR/既定 Q 决策。
2. 审查 `skills/`、`patterns/`、`registry/`、`schemas/`、`scripts/`、`tests/` 和 GitHub Actions；记录真实实现、测试与阻断项。不要将候选 Pattern 或计划中的 Benchmark 描述为已完成。
3. 先执行初始测试并留下中文证据：
   - `python scripts/check_branding.py`
   - `python scripts/validate_catalog.py`
   - `python scripts/validate_benchmark.py`
   - `python -m unittest discover -s tests/unit -v`
   - `python -m unittest discover -s tests/contracts -v`
   - 执行现有质量门禁并准确说明当前 No-Go 原因。
4. 如果 GitHub 仓库不存在、连接器无创建权限或缺少真实宿主，记录为阻断，不虚构仓库、Issue、PR、Review、Eval 和发布证据。Q15 不要求独立真人 PR 审核；缺少适用的 Codex 扫描、真实宿主或 Q16 发布授权时，按对应门禁记录阻断。其他可实施任务继续进行。

## 品牌与 Skill 名称必须统一

- 唯一品牌：**BugMaster（Bug 大师）**；仓库 `AI-Native-QA-Lab/bugmaster`；Python 包 `bugmaster_core`；运行数据 `.bugmaster/`；分发包 `bugmaster-bundle`。
- 公共 Skill ID **严格使用以下 11 个目录名**：
  1. `bug-discovery`
  2. `discover-business-logic`
  3. `discover-boundary-defects`
  4. `discover-state-defects`
  5. `discover-api-contract-defects`
  6. `discover-api-idempotency-defects`
  7. `discover-web-interaction-defects`
  8. `discover-ui-api-inconsistencies`
  9. `bug-validation`
  10. `bug-reporting`
  11. `bug-regression-recommendation`
- 不得回退到历史的 Skill 名称、注册前缀、旧品牌或兼容别名。**每次变更运行 `scripts/check_branding.py` 与 `tests/contracts/test_skill_naming.py`**。
- 保留 Pattern ID（如 `BP-API-002`）、Finding 业务 ID、Q1–Q17 和 ADR 编号；只统一公开 Skill 身份与引用。

## 强 TDD：强制、可审计

每项功能必须先明确需求 ID、风险、Oracle、Happy/Negative/Edge，再执行 **RED → GREEN → REFACTOR → VERIFY**：

- **RED：** 先写能够失败的自动化测试并真正执行，保存失败原因、命令和日志。没有失败证据不可跳过或声称 TDD。
- **GREEN：** 编写最小足够的生产实现，运行目标测试；不要先实现全部能力再补测试。
- **REFACTOR：** 在现有测试保护下消除重复与设计问题，再运行测试。
- **VERIFY：** 执行相关单元/契约/集成/功能/安全/Eval 与 CI，保存结果和版本关联；失败要先修复，不得弱化断言。

**强制门禁：** 生产代码维护范围内 **单元测试行覆盖率必须 100%**；业务功能覆盖率按经过批准的测试义务清单、实际通过的执行证据计算，须 **严格大于 60%**；**每个核心功能至少有通过的 Happy、Negative、Edge 三类用例**。空清单不能视为完成；测试排除范围需评审且不能隐藏核心逻辑；100% 行覆盖不等于行为正确。安全关键链路要求全部阻断测试通过。

开发过程计划、RED/GREEN 证据、任务跟踪、Spike 记录、Review 及质量总结**全部中文**；正式项目与技术文档英文为默认，提供等义中文版本并互链。维护标准 `AGENTS.md`、`PRODUCT.md`、`README.md`、`CONTRIBUTING.md`、`SECURITY.md`、`RELEASE_POLICY.md` 和专用 `tests/` 目录。

## 必须具备的产品行为

1. **自主范围发现：** 仅给网站/单个 API/OpenAPI 即能产生有证据的 Feature Inventory，记录来源；区分 `discovered`、`in_scope`、`pending_authorization`、`out_of_scope`，不可把自动发现当成授权。
2. **风险优先级与动态探索：** 依业务影响、失败风险、复杂度、可观察性和未知程度挑选实验；每轮“假设 → 授权 → API/Browser 动作 → 观察 → Oracle → 证据 → 再规划”；预算、安全停止与恢复可检查。
3. **三层 Bug 判定：** Pattern 生成失败假设；Oracle 从已确认契约/需求/不变量给出正确行为；Evidence Gate 用真实工具来源、E3+、因果检查与必要人工复核判定 Confirmed；未知 Oracle 或未知副作用不得臆测为真实 Bug。
4. **统一入口和归因：** `testSurface`（API/Web）、`failureType`、`observedLayer`、`suspectedComponent`、`rootCauseStatus` 分离；跨端同一缺陷链接/去重；Android/iOS 不调度自动执行。
5. **授权与工具安全：** R0 只读、R1 隔离安全操作、R2 必须工具层强制授权且动作/范围/修订绑定、R3 默认阻断；URL 输入不是测试授权；超范围与未许可的外部目标不访问。拒绝仅靠 Prompt 强制安全。
6. **恢复和真实数据：** Append-only Action Journal、审批绑定、不可盲重放未知副作用、Finding 不可变修订、Evidence blobs 与哈希；哈希仅证明完整性不证明真实性。
7. **两类报告：** Session 探索汇总和单独 Bug 报告，包含功能发现来源、授权范围、计划/实际探索、API/Web/业务分组、Confirmed/Suspected、复现、Oracle、证据、未探索范围和剩余风险；无证据不得声称已执行或已覆盖。
8. **回归：** 仅输出回归测试建议与追踪关系，不自动新增测试代码或 PR。
9. **独立分发：** 11 个 Skill 独立安装、引用闭包和完整 Bundle；Codex-first，Claude Code 通过真实安装及工具调用确认；不引入独立 Agent Runtime、Web UI 或数据库平台。
10. **规则库：** 16 Patterns 均有适用与排除条件、具体执行方法、Oracle 引用、False-positive 排除、正确/缺陷 Fixture 和 Eval 记录；未经验证保持 Candidate。

## 50 场景 Eval 与工程验收

按冻结的 50 个 Benchmark 构成：API/Business 18、Browser/UI 12、安全审批 10、降级恢复 6、Oracle/Evidence 4。保留 G0（原生 Agent）、G1（Skills）、G2（Skills+Patterns）、G3（完整 BugMaster）对比。真实执行正确、缺陷和模糊实现，并在 Agent 可见上下文之外维护 Ground Truth；度量发现率、误报、Precision/Recall、证据有效率、成本与安全。URL-only/OpenAPI-only Scope Discovery 等新要求纳入既定 50 场景的详细验收，不随意提高冻结数量或伪造已执行计数。

按 W0–W11 和七项 BLK-01..BLK-07 阻断 Spike 推进。内部先打通隔离订单 API 的幂等性正/反/未知结果完整垂直链路：用户授权 → 自主发现 → 路由 → 真正工具动作 → Oracle → Evidence → Finding → Session 报告 → Safe Resume；它只是内部验证节点，不是部分发布。

## 提交、审批与安全发布

- 所有实际改动关联 Feature/Obligation、测试 ID、W0–W11、RED/GREEN 证据，使用独立 PR/Commit；不要在未获权限的 GitHub 组织伪造已创建仓库或 Issues。
- 强制 CI：单元行覆盖率 100%、业务功能覆盖率 >60%、核心三类用例、品牌与 Skill 名称扫描、Schema、打包闭包、静态安全、完整 Benchmark、两宿主验证。
- Q15=D：每个 PR 由 Codex 对准确 head 做代码扫描；R2/R3 变更还做安全扫描。项目所有者查看结果后手动合并，不要求独立真人 PR 签署。Q16 正式发布仍需发起人和不同的真人发布审核人批准同一固定 Commit/Manifest/Artifact 摘要。保护 GitHub Environment/Tag 并校验供应链来源；无双人发布授权或任一阻断门禁失败，Release **No-Go**。
- GitHub Actions 第三方 Action 固定经审查的完整 SHA，令牌最小权限；无真实能力或证据则标记待实现，禁止宣称已运行正式发布工作流。

## 开始执行，不要停留在答复

1. 先汇总审计结果，创建中文 `docs/development/` 任务与进度矩阵，标注 `已实现 / 已验证 / 待实现 / 受阻`。
2. 立即按强 TDD 编写第一个尚未实现核心行为的失败测试，真实运行记录 RED，再实现最小功能并验证 GREEN；持续推进所有 W0–W11。不要为了容易通过质量门禁而缩小已确认 MVP。
3. 每个阶段更新中文 TDD 与质量证据，实际写入源码和测试、运行命令并报告结果；未经执行的功能不能标记完成。
4. 遇到无权限或真实环境缺失，保留明确的 No-Go/Blocked 记录，继续可实施工作；不重新开启非阻断架构问答。
5. 最终交付可独立安装的完整 BugMaster、报告样例、真实 Benchmark、双宿主证据、全量测试及覆盖率证明、发布 Go/No-Go 记录。

**现在开始实际开发。先审计基线与运行测试，再进行第一轮 RED → GREEN → REFACTOR → VERIFY。**
