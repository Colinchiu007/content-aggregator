"""
SQLite 数据存储 — 使用 aiosqlite

表结构:
    collected_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL,
        title TEXT,
        content TEXT,
        url TEXT,
        author TEXT,
        published_at TEXT,
        summary TEXT,
        tags TEXT,           -- JSON array
        metadata TEXT,       -- JSON object
        collected_at TEXT NOT NULL,
        source_success INTEGER,
        source_error TEXT
    )
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from content_aggregator.sources.collectors.base_collector import SourceResult
from .abstract import DataStore


class DbDataStore(DataStore):
    """SQLite 数据库存储"""

    def __init__(self, db_path: str = "./output/collected.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collected_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                title TEXT,
                content TEXT,
                url TEXT,
                author TEXT,
                published_at TEXT,
                summary TEXT,
                tags TEXT,
                metadata TEXT,
                collected_at TEXT NOT NULL,
                source_success INTEGER,
                source_error TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON collected_items(source_name)")
        conn.commit()
        conn.close()

    async def save(self, result: SourceResult) -> str:
        conn = self._get_conn()
        now = datetime.now().isoformat()
        count = 0
        for article in result.data:
            conn.execute("""
                INSERT INTO collected_items
                (source_name, title, content, url, author, published_at,
                 summary, tags, metadata, collected_at, source_success, source_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.source_name,
                article.get("title"),
                article.get("content"),
                article.get("url"),
                article.get("author"),
                str(article.get("published_at") or ""),
                article.get("summary"),
                json.dumps(article.get("tags", []), ensure_ascii=False),
                json.dumps(article.get("metadata", {}), ensure_ascii=False),
                now,
                1 if result.success else 0,
                result.error,
            ))
            count += 1
        conn.commit()
        conn.close()
        return f"{self.db_path} ({count} items)"

    async def query(self, source_name: Optional[str] = None,
                    limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        if source_name:
            rows = conn.execute(
                "SELECT * FROM collected_items WHERE source_name = ? "
                "ORDER BY collected_at DESC LIMIT ? OFFSET ?",
                (source_name, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM collected_items ORDER BY collected_at DESC "
                "LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        conn.close()

        results = []
        for row in rows:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
            d["metadata"] = json.loads(d["metadata"]) if d.get("metadata") else {}
            results.append(d)
        return results

    async def count(self, source_name: Optional[str] = None) -> int:
        conn = self._get_conn()
        if source_name:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM collected_items WHERE source_name = ?",
                (source_name,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM collected_items").fetchone()
        conn.close()
        return row["cnt"] if row else 0
