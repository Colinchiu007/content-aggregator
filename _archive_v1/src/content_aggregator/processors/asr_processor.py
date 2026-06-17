"""
ASR 处理器 - 音频转文字

功能：
1. 使用 yt-dlp 从视频链接下载音频
2. 调用 Whisper API（OpenAI 兼容模式）进行语音识别
3. 返回结构化转写结果

使用示例：
    async with ASRProcessor(asr_config) as asr:
        result = await asr.process(video_url)
        if result.success:
            print(result.transcribed_text)
            print(result.word_count)
"""

import asyncio
import hashlib
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from loguru import logger

from content_aggregator.models import Content


@dataclass
class ASRConfig:
    """
    ASR 配置

    Attributes:
        api_endpoint: Whisper API 端点（OpenAI 兼容模式）
        api_key: API Key（可选，设为 "no-key" 表示无需认证）
        model_id: 模型 ID（如 "whisper-1", "whisper-large-v3"）
        language: 默认语言代码（如 "zh", "en"），留空自动检测
        max_audio_size_mb: 最大音频文件大小（MB），默认 50MB
        timeout_seconds: API 调用超时时间（秒），默认 300
    """
    api_endpoint: str = ""
    api_key: str = ""
    model_id: str = "whisper-1"
    language: str = ""
    max_audio_size_mb: int = 50
    timeout_seconds: int = 300


@dataclass
class ASRResult:
    """
    ASR 转写结果

    Attributes:
        success: 是否成功
        transcribed_text: 完整转写文本
        segments: 分段结果（可选，包含时间戳信息）
        word_count: 字数统计
        duration_seconds: 音频时长（秒）
        language: 检测到的语言
        error: 错误信息
        duration: 处理耗时（秒）
    """
    success: bool
    transcribed_text: str = ""
    segments: list[dict[str, Any]] = field(default_factory=list)
    word_count: int = 0
    duration_seconds: float = 0.0
    language: str = ""
    error: str | None = None
    duration: float = 0.0


class ASRProcessor:
    """
    ASR 处理器

    负责：
    1. 从视频链接下载音频（yt-dlp）
    2. 调用 Whisper API 进行语音识别
    3. 返回结构化转写结果
    """

    def __init__(self, config: ASRConfig):
        self.config = config
        self._session: httpx.AsyncClient | None = None
        self._temp_files: list[Path] = []

    async def __aenter__(self):
        self._session = httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers=self._build_headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.aclose()
        # 清理临时文件
        for f in self._temp_files:
            try:
                if f.exists():
                    f.unlink()
            except Exception as e:
                logger.warning(f"清理临时文件 {f} 失败: {e}")
        self._temp_files.clear()

    def _build_headers(self) -> dict[str, str]:
        """构建 API 请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.config.api_key and self.config.api_key != "no-key":
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def _download_audio(self, video_url: str) -> Path:
        """
        使用 yt-dlp 从视频链接下载音频

        Args:
            video_url: 视频链接

        Returns:
            临时音频文件路径

        Raises:
            RuntimeError: 下载失败时抛出
        """
        import yt_dlp

        # 生成唯一的临时文件名
        url_hash = hashlib.md5(video_url.encode()).hexdigest()[:8]
        temp_dir = Path(tempfile.gettempdir()) / "content-aggregator-asr"
        temp_dir.mkdir(parents=True, exist_ok=True)

        output_path = temp_dir / f"audio_{url_hash}.mp3"

        # 如果文件已存在且小于 max_audio_size_mb，直接复用
        max_bytes = self.config.max_audio_size_mb * 1024 * 1024
        if output_path.exists() and output_path.stat().st_size < max_bytes:
            logger.info(f"音频文件已存在，复用: {output_path}")
            return output_path

        # yt-dlp 配置：只下载音频，格式为 mp3
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": str(temp_dir / "audio_%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "noplaylist": True,  # 只下载单个视频
            "max_filesize": max_bytes,
        }

        try:
            logger.info(f"正在下载音频: {video_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if info is None:
                    raise RuntimeError(f"yt-dlp 无法解析视频: {video_url}")

                # yt-dlp 下载后文件名可能不同，查找实际文件
                # 搜索 temp_dir 下最近创建的 mp3 文件
                mp3_files = sorted(
                    [f for f in temp_dir.glob("*.mp3")],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )

                if mp3_files:
                    actual_path = mp3_files[0]
                    # 重命名为标准文件名
                    if actual_path != output_path:
                        actual_path.rename(output_path)
                    logger.info(f"音频下载完成: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
                    return output_path
                else:
                    raise RuntimeError("yt-dlp 下载完成但未找到音频文件")

        except Exception as e:
            logger.error(f"音频下载失败: {e}")
            raise RuntimeError(f"ASR 音频下载失败: {e}") from e

    async def _transcribe(self, audio_path: Path) -> dict[str, Any]:
        """
        调用 Whisper API 进行语音识别

        Args:
            audio_path: 音频文件路径

        Returns:
            API 响应 JSON

        Raises:
            RuntimeError: API 调用失败时抛出
        """
        # 检查文件大小
        file_size = audio_path.stat().st_size
        max_bytes = self.config.max_audio_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise RuntimeError(
                f"音频文件过大 ({file_size / 1024 / 1024:.1f} MB > {self.config.max_audio_size_mb} MB)"
            )

        # 构建 multipart/form-data 请求（OpenAI Whisper API 格式）
        url = f"{self.config.api_endpoint.rstrip('/')}/audio/transcriptions"

        # 读取音频文件
        async with aiofiles.open(audio_path, "rb") as f:
            audio_data = await f.read()

        # 构建 multipart 请求
        headers = {
            "Authorization": f"Bearer {self.config.api_key}"
            if self.config.api_key and self.config.api_key != "no-key"
            else ""
        }

        # 使用 httpx 的 files 参数发送 multipart 请求
        files = {
            "file": ("audio.mp3", audio_data, "audio/mpeg"),
        }
        data = {
            "model": self.config.model_id,
        }
        if self.config.language:
            data["language"] = self.config.language
        data["response_format"] = "json"  # 返回完整文本 + 分段信息

        logger.info(f"正在调用 ASR API: {url} (模型: {self.config.model_id})")

        try:
            response = await self._session.post(
                url,
                files=files,
                data=data,
                headers=headers,
            )

            if response.status_code != 200:
                error_body = response.text[:500]
                raise RuntimeError(
                    f"ASR API 返回 {response.status_code}: {error_body}"
                )

            result = response.json()
            logger.info("ASR 转写完成")
            return result

        except httpx.TimeoutException:
            raise RuntimeError("ASR API 调用超时")
        except httpx.ConnectError as e:
            raise RuntimeError(f"ASR API 连接失败: {e}")

    async def process(self, video_url: str, progress_callback=None) -> ASRResult:
        """
        完整流程：下载音频 → 语音识别 → 返回结果

        Args:
            video_url: 视频链接
            progress_callback: 进度回调函数 async def callback(current, total, message)

        Returns:
            ASRResult 转写结果
        """
        start_time = time.time()

        try:
            # 检查 API 配置
            if not self.config.api_endpoint:
                if progress_callback:
                    await progress_callback(0, 100, "ASR API 端点未配置")
                return ASRResult(
                    success=False,
                    error="ASR API 端点未配置，请在系统设置中配置 ASR 模型",
                )

            if progress_callback:
                await progress_callback(0, 100, "正在下载音频...")

            # Step 1: 下载音频
            audio_path = await self._download_audio(video_url)

            if progress_callback:
                await progress_callback(50, 100, "正在语音识别...")

            # Step 2: 语音识别
            transcribe_result = await self._transcribe(audio_path)

            # Step 3: 解析结果
            transcribed_text = transcribe_result.get("text", "")
            segments = transcribe_result.get("segments", [])

            # 字数统计（中文字符 + 英文单词）
            import re
            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", transcribed_text))
            english_words = len(re.findall(r"[a-zA-Z]+", transcribed_text))
            word_count = chinese_chars + english_words

            duration = time.time() - start_time

            return ASRResult(
                success=True,
                transcribed_text=transcribed_text,
                segments=segments,
                word_count=word_count,
                duration_seconds=transcribe_result.get("duration", 0),
                language=transcribe_result.get("language", ""),
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"ASR 处理失败: {e}")
            return ASRResult(
                success=False,
                error=str(e),
                duration=duration,
            )


async def process_video_asr(
    video_url: str,
    asr_config: ASRConfig,
    progress_callback=None,
) -> ASRResult:
    """
    便捷函数：直接使用 ASRProcessor 处理视频

    Args:
        video_url: 视频链接
        asr_config: ASR 配置
        progress_callback: 进度回调

    Returns:
        ASRResult 转写结果
    """
    async with ASRProcessor(asr_config) as processor:
        return await processor.process(video_url, progress_callback)
