"""初始化 001 用户数据库"""
import sqlite3
import os
from pathlib import Path

os.chdir(Path(__file__).parent.parent)

db_path = 'data/user.db'
os.makedirs('data', exist_ok=True)

conn = sqlite3.connect(db_path)

# 执行迁移脚本
with open('migrations/001_init_user_db.sql', 'r', encoding='utf-8') as f:
    sql_script = f.read()

conn.executescript(sql_script)

# 插入测试用户（密码: test12345）
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')
hashed = pwd_context.hash('test12345')

conn.execute('''
    INSERT OR REPLACE INTO users (uuid, username, email, password_hash, role, is_active)
    VALUES ('test-001', 'testuser', 'test@example.com', ?, 'user', 1)
''', (hashed,))

conn.execute('''
    INSERT OR REPLACE INTO user_profiles (user_id, display_name, preferred_rewrite_strategy, preferred_export_format)
    VALUES (1, '测试用户', 'PARAPHRASE', 'markdown')
''')

conn.commit()

# 验证
cursor = conn.cursor()
cursor.execute('SELECT id, username, email, role FROM users')
rows = cursor.fetchall()
print('Users:', rows)

conn.close()
print('Database initialized successfully!')
