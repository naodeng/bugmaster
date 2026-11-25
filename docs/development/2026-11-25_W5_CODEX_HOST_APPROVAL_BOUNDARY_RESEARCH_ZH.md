# W5-01 Codex 宿主审批信任边界调研

- **日期：** 2026-11-25
- **范围：** 仅依据 OpenAI 官方 Codex 文档、OpenAI 官方 `openai/codex` 源码和协议定义，判断 Codex 宿主（Host）的 MCP（模型上下文协议）审批能否作为 BugMaster 可验证的动作级授权证明。
- **版本说明：** 在线源码查阅截至本日的 `openai/codex` `main` 分支；该分支会变化。已核对本机 `codex-cli 0.171.0` 的 App Server（应用服务器）协议；Codex Desktop（桌面端）当前安装版本仍仅依据更新器显示记录，未核实其内置协议及 UI（用户界面）实现。尝试只读读取 `/Applications/ChatGPT.app` 被 macOS 沙箱拒绝；一次受控只读执行仍返回 `Permission denied`（权限拒绝），因此本机 Desktop 内置 Schema（数据结构规则）未能验证。未更改或更新应用。App Server 文档说明可由具体二进制生成与该版本匹配的协议 Schema；下文的 `userVerification` 明确属于实验 API（编程接口）。[App Server 协议说明](https://developers.openai.com/codex/app-server/) [App Server 源码说明](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)

## 结论

普通 Codex 宿主审批没有向任意 MCP 工具提供可验证的动作级授权凭证。实验性的设备用户验证接口（`userVerification`）能对调用方提供的挑战数据（challenge，签名挑战）签名，但从官方 `main` 源码可推断，这条路由仅接受特定的宿主自有 Apps MCP 服务（宿主集成的应用服务器）。普通第三方 MCP 插件即使运行在 Desktop 本机，也不满足服务来源检查，按该源码会收到取消结果。该结论尚未在当前安装的 Desktop 版本上实测，因此 `userVerification` 目前不能作为 BugMaster 可直接接入的授权来源。未来若取得宿主集成通道，或另行设计 BugMaster 自有签名服务，再评估凭证注册、动作绑定和后端验签；普通审批点击仍不能作为动作授权证明。[官方 App Server 实验 API 说明](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#user-verification-experimental) [官方路由源码](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/user_verification_elicitation.rs) [官方 MCP 服务注册源码](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/catalog.rs)

## 核实结果

- **普通 MCP 审批是宿主调用门禁。** Codex 在调用 MCP 工具前可按宿主配置检查审批；获准后再由宿主向 MCP 服务器发起 `tools/call`（工具调用请求）。官方实现先运行 `maybe_request_mcp_tool_approval`，之后才进入实际工具调用流程。MCP 调用历史结构记录调用 ID、服务器、工具、状态、参数和结果等，没有批准人、审批来源、审批决定或签名字段。因此，服务器收到调用只说明宿主发起了调用，不能证明服务器验证过本次 Action 的真人授权。[MCP 调用实现](https://github.com/openai/codex/blob/main/codex-rs/core/src/mcp_tool_call.rs) [MCP 调用数据结构](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/items.rs)
- **普通审批不保证每次都有真人确认。** MCP 工具可配置为自动放行、提示确认、仅写入操作时确认或始终批准；审核者也可配置为用户或自动审核。因此，工具调用成功或曾显示审批提示，均不能单独证明本次动作经过一次新的真人确认。[Codex 配置参考](https://developers.openai.com/codex/config-reference/)
- **`userVerification` 是单独的实验性签名能力。** `userVerification/enroll` 可返回凭证标识、公钥和算法；`userVerification/verify` 接收挑战数据、标题和说明，返回凭证标识、签名和可选的生物识别方式。当前源码定义使用 P-256 椭圆曲线数字签名（ECDSA）和 SHA-256 摘要算法，对解码后的 1–4096 字节挑战数据签名。公钥采用 SPKI（主体公钥信息）封装，并以 DER（区分编码规则）格式编码后进行无填充 Base64URL（URL 安全的 Base64 编码）编码；挑战数据与 DER 签名也采用无填充 Base64URL 编码。[官方 App Server 实验 API 说明](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#user-verification-experimental)
- **此能力有明确适用范围。** 它需要开启实验接口、受支持的本机生物识别设备和账户；App Server 只对本机 TUI（终端用户界面）及 Codex Desktop（桌面端）宿主启用协议能力。官方插件文档支持 Desktop 本机 stdio（标准输入输出）MCP 插件，但本机部署不会自动授予宿主自有 Apps 通道。根据当前源码，`is_host_owned_apps(...)` 只接受 `codex_apps` 服务名、本机环境，以及 `Compatibility`（兼容注册）或 `Extension`（宿主扩展）中标记 `host_owned_apps: true` 的来源；普通 `Plugin`（插件注册）、`SelectedPlugin`（当前任务选用的插件注册）和用户配置来源不满足条件。可信 UI Host（可信用户界面宿主）负责将凭证注册到后端并验证证明；本机验证成功本身不代表后端已经登记该凭证。BugMaster 当前仓库没有 Codex App Server 连接、凭证注册或验签组件。[App Server 实验 API 说明](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#user-verification-experimental) [服务注册来源源码](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/catalog.rs) [本机插件部署说明](https://developers.openai.com/plugins/deploy/desktop-only)
- **路由限制已由官方源码确认。** App Server 的初始化代码只会为受支持的本机 Desktop/TUI 宿主开启 `userVerification` 扩展；用户验证路由随后检查注册的 MCP 服务来源。来源不符合 `is_host_owned_apps(...)` 条件、事件通道缺失或 MCP 服务审批上下文缺失时，路由直接返回 Cancel（取消）与 `approvalUnavailable`（审批不可用），不会显示可验证的批准结果。该路由源码注释还明确说明设备验证绕开自动审批策略，因此不能把它当成普通 MCP 提示的加强版，也不能将其暴露给任意第三方插件。[初始化能力启用源码](https://github.com/openai/codex/blob/main/codex-rs/app-server/src/request_processors/initialize_processor.rs) [用户验证路由源码](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/user_verification_elicitation.rs)
- **对 `userVerification` 的实现推断。** 如果 BugMaster 未来以宿主自有 Apps MCP 服务获得该通道，它可成为动作摘要签名的候选原语，但仍不是现成的 BugMaster Approval（审批记录）。挑战数据至少需要绑定规范化后的 Scope（授权范围）、Action（动作）、目标、环境、身份、摘要、风险、次数、有效期和一次性随机数；授权适配器还要验证已登记公钥、签名和未消费状态。Codex 提供的标题和说明由调用方传入，不能替代对实际签名挑战内容的核对。
- **真人复核边界。** 一次本机设备验证只证明对应凭证完成了本次确认流程，不能证明有两名不同的人分别担任 RI（复核人）和 IRR（独立复核人），也不能替代 Q16（正式发布双人授权）或项目所有者的代码/安全审查。

## 本机只读探测

- `codex --version` 返回 `codex-cli 0.171.0`。
- Codex Desktop 更新器报告当前安装版本为 `26.1120.41243`（生产版），并显示 `26.1120.50957` 可用；没有安装更新。CLI 与 Desktop 版本号不同，不能据 CLI 协议推断当前 Desktop 的宿主能力。
- 该 CLI 生成的实验协议 Schema 包含 `userVerification/status`、`enroll`、`delete`、`verify` 和 `cancel` 五个接口；本机 App Server 的只读 `status` 请求返回 `credentialMissing`，未发现已登记的设备凭证。
- 从独立 CLI 客户端调用 `userVerification/enroll` 返回 `Local user verification is unavailable`（本机用户验证当前不可用），没有返回凭证或公钥；后续只读状态仍为 `credentialMissing`（缺少凭证），不可用说明为 `no user-verification credential has been created`（尚未创建用户验证凭证），确认没有留下测试凭证。该结果说明这条独立 CLI 客户端路径不可用，不代表 Codex Desktop 的宿主自有插件集成也不可用。
- **未运行：** 未触发生物识别、未完成签名或本地验签，也未验证当前 Codex Desktop 版本是否支持该协议及 UI 流程。当前 `main` 源码显示普通第三方 MCP 插件不会通过用户验证路由；此点未在安装版本实测。尚未取得或验证任何 BugMaster 可用的宿主自有 Apps 集成通道。CLI 接口定义存在和 `credentialMissing` 都不能证明桌面端集成可用。

## W5-01 建议

**暂不接入 Codex 宿主（Host）审批。** 官方支持 Desktop 本机 stdio MCP 插件，但当前 `main` 用户验证路由对第三方插件 fail-closed（失败时拒绝），仅接受宿主自有 Apps（宿主集成应用）服务；该源码结论尚未在当前安装版实测。除非先取得并验证 BugMaster 的宿主集成通道，否则不得实现可放行的 Host Approval（宿主审批）适配，`can_dispatch()` 继续对所有风险等级返回拒绝。下一步由项目所有者选择：查证 BugMaster 是否具备接入宿主自有 Apps 服务的现实路径；维持拒绝并暂缓 W5-01 派发能力；或另开设计讨论 BugMaster 自有签名服务及其凭证生命周期。独立真人安全审查的边界不由该签名能力解决，仍须单独讨论；任何设计或验证均不得声称已完成双人复核或 Q16（正式发布双人授权）。[Codex App Server](https://developers.openai.com/codex/app-server/) [Desktop 本机插件文档](https://developers.openai.com/plugins/deploy/desktop-only) [App Server 实验 API 说明](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#user-verification-experimental) [用户验证路由源码](https://github.com/openai/codex/blob/main/codex-rs/codex-mcp/src/user_verification_elicitation.rs)
