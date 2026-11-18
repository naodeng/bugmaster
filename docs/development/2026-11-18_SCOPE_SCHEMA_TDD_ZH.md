# Scope JSON Schema 契约 TDD 记录

**日期：** 2026-11-18
**Workstream：** W1 数据契约
**需求：** `F-SCOPE` / Scope Proposal；目标授权状态、风险预算、身份与环境引用
**实现范围：** `schemas/scope.schema.json`，不实现真实授权网关或审批身份验证。

## RED

先新增 `tests/contracts/test_scope_schema.py`，覆盖有效 Scope 样例、缺少审批引用、移动端误标可执行、未知风险、待审批零预算、已纳入范围却没有动作预算/风险、以及额外字段。首轮执行：

```text
PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -p 'test_scope_schema.py' -v
```

执行退出码为 5；测试类初始化报 `FileNotFoundError: schemas/scope.schema.json`，0 个测试运行。失败来自待实现契约文件不存在，不是测试导入或依赖问题。

## GREEN

新增 Draft 2020-12 Schema 和 `examples/contracts/scope-proposal.json`：

- 每个目标分别记录 `in_scope`、`pending_authorization` 或 `out_of_scope`；待审批和排除项必须写原因。
- `in_scope` 必须关联审批引用；只有 API/Web 可列为可执行目标，Android/iOS/unknown 只能待批或排除。
- 核验风险枚举、Scope revision、非秘密身份/环境引用、额外属性和动作预算；只有 Scope 中含可执行目标时才要求正的动作预算和非空风险上限。
- Schema 注释和文档说明：审批引用只是结构指针，不证明审批人身份、记录真实性/时效性或与当前 Scope Revision 的绑定。

同一目标测试执行 7/7 通过，包含有效 Scope、待批零预算 Scope 和 5 类拒绝行为。Schema 自身由 `Draft202012Validator.check_schema` 检查。

## REFACTOR

将重复内联样例抽到 `examples/contracts/scope-proposal.json`，测试读取真实示例再针对每个拒绝条件复制并变异。把 Scope 作为当前唯一已实现 Schema 与其它待办契约明确分开，避免将部分状态写成完整通过。

## VERIFY

| 检查 | 环境 / 命令 | 结果 |
|---|---|---|
| Scope Schema 单项 | Python 3.12、临时安装 `jsonschema==4.26.0` | PASS，7/7 |
| 单元测试 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit -v` | PASS，12/12 |
| 契约测试 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v` | PASS，25/25 |
| 单元行/分支覆盖 | Python 3.12 + coverage.py 7.13.3，数据写入 `/private/tmp` | `bugmaster_core` 18/18 语句、12/12 分支，100% / 100% |
| 品牌扫描 | `python3.12 scripts/check_branding.py` | PASS |
| Catalog/Registry | `python3.12 scripts/validate_catalog.py` | PASS |
| Benchmark Manifest | `python3.12 scripts/validate_benchmark.py` | PASS（结构通过；50 场景未执行） |
| Release 质量门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-scope-schema-coverage.json` | NO-GO（预期）：Feature Inventory 未冻结、业务覆盖率未超过 60%、15 个核心义务缺少 Happy/Negative/Edge 实测 |
| 路径与格式过期引用 | 在 `docs/en`、`docs/zh-CN`、`RELEASE_POLICY.md` 搜索 `.BugMaster`、`pattern.yaml`、`capabilities.yaml`、`finding.yaml` | 无命中；数据根与 JSON 路径统一 |

GitHub Actions 契约工作流已固定安装 `jsonschema==4.26.0`。该依赖只用于契约测试；Schema 验证仍不构成执行授权。发布门禁仍为 **No-Go**：Scope 是 W1 的一个契约，不代表其他 Schema、功能义务或全量验收完成。
