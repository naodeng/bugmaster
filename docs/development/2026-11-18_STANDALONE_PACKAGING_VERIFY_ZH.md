# 11 个 Skill Standalone 打包验证记录

**日期：** 2026-11-18
**Workstream：** W2 Portable Skills
**验证范围：** 离线构建、Skill 文件存在、Registry 声明的 Pattern 闭包、manifest 文件摘要。

## 执行

将 Registry 中 11 个 Skill 分别构建到 `/private/tmp/bugmaster-standalone-smoke/<skill>`。对每个输出核验：

- 根目录存在 `SKILL.md`；
- `manifest.json` 中的 Skill ID 与 Registry 相同；
- manifest 的 Pattern ID 列表与 Registry 一致；
- 构建目录中实际 `pattern.json` 集合与声明闭包一致；
- manifest 收录的每个文件 SHA-256 与构建后实际字节一致。

结果：11/11 个 Skill 均通过。每个包包含 2–8 个已摘要文件，Pattern 数量按 Registry 配置分布为 0–3。

已将离线回归加入 `tests/contracts/test_standalone_bundle.py`；`python3.12 -m unittest discover -s tests/contracts -p 'test_standalone_bundle.py' -v`：PASS，1/1。

## 限制

此验证只证明本地生成的目录闭包和 manifest 自洽，不证明 Codex 或 Claude Code 能干净安装/调用，也不验证 Skill 的真实缺陷发现质量。两宿主兼容和 Eval 仍为 W10/W9 待办；未发布或推送代码。
