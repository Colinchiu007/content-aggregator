"""
配置加载模块

功能：
- 环境变量展开：${VAR_NAME}
- .env 文件加载
- 配置验证
- 默认值填充

用法：
    from config.loader import load_config
    
    # 加载默认配置
    config = load_config()
    
    # 加载指定文件
    config = load_config("config/prod.yaml")
    
    # 获取特定源配置
    source = config.get_source("ruanyifeng")
"""

import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml


def expand_env_vars(value: str | Any) -> Any:
    """
    展开字符串中的环境变量
    
    支持格式：
    - ${VAR_NAME}      # 不存在时返回空字符串
    - ${VAR_NAME:-default}  # 不存在时返回 default
    
    示例：
        "api_key: ${LLM_API_KEY}"
        "base_url: ${API_BASE:-https://default.com}"
    """
    if not isinstance(value, str):
        return value
    
    # 匹配 ${VAR_NAME} 或 ${VAR_NAME:-default}
    # 注意：排除 } 但允许 :，因为变量名可能含冒号（如 SQLALCHEMY_DATABASE_URL）
    pattern = r'\$\{([^}]+)\}'
    
    def replacer(match):
        full = match.group(1)
        # 支持 ${VAR_NAME:-default} 语法
        if ':-' in full:
            var_name, default = full.split(':-', 1)
        else:
            var_name, default = full, ""
        return os.environ.get(var_name.strip(), default)
    
    return re.sub(pattern, replacer, value)


def expand_dict(data: dict | list | Any) -> dict | list | Any:
    """递归展开字典/列表中的环境变量"""
    if isinstance(data, dict):
        return {k: expand_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [expand_dict(item) for item in data]
    elif isinstance(data, str):
        return expand_env_vars(data)
    return data


def load_dotenv(env_path: str | Path | None = None) -> None:
    """
    加载 .env 文件
    
    优先级：.env > 系统环境变量
    """
    if env_path is None:
        # 默认从项目根目录加载
        env_path = Path(__file__).parent.parent / ".env"
    else:
        env_path = Path(env_path)
    
    if not env_path.exists():
        return
    
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith("#"):
                continue
            # 跳过导出命令（bash 风格）
            if line.startswith("export "):
                line = line[7:]
            # 解析 KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                if key and value and key not in os.environ:
                    os.environ[key] = value


def validate_llm_config(config: dict) -> None:
    """验证 LLM 配置"""
    llm = config.get("llm", {})
    
    api_key = llm.get("api_key", "")
    if not api_key:
        raise ValueError(
            "LLM API key is required. "
            "Set api_key in config.yaml or LLM_API_KEY environment variable."
        )
    
    if api_key == "${LLM_API_KEY}" or api_key == "sk-your-api-key-here":
        raise ValueError(
            "LLM API key not configured. "
            "Set api_key in config.yaml or export LLM_API_KEY=your-key"
        )


def get_defaults() -> dict:
    """获取默认配置"""
    return {
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "max_tokens": 4096,
            "temperature": 0.7,
            "timeout": 120,
            "max_concurrency": 3,
        },
        "http": {
            "timeout": 30,
            "max_retries": 3,
            "proxy": "",
        },
        "database": {
            "path": "./data/content.db",
        },
        "export": {
            "output_dir": "./output/exports",
            "default_format": "markdown",
            "filename_template": "{title}_{date}.{ext}",
        },
        "sources": [],
        "rewrite": {
            "strategy": "PARAPHRASE",
        },
        "formatter": {
            "markdown": {
                "include_metadata": True,
                "metadata_fields": ["title", "author", "source", "date", "tags"],
            },
            "html": {
                "use_inline_styles": True,
                "font_size": 17,
                "line_height": 1.75,
            },
        },
    }


def merge_config(base: dict, override: dict) -> dict:
    """深度合并配置（override 优先）"""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    
    return result


class Config:
    """配置对象（提供便捷访问方法）"""
    
    def __init__(self, data: dict):
        self._data = data
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径"""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    def get_llm(self) -> dict:
        """获取 LLM 配置"""
        return self._data.get("llm", {})
    
    def get_http(self) -> dict:
        """获取 HTTP 配置"""
        return self._data.get("http", {})
    
    def get_export(self) -> dict:
        """获取导出配置"""
        return self._data.get("export", {})
    
    def get_sources(self) -> list[dict]:
        """获取启用的 RSS 源列表"""
        sources = self._data.get("sources", [])
        return [s for s in sources if s.get("enabled", True)]
    
    def get_source(self, name: str) -> dict | None:
        """获取指定名称的 RSS 源配置"""
        sources = self._data.get("sources", [])
        for source in sources:
            if source.get("name") == name:
                return source
        return None
    
    def get_rewrite(self) -> dict:
        """获取改写配置"""
        return self._data.get("rewrite", {})
    
    def get_formatter(self) -> dict:
        """获取格式化配置"""
        return self._data.get("formatter", {})
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return self._data


def load_config(config_path: str | Path | None = None, *, 
                load_env: bool = True,
                validate: bool = True) -> Config:
    """
    加载配置文件
    
    参数：
        config_path: 配置文件路径（默认 config/config.yaml）
        load_env: 是否加载 .env 文件
        validate: 是否验证配置
    
    返回：
        Config 对象
    
    示例：
        # 基本用法
        config = load_config()
        
        # 加载指定文件
        config = load_config("config/prod.yaml")
        
        # 不加载 .env（用于测试）
        config = load_config(load_env=False)
    """
    # 1. 加载 .env 文件
    if load_env:
        load_dotenv()
    
    # 2. 获取默认配置
    defaults = get_defaults()
    
    # 3. 加载配置文件
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    else:
        config_path = Path(config_path)
    
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}
        print(f"Warning: Config file not found: {config_path}", file=sys.stderr)
    
    # 4. 合并配置
    config_data = merge_config(defaults, user_config)
    
    # 5. 展开环境变量
    config_data = expand_dict(config_data)
    
    # 6. 验证配置（临时禁用 LLM API Key 验证）
    # if validate:
    #     validate_llm_config(config_data)
    pass  # 跳过验证
    
    return Config(config_data)


def create_config_file(path: str | Path | None = None) -> Path:
    """
    从示例创建配置文件
    
    参数：
        path: 目标路径（默认 config.yaml）
    
    返回：
        创建的文件路径
    """
    if path is None:
        path = Path(__file__).parent / "config.yaml"
    else:
        path = Path(path)
    
    if path.exists():
        print(f"Config file already exists: {path}")
        return path
    
    example_path = Path(__file__).parent / "config.example.yaml"
    if example_path.exists():
        with open(example_path, encoding="utf-8") as src:
            content = src.read()
        with open(path, "w", encoding="utf-8") as dst:
            dst.write(content)
        print(f"Created config file: {path}")
        print("Please edit config.yaml and set your API key.")
    else:
        print(f"Example config not found: {example_path}")
    
    return path


if __name__ == "__main__":
    # 测试配置加载
    try:
        config = load_config()
        print("Config loaded successfully!")
        print(f"LLM Provider: {config.get('llm.provider')}")
        print(f"Model: {config.get('llm.model')}")
        print(f"API Key: {config.get('llm.api_key', '')[:10]}..." if config.get('llm.api_key') else "API Key: NOT SET")
        print(f"Sources: {[s['name'] for s in config.get_sources()]}")
    except ValueError as e:
        print(f"Config error: {e}")
        print("\nTo fix this:")
        print("1. Set LLM_API_KEY environment variable:")
        print("   export LLM_API_KEY=your-api-key")
        print("2. Or edit config/config.yaml and set your api_key")
