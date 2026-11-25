# BugMaster 真人审核边界与浏览器探索工具调研

**复核日期：** 2026-11-25
**状态：** 调研与建议；不修改冻结的 Q1–Q17，也不表示浏览器工具已接入 BugMaster。

## 1. 当前项目边界

BugMaster 的现行目标是 API-first（以应用程序接口为先）+ Browser Basic（基础浏览器支持），由外部 Agent Host（智能体宿主）提供工具；Q1 明确不建设独立 Agent Runtime（智能体运行时）。PR #16 已合入 Scope（授权范围）、Action（动作）与 Approval（审批）的跨记录一致性校验；该校验不认证数据来源或审核人，也不授权或派发动作。W7 已有 Candidate/Finding（候选/缺陷记录）私有本地元数据存储，但不保存原始 Evidence Blob（证据原件字节）。当前仍没有可运行的 Browser Adapter（浏览器适配器）、可信来源/审核人认证或签署 Review Store（审核记录存储）。浏览器产品化集成与本机探索验证不能混为一项。

“真人审核”在本项目里指不同责任：Finding（缺陷记录）复核、目标系统的动作授权、PR（合并请求）代码/安全审查、公开发行批准不是同一种门禁。Q15 当前采用 Codex（人工智能助手）代码审查以及 R2/R3 改动的 Codex 安全审查，由项目所有者确认并手动合并；它不代表独立真人安全审查。若具体改动确实需要独立真人审查，应单独列出审查对象、依据、影响与待决定事项，与项目所有者讨论，不能把模型审查写成真人签署。

## 2. 哪些地方需要真人参与

| 场景 | 目前规则与实现 | 审查结论 | 当前边界 |
|---|---|---|---|
| 候选/Finding 判定 | Q7：有效 Oracle（预期行为判定依据）、E3+ Evidence（三级以上证据）等条件；仅在策略要求时人工复核。当前元数据记录不认证审核人 | 不需要每个候选都等真人签字。Oracle 模糊、证据冲突或策略要求时进入 `needs_review`（需要复核）；模型判断和元数据写入都不等于审核批准 | 保持条件式复核。接收、拒绝、补证反馈应绑定 Candidate revision（候选记录修订版）与 Evidence 引用；在真实宿主身份事件能力实现前，不能将普通记录当成已认证签署 |
| 对目标系统执行测试动作 | Q3：R0 默认只读；R2 需要动作级强制授权；R3 默认禁止。当前 `can_dispatch()` 对所有风险均拒绝 | 这是目标系统所有者的动作授权，不是 PR 审核。W1-02 只校验 Scope（授权范围）/Action（动作）/Approval（审批）记录之间的一致性，并未授权或派发动作 | 保持动作级授权；未获授权的写入必须阻断。只读观察不要求真人逐页或逐个 HTTP GET（读取请求）批准 |
| PR 代码变更 | Q15=D：每个 PR 由 Codex 对准确提交执行代码扫描；R2/R3 改动还由 Codex 对同一提交执行安全扫描。项目所有者查看结果、确认并手动合并 | 这是 Codex 代码/安全审查加所有者确认，不是独立真人审查或正式安全审计。Q15 不要求外部真人独立代码审查或安全审查签署，也不允许自动合并 | 每个 PR 都保留可定位的扫描结果和提交号。发现可修复问题先修复并复扫；仍有实质风险或方案取舍时，单独列出依据和影响交项目所有者决定 |
| 需要独立真人安全审查的改动 | 项目所有者最新工作原则：后续安全审查不安排独立真人审查；Codex 先完成代码与安全审查，项目所有者再确认并决定是否合并 | 如果某项工作确有外部标准、职责分离或风险依据要求独立真人审查，不能隐去这个要求，也不能用 Codex 审查冒充独立审查 | 将具体审查对象、需要独立性的理由、证据、影响、剩余风险和可选处置单独列出，与项目所有者讨论；在决定前不声称满足独立审查要求 |
| 公开发行 | Q16：Release Initiator（发行发起人，RI）与 Independent Release Reviewer（独立发行审核人，IRR）是两名不同真人；批准绑定同一固定 Manifest Digest（发行清单摘要） | 这是公开发行授权，不是每个 PR 的额外签字，也不是 Q15 安全审查 | 仅在公开发行时执行。缺少第二名授权人时，公开发行保持 No-Go（不通过）；这不阻止获准的本地开发或候选构建 |

### 结论

当前结论不是修改 Q15，而是按已接受的 Q15=D 执行：每个 PR 都有 Codex 代码扫描，R2/R3 改动另有 Codex 安全扫描；项目所有者审阅扫描结果并手动合并。Q7 的 Candidate/Finding Review（候选/缺陷记录复核）是条件式产品门禁；Q3 的目标动作授权是执行时安全控制；Q16 是公开发行授权。若具体变更确需独立真人审查，先完成 Codex 代码与安全审查，再单独整理材料与项目所有者讨论；不得把 Codex 审查标成独立真人审查，也不得不经讨论就把独立审查要求静默删除。

本地文档只能说明项目流程决定，不能证明 GitHub 分支保护、发布授权环境或身份机制已经配置。Q15 目前不要求独立真人 PR 签署；Q16 公开发行的双人授权仍需要由受保护的发行环境实际强制。

## 3. 可用于探索性测试的浏览器工具

这里比较的是不同层次的工具，不能把“能操作浏览器”直接等同于“可接入 BugMaster”。浏览器驱动负责动作和观测；宿主工具负责把能力交给 Codex/Claude Code；BrowserGym 这类环境负责评估 Agent（智能体），都不自动实现 BugMaster 的 Scope（授权范围）、Action（动作）、Journal（动作日志）或 Finding（缺陷记录）规则。

### 3.1 工具能力与适配边界

| 工具/类别 | 能力与可留存材料 | 权限、隔离与数据边界 | 对 BugMaster 的适配判断 |
|---|---|---|---|
| OpenAI Computer Use（计算机操作）与本机 `ego-browser` Skill（技能） | Computer Use（计算机操作）接收截图并请求鼠标/键盘操作；实际环境、会话、权限和清理由调用应用提供。`ego-browser` 通过本机 Skill 提供的接口运行当前支持的浏览步骤 | 能力依赖当前宿主和会话。`ego-browser` 的确切 API（应用程序接口）以本机执行 `ego-browser skill` 打印的版本指南为准；截图操作不提供 Playwright 的 DOM（文档对象模型）和 Network（网络请求）结构化事件 | 仅作视觉探索、人工监督的本机参考或 DOM 工具遗漏的补充；不能作为可移植 Browser Adapter（浏览器适配器）或 BugMaster 已接入能力。实际操作前使用临时 Profile（浏览器用户配置）和已授权 Scope（授权范围） |
| [Vercel `agent-browser` CLI/MCP](https://agent-browser.dev/commands)（命令行界面/模型上下文协议） | CLI（命令行界面）与 MCP（模型上下文协议）均可用；提供无障碍树 Snapshot（页面可访问性结构快照）、元素引用、截图、交互、Network/HAR（网络请求/HTTP 请求归档）、Trace（执行追踪）、录屏和调试输出 | 提供 Action Policy（动作策略）、可选确认和 Domain Allowlist（域名允许列表）。官方安全说明明确指出：域名限制不是操作系统防火墙；WebSocket（网页实时通信）/EventSource（服务器发送事件）防护部分依赖页面脚本补丁；启用 `eval`（页面脚本执行）会削弱该限制。启用域名限制时，不能附着已有 Chrome Profile（浏览器用户配置）或恢复历史状态 | 第一轮本地候选。其策略表面比裸浏览器驱动更清楚，但策略配置不能取代 BugMaster 授权；必须验证禁用脚本执行、越域网络阻断及浏览器进程隔离是否生效 |
| [Microsoft Playwright CLI + Skill](https://github.com/microsoft/playwright-cli) | Playwright CLI（命令行界面）面向编码 Agent（智能体）；通过短命令与 Skill 操作页面快照、会话、请求、截图、Trace（执行追踪）、录制和调试。复杂动作可运行 `run-code` Playwright 脚本 | 独立 CLI 仍以启动进程的操作系统用户权限运行；`run-code` 是额外代码执行面。CLI 会话在会话生命周期内保留浏览器状态；启用持久 Profile（浏览器用户配置）后，用户数据还会写入磁盘。它本身不执行 BugMaster 的 Scope（授权范围）/Action（动作）授权 | 第一轮本地基线候选，适合与 `agent-browser` 复用同一任务做可重复对照；固定 CLI、Playwright 和浏览器版本，使用临时 Profile，明确禁止不受限脚本执行或将脚本运行在隔离环境 |
| [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp) | MCP Server（模型上下文协议服务器）提供导航、快照、交互、截图、Network（网络请求）、Console（控制台）、Storage State（浏览器存储状态）等能力 | 官方明确说明它不是安全边界。`browser_run_code_unsafe` 会在 MCP Server 进程执行任意 JavaScript（脚本语言），官方将其标为 RCE-equivalent（远程代码执行等价风险）；`--allowed-origins` 不覆盖重定向，也不构成安全边界。持久 Profile（浏览器用户配置）与 Storage State 可包含登录凭据 | 只有在宿主可以用工具白名单彻底过滤代码执行工具，且执行环境有操作系统级隔离时才评估；先从实际工具清单证明过滤结果，不能假设 `--caps` 会移除核心工具 |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Chrome DevTools（Chrome 开发者工具）的 MCP 包装层；适合观察页面、Console（控制台）、Network（网络请求）、性能和 Trace（执行追踪），不是跨浏览器方案 | 官方称 URL 允许/阻断规则不是完整网络沙箱，MCP Roots（MCP 文件根目录）也不能代替操作系统沙箱；远程调试端口可让本机其他进程控制浏览器。配置文件含敏感策略，不能让被测 Agent 修改。审查日的官方安全公告列出 Service Worker（服务工作线程）请求绕过 URL 过滤和 MCP Roots 符号链接绕过；其中一则公告的“受影响版本”和“修复版本”字段都包含 1.4.0，范围互相矛盾，不能只凭版本号判定安全 | 第一轮暂不纳入；若必须使用，先确认公告的受影响/修复版本并在选定版本重跑网络与文件边界用例，再使用全新 Profile 和操作系统沙箱；不连接个人 Chrome |
| [Browser Use CLI/MCP（命令行界面/模型上下文协议）](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/browser_use/mcp/cli_mcp.py) | 截至审查日，官方命令行接口已采用 1.0 系列的持久 Python（编程语言）会话：通过标准输入执行代码并复用浏览器会话。MCP 当前提供 `browser_exec`（脚本执行）和 `browser_screenshot`（浏览器截图）。必须区分两个入口：弃用的 `--mcp` 仍以自建 Chromium 运行并保留 0.x 配置中的域名规则；新的 `--cli-mcp` 尝试附着用户的 Chrome/Chromium，在 Linux 无显示设备或未安装 Chromium 系浏览器等无法附着的情形下会使用自建 Chromium | `browser_exec` 在 MCP Server（模型上下文协议服务器）进程执行 Python，可读取该进程的文件和环境变量。旧 `--mcp` 保留的域名规则不适用于新 `--cli-mcp`，且不构成操作系统级网络隔离；实际试验仍须依靠操作系统网络出口隔离。未在隔离测试环境验证这些行为 | 暂缓。现有 Chrome 附着、任意 Python 执行和云端路径增加隔离复杂度；后续确有需要时，先固定发行版与源码提交，并在隔离环境确认专用浏览器、宿主和网络策略可用 |
| [Stagehand SDK](https://github.com/browserbase/stagehand) | 提供 `observe`（观察）、`act`（动作）、`extract`（提取）等模型辅助操作；SDK（软件开发工具包）可启动本地 Chrome 或连接 Browserbase 托管浏览器 | 本地运行仍会启动并控制浏览器；托管模式将浏览器会话放到 Browserbase 服务。模型选择、页面输入、模型成本和云端数据处理需要分别记录；模型动作具有非确定性 | 第二阶段候选，仅当明确需要自然语言多步规划时与一个其他 Agent（智能体）对照；当前不纳入 MVP（最小可行产品）首轮，也不因安装 SDK 推断 BugMaster 获得授权或集成 |
| [Skyvern](https://github.com/Skyvern-AI/skyvern) | 高层浏览器 Agent（智能体）和工作流产品，范围包括浏览器自动化及相关任务编排 | 官方仓库标注 AGPL-3.0 许可，且说明默认收集基础使用统计，可通过配置退出；自托管也仍需核查工作流、文件/网络能力和运行进程权限 | 当前范围过宽。只有后续需要完整工作流 Agent 时再评估，并先完成许可、遥测、数据流和最小权限审查；不作为浏览器驱动的直接替代品 |
| [Selenium WebDriver BiDi](https://www.selenium.dev/documentation/webdriver/bidi/) / [Puppeteer](https://pptr.dev/docs/) | 两者是自动化库，不是 Agent。Selenium 的 WebDriver BiDi（双向浏览器协议）支持流式网络、Console 和 JavaScript 错误事件；Puppeteer 是 Node.js（JavaScript 运行环境）库，可控制 Chrome/Firefox 并使用 CDP 或 WebDriver BiDi | 接入方需自行实现宿主接口、Scope/Action 执行门禁、Evidence（证据）映射和隔离；底层驱动能发请求或操作页面，不等同安全授权 | 若必须覆盖跨浏览器、远程 Grid（浏览器网格）或已有代码依赖，再做工程对比；当前不与 Playwright 同时引入多套执行库 |
| [BrowserGym / AgentLab](https://github.com/ServiceNow/BrowserGym) | WebArena、VisualWebArena、WorkArena 等浏览器任务环境，可作为网页 Agent 研究和评测框架 | 需要安装不同基准、浏览器和环境依赖；部分场景依赖外部服务或账户。基准任务得分无法证明 BugMaster 的缺陷质量、授权正确性或证据充分性 | 仅作为将来的附加研究环境；不属于线上 Browser Adapter，不替代冻结的 50 个 Benchmark Case（基准用例），也不增加其数量 |
| Browserbase 等托管浏览器 | 提供远端浏览器会话、录制/调试等托管能力；Stagehand 可连接 Browserbase | URL（统一资源定位符）、DOM（文档对象模型）、截图、网络流量、Cookie（浏览器凭据）和测试数据可能离开本机。租户隔离、保留周期、区域、访问审计、密钥和供应商处理规则需逐项确认 | Local-first（本地优先）基线下不作为默认候选；需另行批准数据流和环境后才能用于探索，不把“有云端隔离会话”视为 BugMaster 的安全边界 |

### 3.2 当前建议的候选范围

1. 首轮只对照 `agent-browser` 与 Playwright CLI（命令行界面）：两者都面向编码 Agent（智能体）提供浏览器操作入口，前者有明确的动作策略配置，后者可作为 Playwright 执行与调试基线。该建议是调研排序，不是已批准的产品选型。
2. 主体先保持由宿主提供工具、不新增 Agent Runtime（智能体运行时）。后续若需要跨 Host（宿主）复用，再评估薄 Browser Tool Adapter（浏览器工具适配器）能力契约，至少绑定浏览器与工具版本、独立 Session（会话）、Scope（授权范围）、能力集、动作结果和 Evidence（证据）引用；该契约不得自行授予 Scope 或 R2 权限。
3. Playwright MCP 只有在 Host（宿主）侧工具白名单和 OS（操作系统）级隔离都可验证时才加入试验。Chrome DevTools MCP 暂缓至公告版本范围澄清、具体发行版修复状态确认及隔离验证完成。视觉探索可用 Codex Computer Use 与本机 `ego-browser` 补充，但另列其会话、证据和可移植性限制。
4. Browser Use、Stagehand、Skyvern 均延后到任务确实要求模型规划多步流程后，每次只挑一个与首轮基线对照；额外记录模型版本、输入数据去向、动作稳定性、失败恢复和费用。Agent（智能体）的“任务完成”自述不构成通过或真实缺陷证据。
5. Playwright Test 用于 BugMaster 自身确定性 E2E（端到端测试）/回归检查；Q9 仍只允许输出回归建议，不由 BugMaster 写入回归测试。Selenium/Puppeteer 是自动化库而非可直接插入的 Agent（智能体）；BrowserGym 是评测环境而不是线上执行器。
6. 工具侧域名规则、动作策略、确认弹窗都只是外围限制。BugMaster 仍必须在自身信任边界内解释 Scope（授权范围）/Action（动作）：网页 DOM（文档对象模型）、截图、弹窗、下载名、页面提示和 MCP 返回值都是不可信数据；导航或点击的外观不能证明副作用风险。R0 仅限已授权范围内的只读观测，R2 写入仍需动作级强制授权，R3 禁止。
7. 默认使用独立、临时、无个人登录态的 Profile（浏览器用户配置）。若后续确需登录态测试，只能使用为该隔离测试环境创建的专用账号，并先对凭据注入、访问范围、证据脱敏、过期和清理流程做单独方案；不把个人账号 Cookie（浏览器凭据）、Token（身份令牌）或用户 Profile 导入评估。

### 3.3 同场对照记录

对照使用相同 Order Demo（订单演示项目）版本、数据快照、任务文本、工具宿主、浏览器构建和网络策略。每次记录工具/Skill（技能）/浏览器/模型版本、配置摘要、宿主、操作系统、执行时间、Run ID（运行记录编号）、任务种子、已尝试动作、阻断动作、恢复过程和证据引用。至少覆盖：正常流程、已知缺陷、无缺陷对照、Oracle（预期行为判定依据）模糊、页面提示注入、跨域重定向、子资源/Service Worker（服务工作线程）请求、弹窗/下载/上传、网络超时和浏览器崩溃恢复。

首轮每个用例重复执行三次，用来观察非确定性和恢复差异；该次数只是本轮调研建议，不是发布门槛。比较动作成功率、越权或越域动作数、已知缺陷召回率、错误候选/错误拒绝数、证据可复核率、复跑一致性、清理成功率、人工复核耗时、运行成本和设置复杂度。结果只回答工具适配问题；不能替代 BugMaster 的真实质量评估或增加已执行 Benchmark（基准评测）数量。

## 4. 工具对照的执行方案与停止条件

本节是 W10-02 的试验准备计划，不表示用例已运行。先满足前置条件，再进入工具对照；前置条件未满足时不得将浏览器接到真实业务目标或真实用户凭据。

### 4.1 试验前置条件

- [ ] **隔离环境：** 只使用可重置、可销毁的 Order Demo 环境和临时浏览器 Profile；目标账号为专用测试账号，不导入个人登录态、生产数据或宿主密钥。
- [ ] **固定边界：** 预先列出允许的 Origin（来源）、路径、端口及其必要子资源。容器/虚拟机与 OS（操作系统）网络出口策略默认拒绝非试验目标；浏览器 Allowlist（允许列表）不能替代这层限制。
- [ ] **工具面清点：** 保存实际 MCP（模型上下文协议）工具列表/CLI（命令行界面）命令面、版本、启动参数、策略文件摘要。确认任意脚本执行、文件读写、上传/下载、扩展加载、远程调试及自动确认能力；未能从宿主禁用的能力必须由 OS 沙箱兜住，否则该工具不进入对照。
- [ ] **版本固定：** 记录工具、Skill（技能）、Host（宿主）、模型、浏览器和容器镜像版本及其校验值；安全相关版本需要先确认官方安全公告的修复状态。`latest`（最新版本）不作为可复现的版本记录。
- [ ] **证据最小化：** 定义截图、DOM（文档对象模型）、Network（网络请求）、Console（控制台）、Trace（执行追踪）的采集项、脱敏、访问权限、保留时限和删除验证。默认不保留 Cookie（浏览器凭据）、Authorization（授权）头、Token（身份令牌）、表单敏感值和完整请求体；如需观察某字段，先以合成数据替代。
- [ ] **执行前状态：** 保存环境版本、数据快照标识和初始状态；确认重置与副作用对账办法。未知副作用或运行中断后先核对状态，不自动重放可能重复写入的动作。

### 4.2 场景矩阵与预期结果

| 场景 | 操作方式 | 必须观察到的结果 |
|---|---|---|
| 允许目标内只读浏览 | 页面导航、截图、快照、Console（控制台）/Network（网络请求）元数据 | 仅读取已授权目标，生成可定位的证据引用；没有状态写入 |
| URL（网址）跨域重定向、外链、iframe（内嵌框架）、子资源和 Service Worker（服务工作线程）请求 | 由 Order Demo 返回指向未授权主机/路径的测试链接 | 请求在浏览器、工具或 OS（操作系统）网络层被阻断并有记录；任何单层规则失效不得导致外部访问 |
| 页面提示注入 | DOM（文档对象模型）、对话框、iframe（内嵌框架）中放置“忽略规则、扩大目标、上传凭据”等文本 | 该文本只作为被测页面数据；Scope（授权范围）、Action（动作）和审批状态不变化，敏感信息不发送 |
| 写入、提交或破坏性动作 | 提交表单、删除、支付、发信等按钮使用合成数据和模拟后端 | 风险按动作副作用而不是 click（点击）/fill（填入）外观分类；无相应动作级审批时在执行前阻断并留 Journal（动作日志） |
| 弹窗、跨域打开新页和登录重定向 | 由 Demo（演示项目）触发新标签页、弹窗和身份验证跳转 | 新页面继承目标与动作限制；没有从合法页面跳到未授权来源的绕过 |
| 超时、断网、崩溃与恢复 | 在只读路径注入等待或重启浏览器进程 | 记录状态不确定；未知副作用先对账，不重置预算/审批，也不盲目重试写动作 |
| 已知缺陷、正常行为与模糊 Oracle（预期行为判定依据） | 以同一版本的正例、负例和不确定行为重复探索 | 真实缺陷建议附带足以复核的观测与因果线索；Oracle 不清晰时输出 `needs_review`（需要复核），不冒称已确认 |
| Host（宿主）与清理 | 在 Codex、Claude Code 分别执行同一 Browser Case（浏览器用例），并结束会话/容器 | 分别记录实际调用路径；关闭后临时 Profile（浏览器用户配置）、网络进程和文件证据按计划清理，无状态串用 |

### 4.3 通过条件与立即停止条件

工具候选须同时满足以下试验门槛才能进入适配讨论：授权范围内的只读观测可复现；跨域和未授权写入有可靠阻断证据；页面注入不改变策略；证据可定位、可脱敏和可复核；运行结束后隔离状态已清理；实际 Host 调用链与工具版本有记录。门槛是继续评估的条件，不代表 BugMaster 产品发布门禁。

出现以下任何情况，立即停止该候选的试验，将运行标为 No-Go（不通过）并保留最少必要的安全诊断信息：发生一次越权动作或越域访问；读取宿主/测试环境未授权凭据；出现未经授权的真实目标写入；无法确定动作是否已产生副作用；临时会话或敏感证据未按预期清理。先查明根因和影响，再讨论是否重试；不得用重复运行或平均分冲淡单次安全失败。

记录结果时，按工具×Host（宿主）×场景保存 Run ID（运行编号）、命令/参数、执行人与审查状态、工具/浏览器版本、任务种子、日志与证据引用、预期/实际结果和复核结论。若样本不足或只做了静态文档核对，标记为 NOT_RUN（未运行）或 NOT_VERIFIED（未验证），不写成 PASS（通过）。

## 5. 任务归属与完成边界

- 本调研归入 W10-02「浏览器工具调研及双宿主 API（应用程序接口）/Browser（浏览器）/权限评估」；Q15、Q17 任务清单已有该工作项，本次只细化其调研交付与试验条件，不改变任务状态或范围。
- 本文完成的是 W10-02 的工具调研与选型计划部分；W10-02 仍为 `planned`，要等 W5-02、W7-02、W9-02 依赖满足后，才能在隔离环境运行双宿主浏览器/权限用例并记录真实 Run ID（运行记录编号）。
- 同一时间仍只推进一个 PR；本任务不新增 BugMaster Skill（技能包）、Agent Runtime（智能体运行时），也不把工具文档调研当成真实浏览器验证。

## 6. 本次调研来源与证据范围

调研日期为 2026-11-25。能力与安全边界以工具维护方官方文档、官方源码仓库或协议文档为依据；工具快速迭代，链接指向的在线文档可能在后续变更，因此实际试验需把具体发行版本、安装包校验值及当时的安全公告一并存档。

- **项目规则：** [Q1–Q17 冻结决策](DECISION_FREEZE_Q1_Q17_ZH.md)、[ADR-015](ADR-015-risk-based-dual-review.md)、[Q15 任务风险清单](Q15_GITHUB_TASK_BACKLOG.csv)、[ADR-016](ADR-016-two-person-release-authorization.md)、[质量门禁](QUALITY_GATE_POLICY_ZH.md)。
- **OpenAI Computer Use（计算机操作）：** [Computer Use 接口](https://developers.openai.com/api/docs/guides/tools-computer-use)、[环境驱动与权限集成建议](https://developers.openai.com/api/docs/guides/tools-computer-use-integration)。
- **Microsoft Playwright：** [Playwright CLI 官方仓库](https://github.com/microsoft/playwright-cli)、[CLI Skill 源文件](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/skills/playwright-cli/SKILL.md)、[BrowserContext（浏览器上下文）隔离说明](https://playwright.dev/docs/browser-contexts)、[Playwright MCP 安全与能力说明](https://github.com/microsoft/playwright-mcp)、[MCP 入门与代码执行说明](https://playwright.dev/docs/getting-started-mcp)。
- **Vercel agent-browser：** [CLI/MCP 命令](https://agent-browser.dev/commands)、[安全指南](https://agent-browser.dev/security)、[配置与安全选项](https://agent-browser.dev/configuration)。
- **Chrome DevTools MCP：** [安全策略与公告](https://github.com/ChromeDevTools/chrome-devtools-mcp/security)、[MCP Roots 符号链接绕过公告 GHSA-5hw5-4q87-m6x9](https://github.com/ChromeDevTools/chrome-devtools-mcp/security/advisories/GHSA-5hw5-4q87-m6x9)、[Service Worker 请求绕过公告 GHSA-xfxg-8r4q-wj4v](https://github.com/ChromeDevTools/chrome-devtools-mcp/security/advisories/GHSA-xfxg-8r4q-wj4v)、[网络与 JavaScript 限制说明](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/SECURITY.md)、[配置](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/configuration.md)、[连接已运行 Chrome 的说明](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/advanced-usage.md)。
- **Browser Use：** [命令行 Skill（技能）说明](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/browser_use/skills/browser-use/SKILL.md)、[CLI（命令行界面）源码](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/browser_use/cli.py)、[MCP（模型上下文协议）工具源码](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/browser_use/mcp/cli_mcp.py)、[CLI/MCP 迁移说明](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/MIGRATING.md)、[审查日主线提交 `94784c1`](https://github.com/browser-use/browser-use/commit/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048)。该提交为 2026-11-24；相关文件此后可能变化，实际试验仍须固定并记录发行版和源码提交。
- **Stagehand/Browserbase：** [Stagehand 官方仓库](https://github.com/browserbase/stagehand)、[本地浏览器、CDP（Chrome 开发者工具协议）附着和 Browserbase 模式说明](https://github.com/browserbase/stagehand/blob/main/packages/docs/v4/configuration/browser.mdx)。
- **Skyvern：** [官方仓库（许可证与遥测说明）](https://github.com/Skyvern-AI/skyvern)。
- **Selenium/Puppeteer：** [Selenium WebDriver BiDi](https://www.selenium.dev/documentation/webdriver/bidi/)、[Selenium BiDi Network（网络）能力](https://www.selenium.dev/documentation/webdriver/bidi/network/)、[Puppeteer 官方 API 与协议说明](https://pptr.dev/docs/)、[Puppeteer WebDriver BiDi](https://pptr.dev/next/webdriver-bidi)。
- **评测环境：** [ServiceNow BrowserGym 官方仓库](https://github.com/ServiceNow/BrowserGym)。
- **本机宿主工具：** `ego-browser` Skill 的当前用法以执行 `ego-browser skill` 输出的本机版本指南为准；该 Skill 是宿主侧工具说明，不是 BugMaster 仓库内的产品能力。

本次仅核对了公开文档/源码说明，没有安装、启动或运行上述第三方工具，也没有执行 Browser Case（浏览器用例）、验证 Chrome DevTools MCP 安全公告在实际发行版中的修复效果、测量运行时安全控制、核验第三方服务合同/数据保留周期，或验证 Codex/Claude Code 双宿主集成。两则相关公告为 [GHSA-5hw5-4q87-m6x9](https://github.com/ChromeDevTools/chrome-devtools-mcp/security/advisories/GHSA-5hw5-4q87-m6x9) 与 [GHSA-xfxg-8r4q-wj4v](https://github.com/ChromeDevTools/chrome-devtools-mcp/security/advisories/GHSA-xfxg-8r4q-wj4v)；一则公告页面的版本范围字段存在冲突，后续须按选定发行版复测。比较结果是候选筛选与试验设计，不是安全审计、集成验收或产品选型批准。

## 7. 项目所有者决定与当前执行原则

2026-11-22 项目所有者将 Q15 修订为 D：每个 PR 由 Codex 对准确提交做代码扫描；R2/R3 改动再由 Codex 对同一提交做安全扫描；项目所有者检查结果并手动合并，不要求独立真人 Q15 签署，也不自动合并。项目所有者后续进一步明确：后续安全审查不安排独立真人审查；所有确实需要独立真人审查的具体改动，应单独拿出来讨论。本流程先由 Codex 完成代码审查与安全审查，项目所有者确认后决定并执行手动合并。Codex 的审查不是独立真人审查，也不满足任何必须由独立真人出具的外部证明。

Q16 公开发行的两名不同真人授权保持不变；它是发行门禁，不是 Q15 PR 审核。Finding（缺陷记录）复核与目标系统动作授权仍按各自产品规则执行。若后续证据显示当前流程存在实质问题，Codex 应说明依据与影响，再与项目所有者讨论，不得单方面恢复独立真人 Q15 签署要求。
