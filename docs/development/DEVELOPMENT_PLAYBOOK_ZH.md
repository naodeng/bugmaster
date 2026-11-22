# BugMaster 开发手册（权威｜中文）

## 1. 开发原则
本文件是全部开发过程的中文权威规范。代码符号、公开 README 与技术契约英文为主并提供对应中文页；实施计划、ADR 过程讨论、PR、风险台账、测试执行日志、Eval 审查、迭代总结均用中文。AGENTS.md 强制遵守此规范。

冻结 Q1–Q17 及测试对象 B 范围：v0.1 API-first + Browser Basic；Android/iOS 仅未来适配。全量 11 Skills、16 Patterns、50 Benchmark、双宿主、治理能力一次性交付；不得用内部垂直切片冒充完整 MVP。

## 2. 强 TDD 四阶段
| 阶段 | 开发者动作 | 必须保存的证据 | 不允许 |
|---|---|---|---|
| RED | 根据需求/Oracle 先写 Happy/Negative/Edge 测试，实际执行并确认针对缺失行为失败 | 测试 ID、命令、环境、失败输出、Git SHA | 提前修改生产代码；只新建无断言测试 |
| GREEN | 用最小实现使刚才的测试通过 | 通过命令和日志；变更 Diff | 删除/跳过失败测试；硬编码不符合需求的特例 |
| REFACTOR | 在测试保护下改善代码结构 | 受影响测试及回归结果 | 暗中引入新行为或弱化 Oracle |
| VERIFY | 执行全量单元覆盖、功能矩阵、静态/安全/契约、基准和必要宿主测试 | 可复现命令、Coverage 数据、Eval run ID、Q15 扫描记录；公开 Release 另附 Q16 授权 | 用计划、生成内容或截屏代替真实运行 |

### 单项任务步骤
1. 从 `docs/development/BACKLOG_ZH.md` 领取 W0–W11 任务，定位需求 ID 和归属等级 R0–R3。
2. 先更新 `tests/` 场景及验收矩阵；执行 RED 记录在中文 PR。
3. 开发小步 GREEN；运行目标单测；REFACTOR；VERIFY。
4. 更新 Feature Coverage Ledger：实际探索路径、真实工具证据与确认状态，而非自述“测过”。
5. 每个 PR 做 Q15 Codex 代码扫描；R2/R3 变更还做安全扫描。项目所有者查看结果后手动合并，不要求 Q15 真人签署。公开 Release 仍须 Q16 两名不同人员授权。

## 3. 测试目录
- `tests/unit/`：维护的生产模块单测；行覆盖必须 100%。
- `tests/contracts/`：JSON Schema/安全合同、非法输入与跨模块契约。
- `tests/functional/`：业务特性验收与 Happy/Negative/Edge。
- `tests/integration/`：真实 HTTP、浏览器、授权网关和安全恢复联调。
- `tests/e2e/`：从仅 URL/OpenAPI 到自主发现、验证、报告的端到端路径。
- `tests/security/`：R2/R3、URL 范围越界、凭据、证据伪造/注入。
- `tests/eval/`：50 个真实、独立 Ground Truth 的 Benchmark 与 G0–G3 比较。
- `tests/fixtures/`：合法/缺陷/不确定性实现，隔离基准答案。
- `tests/quality/`：冻结的业务义务清单与核心功能三元用例证据。

## 4. 质量门禁
严格遵循 `QUALITY_GATE_POLICY_ZH.md`，不可用单元覆盖率替代功能覆盖。开发初期可只运行非发布的 Contract CI 以获取反馈；完整 Release Gate 在证据不足时必须失败（fail closed）。

## 5. 本地命令
```bash
python -m unittest discover -s tests/unit -v
python -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit
python -m coverage report --fail-under=100
python scripts/quality_gate.py --mode release
python scripts/validate_catalog.py
python scripts/validate_benchmark.py
```
注意：100% `coverage report` 默认衡量行覆盖（若启用 branch，还会综合计算）；本项目统一用 `coverage json` 中 `covered_lines / num_statements` 判断行覆盖，分支覆盖另独立披露，避免口径混乱。

## 6. 合并与发布
每个 PR 都记录 Codex 代码扫描；R2/R3 变更还记录安全扫描。项目所有者查看结果后手动合并，不要求 Q15 独立真人签署。GitHub branch ruleset、Actions least privilege、Artifact Attestation、Release Manifest 一致性与 Q16 RI+IRR 仍是正式发布先决条件。未验证的配置或签署不得宣称已实现。
