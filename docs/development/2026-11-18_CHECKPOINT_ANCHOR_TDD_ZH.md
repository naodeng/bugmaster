# Checkpoint Journal 锚点核验 TDD 记录

**日期：** 2026-11-18
**工作流 / 义务：** W6 安全恢复；`TDD-FS-003`
**风险：** R3（恢复完整性安全关键；独立安全审查尚未提供）
**状态：** Journal 前缀锚点核验已实现并通过本地自动化测试；Checkpoint 文件持久化与 Safe Resume 未实现；BLK-03 未关闭。

## 需求与 Oracle

已提交的 `checkpoint.schema.json` 将 Checkpoint 绑定到 Journal 序号与头部哈希。恢复时必须能确定该锚点对应当前 append-only Journal 的有效前缀。Oracle 来自 `docs/en/03-contracts.md` 的 Checkpoint invariant 与 `docs/zh-CN/03-contracts.md` 的 Session/恢复约束。核验方法只验证 Journal 前缀完整性；它不验证 Session revision、Scope/审批真实性或剩余预算，也不执行恢复或派发。

验收用例：

- Happy：现存事件序号与 SHA-256 匹配；追加后仍能识别同一有效前缀。
- Negative：哈希不匹配、未来序号、非整数/负序号或无效摘要均返回拒绝。
- Edge：空 Journal 仅接受 `sequence=0`、`headHash=null`。

## RED

先在 `tests/unit/test_action_journal.py` 添加四个行为用例，尚未添加运行方法。执行：

```text
python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v
```

结果：exit 1；33 项测试运行，新加锚点用例因 `ActionJournal.matches_checkpoint_journal_anchor` 尚不存在而产生 7 个预期错误（一个参数化用例含 4 个 subtests）。

## GREEN

在 `ActionJournal` 增加 `matches_checkpoint_journal_anchor(sequence, head_hash)`：拒绝非法位置/摘要，重载并完整校验 Journal，比较指定前缀的真实事件哈希。完整 Journal 有损坏时沿用现有 fail-closed 异常。定向 Action Journal 测试 33/33 通过。

## REFACTOR

复核后保留独立窄方法，不把授权或预算恢复塞进 Journal；输入筛选、文件锁下 Journal 校验和摘要比较均显式完成。未发现可安全消除的重复逻辑，无额外结构改动。

## VERIFY

环境：macOS/POSIX；`python3.12` 为 3.12；默认 `python3` 为 3.9.6。

| 检查 | 命令 / 结果 |
|---|---|
| 定向 Journal | `python3.12 -m unittest discover -s tests/unit -p 'test_action_journal.py' -v`：33/33 PASS |
| 全单元 Python 3.12 | `PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core -m unittest discover -s tests/unit`：60/60 PASS |
| 全单元 Python 3.9 | `python3 -m unittest discover -s tests/unit -q`：60/60 PASS |
| 生产代码行/分支覆盖 | `python3.12 -m coverage report --fail-under=100`：446/446 语句、206/206 分支，100%/100% |
| 全契约 | `PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：63/63 PASS |
| 品牌 / Catalog | `scripts/check_branding.py`、`scripts/validate_catalog.py`：PASS |
| Benchmark Manifest | `scripts/validate_benchmark.py`：结构 PASS，场景未执行 |
| Release Gate | exit 1 / No-Go：功能清单未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 证据缺失 |

`matches_checkpoint_journal_anchor()` 证明给定序号/摘要是当前完整 Journal 的前缀，不证明 Checkpoint 内容真实或获授权。Session revision 的不可变存储、Checkpoint 持久化与原子指针切换、审批/预算恢复核验、八断点故障注入、可信只读验证器和双宿主仍未完成。整体 Release 维持 No-Go，R3 独立安全 Review 待办。
