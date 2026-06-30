---
scope: task_2-5 (test 恢复)
rules:
  - 使用 conftest.py 的 async_client fixture: `client, mock_db = await anext(async_client)` — 注意 async_client 是 AsyncGenerator，需用 `anext()` 或 `async for` 或 `@pytest_asyncio.fixture` fixture 注入
  - 实际上在 test 类中使用 fixture 方式：看 test_monitors.py 的用法 — `def setup_mocks(self, async_client)` 然后在方法中 `self.client, self.mock_db = self.client, self.mock_db`
  - 注意 async_client fixture 返回的是 tuple: `(client, mock_session)`，其中 client 是 httpx.AsyncClient，mock_session 是 MagicMock
  - 所有 test_api 下的测试文件使用 mock DB（不连真实数据库）
  - 每个测试至少覆盖：成功路径 200/201 + 错误路径 401/404/422 + 边界情况
  - 统一用 `@pytest.mark.asyncio` 装饰器（即使 conftest 设置了 asyncio_mode=auto）
---
