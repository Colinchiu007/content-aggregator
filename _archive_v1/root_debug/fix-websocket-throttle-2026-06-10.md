# WebSocket 节流修复 - 2026-06-10

## 问题描述

YouTube 采集去重误过滤问题 + WebSocket 进度回调无节流导致前端卡死。

## 根本原因

1. **WebSocket 进度回调无节流**：`progress_callback` 频繁调用 `broadcast_ws()`，导致 WebSocket 消息洪泛，前端卡死
2. **pipeline dedup 配置结构不匹配**：`config.yaml` 中配置项名称错误（已修复）

## 修复内容

### 1. 添加 `broadcast_ws` 函数（带节流）

**文件**: `web/server.py`

**位置**: 在 imports 之后（约第 70 行）

**新增代码**:
```python
# WebSocket 连接列表
ws_connections: list[WebSocket] = []

# WebSocket 广播节流控制
_last_ws_broadcast = 0
_WS_THROTTLE_MS = 1000  # 1秒节流

async def broadcast_ws(message: dict):
    """广播消息到所有 WebSocket 连接（带节流）"""
    global _last_ws_broadcast
    import time
    now = time.time() * 1000  # 转换为毫秒
    if now - _last_ws_broadcast < _WS_THROTTLE_MS:
        return  # 节流：跳过本次广播
    _last_ws_broadcast = now
    
    disconnected = []
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in ws_connections:
            ws_connections.remove(ws)
```

**节流逻辑**:
- 使用 `_last_ws_broadcast` 记录上次广播时间戳
- 如果距离上次广播不足 1 秒，直接返回（跳过）
- 否则更新时间戳并广播

### 2. 验证 `config.yaml` dedup 配置

**文件**: `config/config.yaml`

**当前配置**:
```yaml
filter:
  dedup:
    enabled: false
```

**代码读取方式** (`src/content_aggregator/workflows/pipeline.py` 第 92 行):
```python
dedup_config_dict = self.filter_config.get("dedup", {})
dedup_enabled = dedup_config_dict.get("enabled", True)  # 默认 True
```

**结论**: 配置结构正确，`enabled: false` 会禁用去重。

## 测试建议

1. 重启 Web 服务器：`python scripts/web.py`
2. 触发 YouTube 采集任务
3. 观察前端进度更新是否流畅（应每 1 秒更新一次，而不是每次进度变化都更新）
4. 检查 `task_manager.update()` 是否正常工作（任务状态、进度、消息）

## 影响范围

- **前端**: 进度条更新更流畅，不会卡死
- **后端**: WebSocket 广播频率降低（最多 1 次/秒）
- **所有采集端点**: 由于 `broadcast_ws` 是统一函数，所有调用者都受益

## 后续优化建议

1. **考虑在 `task_manager.update()` 中添加节流**：目前 `task_manager.update()` 每次都被调用，但只有 `broadcast_ws` 被节流。如果 `task_manager.update()` 有性能问题，也可以添加节流。
2. **考虑使用 WebSocket 二进制协议**：目前发送 JSON 文本，如果消息量大，可以考虑 MessagePack 或 Protobuf。

---

**修复人**: QClaw (CEO)
**修复时间**: 2026-06-10 23:05
**状态**: ✅ 已完成
