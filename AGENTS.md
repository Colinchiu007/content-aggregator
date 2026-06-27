# content-aggregator — 开发规范

> 语言: Python  |  文件数: ~324  |  生成: /init-deep

## 项目概述

content-aggregator: content-aggregator (HotRewrite v2)

## 源目录结构

- `frontend/` — 主源码目录
  - `src/`
- `backend/` — 主源码目录
  - `alembic/`
  - `app/`
- `content_aggregator/` — 主源码目录

## 硬约束（来自 .clinerules）

- 采集来源配置必须通过环境变量管理，禁止硬编码 URL 和 API Key
- AI 改写使用 HotRewrite v2 引擎，不引入其他改写方案
- 改写结果必须经过质量评分（质量分低于阈值时告警不阻塞）

## 入口文件

- `CLAUDE.md` — 开发指南和命令
- `.clinerules` — 项目特定硬约束
- `frontend/` — 源码入口
- `AGENTS.md` — 本文件，AI 行为规范

## 管道位置

- 上游: `trendscope/` — 数据来源
- 当前: `content-aggregator/`
- 下游: `content-aggregator-shared/` — 数据去向
