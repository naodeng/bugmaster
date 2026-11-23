# BugMaster（Bug 大师）

**面向 AI Agent 的证据驱动缺陷发现 Skills**

[English](README.md) · [产品基线](PRODUCT.zh-CN.md) · [中文开发手册](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md)

> 当前是开发工程包，**不是经过真实探索验证的正式版本**。

BugMaster 的目标是为**已授权**的 API 和 Web 应用提供证据驱动的探索测试 Agent Skills。目前本地已实现从 OpenAPI 3 JSON 生成带来源的功能清单；URL/Browser 动态发现、风险驱动执行和自治端到端测试尚未实现或验证。**URL 不构成执行授权**；Android/iOS 仅预留，不支持自动执行。

W7（第七条工作流）的 Oracle（预期行为判定依据）与 Evidence（证据）数据层会校验版本记录、证据制品摘要，以及对本地 Action Journal（动作日志）结果事件的引用。它只检查内容完整性和本地绑定关系，不认证来源、不持久化 Finding（缺陷记录），也不会解锁缺陷确认。

## 目标安装方式（尚未验证）
```bash
# 仓库已存在；正式发布和宿主验证通过前不宣称此安装路径可用。
npx skills add https://github.com/AI-Native-QA-Lab/bugmaster -g -a codex
```

## 当前开发者本地验证
```bash
python3.12 -m pip install coverage==7.13.3 'jsonschema[format-nongpl]==4.26.0'
python3.12 -m unittest discover -s tests/unit -v
python3.12 -m unittest discover -s tests/contracts -v
python3.12 scripts/discover_openapi.py examples/openapi/orders.json --source-ref examples/openapi/orders.json
python3.12 scripts/validate_catalog.py
python3.12 scripts/validate_benchmark.py
```

## 项目资料
[Bug 判定规则](docs/zh-CN/11-bug-judgment-rules.md) · [范围与报告](docs/zh-CN/12-scope-surfaces-and-reporting.md) · [强 TDD 与验收](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md) · [质量门禁](docs/development/QUALITY_GATE_POLICY_ZH.md) · [真实进度](docs/development/IMPLEMENTATION_STATUS_ZH.md)

**[查看完整最终开发规范（中文）](docs/development/BUGMASTER_FINAL_MASTER_SPEC_ZH.md)**

## Codex 开发入口
- [完整开发主提示词](docs/development/CODEX_FULL_IMPLEMENTATION_PROMPT_ZH.md)
