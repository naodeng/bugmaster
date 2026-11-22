# BugMaster 真人审核边界与浏览器探索工具调研

**复核日期：** 2026-11-22
**状态：** 调研与建议；不修改冻结的 Q1–Q17，也不表示浏览器工具已接入 BugMaster。

## 1. 当前项目边界

BugMaster 的现行目标是 API-first + Browser Basic，并以外部 Agent Host 提供工具；Q1 明确不建设独立 Agent Runtime。当前仓库已有 Scope、Action、Journal、Session 等部分契约，但没有可运行的 Browser Adapter、Candidate/Finding Store 或完整的签署 Review Store。浏览器产品化集成与本地探索验证不能混为一项。

真人审核也有不同含义：Finding 复核、目标系统的动作授权、代码变更审核和公开发行批准不是同一种门禁。把它们都写成“必须找真人 Review”，会让开发流程和产品探索流程都显得比实际风险更重。

## 2. 哪些地方需要真人参与

| 场景 | 目前基线 | 审查结论 | 建议边界 |
|---|---|---|---|
| 候选/Finding 判定 | Q7：满足有效 Oracle、E3+ 证据等条件；仅在策略要求时人工复核 | 不需要每个候选都等真人签字。候选可自动形成，确定性门禁可以筛选；Oracle 模糊、证据冲突或策略要求时转人工 Review | 保持条件式 Review。人工接收、拒绝、补证反馈都绑定 Candidate revision 与 Evidence；没有已验证的宿主身份事件时，不能把普通记录当成签署批准 |
| 对目标系统执行测试动作 | Q3：R0 默认只读；R2 需要动作级强制授权；R3 默认禁止 | 这是目标系统所有者的操作授权，不是代码 Reviewer。读操作不应逐次阻塞；会改变目标状态的操作需要实际授权和执行边界 | 保留动作级授权；未授权写操作保持阻断。不要要求真人查看每个只读页面或每条 GET 请求 |
| PR/代码变更 | Q15：R0/R1 常规维护评审；R2 需要作者之外的真人 QR；R3 需要独立真人 SR | R3 的独立安全审查有明确收益。Q15 任务清单把 W0–W4、W8–W10 中多项一般工程任务列为 R2/QR；若按每项任务或 PR 均强制外部 Review，单维护者项目会形成常态阻塞。这里是对清单覆盖面的审查，不代表已查明远端保护规则已启用 | 建议重新细分 R2：只有影响权限、证据真实性、Oracle/Finding 确认、用户数据持久化/恢复、敏感信息、破坏性行为或兼容契约的变更要求独立 QR；普通局部功能、文档和纯内部实现走自动化门禁、测试与维护者审查。此项会改变冻结的 Q15，需另行批准，当前不直接改规则 |
| 安全敏感代码 | Q15：R3 需要独立 SR | 有必要。Authorization、Scope、凭据/敏感数据、证据来源、未知副作用恢复和发布权限一旦出错，模型自审和普通 CI 都不足以承担独立责任 | 对作者以外的人类 SR 保持强制；SR 不能由另一个模型代签 |
| 公开发布 | Q16：RI 与 IRR 是两名不同真人，批准绑定同一个固定 Manifest Digest | 有必要，但它是发布授权，不是每个 PR 的额外签字。当前 ADR 设计的是“发起人 + 一名不同批准人”，不是两名 Reviewer 投票 | 仅在公开发布时执行。没有第二位授权人时可以继续本地开发和候选构建，公开发布维持 No-Go |

### 结论

需要重新审视的是 **Q15 对 R2 的覆盖面和分级落地方式**，不是把真人审核全部删除。Q7 的 Candidate/Finding Review 已是条件式；Q3 的用户动作授权属于目标安全控制；Q16 是公开发行责任。仓库的 `Q15_GITHUB_TASK_BACKLOG.csv` 将多个一般功能工作项直接标成 R2 并要求 QR，这会把策略的人工成本扩散到整个开发面；若它被逐项映射成 PR 必须审批，单维护者就会被流程阻塞。正式更改前应以实际改动影响为准，在新 ADR 中分开定义“PR 风险复核”“目标动作批准”“Finding 复核”和“发行授权”，同时避免因“功能 PR”这个标签自动升级风险。

当前仓库文档把 Q15/Q16 标为已接受设计，但 GitHub 分支保护、真实 Reviewer 身份验证和发布授权环境仍未由这份本地文档证明已经配置。流程文件不能代替实际强制机制。

## 3. 可用于探索性测试的浏览器工具

| 工具 | 主要用途 | 适合 BugMaster 的位置 | 主要限制与安全点 |
|---|---|---|---|
| Codex Computer Use（CUA） | 读取桌面屏幕并用鼠标/键盘操作当前界面，可直接观察视觉布局、Canvas、弹窗和没有稳定 DOM 选择器的控件 | Codex Host 内做视觉探索、复核 DOM 工具遗漏的问题，或在隔离 Demo 上进行人工监督的探索性测试 | 屏幕交互能力绑定 Codex Host 和当前会话，不是 BugMaster 可移植 Runtime，也不提供 Playwright DOM/Network 语义。点击、输入和确认仍可能触发真实副作用；只能在隔离环境和已授权 Scope 中使用，截图还需按敏感证据处理 |
| ego-browser（本机 ego-lite Skill） | 通过 Skill 自带的浏览器 API 执行其支持的导航、页面观察和交互流程 | Codex 本机可复用的浏览器探索步骤；可与 Computer Use 互补：前者走 Skill API，后者直接操作屏幕 | 依赖本机 Skill 与当前 Host，不能当作 BugMaster 内置 Browser Adapter 或 Playwright MCP；具体动作与证据能力以当前 Skill 实际支持范围为准 |
| Vercel `agent-browser` CLI/MCP + 配套 Skill | 本地 Chrome for Testing、无障碍树快照、元素引用、交互、截图、网络、录制/调试 | 本地探索的候选执行器；CLI 与 MCP 可供不同 Agent Host 调用，Skill 文档跟随工具版本 | 安全选项默认关闭；域名白名单、动作策略和确认门禁要显式配置。白名单不是 OS 防火墙；启用白名单时不能依赖已有 Chrome Profile/CDP attach。需固定版本并做本项目测试 |
| Microsoft Playwright CLI + Skill | 通过短 CLI 命令探索页面，Skill 提供命令说明；可保存截图、会话和 Trace | Codex/Claude 等能调用 shell 的开发环境；减少 MCP 工具定义和快照上下文负担 | 属于外部 CLI/Skill，不应包装成 BugMaster 的第 12 个产品 Skill。`run-code` 等能力必须按信任边界限制；Shell 访问范围不能代替 BugMaster 的动作授权 |
| Microsoft Playwright MCP | MCP 浏览器工具，提供导航、快照、交互、截图、Network/Mock、Storage 等 | Host 已支持 MCP 时进行工具集成试验；可以启动隔离 Session | 官方明确说明 MCP Server 不是安全边界，并包含可执行任意 Playwright 代码的工具。只有在 Host 能禁用该工具、或代码运行处于严格隔离环境时，才适合进入安全敏感探索路径 |
| Chrome DevTools MCP | Chrome 页面、Console、Network、Performance、Trace 与调试能力 | 诊断候选缺陷、采集浏览器层辅助证据；适合开发/调查工具 | 以 Chrome 为主，不是跨引擎测试方案。高权限 JavaScript、文件、用户配置和网络能力要在可信配置中限制；配置文件不能让被测 Agent 修改 |
| Stagehand SDK/MCP | 本地 Chrome 或 Browserbase；`observe`、`act`、`extract` 等模型辅助的页面理解与动作 | DOM 复杂、页面结构多变时的可选探索能力；也可用于独立评估智能浏览步骤 | 模型推理带来成本和非确定性，动作结果仍须用页面/Network/后端状态校验。可选 Browserbase 云会把浏览器会话交给外部服务；当前无需为 MVP 建 Agent Runtime |
| Browser Use CLI/MCP | 本地浏览器/Chrome 与可选 Cloud Browser，支持 Agent CLI/Skill 和 MCP | 可作为独立候选执行器，与 Playwright/agent-browser 做同场对比 | 2026 年工具面已发生版本迁移：旧 `browser_navigate` 等 MCP 工具名已弃用，新 `--cli-mcp` 主要提供持久化 `browser_exec`/截图。需要固定版本；任意 Python 执行工具不能直接视为受限浏览器动作 |
| Skyvern Agent / Browser Automation | 自然语言驱动的浏览器 Agent，也支持在 Python/TypeScript 中组合 Playwright 页面操作；提供托管浏览器及本地/自托管模式 | 可作为后续 Agent 能力候选，验证多步探索任务的成功率和恢复行为 | 产品范围超出浏览器驱动，带工作流、文件、HTTP 等能力；官方仓库标注 AGPL-3.0，且项目默认收集基础遥测。若引入需先审查本地部署、遥测、许可证、数据流和最小权限，不建议作为 MVP 首个依赖 |
| Selenium WebDriver / WebDriver BiDi | W3C WebDriver 控制浏览器；BiDi 可流式接收 Network、Console 与 JavaScript 错误事件，支持本地或 Selenium Server 远程会话 | 若后续必须覆盖多浏览器/远程 Grid，可作兼容性与分布式执行候选 | 不是面向 Agent 的 MCP/自然语言界面；引入后需要自己维护 Agent 工具包装与证据导出 |
| Puppeteer | Node.js 浏览器自动化库，可经 DevTools Protocol 或 WebDriver BiDi 控制 Chrome/Firefox，支持无头或可视浏览器 | 适用于现有 Node 组件已有 Puppeteer 依赖，或需要自建精确浏览器操作 | 本身不是 Agent、MCP Server 或 BugMaster Skill；要额外实现宿主工具包装、安全能力限制和 Evidence 采集。避免只因“可操作浏览器”就再引入一套执行栈 |
| BrowserGym / AgentLab | WebArena、VisualWebArena、WorkArena 等 Agent 任务环境和评分框架 | 离线比较浏览 Agent 的完成率、失败类型和安全行为 | 它是研究/Eval 框架，不是 BugMaster 的线上 Browser Adapter；不能替代现有 50 个 Benchmark，也不能把外部基准分数当成本项目真实缺陷发现证据 |
| Browserbase 等托管浏览器 | 云端隔离浏览器、并行会话与调试视图 | 仅在本地浏览器无法覆盖环境或需要远程并行时考虑 | 与 Local-first 默认有数据边界冲突；需单独评估 URL、Cookie、DOM、截图、Network 和测试数据是否离开本机 |

### 选择建议

1. 保留 11 个公开 BugMaster Skill，不把 Playwright/agent-browser/Stagehand 等外部 Skill 复制进产品包。它们是宿主侧工具说明，不是新的 BugMaster 缺陷发现能力。
2. 不新增 Agent Runtime。先用宿主现有工具完成隔离环境探索；若后续需要可移植性，再定义薄的 Browser Tool Adapter 能力契约，描述工具/浏览器版本、Session、Scope、能力集和 Evidence 引用。这个契约不能自行授予 Scope 或 R2 权限。
3. 第一轮只在同一隔离 Order Demo 比较 `agent-browser` 与 Microsoft Playwright CLI；Host 确实需要 MCP 时，再单独验证 Playwright MCP，并确认可关闭任意代码执行工具。视觉场景另用 Codex Computer Use 作屏幕交互基线，并单独记录 ego-browser Skill API 的能力；不要把两者视为同一种执行接口。比较 DOM/无障碍、视觉、Network/Console、会话隔离、证据导出、安装和越界拒绝；不同时引入多套依赖。
4. 只有当任务需要自然语言驱动多步骤规划时，再用同一任务基线评估 Browser Use、Stagehand 或 Skyvern。每次只挑一个 Agent，对比任务成功率、错误动作、恢复率、模型/浏览器成本与输出证据；Agent 的自我陈述不计为通过或缺陷证据。
5. Playwright Test 适合 BugMaster 自身的确定性 E2E/回归检查；不要让 BugMaster 把它用于写入回归测试，因为 Q9 只允许输出建议。Selenium/Puppeteer 是底层执行库候选，不是直接可插入的 Agent。BrowserGym 适合作为额外 Agent 能力研究，不增加 v0.1 的 50 个正式场景。
6. 所有浏览器都必须通过 BugMaster 的 Scope / Action 风险边界。网页 DOM、截图、弹窗、页面提示和 MCP 返回内容都属于不可信输入；浏览器工具的域名规则不能替代项目级授权。R0 只读可在已授权范围内自主执行，R2 写入仍经过动作级授权，R3 不执行。
7. 默认使用独立临时 Profile，不借用用户个人登录态。确需验证已登录业务流程时，将其作为显式授权的人工协作测试，并记录账号/环境引用、工具版本和清理状态；敏感 Cookie、Token 和请求体必须先做脱敏策略。

### 同场对照的验收记录

每个候选工具用相同目标环境和任务种子记录：正确路径、真实缺陷、正常行为、模糊 Oracle、页面提示注入、跨域重定向、弹窗/下载、网络超时、浏览器崩溃恢复。分别记录目标动作执行成功率、越权动作数（必须为 0）、有效证据引用率、错误候选/错误拒绝数、恢复成功率、人工审核秒数、运行成本、安装步骤和版本固定方式。结果只作为工具选型证据；更新既有 50 场景内容，不扩增冻结总数，也不把工具可用性当作 BugMaster 发现质量。

## 4. 进入工具选型前的验证清单

- [ ] 本地、隔离、可销毁的测试 Profile；真实用户 Profile 不作为默认方案。
- [ ] 当前 Host 能限制可调用工具；尤其验证任意代码、下载、上传、跨域导航、弹窗确认和网络拦截能力。
- [ ] 仅输入 URL 不会扩展 Scope；外链/重定向/子资源请求不会绕过工具层目标约束。
- [ ] 页面注入“忽略规则/上传凭据”等内容时，Agent 将页面内容当作不可信数据。
- [ ] R0 浏览器读取能够生成可复核截图/DOM/Network 引用；失败或环境不确定不会被标成真实 Bug。
- [ ] 表单写入、删除、支付、发送消息等动作不会由模型直接执行；R2 需要绑定精确动作的审批。
- [ ] 相同 Browser Case 在 Codex 与 Claude Code 的实际工具路径均有执行记录；同一工具文档能安装不等于双宿主已验证。
- [ ] 记录候选保留/拒绝、错误拒绝、模糊 Oracle、跨表面去重、人工反馈与实测复核秒数；另行报告 Precision、Recall 和审核成本。

## 5. 任务归属与完成边界

- 本调研归入 W10-02「Browser tool research and dual-host API/Browser/permission evaluation」，并同步到 Q15、Q17 两份任务清单。
- 本文完成的是 W10-02 的工具调研与选型计划部分；W10-02 仍为 `planned`，要等 W5-02、W7-02、W9-02 依赖满足后，才能在隔离环境运行双宿主 Browser/permission 用例并记录真实 Run ID。
- 同一时间仍只推进一个 PR；本任务不新增 BugMaster Skill、Agent Runtime，也不把工具文档调研当成真实浏览器验证。

## 6. 本次调研来源

- 项目冻结决策：[Q1–Q17](DECISION_FREEZE_Q1_Q17_ZH.md)、[ADR-015](ADR-015-risk-based-dual-review.md)、[Q15 任务风险清单](Q15_GITHUB_TASK_BACKLOG.csv)、[ADR-016](ADR-016-two-person-release-authorization.md)、[质量门禁](QUALITY_GATE_POLICY_ZH.md)
- [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp) 与 [Playwright CLI/Skill](https://github.com/microsoft/playwright-cli)
- [Selenium WebDriver / BiDi](https://www.selenium.dev/documentation/webdriver/) 与 [Puppeteer](https://pptr.dev/docs/)
- [Skyvern Agent / Browser Automation](https://github.com/Skyvern-AI/skyvern) 与 [Browser Automation 文档](https://github.com/Skyvern-AI/skyvern/blob/main/docs/developers/browser-automations/overview.mdx)
- [Vercel agent-browser](https://github.com/vercel-labs/agent-browser) 与 [Security Guide](https://agent-browser.dev/security)
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)
- [Browser Use 当前迁移说明](https://github.com/browser-use/browser-use/blob/main/MIGRATING.md)
- [Stagehand](https://www.stagehand.dev/) 与 [Browserbase MCP Server（仓库已归档，仅作历史参考）](https://github.com/browserbase/mcp-server-browserbase)
- [ServiceNow BrowserGym](https://github.com/ServiceNow/BrowserGym)

本次只做文档调研，没有启动这些第三方浏览器，也没有验证其实际安全策略或 BugMaster 双宿主集成。上述比较是基于官方公开文档的能力筛选，不是产品选型批准。

## 7. 项目所有者决策（2026-11-22）

项目所有者决定采用 Q15=D：每个 PR 由 Codex 做代码扫描；R2/R3 变更还做安全扫描；项目所有者查看结果后手动合并，不要求独立真人 Q15 签署。以上决定取代本调研第 3 节关于保留独立 QR/SR 的建议。Q16 的公开发布双人授权保持不变，Finding 复核和目标系统动作授权仍按各自产品规则执行。若后续证据显示该流程存在实质问题，Codex 应说明依据与影响，再与项目所有者讨论或请其选择，不单方面恢复真人 Q15 审核。
