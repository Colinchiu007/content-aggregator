#!/usr/bin/env python3
"""
Migration: Create rewrite_strategies table
Run: python scripts/migrate_add_rewrite_strategies.py
"""

import sqlite3
import os

# Database path (relative to project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "content_aggregator.db")

def migrate():
    """Create rewrite_strategies table if not exists"""
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table exists
    check_sql = """
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name='rewrite_strategies';
    """
    
    cursor.execute(check_sql)
    result = cursor.fetchone()
    
    if result:
        print("[OK] Table 'rewrite_strategies' already exists, skipping migration")
        conn.close()
        return
    
    # Create table
    create_sql = """
    CREATE TABLE rewrite_strategies (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        is_default INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    cursor.execute(create_sql)
    conn.commit()
    print("[OK] Table 'rewrite_strategies' created successfully")
    
    # Create index for faster queries
    index_sql = """
    CREATE INDEX IF NOT EXISTS idx_rewrite_strategies_is_default 
    ON rewrite_strategies(is_default);
    """
    cursor.execute(index_sql)
    conn.commit()
    print("[OK] Index created on 'is_default'")
    
    conn.close()

if __name__ == "__main__":
    migrate()
