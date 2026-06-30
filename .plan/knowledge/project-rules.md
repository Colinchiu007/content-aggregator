---
name: content-aggregator-v2-rebuild
scope: 所有涉及 content-aggregator backend/ 目录的任务
rules:
  - 使用 `backend/tests/conftest.py` 中的测试基础设施：async_client fixture（mock DB）、make_token、sample_user_id
  - 测试风格参照 `backend/tests/test_monitors.py`：Class 组织、mock DB、@pytest.mark.asyncio、assert 状态码 + 响应体字段
  - FUSE 警告：D:\Data\projects\ 下文件禁止 Write/Edit 工具写入。使用 Python heredoc 写入文件，然后 ast.parse 验证
  - content-aggregator 是一个 git 仓库，所有改动需通过 /tmp 克隆进行（见 fuse-git-index-corruption 记忆）
  - .clinerules: 采集来源配置通过环境变量管理；AI 改写使用 HotRewrite v2 引擎；改写结果需质量评分
---
