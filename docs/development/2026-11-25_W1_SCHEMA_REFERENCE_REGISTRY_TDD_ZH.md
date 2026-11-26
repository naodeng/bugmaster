# W1-03 Schema 引用完整性与版本兼容 TDD 记录

- **日期：** 2026-11-25
- **工作流 / 功能义务：** W1-03 / `TDD-CON-012..020`
- **风险级别：** R2
- **开发分支：** `develop`
- **基线：** PR #20 合并提交 `42f9b5db5a2085fb6ce4e8c1f2db4582389179ef`
- **实现提交：** `f2a3d3a333b6b88e01c564a10cb42954ef845fc1`
- **PR #21 首轮复核修复提交：** `a80e57b29d32e17c3a24764faac7ef7c91773c6b`
- **PR #21 第二轮复核修复提交：** `2c44652738b74b11ec7962abd5e977b9bb98bdd6`
- **PR #21 第三轮复核修复提交：** `82d3847f6edbeb7aead99f75d061e74d52762433`
- **状态：** PR #21 三轮审查共五条 P2 意见已在 `develop` 修复并推送；另一个 Spec（方案）复核缺口也已补齐。修复提交 `82d3847` 通过 680 项单测、134 项契约测试、1 项安全测试和 100% 行/分支覆盖；最新代码扫描在 PR 头 `4a4c46d` 完成且无新发现。Standards（规范）、Spec（方案）与本地聚焦安全复核无可执行发现；Codex 安全扫描未返回结果，Q15 安全门禁仍待完成。合并前不启动下一片。

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

## PR #21：第二轮复核意见与引用资源边界修复

提交 `bbb82c5` 的复扫又发现两条 P2：嵌套相对 `$id` 以有效 URI 注册后可能在 `Registry.crawl()`（注册表遍历）中被再次拼接；JSON Pointer（JSON 指针）穿过带 `$id` 的子 Schema 后，闭包检查需要沿用该路径实际更新的 URI 基准。Spec（方案）复核还发现：被实际引用的 `default`（默认值）对象如果含有自己的 `$id` 子资源，这些子资源必须先进入本地注册表，才能检查其相对引用。

### RED：复现第二轮发现

- 资源 ID 重复拼接：以嵌套 `$id: "a/n.json"` 构造冲突；复核复现中，缺少 `mustHave` 的实例曾被错误接受。最终回归用例固定验证重复拼接产生的 URI 不会被注册，避免依赖 `Registry.crawl()` 内部集合顺序。
- JSON Pointer 基准丢失：根 Schema 的指针穿过 `$id: "sub/n.json"` 后指向含 `$ref: "allowed.json"` 的普通数据对象。旧代码按根 URI 加载成功，未按子资源 URI 拒绝缺失的 `sub/allowed.json`。
- 被引用默认值的子资源：目标对象声明绝对 `$id`，内部子 Schema 用相对 `$id` 和相对 `$ref`；旧代码以 `schema-reference-unresolved:sub/nested.json` 失败。

### GREEN：第二轮修复

- 在注册表专用深拷贝中把相对嵌套 `$id` 固定为有效绝对 URI，再注册资源；校验器对外返回的原始 Schema 内容保持不变，`Registry.crawl()` 不再二次拼接该 ID。
- 用 `Resource.pointer()`（资源指针解析）和 `_BaseUriTracker`（基准 URI 跟踪器）跟踪 JSON Pointer 穿过的子资源基址，不再读取 `Resolver` 的私有属性。解析结果按该基址继续检查和解析传递引用。
- 将注册逻辑汇总到 `register_resources()`：只有目标对象实际被 `$ref` 或 `$dynamicRef` 引用后，才注册该 Schema 及其嵌套资源；校验重复 ID 后，再检查其引用闭包。未被引用的 `default` 仍作为普通数据跳过。

### VERIFY：第二轮复核修复

环境：macOS；Python 3.12.16；固定依赖位于 `/private/tmp/bugmaster-provenance-test-deps`。当前本地修复尚未推送，Q15 最终 PR 头代码/安全扫描待完成。

| 检查 | 命令 / 范围 | 结果 |
|---|---|---|
| Schema 注册表定向单测 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/unit -p test_schema_registry.py -q` | PASS，38/38 |
| 全量单测 | `COVERAGE_FILE=/private/tmp/bugmaster-pr21-finalfix.coverage PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 python3.12 -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit -q` | PASS，677/677 |
| 契约 / 安全测试 | `python3.12 -m unittest discover -s tests/contracts -q`；`python3.12 -m unittest discover -s tests/security -q` | PASS，134/134、1/1 |
| 行 / 分支覆盖率 | `python3.12 -m coverage report -m --fail-under=100` | PASS，3343/3343 语句、1212/1212 分支，均 100%；JSON：`/private/tmp/bugmaster-pr21-finalfix-coverage.json` |
| 品牌、目录、基准清单及 Diff | `check_branding.py`、`validate_catalog.py`、`validate_benchmark.py`、`git diff --check` | PASS；基准场景未执行 |
| Release Gate（发布门禁） | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr21-finalfix-coverage.json` | 按预期 NO-GO：功能清单未冻结、业务执行覆盖未超过 60%、核心 Happy/Negative/Edge 场景缺少实际证据 |
| Standards（规范）/ Spec（方案）/ 安全代码复核 | 当前修复差异 | 均无可执行问题；不等同独立真人审查或完整渗透测试 |
| Q15 Codex 代码/安全扫描 | 最新本地修复待扫描 | 第二轮发现的两条 P2 已修复；推送后重新触发 PR 头代码与安全扫描 |

## PR #21：第三轮复核意见与 Pointer 基准一致性修复

日期：2026-11-26。PR 最新复扫发现第五条 P2：当 JSON Pointer（JSON 指针）指向普通 `default`（默认值）对象，且对象内 `$id` 改变目录时，加载期曾按新 `$id` 检查嵌套引用，而运行时沿用 Pointer 实际解析基准；因此闭包检查可能检查错误目标或遗漏运行时缺失引用。

### RED：复现

- 新增根 `$id` 为 `https://example.test/root.json` 的正向夹具，`default` 声明 `$id: "sub/target.json"` 并引用 `allowed.json`，但本地只注册 `/sub/allowed.json`。旧实现没有在加载期拒绝，失败输出为 `SchemaRegistryError not raised`。
- 再新增只注册根目录 `/allowed.json` 的正向实例校验，要求加载期闭包与运行时均使用同一目标，并实际执行目标 Schema 约束。

### GREEN：修复

- 对 JSON Pointer 目标使用 `Resource.pointer()`（资源指针解析）得到的有效 URI（统一资源标识符）作为运行时与闭包检查基准。
- 若指针命中尚未注册为 Schema 子资源的普通数据对象，跳过其根对象资源注册，不把对象自身 `$id` 再作为 URI 边界；仍遍历并注册其下由 JSON Schema 规则识别的嵌套子资源。
- 即使目标对象自身 `$id` 不作为运行时边界，仍校验其格式和在当前基址下是否可解析，保留不透明 `urn:` 根 URI 下拒绝无效相对 ID 的既有约束。

### VERIFY：第三轮复核修复

环境：macOS；Python 3.12.16；测试依赖来自 `/private/tmp/bugmaster-provenance-test-deps`。覆盖数据来自包含当前工作区源码快照的临时副本。

| 检查 | 命令 / 范围 | 结果 |
|---|---|---|
| 新增回归 RED | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit -p test_schema_registry.py -k referenced_default_id_does_not_change_pointer_runtime_base -v` | 修复前 FAIL：`SchemaRegistryError not raised` |
| Schema 注册表定向单测 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps python3.12 -m unittest discover -s tests/unit -p test_schema_registry.py -q` | PASS，41/41 |
| 全量单测与覆盖采集 | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps python3.12 -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit -q` | PASS，680/680；覆盖 JSON：`/private/tmp/bugmaster-pr21-fifth-review-coverage.json` |
| 行/分支覆盖率 | 读取以上 JSON 的 `totals` | PASS，3355/3355 语句、1218/1218 分支，均 100% |
| 契约 / 安全测试 | `python3.12 -m unittest discover -s tests/contracts -q`；`python3.12 -m unittest discover -s tests/security -q` | PASS，134/134、1/1 |
| 品牌、目录、基准清单结构 | `check_branding.py`、`validate_catalog.py`、`validate_benchmark.py` | PASS；基准场景未执行 |
| 发布门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-pr21-fifth-review-coverage.json` | 按预期 NO-GO：功能清单未冻结、业务执行覆盖未超过 60%、核心 Happy/Negative/Edge 场景缺少实际证据 |
| Standards / Spec / 聚焦安全复核 | 当前代码与测试差异 | 无可执行发现；安全复核为只读代码检查，不代表独立真人审查或完整渗透测试 |
| Q15 Codex 代码扫描 | PASS（通过） | PR 头 `4a4c46d` 扫描完成，无新发现；后续记录提交只更新中文文档，不改代码 |
| Q15 Codex 安全扫描 | PENDING（待完成） | GitHub 扫描状态未启动；本机 `codex exec --sandbox read-only` 未产出结论并被中断。聚焦源代码审查无可执行发现，但不能替代 Q15 扫描；合并前仍需完成 |
