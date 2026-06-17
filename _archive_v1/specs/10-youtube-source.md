# YouTube 数据源详细规格

> 版本: 1.0.0  
> 最后更新: 2026-05-27  
> 状态: 基于 `collectors/youtube_collector.py` 反向工程

---

## 1. 概述

### 1.1 功能定位

YouTube Collector 通过 **YouTube Data API v3** 采集视频元数据，并可选提取**字幕文本**作为正文内容。

**核心能力**:
- 采集频道最新视频列表
- 采集播放列表视频
- 关键词搜索视频
- 提取视频字幕（自动/手动）
- 无字幕时 fallback 到视频描述

### 1.2 数据流转

```
YouTube API → _fetch() → 视频元数据 → 字幕提取（可选） → SourceResult
```

---

## 2. 配置规格

### 2.1 config.yaml 配置

```yaml
# config.yaml
sources:
  youtube:
    api_key: "AIzaSyA..."           # YouTube Data API Key（必需）
    channel_id: "UC..."               # 频道 ID（可选，二选一）
    playlist_id: "PL..."              # 播放列表 ID（可选，二选一）
    search_query: "AI tutorial"       # 搜索关键词（可选，二选一）
    order: "date"                    # 排序：date/viewCount/relevance
    max_results: 20                  # 最大采集数量
    fetch_transcript: true           # 是否提取字幕（默认 true）
    llm_config:                      # 无字幕时 LLM 识别配置（可选）
      api_key: "sk-..."
      model: "deepseek-chat"
      base_url: "https://api.deepseek.com"
```

### 2.2 环境变量

| 变量名 | 说明 | 优先级 |
|--------|------|----------|
| `YOUTUBE_API_KEY` | YouTube Data API Key | 低于 config.yaml |
| `YOUTUBE_CHANNEL_ID` | 默认频道 ID | 低于 kwargs |
| `YOUTUBE_PLAYLIST_ID` | 默认播放列表 ID | 低于 kwargs |
| `YOUTUBE_SEARCH_QUERY` | 默认搜索关键词 | 低于 kwargs |

---

## 3. 采集模式

### 3.1 频道采集模式（默认）

**触发条件**: 提供 `channel_id`，不提供 `playlist_id` 和 `search_query`

**API 端点**: `GET https://www.googleapis.com/youtube/v3/search`

**参数**:
```python
params = {
    "part": "snippet",
    "channelId": channel_id,
    "type": "video",
    "order": "date",              # 按上传时间排序
    "maxResults": min(max_results, 50),
    "key": api_key,
}
```

**返回字段**:
- `items[].id.videoId` → `video_id`
- `items[].snippet.title` → `title`
- `items[].snippet.description` → `content`（无字幕时）
- `items[].snippet.publishedAt` → `published_at`
- `items[].snippet.thumbnails` → `metadata.thumbnails`
- `items[].snippet.channelTitle` → `author`

### 3.2 播放列表采集模式

**触发条件**: 提供 `playlist_id`

**API 端点**: `GET https://www.googleapis.com/youtube/v3/playlistItems`

**参数**:
```python
params = {
    "part": "snippet",
    "playlistId": playlist_id,
    "maxResults": min(max_results, 50),
    "key": api_key,
}
```

**用途**: 采集特定播放列表（如"AI 教程合集"）的所有视频。

### 3.3 关键词搜索模式

**触发条件**: 提供 `search_query`

**API 端点**: `GET https://www.googleapis.com/youtube/v3/search`

**参数**:
```python
params = {
    "part": "snippet",
    "q": search_query,
    "type": "video",
    "order": order,                   # date/viewCount/relevance
    "maxResults": min(max_results, 50),
    "key": api_key,
}
```

**排序方式**:
| `order` 值 | 说明 |
|--------------|------|
| `date` | 按上传时间（最新优先） |
| `viewCount` | 按播放量（热门优先） |
| `rating` | 按评分（高评分优先） |
| `relevance` | 按相关度（默认） |

---

## 4. 字幕提取规格

### 4.1 字幕来源优先级

```
1. 手动字幕（已翻译，如 zh-Hans / en）
   ↓ (失败)
2. 自动字幕（ASR，如 zh / en）
   ↓ (失败)
3. 视频描述（description）
```

### 4.2 支持的语言

**优先级列表** (`youtube_collector.py` 中定义):
```python
preferred_langs = [
    "zh",        # 中文（自动）
    "en",        # 英文（自动）
    "zh-Hans",  # 中文简体（手动）
    "zh-Hant",  # 中文繁体（手动）
    "en-US",     # 英文（手动）
    "en-GB",     # 英文英国（手动）
]
```

### 4.3 字幕提取实现

**依赖库**: `youtube-transcript-api`

**调用流程**:
```python
from youtube_transcript_api import YouTubeTranscriptApi

# 1. 获取字幕列表
transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

# 2. 查找指定语言的手动字幕
transcript = transcript_list.find_transcript([lang])
text = " ".join([seg["text"] for seg in transcript.fetch()])

# 3. 降级：自动字幕
transcript = transcript_list.find_generated_transcript([lang])
text = " ".join([seg["text"] for seg in transcript.fetch()])
```

### 4.4 字幕文本格式

**输出**: 纯文本字符串，空格连接所有段落

**示例**:
```
"大家好 欢迎回到我的频道 今天我们来聊聊 AI 大模型 ..."
```

**用途**: 作为 `content` 字段（改写器的输入）

---

## 5. 数据模型

### 5.1 输出格式（SourceResult.data[]）

```python
{
    "title": "视频标题",
    "content": "字幕文本或视频描述",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "author": "频道名称",
    "published_at": datetime(2026, 5, 27, 22, 0, 0),
    "summary": "视频描述前 500 字符",
    "tags": [],
    "source": "youtube",
    "metadata": {
        "video_id": "VIDEO_ID",
        "channel_id": "UC...",
        "thumbnails": {
            "default": {"url": "...", "width": 120, "height": 90},
            "high": {"url": "...", "width": 480, "height": 360},
        },
        "transcript_source": "subtitle" | "description",
    }
}
```

### 5.2 metadata 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `video_id` | str | YouTube 视频 ID（11 字符） |
| `channel_id` | str | 频道 ID（UC 开头） |
| `thumbnails` | dict | 缩略图 URL（多种尺寸） |
| `transcript_source` | str | 内容来源：`"subtitle"` 或 `"description"` |

---

## 6. 错误处理

### 6.1 常见错误

| 错误类型 | 原因 | 处理方式 |
|----------|------|----------|
| `EnvironmentError` | `api_key` 未配置 | 抛出例外，由 Pipeline 捕获 |
| `HTTPStatusError(403)` | API Key 无效或配额用尽 | 抛出例外，记录错误日志 |
| `HTTPStatusError(429)` | 请求频率超限 | 抛出例外，建议增加 `RATE_LIMIT` |
| `TranscriptNotFoundError` | 视频无字幕 | 降级使用描述 |
| `TranslationError` | 字幕翻译失败 | 使用原始字幕 |

### 6.2 优雅降级

```python
# youtube_collector.py 中的错误处理
try:
    transcript = await self._get_transcript(video_id)
    if transcript:
        content_text = transcript  # 字幕优先
    else:
        content_text = description  # 降级到描述
except Exception as e:
    logger.warning(f"[YouTube] 视频 {video_id} 字幕提取失败: {e}")
    content_text = description  # 降级到描述
```

---

## 7. 限流控制

### 7.1 默认限流

```python
class YouTubeCollector(BaseCollector):
    RATE_LIMIT = 3.0  # 请求间隔 3 秒
```

**理由**:
- YouTube Data API 免费配额：每天 10,000 单位
- 一次 search 请求消耗 100 单位
- 10,000 / 100 = 100 次请求/天（理论最大值）
- 实际应限制频率，避免耗尽配额

### 7.2 配额管理

**查看配额**: https://console.cloud.google.com/apis/credentials

**优化建议**:
- 使用 `playlistItems` 替代 `search`（消耗更少单位）
- 缓存视频元数据（避免重复请求）
- 使用 `fields` 参数限制返回字段

---

## 8. 使用示例

### 8.1 基本用法

```python
from content_aggregator.sources.collectors.youtube_collector import YouTubeCollector

# 1. 创建 Collector
collector = YouTubeCollector(
    api_key="AIzaSyA...",
    fetch_transcript=True,  # 提取字幕
)

# 2. 采集频道最新视频
import asyncio

async def main():
    result = await collector.collect(
        channel_id="UC_x5XG1OV2P6uZZ5FSM9Ttw",
        max_results=10,
    )
    
    if result.success:
        print(f"采集到 {result.collected_count} 个视频")
        for item in result.data:
            print(f"- {item['title']}")
    else:
        print(f"采集失败: {result.error}")

asyncio.run(main())
```

### 8.2 搜索视频

```python
result = await collector.collect(
    search_query="AI agent tutorial",
    order="viewCount",  # 按播放量排序
    max_results=20,
)
```

### 8.3 无字幕处理

```python
collector = YouTubeCollector(
    api_key="AIzaSyA...",
    fetch_transcript=False,  # 不提取字幕（只用描述）
)

result = await collector.collect(channel_id="UC...")
# content = description（视频描述）
```

---

## 9. 测试清单

- [ ] `api_key` 未配置 → 抛出 `EnvironmentError`
- [ ] 频道采集返回正确数量视频
- [ ] 播放列表采集返回正确数量视频
- [ ] 搜索采集返回相关视频
- [ ] 字幕提取成功（有字幕视频）
- [ ] 字幕提取失败 → 降级到描述
- [ ] API 403 错误 → 抛出例外
- [ ] API 429 错误 → 抛出例外
- [ ] 限流生效（请求间隔 ≥ 3 秒）

---

## 10. 下一步行动

1. **补充单元测试** - 测试各种错误场景和降级逻辑
2. **支持 Shorts** - 识别 YouTube Shorts（时长 < 60 秒）
3. **批量字幕提取** - 优化多次调用（减少 API 请求）
4. **支持评论采集** - 可选采集视频评论（需要额外权限）

---

## 11. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | 初始版本，基于 `youtube_collector.py` 反向工程 |
