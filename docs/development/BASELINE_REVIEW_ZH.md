# Architecture Baseline Review — Q1–Q14

**结论：Conditional Go for implementation, No-Go for public release**。文档结构已可开始工程实现；关键运行时能力、双宿主安装与 Benchmark 均未实测，不能对外宣称已支持。

## 决策一致性

- Q14=A：一次性完整 MVP，不分阶段发布缩水 MVP。实施按依赖顺序串行推进，一次只做一个功能 PR；当前 PR 合并后才开始下一项。VS-01 是集成门禁。
- Q1 + Q13：Session Controller 只允许薄校验与日志工具，不引入后台 Agent Runtime。
- Q2 + Q12：完全独立指不依赖其他 QA Skill 仓库；宿主的通用工具/权限依然是条件性外部能力。
- Q3 + Q12：Prompt 不具备强制授权能力；未验证的通用工具路径不能用于声称受控自动执行。
- Q5 + Q6：Pattern ID 唯一，Registry 只引用，候选路由依赖三值前提过滤；未匹配时走未知假设。
- Q7 + Q8：Finding Revision 为当前结论唯一权威；Evidence 原始材料独立；E0–E4 与 Finding/Review/Severity 分开。
- Q9：回归建议与自动测试实现严格分离；Benchmark 中评估者自行维护参考测试不违反该边界。
- Q10 + Q11：统一独立评估器，私有 Ground Truth 真正隔离；PR 轻量、发布全量。

## 冲突清单和处理

| ID | 原草案冲突或重复 | 收敛结论 | 风险 |
|---|---|---|---|
| REV-01 | 8 / 10 / 11 Skills | 10（Q4）+1（Q9）=11 | Major |
| REV-02 | 12 / 16 Patterns | Q4 后固定 16 | Major |
| REV-03 | `BP-API-IDEMPOTENCY-001` 与 `BP-API-002` | 以 BP-API-002 为 Canonical，长 ID 历史别名 | Major |
| REV-04 | Finding 文档视图 vs revisions/current pointer | 不可变 Revision + Current Pointer 权威；`finding.json` 为生成视图 | Critical |
| REV-05 | Q7 Evidence E3 自动 Confirmed vs 人工审查 | E3 是最低证据条件，还需全部 Gate/必要人工审批 | Critical |
| REV-06 | CLI/Commands 统一语法假设 | 统一语义，不承诺同一斜杠命令格式 | Major |
| REV-07 | 完全独立 vs Browser/HTTP 工具依赖 | 无外部 QA Skills；执行依赖宿主实际工具，缺失即降级 | Major |
| REV-08 | Journal append-only vs 中断时真实强一致 | 只承诺已实现且通过故障注入的能力，未知副作用不重放 | Critical |
| REV-09 | Pattern Verified vs Finding Confirmed | 知识状态/某次缺陷状态严格分离 | Major |
| REV-10 | 50 场景 vs 50 个已知 Bug | 50 是不同任务类型总数，召回仅统计可评估的注入缺陷 | Major |
| REV-11 | Git-friendly vs 敏感 Evidence | 原始证据默认不提交 Git，仅脱敏/已审批包导出 | Critical |
| REV-12 | Q14 一次性 MVP vs Vertical Slice | VS 是内部测试里程碑，不单独对外作为 MVP | Critical |

## 当前阻断项（要在发布前消除）

| ID | 阻断风险 | 验证 Spike | 解除条件 |
|---|---|---|---|
| BLK-01 | Codex/Claude Code 安装器对资源依赖闭包支持不确定 | 干净安装单 Skill + Pattern 引用检查 | 两宿主正式分发路径证据 |
| BLK-02 | 工具执行的审批/限制无法强制保证 | R2 越权模拟和工具绕过试验 | 受控路径确实阻断，其他路径明确禁用 |
| BLK-03 | 多文件持久化/Journal 崩溃一致性 | 八个故障注入点 | 指针不指向不完整版本、未知副作用不重放 |
| BLK-04 | E3 证据真实性不可仅凭哈希证明 | 伪造工具结果与来源绑定对抗样本 | 伪造结果不能升 Confirmed |
| BLK-05 | Benchmark 答案泄漏 | 进程/容器隔离访问攻击测试 | Agent 无法读取 Ground Truth |
| BLK-06 | 浏览器工具跨宿主可用性和网络/重定向风险 | API/UI 联合测试、目标跳转与授权模拟 | 每个宿主有真实证据或正式限制声明 |
| BLK-07 | 一次性范围大导致集成失败 | VS-01 内部垂直闭环 + 全量清单 | 全范围统一 RC 验收成功 |

## 待办

- [ ] 为所有核心 Schema 加正反 JSON Fixture 与状态转换表。
- [ ] 编写 11 个真正可独立安装的 SKILL.md（本文档包仅含规范草案）。
- [ ] 编写 16 Pattern 的 Canonical 数据及 50 场景真实任务和答案。
- [ ] 验证权限强制路径、崩溃恢复、证据真实性与 Ground Truth 隔离。
- [ ] 完成双宿主实测并填充兼容矩阵。
- [ ] 完成所有完整 MVP Release Gates；在证据齐全之前保持 No-Go 发布状态。
