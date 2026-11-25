# W1-03 Schema 引用完整性与版本兼容 TDD 记录

- **日期：** 2026-11-25
- **工作流 / 功能义务：** W1-03 / `TDD-CON-012..020`
- **风险级别：** R2
- **开发分支：** `develop`
- **基线：** PR #20 合并提交 `42f9b5db5a2085fb6ce4e8c1f2db4582389179ef`
- **实现提交：** `f2a3d3a333b6b88e01c564a10cb42954ef845fc1`
- **状态：** 实现、全量验证、Codex 代码扫描与聚焦安全扫描均通过；提交已推送到 `origin/develop`；项目所有者已于 2026-11-25 指示继续推进 PR（拉取请求）。后续按 `develop` → `main` 单 PR 流程审阅和手动合并，合并前不启动下一片。

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
