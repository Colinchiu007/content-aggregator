# v1 Content Aggregator — Archived Code

This directory contains the v1 codebase of **Content Aggregator** (内容聚合与改写平台), a Python 3.12 + Jinja2 + SQLite MVP (~23K LOC) that provided:

- Multi-source content collection (RSS, YouTube, Twitter, TikTok, etc.)
- AI-powered rewriting via DeepSeek / OpenAI / Qwen (6 strategies)
- Content filtering (sensitive word detection, deduplication)
- Multi-format export (Markdown, HTML, JSON, TXT, Xiaohongshu)
- Web UI (Jinja2 templates via FastAPI)
- CLI tools

## Why Archived?

The project has been redirected toward **v2: HotRewrite 热文改写一站式平台**, a Vue 3 + PostgreSQL vision. See `02-source/PRD/PROJECT-001-PRD-2026-06-15.md` for the current design spec.

## Directory Layout

| Directory | Description |
|-----------|-------------|
| `src/` | Python source (content_aggregator package) |
| `web/` | Jinja2 web UI + FastAPI server |
| `wechat_publisher/` | WeChat publishing integration |
| `tests/` | Test suite |
| `scripts/` | CLI scripts (run.py, web.py, etc.) |
| `tools/` | Development utilities |
| `config/` | YAML configuration files |
| `data/` | SQLite databases |
| `migrations/` | Database migration scripts |
| `specs/` | Functional specifications |
| `docs/` | API documentation |
| `output/` | Export output directory |
| `openspec/` | OpenSpec formal specs |
| `root_debug/` | Root-level debug scripts and artifact files |
