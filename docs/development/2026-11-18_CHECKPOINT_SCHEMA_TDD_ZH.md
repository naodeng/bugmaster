# Checkpoint Schema TDD 记录

**日期：** 2026-11-18
**工作流 / 义务：** W1 契约、W6 安全恢复；`TDD-CON-013`
**风险：** R2（本次是结构契约；恢复写入、指针切换和授权重核验仍需 R3 安全审查）
**状态：** Schema 与契约测试已验证；Checkpoint 持久化和 Safe Resume 未实现；BLK-03 未关闭。

## 需求与 Oracle

Checkpoint 必须指向一个正整数 Session revision 和 Scope revision，并绑定 Journal 的序号与头部哈希。空 Journal 允许使用 `sequence=0` 且 `headHash=null`；非空 Journal 必须提供 SHA-256 头部摘要。此结构来源于 `docs/en/03-contracts.md` 的 Checkpoint invariant、`docs/zh-CN/03-contracts.md` 的 Session/恢复约束，以及冻结的 Q13。哈希只证明记录完整性，不能证明真实性或恢复授权。恢复仍必须核验所引用的 Session/Journal、当前授权和剩余预算。

验收用例：

- Happy：非空 Journal Checkpoint 正确绑定 Session revision、Scope revision 与 Journal head。
- Negative：非空 Journal 缺 hash、空 Journal 携带 hash、非法摘要、非法时间、非正 Session revision 和自称 `approved` 等未定义授权字段均被拒绝。
- Edge：尚无 Journal 事件时，`sequence=0` 与 `headHash=null` 可通过。

## RED

先添加 `tests/contracts/test_checkpoint_schema.py`，尚未添加 Schema。执行：

```text
PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -p 'test_checkpoint_schema.py' -v
```

结果：exit 5，`setUpClass` 因缺少 `schemas/checkpoint.schema.json` 失败（预期 RED，0 项断言运行）。失败原因是契约文件不存在。

## GREEN

新增 `schemas/checkpoint.schema.json`，仅实现上述结构、时间格式与空/非空 Journal 锚点约束。实现后定向命令 6/6 通过。

## REFACTOR

统一 SHA-256 格式为 `$defs/sha256`，将 revision、Journal 锚点、日期时间及额外字段拒绝拆成独立可读断言；未增加恢复执行行为。最终定向执行 8/8 通过。

## VERIFY

环境：macOS/POSIX，Python 3.12；`jsonschema[format-nongpl]==4.26.0` 位于 `/private/tmp/bugmaster-jsonschema`。

| 检查 | 命令 / 结果 |
|---|---|
| 全单元 | `python3.12 -m unittest discover -s tests/unit -v`：56/56 PASS |
| 全契约 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts -v`：63/63 PASS |
| 品牌 | `python3 scripts/check_branding.py`：PASS |
| Catalog | `python3 scripts/validate_catalog.py`：PASS |
| Benchmark Manifest | `python3 scripts/validate_benchmark.py`：结构 PASS，50 个场景未执行 |
| Release Gate | exit 1 / No-Go：功能清单未冻结、业务覆盖率未超过 60%、核心 Happy/Negative/Edge 证据缺失 |
| Diff 空白 | `git diff --check`：PASS |

本轮未修改生产 Python 代码。契约通过不代表 Checkpoint 已持久化，也不代表 Journal 前缀匹配、Scope/审批真实性、预算保留或崩溃恢复安全。Session revision 存储、Checkpoint 原子写入/指针恢复、八断点注入、可信只读核验和双宿主验证仍待实现；Release 保持 No-Go。独立 QR/SR 审核尚未提供。
