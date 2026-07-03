# content-aggregator — 测试规范

## TDD 流程

```
RED   → 在 backend/tests/ 下写失败测试（ASGITransport 模拟请求）
GREEN → 最小实现让测试通过
REFACTOR → 重构，保持测试通过
```

### 测试规范

```python
# backend/tests/test_api/
async def test_collect_url(async_client):
    resp = await async_client.post("/api/v1/collect/url", json={"url": "https://example.com"})
    assert resp.status_code == 200
    assert "title" in resp.json()

async def test_rewrite(async_client):
    resp = await async_client.post("/api/v1/rewrite/", json={
        "content": "原始内容", "style": "轻松易懂"
    })
    assert resp.status_code == 200
```

