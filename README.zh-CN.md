# BugMaster（Bug 大师）

**面向人工智能（AI）智能体的证据驱动探索式测试技能包**

[English](README.md) · [产品基线](PRODUCT.zh-CN.md) · [中文开发手册](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md)

> 当前是开发工程包，**不是经过真实探索验证的正式版本**。

BugMaster 的目标是为**已授权**的 API（应用程序接口）和 Web（网络）应用提供证据驱动的探索式测试技能包。目前本地已实现从 OpenAPI 3（开放 API 规范）JSON（数据交换格式）生成带来源的功能清单；URL（统一资源定位符）/Browser（浏览器）动态发现、风险驱动执行和自治端到端测试尚未实现或验证。**URL 不构成执行授权**；Android/iOS（安卓/苹果移动系统）仅预留，不支持自动执行。

W7（第七条工作流）现在具备 Candidate（候选记录）和 Finding（缺陷记录）的版本化 Schema（数据结构规则）及私有本地元数据持久化。修订记录保存标识、引用和摘要，不提供 Evidence Blob（证据原件字节）字段或存储服务。存储不会检查叙述字段是否含有原始或 Base64（文本编码格式）证据；调用方必须避免把这类内容写入自由文本。该存储只检查本地结构与完整性，不认证证据来源或审核人身份，也没有接入可信工作流或缺陷确认门禁。

W1-02（第一条工作流第 2 项）新增 `bugmaster_core.contract_binding.validate_contract_bindings()`，先校验 Scope（授权范围）、Action（动作）和 Approval（审批）Schema（数据结构规则），再检查记录间引用与字段绑定。结果只说明记录是否一致；不认证审批来源、不授予动作权限，也不开放派发。

W1-03（第一条工作流第 3 项）新增共享本地 Schema（数据结构规则）加载器 `bugmaster_core.schema_registry`，供契约绑定校验和 Candidate/Finding（候选记录/缺陷记录）存储使用。它要求每份 Schema 声明固定的主版本号与次版本号、检查 Schema ID（规则标识）不重复，并在封闭的本地注册表中解析全部 `$ref`（引用）；引用目标必须是有效的对象 Schema 或布尔 Schema，不会从网络下载 Schema。

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
