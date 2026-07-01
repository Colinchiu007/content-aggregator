"""应用配置 - 基于 pydantic-settings 的环境变量管理"""

from pathlib import Path
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- 数据库 ---
    DATABASE_URL: str = "postgresql+asyncpg://hotrewrite:hotrewrite@localhost:5432/hotrewrite"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT 认证 ---
    SECRET_KEY: str = ""  # must set PO_SECRET_KEY or SECRET_KEY in environment
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- LLM / AI 改写 ---
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # --- 应用 ---
    DEBUG: bool = True
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- TrendScope ---
    TRENDSCOPE_API_URL: str = "http://localhost:8001"

    # --- Orchestrator ---
    ORCHESTRATOR_API_URL: str = "http://localhost:8000"

    # --- 项目路径 ---
    @property
    def PROJECT_ROOT(self) -> Path:
        return Path(__file__).parent.parent

    @property
    def ALEMBIC_INI_PATH(self) -> Path:
        return self.PROJECT_ROOT / "alembic.ini"

    @model_validator(mode="after")
    def _validate_secret_key(self):
        if not self.SECRET_KEY:
            raise ValueError(
                "SECRET_KEY / PO_SECRET_KEY environment variable is not set. "
                "Set a strong random key before starting the server."
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    """获取缓存的应用配置单例"""
    return Settings()
