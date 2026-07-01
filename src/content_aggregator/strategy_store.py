"""
Rewrite Strategy Storage
"""

import sqlite3
import uuid
from datetime import datetime


class RewriteStrategyStore:
    """Rewrite strategy storage class"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create(self, name: str, description: str, is_default: bool = False) -> dict:
        """Create a new rewrite strategy"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        strategy_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        # If setting as default, clear other defaults first
        if is_default:
            cursor.execute("UPDATE rewrite_strategies SET is_default = 0")
        
        cursor.execute(
            """INSERT INTO rewrite_strategies 
               (id, name, description, is_default, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (strategy_id, name, description, 1 if is_default else 0, now, now)
        )
        
        conn.commit()
        conn.close()
        
        return self.get(strategy_id)
    
    def get_all(self) -> list:
        """Get all strategies"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM rewrite_strategies ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_default(self):
        """Get default strategy"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM rewrite_strategies WHERE is_default = 1 LIMIT 1")
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get(self, strategy_id: str):
        """Get strategy by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM rewrite_strategies WHERE id = ?", (strategy_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update(self, strategy_id: str, name=None, description=None, is_default=None):
        """Update strategy"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if strategy exists
        cursor.execute("SELECT id FROM rewrite_strategies WHERE id = ?", (strategy_id,))
        if not cursor.fetchone():
            conn.close()
            return None
        
        # If setting as default, clear other defaults first
        if is_default is not None and is_default:
            cursor.execute("UPDATE rewrite_strategies SET is_default = 0")
        
        # Build update query dynamically
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if is_default is not None:
            updates.append("is_default = ?")
            params.append(1 if is_default else 0)
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        
        params.append(strategy_id)
        
        sql = f"UPDATE rewrite_strategies SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, params)
        
        conn.commit()
        conn.close()
        
        return self.get(strategy_id)
    
    def delete(self, strategy_id: str) -> bool:
        """Delete strategy"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if it's the default strategy
        cursor.execute("SELECT is_default FROM rewrite_strategies WHERE id = ?", (strategy_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False
        
        # Don't allow deleting default strategy
        if row[0] == 1:
            conn.close()
            raise ValueError("Cannot delete default strategy. Please set another strategy as default first.")
        
        cursor.execute("DELETE FROM rewrite_strategies WHERE id = ?", (strategy_id,))
        
        conn.commit()
        conn.close()
        
        return True
