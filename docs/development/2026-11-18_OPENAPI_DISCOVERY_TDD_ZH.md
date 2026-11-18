# 本地 OpenAPI 发现切片：TDD 记录

**日期：** 2026-11-18
**Workstream：** W4 风险路由 / W1 Feature Discovery 输入
**需求：** `F-API`；产生带来源的 API Feature 候选，发现与授权/执行分离。

## RED

先新增 `tests/unit/test_openapi_discovery.py`，覆盖：OpenAPI 3.0/3.1 操作发现、参数/Request Body/Responses/Security 引用、ID 稳定性、路径确定性、输入字段错误，以及不得把 path 元数据误报为操作。

执行 `python3.12 -m unittest discover -s tests/unit -p 'test_openapi_discovery.py' -v`：导入失败 `ModuleNotFoundError: bugmaster_core.openapi_discovery`，证实模块尚未实现。测试构造的是内存文档，RED 不访问网络。

补充文件入口测试 `tests/unit/test_openapi_cli.py` 后，执行对应 `unittest discover` 也以 `ModuleNotFoundError: bugmaster_core.openapi_cli` 失败，证明本地文件读取/CLI 入口尚未实现。

## GREEN

新增 `bugmaster_core/openapi_discovery.py` 和 `bugmaster_core/openapi_cli.py`，并提供 `scripts/discover_openapi.py` 入口：

- 仅接收调用方已加载的 OpenAPI 3.x Mapping 和来源标识；不使用 HTTP、浏览器或文件发现，不产生 API 动作。
- 每个已声明 HTTP operation 生成确定性 `featureId`（规范化 method + path 的 SHA-256 前缀）、`surface=api`、`discoveryStatus=discovered` 与 `observationKind=openapi-declaration`。
- `sourceRef` 使用 URI fragment 中的 JSON Pointer；同时给出 path/operation parameters、Request Body、Responses、Security 的来源指针。Operation 的 Security 优先；缺省时记录文档级 Security 指针。
- `operationId`、`summary`、`tags` 用作来源描述；未提供名称时回退到 `METHOD path`。未知 Path Item 字段不生成 Feature。
- 输入结构不符合本切片契约时抛出 `ValueError`；只支持 OpenAPI 3.x，尚不解析 `$ref` 内容、不校验整个 OpenAPI Schema、不证明线上实现与规格一致。
- CLI 只从本地路径读取 UTF-8 JSON；读文件、JSON 解析或结构校验失败时返回 2 且不输出清单。可通过 `--source-ref` 避免在清单中记录本地绝对路径。

之后先增加 `tests/contracts/test_feature_inventory_schema.py` 并执行，RED 因 `schemas/feature-inventory.schema.json` 缺失而以退出码 5 失败。补入 Draft 2020-12 Schema 后，7/7 契约通过；测试直接运行本地 CLI 并验证其实际 JSON 输出，且拒绝将 `discovered` 改写成 `in_scope`、混入执行状态、缺失来源或伪造 Feature ID。

## REFACTOR

通过 canonical method/path 派生稳定 ID，按 path/method 排序保证输出可复现；JSON Pointer 转义 `~` 与 `/` 并对 fragment token 做 URI 编码；将操作声明明确标记为静态来源观察，避免把文档声明误说成线上端点已验证或获得授权。

## VERIFY

| 检查 | 命令 / 环境 | 结果 |
|---|---|---|
| Discovery 单元 | `python3.12 -m unittest discover -s tests/unit -p 'test_openapi_discovery.py' -v` | PASS，10/10 |
| 本地 CLI 单元 | `python3.12 -m unittest discover -s tests/unit -p 'test_openapi_cli.py' -v` | PASS，5/5 |
| Feature Inventory Schema | `python3.12 -m unittest discover -s tests/contracts -p 'test_feature_inventory_schema.py' -v` | PASS，7/7 |
| CLI 示例 | `python3.12 scripts/discover_openapi.py examples/openapi/orders.json --source-ref examples/openapi/orders.json` | PASS，输出 2 个带来源的 declared-operation Features |
| 全量单元 | Python 3.12 + coverage.py 7.13.3：`python -m coverage run --branch --source=bugmaster_core -m unittest discover -s tests/unit` | PASS，27/27 |
| 行/分支覆盖 | `/private/tmp/bugmaster-openapi-coverage.data` | `bugmaster_core` 156/156 语句、68/68 分支，100% / 100% |
| 全量契约 | Python 3.12 + `jsonschema[format-nongpl]==4.26.0` | PASS，52/52 |
| 品牌扫描 | `python3.12 scripts/check_branding.py` | PASS |
| Catalog/Registry | `python3.12 scripts/validate_catalog.py` | PASS |
| Benchmark Manifest | `python3.12 scripts/validate_benchmark.py` | PASS（仅结构验证，50 场景未执行） |
| Release Gate | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-openapi-coverage.json` | NO-GO（预期）：Inventory 未冻结、业务覆盖率未超过 60%、15 个核心义务缺 Happy/Negative/Edge 实测 |

100% 只覆盖当前 `bugmaster_core` 中的确定性 helper，不能代表 Browser/URL 动态发现、网络执行、用户功能覆盖率或全量生产代码验收。代码未提交或推送。
