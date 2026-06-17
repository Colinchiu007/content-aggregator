#!/usr/bin/env python3
"""自动找可用端口并启动服务器"""
import socket
import os
import sys

def find_free_port(start_port=8080):
    """找可用端口"""
    for port in range(start_port, start_port + 100):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', port))
            s.close()
            return port
        except OSError:
            continue
    return None

port = find_free_port(8080)
if port is None:
    print("[ERROR] 找不到可用端口（8080-8179 均被占用）")
    sys.exit(1)

print(f"[INFO] 找到可用端口: {port}")
print(f"[INFO] 启动服务器: http://127.0.0.1:{port}")

# 设置环境变量
os.environ['PORT'] = str(port)

# 启动服务器
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from web.server import app
import uvicorn

uvicorn.run(app, host="127.0.0.1", port=port)
