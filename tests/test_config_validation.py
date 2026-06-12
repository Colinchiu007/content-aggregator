"""
配置完整性验证测试。

防止 API Key 加密/解密不一致、配置缺失等问题悄然发生。
每次添加新 Key 或修改配置后，运行本测试即可验证一切正常。
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def get_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestConfigStructure:
    """验证配置文件结构完整性"""

    @pytest.fixture(scope="class")
    def config(self):
        return get_config()

    def test_config_file_exists(self):
        """配置文件必须存在"""
        assert CONFIG_PATH.exists(), f"配置文件不存在: {CONFIG_PATH}"

    def test_sources_section(self, config):
        """必须有 sources 节"""
        assert "sources" in config, "缺少 sources 配置节"

    def test_llm_section(self, config):
        """必须有 llm 配置节"""
        assert "llm" in config, "缺少 llm 配置节"

    def test_youtube_config(self, config):
        """必须有 YouTube 配置"""
        sources = config.get("sources", {})
        assert "youtube" in sources, "缺少 sources.youtube 配置"
        yt = sources["youtube"]
        assert yt.get("api_key"), "YouTube API Key 未配置"
        assert not yt["api_key"].startswith("enc:"), "YouTube API Key 仍是加密状态，解密失败"
        assert yt.get("channels") or yt.get("search_queries"), "YouTube 没有配置任何频道或搜索关键词"


class TestEncryptedKeys:
    """验证所有 enc: 前缀的密钥可被正确解密。

    这是核心防护：如果加密密钥（CONTENT_AGGREGATOR_ENC_KEY）变更或损坏，
    本测试会立刻失败，避免运行时出现「采集 0 篇」等难以排查的故障。
    """

    @pytest.fixture(scope="class")
    def config(self):
        return get_config()

    @pytest.fixture(scope="class")
    def fernet_key(self):
        key = os.environ.get("CONTENT_AGGREGATOR_ENC_KEY")
        if not key:
            config = get_config()
            key = config.get("encryption_key")
        return key

    def test_fernet_key_exists(self, fernet_key):
        """加密密钥必须可用"""
        assert fernet_key, (
            "CONTENT_AGGREGATOR_ENC_KEY 环境变量未设置，config.yaml 中也无 encryption_key。\n"
            "请运行：$env:CONTENT_AGGREGATOR_ENC_KEY='your-key-here'"
        )

    def test_fernet_key_valid(self, fernet_key):
        """加密密钥必须是合法的 Fernet 格式（32字节 base64）"""
        from cryptography.fernet import Fernet
        try:
            Fernet(fernet_key.encode())
        except Exception as e:
            pytest.fail(f"Fernet 密钥格式无效: {e}")

    def _find_enc_values(self, obj, path=""):
        """递归查找所有 enc: 前缀的值"""
        results = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                results.extend(self._find_enc_values(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                results.extend(self._find_enc_values(v, f"{path}[{i}]"))
        elif isinstance(obj, str) and obj.startswith("enc:"):
            results.append((path, obj))
        return results

    def test_all_enc_values_decryptable(self, config, fernet_key):
        """所有 enc: 前缀的值都能被成功解密"""
        from cryptography.fernet import Fernet

        if not fernet_key:
            pytest.skip("未找到加密密钥")

        enc_values = self._find_enc_values(config)
        if not enc_values:
            pytest.skip("没有 enc: 前缀的值需要检查")

        fernet = Fernet(fernet_key.encode())
        errors = []
        for path, val in enc_values:
            try:
                fernet.decrypt(val[4:].encode())
            except Exception as e:
                errors.append(f"  ❌ {path}: 解密失败 — {e}")

        if errors:
            pytest.fail(
                f"发现 {len(errors)} 个无法解密的密钥，请重新加密或手动替换为明文：\n"
                + "\n".join(errors)
                + "\n\n修复方法：\n"
                "  1. 确认 CONTENT_AGGREGATOR_ENC_KEY 环境变量正确\n"
                "  2. 运行 tools/encrypt_key.py 重新加密\n"
                "  3. 或直接写入明文（去掉 enc: 前缀）"
            )


class TestYouTubeConfig:
    """YouTube 采集器配置验证"""

    def test_decrypt_key_function(self):
        """验证 _decrypt_key 函数可以正确处理明文和加密值"""
        from content_aggregator.sources.collectors.youtube_collector import YouTubeCollector

        # 测试 1：明文 Key 原样返回
        collector = YouTubeCollector.__new__(YouTubeCollector)
        result = collector._decrypt_key("sk-test-plain")
        assert result == "sk-test-plain", f"明文 Key 不应被修改: {result}"

        # 测试 2：None 返回 None
        result = collector._decrypt_key(None)
        assert result is None, f"None 应返回 None: {result}"

    def test_youtube_api_key_is_plaintext(self):
        """YouTube API Key 应该是明文（加密密钥不匹配的问题已修复）"""
        config = get_config()
        yt_key = config["sources"]["youtube"]["api_key"]
        assert not yt_key.startswith("enc:"), (
            "YouTube API Key 不应以 enc: 开头。加密密钥不匹配导致解密失败。\n"
            "请写入明文 Key 或确认加密密钥正确。"
        )
