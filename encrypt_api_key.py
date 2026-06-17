#!/usr/bin/env python3
"""加密 API Key 并更新 config.yaml"""

import os
import re
from cryptography.fernet import Fernet

# 明文 API Key（用户刚刚提供）
PLAINTEXT_KEY = "sk-ebc59537890a49b3a86aabef1ba1b8c7"

# 从环境变量读取加密密钥
ENC_KEY = os.getenv("CONTENT_AGGREGATOR_ENC_KEY")
if not ENC_KEY:
    print("❌ 环境变量 CONTENT_AGGREGATOR_ENC_KEY 未设置")
    exit(1)

print(f"🔑 使用加密密钥: {ENC_KEY[:20]}...")

# 加密
fernet = Fernet(ENC_KEY.encode())
encrypted = fernet.encrypt(PLAINTEXT_KEY.encode()).decode()
enc_value = f"enc:{encrypted}"

print(f"✅ 加密完成: {enc_value[:40]}...")

# 读取 config.yaml
config_path = "config/config.yaml"
with open(config_path, "r", encoding="utf-8") as f:
    content = f.read()

# 替换 llm.api_key
# 匹配: api_key: "enc:..." 或 api_key: "sk-..."
pattern = r'(api_key:\s+")enc:[^"]*("|sk-[^"]*")'
replacement = f'\\1{enc_value}\\2'

new_content = re.sub(pattern, replacement, content)

if new_content == content:
    print("⚠️  未找到 api_key 行，手动检查 config.yaml")
    print("请手动将 llm.api_key 改为:")
    print(f'  api_key: "{enc_value}"')
else:
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"✅ 已更新 {config_path}")
    print(f"   新值: api_key: \"{enc_value[:60]}...\"")

print("\n🔄 请重启服务器以应用新配置")
print("   Get-Process python | Stop-Process -Force")
print("   python start_server.py")
