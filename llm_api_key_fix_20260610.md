# LLM API Key 修复记录 - 2026-06-10

## 问题

改写时报错：`LLM API key is required`

**时间**：2026-06-10 18:06 (GMT+8)

## 根因分析

### 配置文件结构

`config.yaml` 中 API Key 只在 `llm.models[]` 里配置（每个模型单独加密），**顶层 `llm.api_key` 不存在**。

`llm_client.py` 的 `_normalize_config()` 会正确提取默认模型的 `api_key`，所以配置读取没问题。

### 真正的问题：`_decrypt_key()` 返回 `None`

`llm_client.py` 第 122 行：

```python
self.api_key = self._decrypt_key(raw_key) if raw_key else ""
```

当 `_decrypt_key()` 解密失败时（环境变量 `CONTENT_AGGREGATOR_ENC_KEY` 未设置，或密钥错误），它返回 `None`。

然后 `self.api_key = None`。

在 `__init__()` 里没有二次检查，导致后续 API 调用时 `if not self.api_key:` 为 `True`，触发错误。

## 修复

**文件**：`src/content_aggregator/clients/llm_client.py`

**第 122 行**，将：

```python
self.api_key = self._decrypt_key(raw_key) if raw_key else ""
```

改为：

```python
self.api_key = self._decrypt_key(raw_key) or ""
```

`None or ""` 返回 `""`，确保 `self.api_key` 永远是字符串（不会是 `None`）。

## 提交

- **Commit**: （待用户执行 `git commit`）
- **Message**: `fix(llm_client): _decrypt_key 失败时返回空字符串而非 None`
- **Push**: `git push origin main`

## 验证步骤

1. **新开 PowerShell 窗口**（加载 `CONTENT_AGGREGATOR_ENC_KEY` 环境变量）
2. 执行 `cd C:\Users\邱领\.qclaw\workspace\content-aggregator`
3. 杀掉旧进程：`Get-Process python | Stop-Process -Force`
4. 启动服务器：`python start_server.py`
5. 看到 `Uvicorn running on http://127.0.0.1:8080` 后，测试改写功能

## 其他注意事项

### 环境变量 `CONTENT_AGGREGATOR_ENC_KEY`

- **用户级**：设置后新开 PowerShell 窗口自动加载
- **当前窗口**：需要重启 PowerShell 才能生效
- **验证**：`Get-ChildItem Env: | Where-Object {$_.Name -eq "CONTENT_AGGREGATOR_ENC_KEY"}`

### `config.yaml` 中的加密 Key

- `deepseek-v4` 的 `api_key` 已更新为新的加密值（commit `3491a57`）
- 加密密钥：`FBKt8yK3y9_N0kuh4PGpxVK7T5gW9BKp2f-CFfTbg6M=`
- 明文 Key：`sk-ebc59537890a49b3a86aabef1ba1b8c7`

### 如果还是 401 错误

1. 检查环境变量是否生效（新开 PowerShell 窗口）
2. 检查 `llm_client.py` 的 `_decrypt_key()` 方法是否被正确调用
3. 查看服务器日志 `server.log` 中的 `LLMClient` 初始化信息

---

*由 CEO (QClaw) 记录，2026-06-10 18:15*
