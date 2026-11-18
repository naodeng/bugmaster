[English](../en/06-repository.md)

# GitHub 仓库规范与双语维护

## 唯一仓库布局

```text
BugMaster/
├── README.md / README.zh-CN.md / AGENTS.md
├── CONTRIBUTING.md / CONTRIBUTING.zh-CN.md / SECURITY.md
├── CHANGELOG.md / RELEASE_POLICY.md / LICENSE
├── skills/                        # 11 个 Canonical Skill
├── patterns/                      # 16 个 Pattern + Catalog / Taxonomy
├── registry/capabilities.json
├── routing/ policies/ schemas/ scripts/ templates/
├── adapters/codex/ adapters/claude-code/
├── compatibility/
├── benchmark/fixtures/order-demo/ # 正确/注入缺陷变体
├── benchmark/datasets/v0.1/       # 50 个规划场景
├── eval/ tests/
├── docs/en/ docs/zh-CN/ docs/development/
├── .github/workflows/ .github/ISSUE_TEMPLATE/
└── dist/                           # 构建生成，不手改
```

用户项目运行产物使用 `.bugmaster/`，而非源码仓库的 `benchmark/`。含敏感证据的运行目录默认 Git 忽略。

## 双语规则

单一英文 Canonical `SKILL.md`，中文存于 `references/*.zh-CN.md` 和双语示例；Pattern 共享同一 `pattern.json` 元数据，英文方法与中文翻译并存。不因语言拆分第二套执行逻辑。正式项目文档英文默认 + 中文配套；过程、风险、TDD 决策文档中文。

## PR 规则

提案 → 差异/来源/许可审查 → RED 测试 → GREEN → Behavioral/Executable Eval → 影响回归 → 安全审核 → 人工批准 → 发布。R0 文档，R1 兼容新增，R2 语义/行为，R3 权限、安全和核心契约。Fork PR 不提供密钥，不能用未经审查的贡献代码配合高权限 Token 运行。

## AGENTS.md 硬规则

禁止编造工具执行、Evidence、人工审批和 Eval 结果；禁止测试未授权目标；Q9 回归交接不得写测试代码；变更契约必须附 TDD/Eval；不得依赖外部 QA Skill；保留 Finding 与 Evidence 历史版本；无法强制工具安全边界时降级 Guided/Assisted。

许可证需在正式公开前确定；复用外部内容按来源单独核查，不直接复制 third-party comparator project 的大段内容。
