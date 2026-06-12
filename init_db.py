#!/usr/bin/env python3
"""初始化认证数据库"""
import sys
import os

# 添加项目路径
sys.path.insert(0, r"C:\Users\邱领\.qclaw\workspace\content-aggregator")
os.chdir(r"C:\Users\邱领\.qclaw\workspace\content-aggregator")

from web.auth_router import init_db, get_db
import sqlite3

# 初始化数据库（创建表）
init_db()
print("✅ 数据库表初始化成功")

# 检查表是否存在
conn = get_db()
try:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        print("✅ users 表已存在")
        # 检查是否有用户
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        print(f"   当前用户数: {count}")
    else:
        print("❌ users 表不存在")
finally:
    conn.close()

print("\n数据库路径: data/user.db")
