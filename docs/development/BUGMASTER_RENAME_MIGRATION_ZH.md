# BugMaster 名称迁移记录（开发过程中文）

## 定稿规则

- 对外统一品牌为 **BugMaster（Bug 大师）**，仓库 `AI-Native-QA-Lab/bugmaster`。
- 所有 11 个 Skill 的公开目录名、`SKILL.md` frontmatter、调用示例、Registry capability ID 与测试引用，统一采用 Discovery / Validation / Reporting 语义。
- 本项目尚未对外正式发布这些 Skill，因此不保留旧 Skill ID 或运行别名。
- 稳定 Pattern 编号（例如 `BP-API-002`）、ADR/Q 编号和 Finding 业务标识继续保留。
- 运行目录 `.bugmaster/`、Python 模块 `bugmaster_core`、发布包 `bugmaster-bundle`。
- 任何旧品牌词或旧 Skill 前缀重新出现均应由 `scripts/check_branding.py` 拦截。
- 开发过程文档全中文；正式技术文档英文默认，中文互链。

## 验收

运行 `python scripts/check_branding.py`、`python scripts/validate_catalog.py`、`python -m unittest discover -s tests/unit -v` 和 `python -m unittest discover -s tests/contracts -v`，并检查 11 个 Skill 目录及其安装闭包。
