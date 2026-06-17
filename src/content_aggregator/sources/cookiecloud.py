"""
CookieCloud 集成模块（独立）

从 Y2A-Auto 移植的 CookieCloud 客户端，用于自动同步浏览器 Cookies。

CookieCloud 是开源工具（https://github.com/easychen/CookieCloud）：
1. 浏览器装 CookieCloud 扩展 → 加密上传 cookies 到自建服务器
2. 本模块加密拉取 → 解密 → 过滤 YouTube cookies → 写入本地文件

用法（独立）：
    from content_aggregator.sources.cookiecloud import sync_youtube_cookies

    result = sync_youtube_cookies({
        "server_url": "https://cc.example.com",
        "uuid": "your-uuid",
        "password": "your-password",
    })
    print(f"已同步 {result['cookie_count']} 个 cookies → {result['output_path']}")

配置（config.yaml）：
    cookiecloud:
        enabled: false
        server_url: ""
        uuid: ""
        password: ""
        output_path: "data/yt_cookies.txt"     # 输出路径（相对于项目根目录）
        allow_plaintext_export: true             # 必须 true 才能写入本地文件
"""

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────

DEFAULT_OUTPUT_PATH = "data/yt_cookies.txt"
DEFAULT_TIMEOUT = (5, 20)  # connect, read
AES_BLOCK_SIZE = 128  # bits
YOUTUBE_DOMAINS = ("youtube.com", "youtu.be", "google.com")

# ── 异常 ──────────────────────────────────────────────────────────


class CookieCloudError(Exception):
    """CookieCloud 基类异常"""


class ConfigError(CookieCloudError):
    """配置错误"""


class RequestError(CookieCloudError):
    """网络请求失败"""


class DecryptError(CookieCloudError):
    """解密失败"""


class DataError(CookieCloudError):
    """返回数据无效"""


# ── 配置校验 ──────────────────────────────────────────────────────


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """
    验证并规整 CookieCloud 配置。

    Args:
        settings: config.yaml 中 cookiecloud 段的配置

    Returns:
        规整后的配置字典

    Raises:
        ConfigError: 配置无效
    """
    enabled = _as_bool(settings.get("enabled", False))
    if not enabled:
        raise ConfigError("CookieCloud 未启用")

    server_url = str(settings.get("server_url", "")).strip()
    if not server_url:
        raise ConfigError("请配置 CookieCloud 服务地址")
    if not server_url.startswith(("http://", "https://")):
        raise ConfigError("CookieCloud 服务地址格式无效（需 http/https）")

    uuid_val = str(settings.get("uuid", "")).strip()
    password_val = str(settings.get("password", "")).strip()
    if not uuid_val:
        raise ConfigError("请配置 CookieCloud UUID")
    if not password_val:
        raise ConfigError("请配置 CookieCloud 密码")

    output_path = str(settings.get("output_path", DEFAULT_OUTPUT_PATH)).strip() or DEFAULT_OUTPUT_PATH
    allow_export = _as_bool(settings.get("allow_plaintext_export", False))

    if allow_export and not output_path:
        raise ConfigError("启用明文导出时需设置 output_path")

    return {
        "enabled": enabled,
        "server_url": server_url.rstrip("/"),
        "uuid": uuid_val,
        "password": password_val,
        "output_path": output_path,
        "allow_plaintext_export": allow_export,
    }


# ── 网络请求 ──────────────────────────────────────────────────────


def fetch_payload(server_url: str, uuid_val: str, timeout: tuple[int, int] = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """
    向 CookieCloud 服务器请求加密的 cookie 数据。

    Returns:
        {"encrypted": "...", "cookie_data": {...}} 等

    Raises:
        RequestError: 网络或连接错误
        DataError: 响应数据无效
    """
    url = f"{server_url}/get/{uuid_val}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RequestError(f"CookieCloud 请求失败: {e}") from e

    try:
        payload = resp.json()
    except ValueError as e:
        raise DataError(f"CookieCloud 返回数据不是 JSON: {e}") from e

    if not isinstance(payload, dict):
        raise DataError("CookieCloud 返回数据格式无效")

    if not payload.get("encrypted") and not isinstance(payload.get("cookie_data"), dict):
        # 如果既没有 encrypted 也没有 cookie_data，可能有问题
        if not payload.get("encrypted"):
            raise DataError("CookieCloud 未返回加密数据（encrypted 字段为空）")

    return payload


# ── 解密 ──────────────────────────────────────────────────────────


def _derive_key(uuid_val: str, password_val: str) -> bytes:
    """CookieCloud 协议 required key derivation: MD5(\"{uuid}-{password}\")[:16]"""
    raw = f"{uuid_val}-{password_val}".encode("utf-8")
    return hashlib.md5(raw, usedforsecurity=False).hexdigest()[:16].encode("utf-8")


def _derive_key_pbkdf2(uuid_val: str, password_val: str) -> bytes:
    """Preview 增强版: PBKDF2-HMAC-SHA256(200000次)"""
    salt = uuid_val.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", password_val.encode("utf-8"), salt, 200000, dklen=16)


def _evp_kdf(data: bytes, salt: bytes, key_len: int, iv_len: int) -> tuple[bytes, bytes]:
    """OpenSSL EVP_BytesToKey (MD5) — CookieCloud protocol mandated"""
    total = key_len + iv_len
    derived = b""
    block = b""
    while len(derived) < total:
        block = hashlib.md5(block + data + salt, usedforsecurity=False).digest()
        derived += block
    return derived[:key_len], derived[key_len:total]


def _aes_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CBC 解密 + PKCS7 unpad"""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(AES_BLOCK_SIZE).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _decrypt_legacy(ciphertext: str, uuid_val: str, password_val: str) -> bytes:
    """Legacy 模式: Salted__ 格式"""
    raw = base64.b64decode(ciphertext)
    if len(raw) < 17 or raw[:8] != b"Salted__":
        raise DecryptError("密文不是 legacy Salted__ 格式")
    salt = raw[8:16]
    body = raw[16:]
    seed = _derive_key(uuid_val, password_val)
    key, iv = _evp_kdf(seed, salt, key_len=32, iv_len=16)
    return _aes_decrypt(body, key, iv)


def _decrypt_legacy_pbkdf2(ciphertext: str, uuid_val: str, password_val: str) -> bytes:
    """Legacy + PBKDF2 增强版"""
    raw = base64.b64decode(ciphertext)
    if len(raw) < 17 or raw[:8] != b"Salted__":
        raise DecryptError("密文不是 legacy Salted__ 格式")
    salt = raw[8:16]
    body = raw[16:]
    seed = _derive_key_pbkdf2(uuid_val, password_val)
    # PBKDF2 derive key+iv
    total = 32 + 16
    derived = hashlib.pbkdf2_hmac("sha256", seed, salt, 200000, dklen=total)
    key, iv = derived[:32], derived[32:]
    return _aes_decrypt(body, key, iv)


def _decrypt_fixed_iv(ciphertext: str, uuid_val: str, password_val: str) -> bytes:
    """Fixed IV 模式: IV = \\x00×16"""
    raw = base64.b64decode(ciphertext)
    key = _derive_key(uuid_val, password_val)
    fixed_iv = b"\x00" * 16
    return _aes_decrypt(raw, key, fixed_iv)


def _decrypt_fixed_iv_pbkdf2(ciphertext: str, uuid_val: str, password_val: str) -> bytes:
    """Fixed IV + PBKDF2 增强版"""
    raw = base64.b64decode(ciphertext)
    seed = _derive_key_pbkdf2(uuid_val, password_val)
    fixed_iv = b"\x00" * 16
    return _aes_decrypt(raw, seed, fixed_iv)


_DECRYPTORS = [
    ("legacy", _decrypt_legacy),
    ("legacy+pbkdf2", _decrypt_legacy_pbkdf2),
    ("aes-128-cbc-fixed", _decrypt_fixed_iv),
    ("aes-128-cbc-fixed+pbkdf2", _decrypt_fixed_iv_pbkdf2),
]


def decrypt_payload(payload: dict[str, Any], uuid_val: str, password_val: str) -> tuple[dict[str, Any], str]:
    """
    解密 CookieCloud 返回的数据。

    自动尝试所有支持的加密模式，返回 (解密后的 dict, 使用的加密模式名)。

    Raises:
        DataError: 数据格式无效
        DecryptError: 所有解密模式均失败
    """
    # 如果是明文数据（未加密），直接返回
    if isinstance(payload.get("cookie_data"), dict):
        return payload, "plaintext"

    ciphertext = payload.get("encrypted")
    if not isinstance(ciphertext, str) or not ciphertext.strip():
        raise DataError("CookieCloud 未返回加密数据")

    last_error: Exception | None = None
    for name, decryptor in _DECRYPTORS:
        try:
            decrypted = decryptor(ciphertext, uuid_val, password_val)
            parsed = json.loads(decrypted.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise DataError("解密后的数据不是 JSON 对象")
            return parsed, name
        except Exception as e:
            last_error = e
            continue

    raise DecryptError(f"CookieCloud 解密失败（已尝试 {len(_DECRYPTORS)} 种模式）") from last_error


# ── Cookie 过滤与写入 ──────────────────────────────────────────────


def _is_youtube_domain(domain: str) -> bool:
    """检查域名是否与 YouTube 相关"""
    domain = domain.lower().lstrip(".")
    for base in YOUTUBE_DOMAINS:
        if domain == base or domain.endswith(f".{base}"):
            return True
    return False


def _sanitize(value: Any) -> str:
    """清洗 cookie 字段值"""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def extract_youtube_cookies(payload: dict[str, Any]) -> tuple[str, int]:
    """
    从 CookieCloud 解密数据中提取 YouTube 相关 cookies。

    Returns:
        (Netscape cookie 文件内容, cookie 数量)
    """
    cookie_data = payload.get("cookie_data", {})
    if not isinstance(cookie_data, dict):
        # 也支持列表格式
        if isinstance(cookie_data, list):
            cookie_data = {"_": cookie_data}
        else:
            raise DataError("cookie_data 不是 dict 或 list")

    seen: dict[tuple[str, str, str], str] = {}  # (domain, path, name) → line

    for bucket, items in cookie_data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            domain = _sanitize(item.get("domain", bucket))
            if not domain or not _is_youtube_domain(domain):
                continue

            name = _sanitize(item.get("name"))
            if not name:
                continue

            path = _sanitize(item.get("path")) or "/"
            host_only = _as_bool(item.get("hostOnly", False))
            normalized_domain = domain.lstrip(".").lower()
            include_sub = "FALSE" if host_only else "TRUE"
            secure = "TRUE" if _as_bool(item.get("secure", False)) else "FALSE"
            value = _sanitize(item.get("value", ""))

            # 提取过期时间
            expires = 0
            for key in ("expirationDate", "expires", "expiry"):
                raw = item.get(key)
                if raw is not None:
                    try:
                        expires = max(0, int(float(str(raw))))
                        break
                    except (TypeError, ValueError):
                        continue

            line = "\t".join([normalized_domain, include_sub, path, secure, str(expires), name, value])
            seen[(normalized_domain, path, name)] = line

    if not seen:
        raise DataError("CookieCloud 中未找到 YouTube/Google 域名下的 cookies")

    header = [
        "# Netscape HTTP Cookie File",
        "# Generated by content-aggregator CookieCloud integration",
    ]
    body = [seen[k] for k in sorted(seen)]
    content = "\n".join(header + body) + "\n"
    return content, len(body)


# ── 输出 ──────────────────────────────────────────────────────────


def _resolve_output_path(path: str) -> str:
    """解析输出路径（相对于项目根目录）"""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    # 从模块位置向上找项目根
    module_dir = Path(__file__).resolve().parent.parent.parent.parent  # src/../../
    return str((module_dir / p).resolve())


def write_cookie_file(content: str, output_path: str) -> str:
    """将 cookies 写入本地文件"""
    resolved = _resolve_output_path(output_path)
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    with open(resolved, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    logger.info(f"[CookieCloud] 已写入 {resolved}")
    return resolved


# ── 主入口 ─────────────────────────────────────────────────────────


def sync_youtube_cookies(
    settings: dict[str, Any],
    timeout: tuple[int, int] = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    一键同步: 拉取 → 解密 → 过滤 YouTube cookies → 写入本地文件。

    Args:
        settings: CookieCloud 配置字典
        timeout: 请求超时 (connect, read)

    Returns:
        {
            "success": bool,
            "cookie_count": int,
            "output_path": str,
            "crypto_mode": str,
            "error": str | None,
        }

    Usage:
        result = sync_youtube_cookies({
            "server_url": "https://cc.example.com",
            "uuid": "xxxx",
            "password": "xxxx",
        })
    """
    try:
        config = validate_settings(settings)
        payload = fetch_payload(config["server_url"], config["uuid"], timeout=timeout)
        decrypted, crypto_mode = decrypt_payload(payload, config["uuid"], config["password"])
        cookie_content, count = extract_youtube_cookies(decrypted)

        output_path = config.get("output_path", DEFAULT_OUTPUT_PATH)
        if config.get("allow_plaintext_export", False):
            resolved_path = write_cookie_file(cookie_content, output_path)
        else:
            resolved_path = _resolve_output_path(output_path)
            logger.info(f"[CookieCloud] 已提取 {count} 个 cookies（allow_plaintext_export=false，未写入文件）")

        return {
            "success": True,
            "cookie_count": count,
            "output_path": resolved_path,
            "crypto_mode": crypto_mode,
            "error": None,
        }

    except CookieCloudError as e:
        logger.error(f"[CookieCloud] 同步失败: {e}")
        return {
            "success": False,
            "cookie_count": 0,
            "output_path": "",
            "crypto_mode": "",
            "error": str(e),
        }


# ── 配置读取助手 ──────────────────────────────────────────────────


def load_config(config: dict[str, Any]) -> dict[str, Any] | None:
    """
    从项目 config 字典加载 CookieCloud 配置。

    Returns:
        settings dict 或 None（未启用时）
    """
    cc = config.get("cookiecloud", {})
    if not _as_bool(cc.get("enabled", False)):
        return None
    return cc


# ── 工具函数 ──────────────────────────────────────────────────────


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


# ── CLI ──────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 4:
        print("用法: python cookiecloud.py <server_url> <uuid> <password> [output_path]")
        sys.exit(1)

    settings = {
        "enabled": True,
        "server_url": sys.argv[1],
        "uuid": sys.argv[2],
        "password": sys.argv[3],
        "allow_plaintext_export": True,
    }
    if len(sys.argv) >= 5:
        settings["output_path"] = sys.argv[4]

    result = sync_youtube_cookies(settings)
    if result["success"]:
        print(f"✅ 同步成功: {result['cookie_count']} 个 cookies → {result['output_path']} (模式: {result['crypto_mode']})")
    else:
        print(f"❌ 同步失败: {result['error']}")
        sys.exit(1)
