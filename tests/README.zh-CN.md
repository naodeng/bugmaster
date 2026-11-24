# 测试目录说明

English version：[README.md](README.md)。

`unit`（单元测试）负责维护 `bugmaster_core/` 和 `scripts/` 中的生产 Python 代码。当前范围要求行覆盖率达到 100%；分支覆盖率单独统计和报告。

`functional`（功能测试）按实际运行证据计算已验证功能占批准功能清单的比例。比例必须严格大于 60%。每个核心功能都要有 Happy（成功）、Negative（失败）和 Edge（边界）场景，并提供真实执行证据。

`contracts`（契约测试）、`integration`（集成测试）、`e2e`（端到端测试）、`security`（安全测试）和 `eval`（评测）只有在真实执行后才能标记为通过。空测试目录不代表工作已完成。

JSON Schema（JSON 数据结构规则）契约测试使用 Python 3.12 和固定版本 `jsonschema[format-nongpl]==4.26.0`，以实际检查日期时间格式。Candidate（候选记录）/Finding（缺陷记录）元数据存储的默认校验器也依赖该库。GitHub Actions（自动化工作流）在 `contract.yml` 中安装固定依赖。

Action Journal（动作日志）单元测试使用真实临时文件，覆盖先写后执行、重启后阻断、结果对账、哈希校验和截断日志时失败关闭。Candidate/Finding 存储测试使用真实私有临时目录，覆盖不可变版本、锁文件创建竞争、完整性摘要和不安全文件系统项。
