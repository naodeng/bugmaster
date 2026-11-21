# BugMaster 测试覆盖率与发布质量门禁（中文权威）

## 定义与统计口径

### GATE-U100：单元测试 100%
- 分母为全部**需要单测的生产 Python 模块**可执行语句行，不能只挑选容易覆盖的模块。当前生产 Python 清单为 `bugmaster_core/` 与 `scripts/`；对应单元测试共同统计，仓库门禁明确列出两者。
- 行覆盖率必须 `covered_lines / measured_lines == 1.0`，基于 coverage.py JSON `totals.covered_lines / totals.num_statements`；新增生产 Python 包必须纳入 `--source`。分支覆盖率独立披露并推动提高，不混称为 100% 行覆盖。
- 若以后存在 TypeScript/其他语言，需分别建立同等 100% 单测门禁，并在汇总中检查所有生产代码的非豁免范围。
- 非生产生成文件、第三方依赖可以有经审查的明确豁免；不能以忽略文件、`pragma: no cover`、调整分母掩盖缺陷。

### GATE-F60：业务功能覆盖必须严格 >60%
- 分母为审核批准且版本冻结的 `tests/quality/feature_coverage.json` 全量业务**功能义务**数量，标注 `applicable=true`；包含 API-first、Browser Basic、自主 Scope、Bug Judgment、Finding、Report、安全恢复等。允许人工审批新增/删减义务，不允许发布时缩小分母。
- 分子为 `status=validated` 且存在至少一个真实执行证据、可追溯的 Feature ID、有效验收 Oracle 的义务。`planned/implemented/blocked/untested` **都不算覆盖**。
- 必须 `validated / applicable > 0.60`，等于 60% 不算通过。Release 同时需要全部其他核心门禁通过，因此 61% 也不能豁免未完成的 11 Skills、16 Patterns、50 Eval 等。

### GATE-C3：核心功能每项三类用例
- 每个 `critical=true` 义务必须在 `tests/quality/core_case_matrix.json` 对应至少 Happy、Negative、Edge 三类不同 Case ID。
- 三类必须真实执行 `result=passed` 且有不可伪造的 evidence reference 与 applicable oracle ID。单测、伪日志、没有环境的快照不能替代系统级业务验收。
- Safety 负例与受控权限边界必须验证拒绝；永不向非授权外部站点实际发起破坏操作。

## Fail closed
- 任何 missing evidence、重复 Case ID、未知 Feature ID、不可信状态、失配 Oracle、错误分母、未覆盖核心情况，一律 No-Go。
- CI `contract` 是开发反馈不是 Release Gate；独立 `release-quality-gate` 不达标应失败。PR 不能用降低阈值来获得通过。
- Q10 50 Benchmark 是真实执行用例，当前 planned 无法通过正式 Eval Gate；不得把清单等同完成。

## 工具命令
```bash
python -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit
python -m coverage json -o coverage.json
python scripts/quality_gate.py --mode release --coverage coverage.json
```
## 变更控制
任何覆盖范围、排除、Feature Inventory、Oracle 和用例分类修改，必须进入中文 PR、关联需求 ID、附 Red/Green 证据和独立 Review；Release 必须冻结版本和摘要。
