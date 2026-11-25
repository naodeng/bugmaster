# W1-02 Scope、Action 与 Approval 契约绑定校验测试驱动开发（TDD）记录

- **日期：** 2026-11-25
- **工作流 / 功能义务：** W1-02 / `F-AUTH`
- **状态：** Ponytail（精简代码审查）及三轮 Codex 安全复核发现四项输入边界问题，均已修复并补充回归测试。最新修复后的全量测试、覆盖率与质量检查通过；最终代码复核与安全复扫通过。安全复核发现的设计文档问题计数歧义已更正。已提交为 `069b1a7d30cf8cc461dbeee988758c5b1991ed1f`，PR #16 已开放，等待项目所有者审阅并手动合并。
- **基线：** `develop` 提交 `4e82d7f`；PR #15 已合并到 `main` 的 `d578c61`。
- **范围：** 结构与跨记录一致性校验。结果不是授权、来源真实性或派发证明。

## RED（先失败）

先新增契约绑定单测与 Approval（审批）方法格式契约测试，验证正向绑定、R2 审批字段绑定、缺失/重复引用、Scope（授权范围）目标状态、风险清单、时间区间、无效结构和方法兼容性。

在生产实现前，定向测试得到以下行为失败证据：

- Approval Schema（审批数据结构规则）拒绝与 Action（动作）Schema 相同的合法方法 `M-SEARCH`、`GET2` 和 `POST_V2`，因为原 Approval 正则只接受大写字母。
- `tests/unit/test_contract_binding.py` 因 `bugmaster_core.contract_binding` 模块尚未实现而导入失败。
- 测试环境最初缺少 `jsonschema`；这属于依赖环境问题，不计作行为 RED（先失败）证据。改用仓库固定依赖后复现上述两项真实失败。
- 最终 Codex 安全复核发现 SHA-256 正则的 `$` 结束锚点会接受末尾换行。先为 Action 的 `intentDigest` / `parameterDigest` 和 Approval 的 `actionDigest` / `parameterDigest` 增加负例；两个定向测试均按预期失败，四个字段都没有拒绝末尾 LF。

## GREEN（最小实现）

- 新增 `bugmaster_core.contract_binding.validate_contract_bindings(scope, action, approvals)`。
- 使用 Draft 2020-12（JSON Schema 2020-12 版本）校验器和 `FormatChecker`（格式检查器）验证 Scope、Action、Approval；校验失败时在任何跨记录读取前返回 `schema-invalid`。
- 在 Action 和 Approval 的 SHA-256 摘要 Schema 上显式拒绝 CR、LF、U+2028、U+2029；由 RED（先失败）用例确认四个摘要字段均会拒绝这些行终止符。
- 比较 Action 与 Scope 的标识、修订、环境、唯一目标、目标状态和显式风险清单；解析并校验每个 Scope 目标的审批引用。
- 按 R2 状态要求核对动作审批及其摘要、方法、参数摘要、风险和计数；可选引用同样需要解析与绑定，但不因其状态改变 Action 状态。
- 以 RFC 3339 `date-time`（带时区日期时间）严格解析 Action 的 `createdAt` 和 Approval 的 `issuedAt` / `expiresAt`；检查 `expiresAt` 晚于 `issuedAt`。保留任意精度的小数秒，并通过本地时间整数秒减时区偏移比较，避免微秒截断和 Python 年份边界溢出。
- 将 Approval `method` 模式对齐到 Action 的 `^[A-Z][A-Z0-9_-]*$`；Action 和 Approval 的 SHA-256 摘要 Schema 均显式拒绝回车、换行及 U+2028/U+2029 行分隔符。
- 返回只包含 `bindingConsistent` 和排序去重后的 `reasonCodes`；不修改输入，不添加可信、授权或派发字段。`can_dispatch()` 与 `action_allowed()` 未改动。

## REFACTOR（收敛与边界修正）

Codex 首轮复核发现两个时间处理缺陷，均已修复并新增回归用例：

1. `datetime.fromisoformat()` 会把超过 6 位的小数秒截断，导致很短但合法的审批区间被误判为无效。改为整数秒与 `Decimal`（十进制精确数）小数部分分开比较。
2. 将合法的年份边界时间换算成 UTC `datetime` 可能越过 Python 支持的年份范围并抛出异常。改为把本地日期转整数秒，再减去带符号时区偏移；新增年份 0001 和 9999 两端的回归用例。
3. `^[A-Z][A-Z0-9_-]*$` 的结束锚点可能让正则校验接受末尾换行，导致 Action 与 Approval 同时携带 `POST\n` 时被报告为绑定一致。Action / Approval Schema 均新增对回车、换行及 U+2028/U+2029 行分隔符的排除条件，契约测试与绑定测试先复现失败，修复后通过。
4. Codex 安全复核发现 `FormatChecker` 会接受末尾换行的 Approval 时间，但解析器的 `fullmatch()` 会拒绝同一字符串并触发未分类异常。新增 `issuedAt`、`expiresAt` 回归用例；解析器对 Schema 检查器与严格时间语法不一致的输入返回 `schema-invalid`。
5. 最后一轮 Codex 安全复核发现同类格式差异也适用于 Action 的 `createdAt`。新增末尾换行回归用例，并在 Action Schema 校验后执行相同的严格 RFC 3339 解析；该字段格式不一致时返回 `schema-invalid`。
6. 随后的 Codex 安全复核发现 SHA-256 模式的 `$` 结束锚点也会接受末尾换行。Action 与 Approval 摘要 Schema 新增行终止符排除条件；四个摘要字段均新增负例，覆盖 CR、LF、U+2028 和 U+2029。

同时补充原因码中文含义、开发进度、英文和中文 README 的能力边界说明。

## VERIFY（验证）

执行环境为 macOS、Python 3.12.16；使用仓库固定的 `jsonschema[format-nongpl]==4.26.0` 与 `coverage.py==7.13.3`，依赖目录为 `/private/tmp/bugmaster-provenance-test-deps`。覆盖率数据存于临时目录 `/private/var/folders/y4/8p8hgnhj3ps48wcxyc3n_nyw0000gn/T/bugmaster-w1-review.sZqshp/final-coverage`，不在仓库中。

| 检查 | 结果 |
|---|---|
| W1-02 绑定单元测试 | PASS（通过，24/24，含 Approval 时间和 Action.createdAt 末尾换行负例） |
| Action.createdAt 末尾换行回归测试 RED → GREEN | PASS（先因 `bindingConsistent=true` 失败，添加严格解析后通过） |
| Action Schema 定向契约测试 | PASS（通过，13/13；摘要负例覆盖 CR、LF、U+2028、U+2029） |
| Approval Schema 定向契约测试 | PASS（通过，10/10；摘要负例覆盖 CR、LF、U+2028、U+2029） |
| 完整单元测试 | PASS（通过，639/639） |
| 完整契约测试 | PASS（通过，134/134） |
| 安全测试 | PASS（通过，1/1） |
| `bugmaster_core` 与 `scripts` 行覆盖 / 分支覆盖 | PASS（通过，3159/3159 条语句、1152/1152 条分支，均为 100%）；覆盖报告 `/private/tmp/bugmaster-w1-02-final-coverage.json` |
| 品牌与 Skill 命名扫描 | PASS（通过） |
| Catalog（目录）/Registry（注册表）扫描 | PASS（通过） |
| Benchmark（基准评测）清单结构扫描 | PASS（通过）；场景未执行 |
| `quality_gate.py --mode release` | NO-GO（暂不发布）：功能清单未冻结、功能执行证据未超过 60%、核心功能缺少真实 Happy（成功）/Negative（失败）/Edge（边界）证据 |
| `git diff --check` | PASS（通过） |

Codex 代码复核未发现可执行缺陷。Ponytail 复核修复了方法名末尾行终止符问题；三轮 Codex 安全复核先后发现 Approval 时间、Action `createdAt` 和 SHA-256 摘要末尾换行问题，均新增回归测试并修复。最终安全复核未发现代码问题，发现设计文档问题计数表述不清，已改为分项列出四项修复。针对 Approval / Action 审批是否需要绑定 `surface` 的潜在区别，当前没有改动契约，将作为未来可信网关设计事项保留。安全复核是 AI 源码复核，不是独立真人审查，也不等于完整代码库渗透测试。

## 安全边界与未完成事项

- `bindingConsistent=true` 只表示记录结构与彼此字段一致；调用方不得把它当作 `trusted`（可信）、`authorized`（已授权）或 `dispatchAllowed`（允许派发）。
- 不检查审批相对于当前时间是否仍有效，不认证审批人或来源事件，不验证签名、撤销或宿主执行控制。
- `can_dispatch()` 对 R0、R1、R2、R3 继续全风险拒绝。浏览器探索工具、可信授权宿主和真人审核规则未在本切片接入。
- Approval 目前以 `targetRef` 绑定目标，不单独绑定 `surface`。若后续可信网关需要区分同一 `targetRef` 下不同 `surface` 的审批，须先讨论是否扩充审批契约或限制该类重复目标；本切片不授予执行权。
- 最终合并前由项目所有者确认；未来若需要独立真人安全复核或真实宿主授权，按既定原则单独讨论。

## 复核与交接

本记录针对基线 `4e82d7f` 到提交 `069b1a7d30cf8cc461dbeee988758c5b1991ed1f` 的 W1-02 差异。个人仓库 PR [#16](https://github.com/naodeng/bugmaster/pull/16) 已从 `develop` 指向 `main`，等待项目所有者审阅并手动合并；对应 GitHub Actions（自动化检查）状态以 PR 页面为准。该 PR 合并前暂停后续开发；合并后再进入浏览器工具与真人审核边界文档细化。
