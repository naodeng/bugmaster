# W6 Checkpoint 持久化 TDD 记录

**日期：** 2026-11-19

**Workstream / 义务：** W6-01 Checkpoint Persistence；`F-RECOVERY`；`TDD-ACT-005`

**风险：** R3；合并前需要独立 Security Reviewer。

**实现提交：** `ba8bc6a37d973af720519e200fb8fbdcb0e0b606`；草稿 PR [#4](https://github.com/naodeng/bugmaster/pull/4)，以 SessionStore PR #3 的 `codex/session-revision-store` 为 base，尚未合并。

## Oracle 与范围

沿用 `schemas/checkpoint.schema.json` 和 `docs/zh-CN/03-contracts.md` 的 Checkpoint identity/binding 结构。Store 按 Checkpoint ID 保存单独、不可覆盖的记录；写入使用版本化 Schema validator；读取需校验 Session 身份、记录格式、权限和 ID 绑定；并发写入通过每 Session 锁序列化。

本切片只持久化结构记录，不确认被引用的 Session revision、Scope revision 或 Journal head 是否存在或真实；不更新 Session 的 `checkpointRefs`，不校验 Journal 前缀，不做预算/授权核验，也不批准恢复。它不构成 BLK-03、Safe Resume 或 exactly-once 完成证据。使用 POSIX 文件锁；Windows 尚未验证。

## RED

首轮先增加 8 项 `tests/unit/test_checkpoint_store.py` 单测和 2 项 `tests/contracts/test_checkpoint_schema.py` 集成测试。运行后 8 项单测和 2 项契约测试均因 `bugmaster_core.checkpoint_store` 不存在而失败。

写入实现后，审查发现读取逻辑先用 `Path.exists()` 判断 Checkpoint 目录；悬空符号链接因此被当成“无记录”。增加 `test_read_fails_closed_when_checkpoint_directory_is_dangling_symlink` 后先失败（期望 `CheckpointCorruptionError`、实际没有抛错），证明读取边界有漏洞。

第一次 GREEN 测试运行还发现并发用例的断言引用了未定义变量 `store`。这是测试本身的 NameError，不作为实现通过证据；将断言改为读取 `first_store` 后，重新运行 19 项单测全部通过。

## GREEN / REFACTOR

- 新增 `bugmaster_core.checkpoint_store.CheckpointStore`；要求调用方传入 Checkpoint Schema validator；Session ID 和 Checkpoint ID 都经 SHA-256 映射后用于本地路径。
- 每个 Session 的 `checkpoints/` 目录使用 `0700`，Checkpoint 文件和共享 Session lock 使用 `0600`。不更改调用方根目录权限。
- Checkpoint 与 SessionStore 共用相同的 Session lock 路径，避免两个存储器并行更新同一 Session 目录。通过同步临时文件、`fsync` 和不覆盖硬链接发布；重复 Checkpoint ID 被拒绝。
- 读取拒绝悬空/有效目录符号链接、文件符号链接、错误文件类型/权限、超限、截断、非法或非规范 JSON、Schema 错误和文件名 ID 不匹配。

## VERIFY

环境：macOS/POSIX；Python 3.12；coverage.py 7.13.3；契约测试使用 `jsonschema[format-nongpl]==4.26.0`（`/private/tmp/bugmaster-jsonschema`）。测试依赖仅位于 `/private/tmp`，不是 BugMaster 运行时依赖。

| 检查 | 命令 / 结果 |
|---|---|
| CheckpointStore 单元 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/unit -p 'test_checkpoint_store.py' -v`：19/19 PASS |
| 全单元 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-coverage python3.12 -m coverage run --branch --source=bugmaster_core --data-file=/private/tmp/bugmaster-checkpoint-full.coverage -m unittest discover -s tests/unit`：111/111 PASS |
| 全契约 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/bugmaster-jsonschema python3.12 -m unittest discover -s tests/contracts`：77/77 PASS |
| 行覆盖率 | `/private/tmp/bugmaster-checkpoint-full-coverage.json`：`bugmaster_core` 939/939 行，100%；`checkpoint_store.py` 187/187 行，100% |
| 分支覆盖率 | `bugmaster_core` 384/384（100%）；`checkpoint_store.py` 60/60（100%）。分支与行覆盖率分别测量 |
| Catalog / Benchmark / 品牌 | `scripts/validate_catalog.py` PASS；`scripts/validate_benchmark.py` 结构 PASS（场景未执行）；`scripts/check_branding.py` PASS |
| Release 门禁 | `python3.12 scripts/quality_gate.py --mode release --coverage /private/tmp/bugmaster-checkpoint-full-coverage.json`：No-Go，Feature Inventory 未冻结、真实业务覆盖未超过 60%、核心 Happy/Negative/Edge 缺少执行证据 |
| GitHub Actions | [Run 44446002412](https://github.com/naodeng/bugmaster/actions/runs/44446002412)：最终代码提交 `ba8bc6a37d973af720519e200fb8fbdcb0e0b606`，结论 success，所有步骤通过 |
| Diff 空白 | `git diff --check`：PASS |

## 未覆盖能力

没有验证 Checkpoint 与 SessionStore 中实际 Session revision 的一致性，没有核对 Checkpoint Journal head 对应的真实事件前缀，没有从 Checkpoint 恢复状态，也没有重新授权或预算对账。未运行崩溃断点注入、长时间多进程竞争、Windows、真实 API/Browser、双宿主或 50 个 Benchmark 场景。整体 Release 维持 **No-Go**；R3 变更需独立安全审查后再合并。

## 交叉审核修复（PR #4）

### RED

新增 `tests/unit/test_checkpoint_store.py` 用例，先对原实现运行：22 项中 3 项失败，分别证实读取会沿 `sessions/` 符号链接访问另一存储根、只读锁文件不能按只读方式读取且读取会改权限、构造后切换工作目录会改变相对根路径解析。

### GREEN / REFACTOR

- `CheckpointStore` 在构造时将根路径转为绝对路径，避免进程工作目录变化后存储身份漂移。
- 只读路径对根目录、`sessions/`、Session 目录和 `checkpoints/` 使用 `lstat` 校验；拒绝软链接及非目录路径。共享锁以只读方式打开并使用 `LOCK_SH`，不创建锁文件，也不更改其权限；写入路径仍以独占锁串行化并设置私有权限。
- 手工构造损坏存储的测试夹具现在显式创建 Session 锁文件，保持测试符合持久化布局。

### VERIFY

实现提交：`af9a92c059eccaf0ffb3e2dac607b29a0ff2b848`。修复后证据：CheckpointStore 定向测试 22/22 PASS；全单元 127/127 PASS；全契约 77/77 PASS；`bugmaster_core` 行覆盖 1017/1017（100%）、分支覆盖 414/414（100%）；`git diff --check` PASS。运行环境为 macOS/POSIX、Python 3.12.16、coverage.py 7.13.3、`jsonschema[format-nongpl]==4.26.0`，测试依赖安装于 `/private/tmp/bugmaster-review-venv`。本次没有新增安全测试目录或报告；Release 门禁仍按上文记录为 No-Go。
