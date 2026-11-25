# W1-03 Schema 引用完整性与版本兼容 TDD 记录

- **日期：** 2026-11-25
- **工作流 / 功能义务：** W1-03 / `TDD-CON-012..020`
- **风险级别：** R2
- **开发分支：** `develop`
- **基线：** PR #20 合并提交 `42f9b5db5a2085fb6ce4e8c1f2db4582389179ef`
- **实现提交：** `f2a3d3a333b6b88e01c564a10cb42954ef845fc1`
- **PR #21 复核修复提交：** `a80e57b29d32e17c3a24764faac7ef7c91773c6b`
- **状态：** PR #21 的两条 P2 代码审查意见已在本地 `develop` 修复并通过全量验证；原实现提交 `f2a3d3a` 的代码与聚焦安全扫描通过，但针对修复提交的 Q15（逐 PR 代码扫描及适用的安全扫描）复扫待完成。合并前不启动下一片。

## 范围

为仓库内 `schemas/*.schema.json` 增加封闭的本地 Schema（数据结构规则）注册表，并让契约绑定和 Candidate/Finding（候选记录/缺陷记录）元数据存储复用同一加载器。只校验 Schema 定义、版本、ID（规则标识）和 `$ref` / `$dynamicRef`（规则引用）闭包。

不验证业务记录引用是否存在或可信，不认证来源或审核人，不改变动作授权与派发，不保存证据原件，不接入浏览器运行时。当前改动不要求独立真人安全审查；Codex 代码/安全复核不等同于真人签署。

## RED：失败用例先行

- 将新增注册表用例放入 PR #20 基线工作树运行，得到 `ModuleNotFoundError: No module named 'bugmaster_core.schema_registry'`，确认基线尚无该能力。
- 针对复核发现的边界先加回归用例：根 `$id` 的空片段、引用到字符串或非法 Schema 对象。运行时 23 项用例中这 3 项失败；分别复现空片段被接受、无效目标被延迟到实例校验时才崩溃。
- 针对 URI（统一资源标识符）等价但大小写/默认端口不同的重复 ID，加根级与嵌套级用例。运行时 26 项用例中这 2 项失败。
- 针对 URI 等价写法的跨文件引用，加本地解析正例。运行时 30 项用例中该例以 `schema-reference-unresolved` 失败。

## GREEN：实现及重构

- 新增 `bugmaster_core.schema_registry`：检查 Draft 2020-12、绝对且无片段的根/嵌套 `$id`、规范化后的 ID 唯一性和固定的 `主版本号.次版本号` `schemaVersion`。
- 使用 `referencing.Registry` 注册根与嵌套资源；只映射已加载本地资源的 URI 等价引用，不添加网络检索器。未知资源仍失败关闭。
- 对 `$ref` 和 `$dynamicRef` 的解析结果再次校验 Draft 2020-12 Schema；对象 Schema 与布尔 Schema 均合法，标量或非法结构在加载时拒绝。
- 依赖 `Resource.subresources()` 识别 Schema 子规则，避免扫描 `default`（默认值）中的普通数据对象；嵌套 `$id` 采用有效基准 URI 解析相对引用。
- `contract_binding` 与 `metadata_store` 改用共享加载器；既有元数据读取错误仍包装为 `MetadataStoreError` 并失败关闭。

## VERIFY：验证证据

环境：macOS；Python 3.12.16；`jsonschema[format-nongpl]==4.26.0`、`coverage.py` 来自 `/private/tmp/bugmaster-provenance-test-deps`。

| 检查 | 命令 / 范围 | 结果 |
|---|---|---|
| 注册表定向单测 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p test_schema_registry.py -q` | PASS，30/30 |
| 全量单测 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -q` | PASS，669/669 |
| 契约测试 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/contracts -q` | PASS，134/134 |
| 安全测试集 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/security -q` | PASS，1/1；不替代 Q15 源码安全扫描 |
| 全量行/分支覆盖率 | `COVERAGE_FILE=/private/tmp/bugmaster-w1-03.final.coverage PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit -q`，随后 `coverage report -m --fail-under=100` | PASS，3294/3294 行、1200/1200 分支，均为 100%；JSON：`/private/tmp/bugmaster-w1-03-final-coverage.json` |
| 品牌、目录、基准清单 | `python3.12 scripts/check_branding.py`；`python3.12 scripts/validate_catalog.py`；`python3.12 scripts/validate_benchmark.py` | PASS；基准清单仅通过结构校验，场景未执行 |
| Diff 空白检查 | `git diff --check` | PASS |
| Release Gate（发布门禁） | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-w1-03-final-coverage.json` | 按预期 NO-GO：功能清单未冻结、真实功能覆盖未超过 60%、核心功能缺少 Happy/Negative/Edge 实际执行证据；不是本切片测试失败 |
| Q15 Codex 代码扫描 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps codex review --uncommitted` | PASS；最终扫描未发现可执行缺陷；扫描输出 `/private/tmp/bugmaster-w1-03-code-review-final3.txt`，扫描包含 669 个单测通过证据 |
| Q15 Codex 聚焦安全扫描 | 完整命令见下方 | PASS；针对提交 `f2a3d3a333b6b88e01c564a10cb42954ef845fc1` 未发现可执行安全问题；输出 `/private/tmp/bugmaster-w1-03-security-review-final.txt`。只读源码审查；未检查部署/打包，也未执行完整渗透测试，不代表独立真人审查 |

安全扫描命令：

```bash
PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps codex exec --sandbox read-only -C /Users/inaodeng/.codex/worktrees/w5-scope-action-gateway/bugmaster "Perform a focused security review of committed W1-03 changes from base 42f9b5d to commit f2a3d3a. Read the diff and source only; do not modify files or execute code. Inspect schema file/path handling, URI ID normalization, local alias registration, reference resolution and target validation, error/fail-closed behavior, and confirm whether any network retrieval or authorization/dispatch/provenance boundary changed. Report actionable findings with severity and file/line, or explicitly report no actionable security defects. State scope limits; do not claim an independent human review or full penetration test." > /private/tmp/bugmaster-w1-03-security-review-final.txt 2>&1
```

完整产品仍为 Release No-Go（暂不发布）。本切片未改变 W5 的 fail-closed（失败时保持阻断）授权边界，也未解除 Q16 公开发布的双人授权要求。

## PR #21：Codex 代码审查意见修复

PR #21 的 Codex Review（代码审查）在提交 `7176b34` 上指出两处 P2 问题：

1. URI（统一资源标识符）等价别名解析到本地资源后，目标资源内的相对 `$ref`（Schema 规则引用）仍沿用别名基准 URI，导致本地注册的子资源无法解析。
2. `$ref` 指向 `default`（默认值）等普通数据对象时，目标对象会作为 Schema（数据结构规则）执行；旧逻辑校验其结构后没有继续检查其中的传递引用，未注册的外部引用会延迟到实例验证时才失败。

### RED：复现审查发现

- 新增三份本地 Schema（数据结构规则）的回归用例：A 通过大写主机名与默认端口别名引用 B，B 再以 `c.json` 相对引用 C；旧实现加载成功，但验证合法嵌套记录时抛出 `Unresolvable: c.json`。
- 新增目标指向 `properties.payload.default` 的用例，其中目标对象含未注册外部 `$ref`；旧实现未在加载期抛出 `SchemaRegistryError`。
- 增加递归 `$ref`（规则引用）场景，要求引用闭包遍历在环路中终止。

### GREEN：修复

- 改用待处理资源队列递归检查每个已解析目标及其 Schema 子规则；仍通过 `Resource.subresources()` 区分 Schema 与普通数据，只有被实际引用的 `default` 对象才作为 Schema 检查。
- 解析到 URI 等价的已注册别名后，保留运行时有效基准 URI，并沿相对引用补齐本地别名解析。候选目标仍必须命中已加载本地资源，不增加网络取回。
- 使用 `(contents 对象身份, 有效基准 URI)` 作为访问键，终止递归闭包遍历，同时保留同一资源在不同别名基准下的解析。
- 对片段引用保留当前基准 URI，支持不透明 `urn:` 根 URI 下的本地引用。

### VERIFY：复核修复验证

环境：macOS；Python 3.12.16；依赖位于 `/private/tmp/bugmaster-provenance-test-deps`。验证对应修复提交 `a80e57b29d32e17c3a24764faac7ef7c91773c6b`。

| 检查 | 命令 / 范围 | 结果 |
|---|---|---|
| Schema 注册表定向单测 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p test_schema_registry.py -q` | 35/35 通过 |
| 全量单测 | `COVERAGE_FILE=/private/tmp/bugmaster-pr21-review-fix.coverage PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit -q` | 674/674 通过 |
| 契约 / 安全测试 | `python3.12 -m unittest discover -s tests/contracts -q`；`python3.12 -m unittest discover -s tests/security -q` | 134/134、1/1 通过 |
| 行 / 分支覆盖率 | `python3.12 -m coverage report -m --fail-under=100` | 3311/3311 语句、1204/1204 分支，均 100%；JSON：`/private/tmp/bugmaster-pr21-review-fix-coverage.json` |
| 品牌、目录、基准清单及 Diff | `check_branding.py`、`validate_catalog.py`、`validate_benchmark.py`、`git diff --check` | 通过；基准场景未执行 |
| Release Gate（发布门禁） | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr21-review-fix-coverage.json` | 按预期 NO-GO：功能清单未冻结、业务执行覆盖未超过 60%、核心 Happy/Negative/Edge 场景缺少实际证据 |
| 代码方案审查 | Standards（规范）与 Spec（方案） | 均无发现；聚焦安全复核也未发现可确认问题。安全复核为只读代码审查，不等于独立真人审查或渗透测试 |
| Q15 Codex 代码/安全扫描 | 待完成 | 修复提交尚未推送到 PR #21；推送后触发针对最新 PR 头的代码与安全扫描，收到结果前不标记通过 |
