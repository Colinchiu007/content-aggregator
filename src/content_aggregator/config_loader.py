"""
配置加载器：优先读环境变量，fallback 到 .env 文件。

使用方式：
    from content_aggregator.config_loader import get_secret

    # 获取 API Key（优先 env var → config.yaml → .env）
    api_key = get_secret("YOUTUBE_API_KEY")

设计目标：
    1. 消除 enc: 加密方案（密钥不匹配的根源）
    2. 密钥全部移出 config.yaml，改存 .env（gitignore）
    3. 兼容旧的 enc: 逻辑（过渡期）
"""

import os
from pathlib import Path
from loguru import logger

# .env 文件路径
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

# 已加载标记
_loaded = False


def _load_dotenv():
    """加载 .env 文件（仅一次）"""
    global _loaded
    if _loaded:
        return
    _loaded = True

    if ENV_FILE.exists():
        try:
            # 手动解析 .env 文件（避免引入 python-dotenv 依赖）
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # 只在环境变量未设置时写入（不覆盖已有的环境变量）
                    if key and value and key not in os.environ:
                        os.environ[key] = value
            logger.info(f"[config_loader] 已加载 {ENV_FILE.name}（{ENV_FILE.stat().st_size} bytes）")
        except Exception as e:
            logger.warning(f"[config_loader] 加载 .env 失败: {e}")
    else:
        logger.warning(
            f"[config_loader] .env 文件不存在: {ENV_FILE}\n"
            f"  请复制 .env.example 为 .env 并填入密钥。"
        )


def get_secret(key: str, default: str | None = None) -> str | None:
    """
    获取密钥值，优先级：
    1. 环境变量（最高）
    2. .env 文件
    3. 传入的 default

    示例：
        get_secret("YOUTUBE_API_KEY")
        get_secret("DEEPSEEK_API_KEY", default="")
    """
    _load_dotenv()
    return os.environ.get(key, default)


def require_secret(key: str) -> str:
    """
    获取密钥值，不存在则抛异常。

    在关键路径（如 LLM 调用、YouTube 采集）中使用，
    避免拿到空值后静默失败。
    """
    value = get_secret(key)
    if not value:
        raise EnvironmentError(
            f"[config_loader] 缺少密钥: {key}\n"
            f"  请将 {key} 添加到 .env 文件或设为环境变量。"
        )
    return value


def check_secrets(*keys: str) -> list[str]:
    """
    批量检查密钥是否存在，返回缺失列表。
    用于启动时验证 + 测试。

    示例：
        missing = check_secrets("YOUTUBE_API_KEY", "DEEPSEEK_API_KEY")
        if missing:
            print(f"缺失密钥: {missing}")
    """
    _load_dotenv()
    missing = []
    for key in keys:
        if not os.environ.get(key):
            missing.append(key)
    return missing
