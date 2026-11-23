# W7 Candidate（候选记录）/Finding（缺陷记录）元数据持久化 TDD（测试驱动开发）记录

**日期：** 2026-11-23
**工作流：** W1（数据契约）/ W7（缺陷记录）；基础内容对应 PR #14 合并提交 `e594946ca4d823c044897c000c1975a7301631c7`。
**实现提交（生产代码与测试）：** [`1a86eeabffad401df3f5e1f484c856e548a10360`](https://github.com/naodeng/bugmaster/commit/1a86eeabffad401df3f5e1f484c856e548a10360)。验证命令运行时的生产代码与测试内容和该提交一致；后续 TDD 记录修订仅补充提交与 RED 证据说明。
**Feature/Obligation（功能/义务）ID：** `F-FINDING`。
**术语：** `JSON Schema`（JSON 数据结构规则）；`revision`（修订版本）；`fail-closed`（失败时保持阻断）；`Q15`（逐个 PR 执行的 Codex 代码扫描；R2/R3 改动还需 Codex 安全扫描）。
**用户批准范围：** 增加 Candidate（候选记录）/Finding（缺陷记录）结构契约和私有本地元数据持久化。只存元数据与证据引用，不存原始 Evidence Blob（证据原件字节）；不认证来源或审核人身份；不接入 Confirmed Gate（缺陷确认门禁）。Codex 负责代码与安全审查，项目所有者最终确认并手动合并。

## RED（先失败）：锁定缺失行为

- RED 测试针对 GitHub 上 PR #14 的合并基线 `e594946ca4d823c044897c000c1975a7301631c7`。本地工作树 HEAD 为 `1cbda3762261a968199a00e1696608da9978b6ed`，其内容树 `b6b4dbd6058ac3391758996f8ca838d400605ef4` 与远端合并基线一致；该合并提交对象不在本地 Git 数据库中。测试先写，并在对应实现修改前运行；5 个仅含测试的提交已推到独立功能分支，生产实现仍在本地未提交工作树。
- GitHub 相邻提交比较确认，下列 5 个 RED 提交的变更都只涉及 `tests/`：

| 提交 | 新增或扩展的测试范围 | 实现前的失败证据 |
|---|---|---|
| `c3587362442c1724edf0a8c8f60bbadc2f6569a6` | Candidate（候选记录）/Finding（缺陷记录）数据结构规则与本地元数据存储 | 对应数据结构规则文件不存在；导入 `bugmaster_core.metadata_store` 失败 |
| `c2feb86dd03168b918f3cda342706fdfd5f6df18` | Candidate（候选记录）/Candidate Assessment（候选评估）中的非规范 Oracle（预期行为判定依据）/Evidence（证据）ID | 合法格式断言未拒绝 `oracle-1`、`evidence-1` 等引用 |
| `492d0c62c45cd4b55a235264db6d0c0d2551affd` | 嵌套误报检查、反证及审核引用 | 非规范嵌套引用未被拒绝，输出可能违反对应 Schema |
| `aea86607a7f3662912efa76bc15d377197ad40b4` | Candidate、Finding、Oracle、Evidence 和摘要 ID 的尾换行边界 | Python 正则的 `$` 在尾换行前匹配，相关用例未被拒绝 |
| `d2d3ecd2bf119ffc79fbe9d272c4634c070a9d19` | 候选评估 helper（辅助函数）与 Schema 一致性、重复目标 ID | helper（辅助函数）会输出非法引用；`duplicateOf.candidateId` 接受非规范 ID |

- `c358736` 的 RED 在 PR #14 基线上运行：`PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m unittest discover -s tests/contracts -p 'test_candidate_schema.py'`、对应的 `test_finding_schema.py` 和 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m unittest discover -s tests/unit -p 'test_metadata_store.py'`；输出分别报告契约文件缺失和 `bugmaster_core.metadata_store` 模块不存在。
- 原始开发运行没有归档标准输出。为提供可复核失败证据，现已用 PR #14 基线源码和仅含测试的远端提交重建临时副本并回放 RED；包含测试版本、Python 环境、失败统计与完整输出文件的说明见 [W7 RED 基线回放证据](evidence/w7-candidate-finding-red/证据说明.md)。该回放能复现实现前的失败行为，但不冒充原始开发时的日志。
- `c2feb86`、`492d0c6` 的引用格式 RED 由新增的 `test_oracle_and_evidence_references_use_canonical_ids`、`test_nested_review_and_identity_references_use_canonical_ids` 和相关存储测试复现；运行相应测试时，非法 ID 未触发预期拒绝断言。尾换行 RED 由 `test_identifier_patterns_reject_trailing_newlines` 和存储测试复现；Candidate（候选记录）9 项、Candidate Assessment（候选评估）8 项、Finding（缺陷记录）8 项、Oracle/Evidence（预期行为判定依据/证据）7 项、存储 2 项检查在严格结束锚点修复前失败。
- `d2d3ecd` 的 RED 由候选评估 helper（辅助函数）新增用例复现：6 个回归测试在修复前失败，其中包含 8 个子用例断言；重复目标格式测试分别在 Candidate Assessment 契约和元数据存储中失败。测试确认 helper（辅助函数）可能生成不符合新 Schema 的记录，以及 `duplicateOf.candidateId` 没有执行规范格式检查。
- 对应 Schema（数据结构规则）创建前运行 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m unittest discover -s tests/contracts -p 'test_candidate_schema.py'` 与 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m unittest discover -s tests/contracts -p 'test_finding_schema.py'`；失败用例指出对应文件缺失。`metadata_store.py` 创建前运行 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m unittest discover -s tests/unit -p 'test_metadata_store.py'`，失败原因是 `bugmaster_core.metadata_store` 模块不存在。
- 先写扩展校验器回归测试 `test_additional_validator_cannot_mutate_persisted_metadata`，再运行 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m unittest discover -s tests/unit -p 'test_metadata_store.py' -k 'additional_validator_cannot_mutate' -v`；修复前 `created` 与预期输入不相等，失败定位在 `assertEqual(created, expected)`。
- 先写 Candidate 审核事件回归测试，再运行 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m unittest discover -s tests/unit -p 'test_metadata_store.py' -k 'candidate_review_event' -v`；修复前“事件 Candidate ID 不匹配”和“引用未来版本”两项均以 `MetadataStoreError not raised` 失败。
- 需求规范复核后新增跨版本审核历史、去重身份、重复事件 ID、事件证据引用和 Schema（数据结构规则）整数语义测试；在相应实现修改前分别复现：`test_review_history_can_grow_across_candidate_revisions` 抛出 `ValueError: review-event-binding-invalid`；身份、重复 ID、外部证据引用三项未抛预期 `MetadataStoreError`；整数版本用例收到 `float` 而非 `int`。复现命令均使用 `/opt/homebrew/bin/python3.12 -m unittest discover -s tests/unit -p '<对应测试文件>' -k '<测试名>' -v`，并设置 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps`。
- 新增历史审核事件最低版本要求和 Candidate 的 identity（去重身份）与顶层 Oracle 引用一致性测试；修复前以 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -m unittest tests.unit.test_candidate_assessment.CandidateAssessmentTests.test_historical_review_event_requires_a_positive_candidate_revision tests.unit.test_metadata_store.MetadataStoreTests.test_candidate_identity_oracle_must_match_candidate_oracle_reference` 运行，两个用例分别因 `ValueError not raised`、`MetadataStoreError not raised` 失败。
- 安全复核发现已存在的宽权限目录可能在写入时被改权限；新增 `test_create_does_not_repair_an_existing_shared_storage_root`，修复前运行 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -m unittest tests.unit.test_metadata_store.MetadataStoreTests.test_create_does_not_repair_an_existing_shared_storage_root`，因预期 `MetadataStoreError` 未抛出而失败。
- Codex 代码扫描发现存储可接受自我重复引用，以及历史审核事件可引用到其所指版本中尚不存在的 Evidence；新增 `test_duplicate_candidate_cannot_reference_itself` 和 `test_historical_review_event_evidence_must_exist_in_referenced_revision`，修复前运行 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -m unittest tests.unit.test_metadata_store.MetadataStoreTests.test_duplicate_candidate_cannot_reference_itself tests.unit.test_metadata_store.MetadataStoreTests.test_historical_review_event_evidence_must_exist_in_referenced_revision`，两项都因预期 `MetadataStoreError` 未抛出而失败。
- 最终 Codex 扫描发现 Finding 的同一 Evidence ID 可带不同摘要重复出现；新增 `test_finding_evidence_ids_must_be_unique_even_with_different_fingerprints`，修复前运行 `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -m unittest tests.unit.test_metadata_store.MetadataStoreTests.test_finding_evidence_ids_must_be_unique_even_with_different_fingerprints`，因预期 `MetadataStoreError` 未抛出而失败。
- RED 环境统一使用 `/opt/homebrew/bin/python3.12` 和 `/private/tmp/bugmaster-provenance-test-deps`。先前一次默认 Python 3.9 调用因测试依赖环境不兼容而失败，不作为实现行为的 RED 证据。

## GREEN（修复后通过）：实现最小行为

- 新增 Candidate/Finding v1.0 Schema（数据结构规则）和 `CandidateStore` / `FindingStore`。默认执行 Schema 校验，可另加调用方校验器；扩展校验器接收由规范 JSON 重新解析的副本，不能篡改返回值或写入值。
- 每个 ID 映射到 SHA-256（安全哈希算法）命名的独立目录；版本文件不可覆盖，`metadata.head`（最新版本指针）保存最新版本摘要与完整历史摘要。追加版本要求 `expected_revision`（预期当前版本）匹配，读取时重新校验完整历史和摘要。
- 文件系统边界复用现有 POSIX（类 Unix 操作系统接口）安全目录打开逻辑：拒绝符号链接、硬链接、错误所有者和不安全文件权限；macOS 上通过 ACL（访问控制列表）检查扩展权限。缺失的配置根目录会以仅所有者访问权限创建；已有根目录必须已是私有目录，写入不会擅自改动其权限；其下的记录目录写入前会核验所有者和 ACL，再收紧到仅所有者访问。读取拒绝非私有目录；已有文件权限不安全时不修复。临时文件、同步到磁盘及不可覆盖发布用于降低部分写入风险；发现孤立版本或未登记项时读取阻断，不自动修复。
- Candidate Assessment 的 ID、版本、表面、Pattern（缺陷模式）、Oracle（预期行为判定依据）引用、Evidence（证据）引用、误报检查、审核要求和可选去重身份与 Candidate 版本绑定。其 identity（去重身份）中的 Oracle 引用必须与 Candidate 顶层一致；Candidate 不能把自己标记为重复项。审核事件必须指向同一 Candidate、引用该 Candidate 已存在的版本、拥有唯一事件 ID，且 Evidence ID 必须存在于事件所引用的确切版本中。既有 `append_review_event()` 仍要求新审核事件绑定当前版本；历史事件可保留较早版本号并继续追加。这些检查不认证审核人。
- Finding 的证据引用按 Evidence ID 唯一；同一 ID 即使带不同摘要或字节长度，也不能在一条记录中重复出现。
- 只允许 Candidate `candidate`、`needs_review`、暂定 `duplicate` 和 Finding `hypothesis`、`observed`、`suspected`、`needs_review` 状态。Candidate `rejected` 与 Finding `confirmed`、`rejected`、`duplicate`、`resolved`、`reopened` 会被阻断。
- Candidate 的 Evidence 引用只存 ID；Finding 的 Evidence 引用还存 SHA-256 摘要与字节长度。两者都不读取或写入 Evidence 原件字节；不核验外部引用、不抑制重复项、不生成报告，也不接入缺陷确认门禁。
- 存储不提供二进制 Evidence Blob（证据原件）字段或单独的原件服务。直接的 Python `bytes`（字节序列）无法通过 JSON（数据交换格式）规范化。叙述字段接受自由文本，存储不会识别其中的原始或 Base64（文本编码格式）证据内容；调用方必须避免把这类内容写入自由文本。

## REFACTOR（整理实现）：收敛校验边界

- Schema 校验和附加校验器只接收序列化后的独立副本；内部交叉字段校验与持久化使用未被调用方修改的数据。
- 版本校验共用同一套规范 JSON、完整历史、文件权限和目录项检查；已有配置根目录必须已私有且不会被修权限，子级记录目录可在安全检查后修复；Candidate 的跨版本审核事件按其引用版本校验证据。Candidate/Finding 的状态及追加规则分别放在具体存储类中。
- README、契约说明、Schema 清单和测试说明已同步新增存储能力与明确限制；中文专业词汇在首次出现时附英文和中文解释。

## VERIFY（最终验证）：命令与结果

| 检查 | 结果 | 证据范围 |
|---|---|---|
| 全量单元测试 | PASS（通过，615/615） | Python 3.12；`PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=/private/tmp/bugmaster-w7-finding-metadata-final.coverage /opt/homebrew/bin/python3.12 -m coverage run --branch --source=bugmaster_core,scripts -m unittest discover -s tests/unit` |
| 全量契约测试 | PASS（通过，129/129） | Python 3.12 + 固定 `jsonschema[format-nongpl]==4.26.0`；`PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -m unittest discover -s tests/contracts` |
| 安全测试 | PASS（通过，1/1） | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 -m unittest discover -s tests/security`；不代替代码扫描或独立真人审查 |
| 行/分支覆盖率 | PASS（通过，100% / 100%） | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps /opt/homebrew/bin/python3.12 -m coverage report --data-file /private/tmp/bugmaster-w7-finding-metadata-final.coverage --skip-covered`；`bugmaster_core` 与 `scripts`：3057/3057 语句、1096/1096 分支 |
| Candidate/Finding 存储与评估历史 | PASS（通过，83 + 59 项单测） | 存储覆盖状态限制、追加版本、身份/事件/证据绑定、Finding Evidence ID 唯一、整数归一化、摘要损坏、权限与软硬链接拒绝、孤立版本 fail-closed、根目录不修复及历史审核引用版本校验 |
| 品牌、目录和基准清单结构 | PASS（通过） | `scripts/check_branding.py`、`scripts/validate_catalog.py`、`scripts/validate_benchmark.py`；基准场景只验证清单结构，未执行 |
| 差异空白检查 | PASS（通过） | `git diff --check` |
| Codex Q15 代码扫描 | PASS（通过） | `codex review --uncommitted`；Codex CLI 0.171.0 对与实现提交相同的生产代码和测试差异扫描，未发现可执行缺陷；扫描复核单元测试 615/615、契约测试 129/129、安全测试 1/1，行/分支覆盖率均为 100%。后续只修改了验证记录文档 |
| Codex 安全审查 | PASS（通过） | 聚焦复核未发现新阻断项；尾换行 ID、helper（辅助函数）与 Schema（数据结构规则）不一致及重复目标格式问题均已修复。摘要链不防止根目录所有者整体篡改或回滚；Windows 未验证，扩展 ACL（访问控制列表）直接检查限于 macOS |
| 独立真人安全审查 | 未进行 | 当前批准范围不认证来源/审核人、不修改 R2/R3 动作授权、不接入 Confirmed Gate；如后续跨入这些边界，先单独与项目所有者讨论真人审查范围 |
| GitHub PR / Actions | 待创建 | 本实现提交及其验证记录已在 W7 功能分支；该分支相对 `main` 领先 7 个提交、落后 0 个提交，当前没有开放 PR。审查完成后创建单个 PR，再记录远端 Actions（自动化检查）结果；不自动合并 |
| Release（正式发布）质量门禁 | NO-GO（不满足发布门槛，预期） | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-w7-finding-metadata-final.json`；exit 1 的原因是功能义务清单未冻结、真实功能覆盖未超过 60%，并缺少核心功能三类场景证据。本切片不提供真实业务覆盖、50 个 Benchmark（基准评测）场景执行、双宿主验证或正式发布所需双人授权 |

## 后续顺序

1. 在当前 W7 功能分支创建单个 PR，确认远端 CI 后交项目所有者最终确认并手动合并。
2. 在本 PR 合并前，不启动下一个功能 PR；浏览器探索工具仍按 W5/W7/W9 依赖顺序另行推进。
3. 若后续需要来源认证、审核人身份认证、R2/R3 授权或 Confirmed Gate 集成，先把真人审查边界单独提出来与项目所有者讨论。
