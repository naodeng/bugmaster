[English](README.md)

# 安全测试

本目录覆盖 R2/R3 行为的安全不变量。运行命令：
`python -m unittest discover -s tests/security -v`；CI 会与单元和契约测试分开执行本套件。Checkpoint 持久化测试验证目录权限被放宽后读取会失败关闭。
