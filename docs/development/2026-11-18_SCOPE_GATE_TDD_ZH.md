# 范围与动作风险门禁 TDD 记录

**日期：** 2026-11-18
**Workstream：** W1 / W5（首个确定性安全切片）
**Feature IDs：** `F-SCOPE`、`F-AUTH`
**风险：** R0/R1 门禁判断；本切片不执行外部 API 或浏览器动作。
**基线：** `7f456e8`（开始时 HEAD）；工作区改动未提交，执行环境将 `.git` 标记为只读。

## RED

先更新 `tests/unit/test_scope.py`，以实际函数行为覆盖以下要求：

- R0 只允许显式声明为只读的动作。
- Scope approval 必须是严格布尔 `True`；字符串或整数真值不算授权。
- R1 需要严格布尔 `enforced=True`。
- `operation_mutates` 必须显式提供且为布尔值。
- 非字符串测试表面要安全拒绝，不能因不可哈希输入抛异常。
- R2、R3 和未知风险不通过基础门禁。

初次执行 `python3 -m unittest discover -s tests/unit -p 'test_scope.py' -v`：11 个用例中 5 个失败，分别证实非字符串表面抛错、R0 放行变更动作、R1 接受字符串真值、字符串 Scope approval 被接受、整数 Scope approval 被接受。其余原有表面和风险规则通过。

补充 `test_non_boolean_mutation_classification_is_denied` 后，执行 `python3 -m unittest discover -s tests/unit -p 'test_scope.py' -k non_boolean -v`：断言失败，实际 R1 请求将字符串 `"no"` 作为变更分类仍被放行。

失败来自被测行为与契约不符，不是导入、语法或测试配置错误。

## GREEN

在 `bugmaster_core/scope.py` 中实现最小门禁：

- `classify_surface` 对非字符串及未知表面返回 `unknown / executable=False`。
- `action_allowed` 要求 `scope_approved is True`，且 `operation_mutates` 是必填布尔关键字参数。
- R0 仅在 `operation_mutates is False` 时允许；R1 仅在 `enforced is True` 时允许。
- R2、R3 与未知风险返回拒绝；R2 动作级授权仍由尚未实现的独立网关负责。

执行 `python3 -m unittest discover -s tests/unit -p 'test_scope.py' -v`：12/12 通过。

## REFACTOR

删除 RED 阶段为兼容旧函数签名而临时加入的测试适配；最终测试直接调用正式 API。没有改变已通过的行为契约。

## VERIFY

| 检查 | 命令 / 环境 | 结果 |
|---|---|---|
| 单元回归 | `python3 -m unittest discover -s tests/unit -v`，Python 3.9.6 | PASS，12/12 |
| 契约回归 | `python3 -m unittest discover -s tests/contracts -v`，Python 3.9.6 | PASS，18/18 |
| 品牌与公开名称扫描 | `python3 scripts/check_branding.py` | PASS |
| Catalog / Registry | `python3 scripts/validate_catalog.py` | PASS |
| Benchmark 清单 | `python3 scripts/validate_benchmark.py` | PASS（仅结构检查，场景未执行） |
| 行/分支覆盖 | coverage.py 7.13.3，Python 3.12；数据与 JSON 写入 `/private/tmp` | `bugmaster_core` 行覆盖 18/18（100%），分支覆盖 12/12（100%） |
| Release 质量门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-coverage.json` | NO-GO（预期）：功能义务未冻结、业务覆盖率未超过 60%、15 个核心义务缺少 Happy/Negative/Edge 实际执行证据 |

覆盖率只证明当前 `bugmaster_core` 单元范围被测试执行，不证明自主探索、真实 API/Web、双宿主、Benchmark 或完整 MVP 已通过。完整发布状态仍为 No-Go。

## 工作区与提交记录

本次未生成新 Commit SHA：当前 `.git` 为只读，不能提交代码。基线 HEAD 为 `7f456e8`；RED/GREEN 命令及结果已在本文件记录。代码与文档保留在工作区供审阅，不宣称已推送到上游或 fork。
