# ──────────────────────────────────────────────
# HotRewrite v2 Backend Dockerfile
# 多阶段构建：builder → runtime
# ──────────────────────────────────────────────

FROM python:3.12-slim AS builder

WORKDIR /app

# 复制依赖文件
COPY pyproject.toml .
COPY README.md .

# 安装依赖到隔离目录（用于后续复制）
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/deps \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.30.0 \
    sqlalchemy[asyncio]>=2.0.30 \
    asyncpg>=0.29.0 \
    alembic>=1.13.0 \
    pydantic>=2.7.0 \
    pydantic-settings>=2.3.0 \
    python-jose[cryptography]>=3.3.0 \
    passlib[bcrypt]>=1.7.4 \
    httpx>=0.27.0 \
    trafilatura>=1.12.0 \
    redis[hiredis]>=5.0.0 \
    python-multipart>=0.0.9


FROM python:3.12-slim AS runtime

WORKDIR /app

# 从 builder 复制依赖
COPY --from=builder /deps /usr/local/lib/python3.12/site-packages/

# 复制应用代码
COPY app/ ./app/
COPY alembic.ini .
COPY alembic/ ./alembic/

# 非 root 用户
RUN groupadd -r hotrewrite && useradd -r -g hotrewrite hotrewrite && \
    chown -R hotrewrite:hotrewrite /app
USER hotrewrite

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
