#!/usr/bin/env python3
"""检查用户数据库"""
import sqlite3
import os
import sys

db_path = "data/user.db"

if not os.path.exists(db_path):
    print("[ERROR] 数据库不存在: {}".format(db_path))
    sys.exit(1)

print("[OK] 数据库文件存在: {}".format(db_path))
print("  文件大小: {} 字节".format(os.path.getsize(db_path)))

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("\n数据库表: {}".format(tables))

if not tables:
    print("[ERROR] 数据库为空（0字节或刚创建）")
    conn.close()
    sys.exit(1)

# 检查用户表
try:
    cursor.execute("SELECT id, username, email, created_at FROM users")
    users = cursor.fetchall()
    if users:
        print("\n[OK] 找到 {} 个用户:".format(len(users)))
        for u in users:
            print("  - ID:{} | 用户名:{} | 邮箱:{} | 创建时间:{}".format(u[0], u[1], u[2], u[3]))
    else:
        print("\n[ERROR] 用户表为空，需要创建测试用户")
except sqlite3.OperationalError as e:
    print("[ERROR] 查询用户表失败: {}".format(e))

conn.close()
