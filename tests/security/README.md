# Security tests

[简体中文](README.zh-CN.md)

This suite covers security invariants for R2/R3 behavior. Run it with
`python -m unittest discover -s tests/security -v`; CI executes it alongside
unit and contract tests. Checkpoint storage tests verify fail-closed behavior
when persisted directory permissions are weakened.
