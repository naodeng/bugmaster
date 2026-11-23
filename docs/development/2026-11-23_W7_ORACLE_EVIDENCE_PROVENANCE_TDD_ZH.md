# W7 Oracle（预期行为判定依据）与 Evidence（证据）本地绑定校验 TDD（测试驱动开发）记录

**日期：** 2026-11-23
**工作流：** W1 / W7；基线为个人仓库 PR #13 合并提交 `5c640a21cb97b20229bce85ee33f4c4f4f0af836`。Q1–Q17 冻结决定未修改。
**术语：** `Oracle`（预期行为判定依据）；`Evidence`（证据）；`Action Journal`（动作日志）；`canonical JSON`（按本项目规则生成的规范 JSON）；`fail-closed`（失败时保持阻断）；`Q15`（每个 PR 的代码扫描门禁，适用时增加安全扫描）。

## 目标与边界

实现 Oracle/Evidence v1 数据结构规则和一个本地绑定校验器：重新计算调用方提供的来源字节与证据制品摘要，绑定精确 Oracle ID、版本和记录摘要，并要求本地 Action Journal 中存在相同的结果事件。

通过校验只说明给定字节的内容摘要一致、Oracle 版本引用一致、本地日志链及结果事件引用匹配。它不认证 Oracle 作者、来源文件、证据采集过程、Journal 事件来源或外部事实；不从引用路径读取制品，不持久化 Finding，也不接入自动 `rejected`（拒绝）或 `Confirmed Gate`（缺陷确认门禁）。成功结果仍为 `source_authenticity="unverified"`（来源真实性未验证）和 `finding_gate="blocked"`（缺陷确认门禁阻断）。

`canonical_record_sha256()` 将记录编码为排序键、紧凑分隔符、UTF-8、非 ASCII 字符原样输出且拒绝非有限数值的 JSON，再计算 SHA-256（内容摘要）。这是本项目本地稳定引用规则，不宣称实现通用跨语言签名标准。

## RED（先失败）：确认缺失行为

- 新增 `test_provenance.py` 后、生产模块创建前运行 `python3.12 -m unittest discover -s tests/unit -p 'test_provenance.py'`，因 `bugmaster_core.provenance` 尚不存在而以 `ModuleNotFoundError` 失败。
- `ActionJournal.recorded_outcome()` 实现前运行 `python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py'`，新增的两个结果读取用例以 `AttributeError` 失败。
- 安全复核指出自定义 `float`（浮点数）子类能伪装整数。实现精确内建类型校验和回归测试；最终测试覆盖该子类对 `is_integer()` 与 `__int__()` 的覆写。
- 自定义 `str` 子类和日志实例覆盖问题也用新增用例复现：`-k custom_string_subclass` 首次运行 3 项、2 项失败；`-k instance_override` 运行 1 项、1 项失败；后续发现 `_load_current` 覆盖仍能伪造结果，`-k override_of_journal_loader` 运行 1 项、1 项失败。第一轮 `schemaVersion` 子类用例未复现，因为当时只覆写 `__eq__`；后来补强为同时覆写 `__ne__`，并由最终精确 `str` 类型校验拒绝。该补强用例没有另行保留修复前的失败输出。
- Schema（数据结构规则）契约测试最初因缺少 `jsonschema` 无法导入，属于依赖阻塞，不作为行为 RED。固定版测试依赖后来安装至 `/private/tmp/bugmaster-provenance-test-deps`，未改项目或系统 Python。

## GREEN（修复后通过）：实现并通过回归

- 新增 `schemas/oracle.schema.json`、`schemas/evidence.schema.json` 和 `bugmaster_core.provenance`。运行时只接受字段精确匹配、内建 JSON 数据类型、有限枚举值、有效时间戳、摘要与字节长度匹配的记录。
- `ActionJournal.recorded_outcome(action_id)` 只读读取完整校验后的本地日志链并返回结果事件绑定；文档与返回类型明确不认证来源或外部结果。
- `verify_provenance()` 使用 `ActionJournal` 类直接调用结果读取方法，并拒绝实例覆盖结果读取、日志加载、父目录打开、日志文件验证或路径复核方法，以避免可变实例绕过日志链检查。
- 本地定向测试：`test_provenance.py` **33/33 PASS**；`test_action_journal.py` **83/83 PASS**。
- 完整单元测试：Python 3.12，**523/523 PASS**。完整契约测试：**105/105 PASS**。安全测试：**1/1 PASS**。
- 行/分支覆盖：`bugmaster_core` 与 `scripts` 共 **2535/2535 语句、930/930 分支**，均为 100%。新 `provenance.py` 为 **144/144 语句、48/48 分支**。覆盖率由以下命令产生：

  ```sh
  PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps \
  COVERAGE_FILE=/private/tmp/bugmaster-w7-final.coverage \
  python3.12 -m coverage run --branch --source=bugmaster_core,scripts \
    -m unittest discover -s tests/unit
  ```

- 两份 Schema 均可由 `python3.12 -m json.tool` 解析。额外将 Schema 中显式列出的空白字符规则与 Python `str.isspace()` 对全部 Unicode（统一字符编码）码点逐一比较，结果一致；Schema 契约测试还覆盖 U+0085 仅空白输入。
- `check_branding.py`、`validate_catalog.py`、`validate_benchmark.py` 和 `git diff --check` 均 PASS。Benchmark 只校验清单结构，正式场景仍未执行。

## REFACTOR（整理实现）：收敛验证边界

- 将文本、整数、摘要、时间戳和字节输入校验留在各记录边界；之后只用已校验的值进行交叉绑定。
- 结果读取只返回动作 ID、终态、结果引用、序号与事件摘要，不扩展为持久化、适配器或授权层。
- 将 Unicode 空白集合明确写入 Schema，避免 Python 与 Schema 正则引擎对 `\S` 的解释差异。

## VERIFY（最终验证）：验证与审查结果

| 检查 | 结果 | 证据范围 |
|---|---|---|
| 单元测试 | PASS（通过，523/523） | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps python3.12 -m unittest discover -s tests/unit` |
| 契约测试 | PASS（通过，105/105） | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps python3.12 -m unittest discover -s tests/contracts` |
| 安全测试 | PASS（通过，1/1） | `PYTHONPATH=/private/tmp/bugmaster-provenance-test-deps python3.12 -m unittest discover -s tests/security` |
| 行/分支覆盖 | PASS（通过，100% / 100%） | `coverage report -m`：2535/2535 语句、930/930 分支；当前覆盖 JSON 在 `/private/tmp/bugmaster-w7-final-coverage.json` |
| 发布质量门禁 | NO-GO（不满足发布门槛，预期） | 功能清单未冻结、业务覆盖未超过 60%、核心功能缺少成功/失败/边界执行证据；本切片不改变这些发布条件 |
| JSON Schema（JSON 数据结构规则）语法与空白规则 | PASS（通过） | 两份 JSON 可解析；显式空白规则逐码点匹配 Python `isspace()`；完整 Draft 2020-12（JSON Schema 版本草案）契约测试 105/105 通过 |
| Codex 代码扫描 | PASS（通过） | `codex review --uncommitted`：没有发现可执行缺陷；扫描同时复跑了 523 项单测、105 项契约测试和 1 项安全测试 |
| 安全复核 | PASS（静态 AI 复核） | 复核确认本轮修复覆盖精确数值/字符串类型和 Journal 实例方法覆盖；复核者未运行测试，测试结果由上述命令单独证明 |
| 独立真人安全复核 | 未进行 | 当前代码只做数据格式与本地完整性绑定，来源真实性未验证且缺陷确认门禁仍阻断；PR #13 的 Q15 决定不要求独立真人签署此类扫描。未来若实现来源认证、签名身份、授权或接入确认门禁，先与项目所有者单独讨论所需真人复核边界 |
| GitHub PR / CI | 尚未建立 | 当前分支以 PR #13 合并提交为基线；未推送本轮代码，因此没有本轮远端 CI 结果 |

## 后续顺序

1. 将已完成的 Codex 代码扫描和静态 AI 安全复核结果整理进 PR，由项目所有者确认并手动合并；本轮不自动合并。本切片未修改 R2/R3 动作授权，按项目规则无需另做对应的专项安全扫描。
2. 合并后再设计可信来源适配器、持久化和 Candidate（候选记录）/Finding（缺陷记录）集成。凡涉及来源认证、签名身份、动作授权或缺陷确认门禁的方案，先与项目所有者讨论是否需要独立真人安全复核，再开始实现。
3. 浏览器探索运行时继续按 W5/W7/W9 的依赖顺序推进；本轮没有引入浏览器工具或真实 API 执行。
