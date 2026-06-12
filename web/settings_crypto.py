"""
API Key 加密模块

使用 Fernet（对称加密）保护配置中的敏感字段。
密钥文件存储在 data/ 目录下（gitignored），自动生成。

加密流程：
  save_config → encrypt_api_keys → 写入 YAML
  读取 YAML → decrypt_api_keys → load_config
"""

import os
import base64
from pathlib import Path

# 敏感字段后缀列表（匹配到这些后缀的字段值会被加密）
SENSITIVE_SUFFIXES = ("api_key", "key", "secret", "token", "password")

# 密钥文件路径（项目 data/ 目录下）
DATA_DIR = Path(__file__).parent.parent / "data"
KEY_FILE = DATA_DIR / ".settings_key"
KEY_FILE_GITIGNORE = DATA_DIR / ".gitignore"


def _ensure_key():
    """确保密钥文件存在，不存在则生成"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not KEY_FILE_GITIGNORE.exists():
        # 确保 data/ 被 gitignore
        try:
            KEY_FILE_GITIGNORE.write_text(".settings_key\n", encoding="utf-8")
        except Exception:
            pass
    if not KEY_FILE.exists():
        # 生成新密钥
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        # 仅当前用户可读
        try:
            os.chmod(str(KEY_FILE), 0o600)
        except Exception:
            pass
    return KEY_FILE.read_bytes()


def _get_cipher():
    """获取 Fernet 加密器"""
    from cryptography.fernet import Fernet
    key = _ensure_key()
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """加密单个字符串值，返回 base64 格式密文（带 enc: 前缀）"""
    if not plaintext:
        return ""
    cipher = _get_cipher()
    encrypted = cipher.encrypt(plaintext.encode("utf-8"))
    return "enc:" + base64.urlsafe_b64encode(encrypted).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """解密单个值（自动识别 enc: 前缀）"""
    if not ciphertext or not ciphertext.startswith("enc:"):
        return ciphertext  # 非加密字段原样返回
    try:
        cipher = _get_cipher()
        encrypted = base64.urlsafe_b64decode(ciphertext[4:])
        return cipher.decrypt(encrypted).decode("utf-8")
    except Exception:
        return ciphertext  # 解密失败，原样返回


def is_encrypted(value: str) -> bool:
    """判断值是否已加密"""
    return bool(value and value.startswith("enc:"))


def _walk_and_transform(obj, transformer, suffixes):
    """递归遍历字典/列表，对匹配后缀的字符串字段执行 transformer"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                _walk_and_transform(value, transformer, suffixes)
            elif isinstance(value, str) and any(key.endswith(sfx) for sfx in suffixes):
                obj[key] = transformer(value)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _walk_and_transform(item, transformer, suffixes)


def encrypt_config(config: dict) -> dict:
    """加密配置中所有敏感字段，返回加密后的配置（原地修改）"""
    _walk_and_transform(config, encrypt_value, SENSITIVE_SUFFIXES)
    return config


def decrypt_config(config: dict) -> dict:
    """解密配置中所有敏感字段，返回解密后的配置（原地修改）"""
    _walk_and_transform(config, decrypt_value, SENSITIVE_SUFFIXES)
    return config
