# 参与 BugMaster 开发

[English](CONTRIBUTING.md) · [开发规范](docs/development/DEVELOPMENT_PLAYBOOK_ZH.md)

**所有开发过程文档、PR 说明、缺陷排查记录与 TDD 证据使用中文。** 技术/产品公开文档英文默认，提供中文互链。

必须遵循 **RED → GREEN → REFACTOR → VERIFY**：提交前先写能失败的测试，记录 Red 执行证据；最小实现直至 Green；重构时回归；最终执行覆盖率、功能完整性及安全门禁。PR 模板必须填写实际执行命令、结果及对应任务/需求 ID。

**质量门槛：单元代码行覆盖率 100%；业务功能实测覆盖率 >60%；每个核心功能至少 Happy、Negative、Edge 各一条真实场景。** 未执行及缺证据不能计入覆盖率。

Q15：每个 PR 做 Codex 代码扫描；R2/R3 变更还做安全扫描。项目所有者查看结果后手动合并，不要求独立真人 PR 签署。公开 Release 仍按 Q16 由两名不同人员授权。
