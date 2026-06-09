"""
本地认证路由（当共享认证模块不可用时使用）

提供基础的用户注册、登录、Token 刷新功能。
使用 SQLite 数据库持久化存储。
"""

import jwt
import hashlib
import sqlite3
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# 配置
JWT_SECRET = "content-aggregator-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_ALGORITHM = JWT_ALGORITHM  # 别名（兼容旧代码）
ACCESS_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_EXPIRE_DAYS = 30

# 数据库路径
DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "user.db"
DB_DIR.mkdir(parents=True, exist_ok=True)

# 密码哈希
PASSWORD_SALT = "content-aggregator-salt-2026"

def hash_password(password: str) -> str:
    """SHA-256 哈希密码"""
    return hashlib.sha256((password + PASSWORD_SALT).encode()).hexdigest()

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

# 初始化数据库
init_db()

# 安全方案
security = HTTPBearer(auto_error=False)


# ========== 数据模型 ==========

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


# ========== 工具函数 ==========

def hash_password(password: str) -> str:
    """SHA-256 哈希密码（简单实现，生产环境应使用 bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(user_id: str, username: str, expires_days: int = ACCESS_TOKEN_EXPIRE_DAYS) -> str:
    """创建 JWT Token"""
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(days=expires_days),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """解码 JWT Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        print(f"[DECODE_TOKEN] Token 已过期: {token[:30]}...")
        return None
    except jwt.InvalidTokenError as e:
        print(f"[DECODE_TOKEN] Token 无效: {e}, token={token[:30]}...")
        return None
    except Exception as e:
        print(f"[DECODE_TOKEN] 未知错误: {e}, token={token[:30]}...")
        return None


def _get_user_by_id(user_id: str) -> dict | None:
    """从数据库按 ID 获取用户"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT id, username, email, role FROM users WHERE id = ? AND is_active = 1",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "role": row["role"],
        }
    finally:
        conn.close()


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    """获取当前用户（依赖注入）"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("sub")
    user = _get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_user_from_token(token: str) -> dict | None:
    """Decode JWT token and return user info (for use by server.py require_auth)"""
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    return _get_user_by_id(user_id)


# ========== 路由 ==========

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    """用户注册"""
    conn = get_db()
    try:
        # 检查用户名是否已存在
        cursor = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (req.username,)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # 创建用户
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 'user', 1, ?, ?)",
            (req.username, req.email, hash_password(req.password), now, now)
        )
        user_id = cursor.lastrowid
        conn.commit()
        
        # 创建 Token
        access_token = create_token(str(user_id), req.username, ACCESS_TOKEN_EXPIRE_DAYS)
        refresh_token = create_token(str(user_id), req.username, REFRESH_TOKEN_EXPIRE_DAYS)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 3600,
            "user": {
                "id": user_id,
                "username": req.username,
                "email": req.email,
                "role": "user",
            }
        }
    finally:
        conn.close()


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """用户登录"""
    # 从数据库查找用户
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT id, username, email, password_hash, role FROM users WHERE username = ? AND is_active = 1",
            (req.username,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # 验证密码
        stored_hash = row["password_hash"]
        computed_hash = hash_password(req.password)
        print(f"[LOGIN] Username: {req.username}")
        print(f"[LOGIN] Stored hash (first 30): {stored_hash[:30]}...")
        print(f"[LOGIN] Computed hash (first 30): {computed_hash[:30]}...")
        print(f"[LOGIN] Hash match: {stored_hash == computed_hash}")
        
        if stored_hash != computed_hash:
            print(f"[LOGIN] Password mismatch!")
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        print(f"[LOGIN] Password OK, creating token...")
        
        # 创建 Token
        user_id = row["id"]
        username = row["username"]
        access_token = create_token(user_id, username, ACCESS_TOKEN_EXPIRE_DAYS)
        refresh_token = create_token(user_id, username, REFRESH_TOKEN_EXPIRE_DAYS)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 3600,
            "user": {
                "id": user_id,
                "username": username,
                "email": row["email"],
                "role": row["role"],
            }
        }
    finally:
        conn.close()


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        "role": user.get("role", "user"),
    }


@router.post("/refresh", response_model=AuthResponse)
async def refresh(req: RefreshRequest):
    """刷新 Access Token"""
    payload = decode_token(req.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    user_id = payload.get("sub")
    username = payload.get("username")
    
    user = _get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # 创建新的 Access Token
    access_token = create_token(user_id, username, ACCESS_TOKEN_EXPIRE_DAYS)
    refresh_token = create_token(user_id, username, REFRESH_TOKEN_EXPIRE_DAYS)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 3600,
        "user": {
            "id": user_id,
            "username": username,
            "email": user.get("email"),
            "role": user.get("role", "user"),
        }
    }


# ===== 忘记密码端点 =====

class ForgotPasswordRequest(BaseModel):
    """忘记密码请求"""
    email: str

class ForgotPasswordResponse(BaseModel):
    """忘记密码响应"""
    email_registered: bool
    message: str = ""
    reset_link: str = ""
    note: str = ""

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(req: ForgotPasswordRequest):
    """忘记密码：生成重置链接（开发模式：直接返回链接）"""
    print(f"[FORGOT] Received request: email={req.email}")
    
    conn = get_db()
    try:
        # 查找用户
        cursor = conn.execute(
            "SELECT id, username, email FROM users WHERE email = ? AND is_active = 1",
            (req.email,)
        )
        row = cursor.fetchone()
        
        print(f"[FORGOT] DB query result: {row}")
        
        if not row:
            # 邮箱未注册（为了安全，不透露具体原因）
            print(f"[FORGOT] Email NOT found: {req.email}")
            return ForgotPasswordResponse(
                email_registered=False,
                message="如果您输入的邮箱已注册，重置链接将显示在下方。"
            )
        
        print(f"[FORGOT] ***** DEBUG: v2.0 *****")
        print(f"[FORGOT] Email found: user_id={row['id']}, username={row['username']}")
        
        # 生成重置 token（简化版：用 JWT）
        user_id = row["id"]
        username = row["username"]
        reset_token = create_token(user_id, username, expires_days=1)  # 1小时有效
        
        # 构建重置链接（指向 HTML 页面，不是 API 端点）
        # 动态读取端口（从环境变量 PORT，默认 8080）
        import os as _os
        _port = _os.environ.get('PORT', '8080')
        reset_link = f"http://127.0.0.1:{_port}/api/auth/reset-password?token={reset_token}"
        
        print(f"[FORGOT] Reset link generated for {req.email}")
        
        return ForgotPasswordResponse(
            email_registered=True,
            message="密码重置链接已生成：",
            reset_link=reset_link,
            note="链接1小时内有效。请复制链接到浏览器打开。"
        )
    finally:
        conn.close()


# ===== 重置密码页面 =====

@router.get("/reset-password")
async def reset_password_page(token: str = None):
    """重置密码页面（GET 请求，显示 HTML 表单）"""
    print(f"[RESET-PAGE] Received request with token: {token[:30] if token else 'None'}...")
    
    if not token:
        html = """<html><body style="font-family: sans-serif; padding: 40px; text-align: center;"><h1>无效的重置链接</h1><p>缺少 token 参数。</p><p><a href="/auth/forgot">重新申请密码重置</a></p></body></html>"""
        return HTMLResponse(content=html, status_code=400)
    
    # 验证 token
    payload = decode_token(token)
    if not payload:
        html = """<html><body style="font-family: sans-serif; padding: 40px; text-align: center;"><h1>重置链接已过期</h1><p>请重新申请密码重置。</p><p><a href="/auth/forgot">重新申请</a></p></body></html>"""
        return HTMLResponse(content=html, status_code=400)
    
    print(f"[RESET-PAGE] Token valid: user_id={payload.get('sub')}, username={payload.get('username')}")
    
    # Token 有效，显示重置密码表单
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <title>重置密码 - Content Aggregator</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
        .auth-container {{ width: 100%; max-width: 400px; padding: 20px; }}
        .auth-card {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }}
        h1 {{ font-size: 24px; color: #1a1a1a; margin-bottom: 8px; }}
        .subtitle {{ color: #666; font-size: 14px; margin-bottom: 32px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; font-size: 14px; font-weight: 500; color: #333; margin-bottom: 8px; }}
        input {{ width: 100%; padding: 12px; border: 2px solid #e1e5e9; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }}
        button:hover {{ transform: translateY(-2px); }}
        button:disabled {{ opacity: 0.6; cursor: not-allowed; transform: none; }}
        .error-message {{ background: #fee; color: #c33; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; display: none; }}
        .error-message.show {{ display: block; }}
        .success-message {{ background: #d4edda; color: #155724; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; display: none; }}
        .success-message.show {{ display: block; }}
        .links {{ margin-top: 24px; text-align: center; font-size: 14px; }}
        .links a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .links a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="auth-card">
            <h1>🔑 重置密码</h1>
            <p class="subtitle">请输入新密码</p>
            
            <div class="error-message" id="errorEl"></div>
            <div class="success-message" id="successEl"></div>
            
            <form id="form" style="display: ;">
                <div class="form-group">
                    <label for="password">新密码</label>
                    <input type="password" id="password" placeholder="请输入新密码（至少6位）" required minlength="6">
                </div>
                <div class="form-group">
                    <label for="confirmPassword">确认新密码</label>
                    <input type="password" id="confirmPassword" placeholder="请再次输入新密码" required minlength="6">
                </div>
                <button type="submit" id="btn">重置密码</button>
            </form>
            
            <div class="links" id="links" style="display: none;">
                <a href="/auth/login">返回登录</a>
            </div>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('form');
        const btn = document.getElementById('btn');
        const errorEl = document.getElementById('errorEl');
        const successEl = document.getElementById('successEl');
        const links = document.getElementById('links');
        
        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            
            if (password.length < 6) {{
                errorEl.textContent = '密码长度至少6位';
                errorEl.classList.add('show');
                return;
            }}
            
            if (password !== confirmPassword) {{
                errorEl.textContent = '两次输入的密码不一致';
                errorEl.classList.add('show');
                return;
            }}
            
            btn.disabled = true;
            btn.textContent = '重置中...';
            errorEl.classList.remove('show');
            
            try {{
                const resp = await fetch('/api/auth/reset-password', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        token: '{token}',
                        new_password: password
                    }})
                }});
                
                const data = await resp.json();
                
                if (resp.ok && data.success) {{
                    successEl.textContent = '密码重置成功！正在跳转到登录页面...';
                    successEl.classList.add('show');
                    form.style.display = 'none';
                    links.style.display = '';
                    
                    setTimeout(() => {{
                        window.location.href = '/auth/login';
                    }}, 2000);
                }} else {{
                    errorEl.textContent = data.detail || '重置失败，请重试';
                    errorEl.classList.add('show');
                    btn.disabled = false;
                    btn.textContent = '重置密码';
                }}
            }} catch (err) {{
                errorEl.textContent = '网络错误，请稍后重试';
                errorEl.classList.add('show');
                btn.disabled = false;
                btn.textContent = '重置密码';
            }}
        }});
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html)


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    token: str
    new_password: str


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """重置密码（POST 请求，处理密码重置）"""
    print(f"[RESET] Received request: token={req.token[:30]}...")
    
    # 验证 token
    payload = decode_token(req.token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    user_id = payload.get("sub")
    username = payload.get("username")
    
    print(f"[RESET] Token valid: user_id={user_id}, username={username}")
    
    # 更新密码
    conn = get_db()
    try:
        new_hash = hash_password(req.new_password)
        cursor = conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_hash, datetime.utcnow().isoformat(), user_id)
        )
        conn.commit()
        
        print(f"[RESET] Password updated for user {username}")
        
        return {"success": True, "message": "Password reset successfully"}
    finally:
        conn.close()
