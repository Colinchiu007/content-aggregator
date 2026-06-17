# API Key 更新记录 - 2026-06-10

## 目标
更新 `config.yaml` 中 `deepseek-v4` 模型的 API Key 为新的加密值。

## 操作步骤

### 1. 加密明文 Key
- 用户提供明文 API Key：`sk-ebc59537890a49b3a86aabef1ba1b8c7`
- 运行 `python encrypt_api_key.py`
- 加密密钥：`FBKt8yK3y9_N0kuh4PGpxVK7T5gW9BKp2f-CFfTbg6M=`
- 加密结果：`enc:gAAAAABqKS9836hJK5Lj7TN5Rx1bgA0r5DwtVXsQ6vOtN05MGXZ05d7ZCtUPTAWq15-KOEQjHI7XfnQcZsGei0hFbSzZGtpQhWKsQXfGJpXYD5aQq7z-ZJvjnisirxotYAWC2LlZto7u`

### 2. 更新 config.yaml
- 文件：`C:\Users\邱领\.qclaw\workspace\content-aggregator\config\config.yaml`
- 位置：`llm.models[]` 中 `id: deepseek-v4` 的 `api_key` 字段
- 原值：`enc:Z0FBQUFBQnFLU09QWWFiUE9vX0lqYzh5Qjcwa0h6UG51WmFUOVA0X3NaQW5ZdWUwaGpPanZxSmxMYlo5OXZPWFdfUWYwblB5WEljRnJURjEySE9iZFU3dWZKRjVCUXVmQnJGdGgxcHZQSWYyOFk1TXBFNVFiSDJkWlV2ZURkUVU5cUZsS1hvUUdidEI=`
- 新值：`enc:gAAAAABqKS9836hJK5Lj7TN5Rx1bgA0r5DwtVXsQ6vOtN05MGXZ05d7ZCtUPTAWq15-KOEQjHI7XfnQcZsGei0hFbSzZGtpQhWKsQXfGJpXYD5aQq7z-ZJvjnisirxotYAWC2LlZto7u`

### 3. Git 提交与推送
- Commit：`3491a57` - `fix(llm): 更新 deepseek-v4 API Key 加密配置`
- 推送成功到 `origin/main`

### 4. 环境变量设置
- 用户级环境变量：`CONTENT_AGGREGATOR_ENC_KEY=FBKt8yK3y9_N0kuh4PGpxVK7T5gW9BKp2f-CFfTbg6M=`
- 新终端自动生效

### 5. 重启服务器
- 杀掉占用端口 8080 的进程（PID 22792）
- 启动成功：`http://127.0.0.1:8080`
- WebSocket 连接已建立

## 结论
- ✅ API Key 已加密并更新到 `config.yaml`
- ✅ 环境变量已配置
- ✅ 服务器已重启，可以测试改写功能

## 待验证
- [ ] LLM 改写功能是否正常（不再返回 401 Authentication Error）
- [ ] 推理模型输出是否正常（SenseNova-6.7 Flash Lite）
- [ ] YouTube 采集功能
