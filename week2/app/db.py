from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"


class DatabaseError(Exception):
    """数据库操作错误"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class DatabaseConnection:
    """数据库连接管理器"""
    _instance: Optional["DatabaseConnection"] = None
    
    def __new__(cls) -> "DatabaseConnection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def ensure_data_directory_exists(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        self.ensure_data_directory_exists()
        connection = None
        try:
            connection = sqlite3.connect(str(DB_PATH))
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise DatabaseError(f"数据库连接失败: {str(e)}", e)
        finally:
            if connection:
                connection.close()
    
    def initialize_database(self) -> None:
        """初始化数据库表结构"""
        try:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT NOT NULL,
                        created_at TEXT DEFAULT (datetime('now'))
                    );
                    """
                )
                
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS action_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        note_id INTEGER,
                        description TEXT NOT NULL,
                        priority TEXT,
                        assignee TEXT,
                        deadline TEXT,
                        category TEXT,
                        estimated_time TEXT,
                        done INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT (datetime('now')),
                        extraction_method TEXT DEFAULT 'rule_based',
                        FOREIGN KEY (note_id) REFERENCES notes(id)
                    );
                    """
                )
                
                # 检查并添加缺失的列
                self._migrate_table_structure(cursor)
                
                # 创建索引以提高查询性能
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_action_items_note_id ON action_items(note_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_action_items_done ON action_items(done)"
                )
                
                connection.commit()
                logger.info("Database initialized successfully")
                
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise DatabaseError(f"数据库初始化失败: {str(e)}", e)
    
    def _migrate_table_structure(self, cursor) -> None:
        """迁移表结构，添加缺失的列"""
        try:
            # 检查action_items表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='action_items'")
            if not cursor.fetchone():
                return
            
            # 检查缺失的列并添加
            cursor.execute("PRAGMA table_info(action_items)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            required_columns = {
                'description', 'priority', 'assignee', 'deadline', 
                'category', 'estimated_time', 'done', 'created_at', 'extraction_method'
            }
            
            missing_columns = required_columns - existing_columns
            
            for column in missing_columns:
                if column == 'description':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN description TEXT NOT NULL DEFAULT ''")
                elif column == 'priority':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN priority TEXT")
                elif column == 'assignee':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN assignee TEXT")
                elif column == 'deadline':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN deadline TEXT")
                elif column == 'category':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN category TEXT")
                elif column == 'estimated_time':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN estimated_time TEXT")
                elif column == 'done':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN done INTEGER DEFAULT 0")
                elif column == 'created_at':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")
                elif column == 'extraction_method':
                    cursor.execute("ALTER TABLE action_items ADD COLUMN extraction_method TEXT DEFAULT 'rule_based'")
                
                logger.info(f"Added missing column '{column}' to action_items table")
                
        except sqlite3.Error as e:
            logger.warning(f"Table migration failed: {e}")
            # 迁移失败不应阻止应用启动


# 全局数据库实例
db_connection = DatabaseConnection()


def insert_note(content: str) -> int:
    """插入笔记并返回ID"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO notes (content) VALUES (?)",
                (content.strip(),)
            )
            connection.commit()
            note_id = int(cursor.lastrowid)
            logger.debug(f"Inserted note with ID: {note_id}")
            return note_id
            
    except sqlite3.Error as e:
        logger.error(f"Failed to insert note: {e}")
        raise DatabaseError(f"插入笔记失败: {str(e)}", e)


def get_note(note_id: int) -> Optional[Dict[str, Any]]:
    """获取单个笔记"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, content, created_at FROM notes WHERE id = ?",
                (note_id,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
                
            return {
                "id": row["id"],
                "content": row["content"],
                "created_at": row["created_at"]
            }
            
    except sqlite3.Error as e:
        logger.error(f"Failed to get note {note_id}: {e}")
        raise DatabaseError(f"获取笔记失败: {str(e)}", e)


def list_notes(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """列出笔记（支持分页）"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, content, created_at 
                FROM notes 
                ORDER BY id DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "created_at": row["created_at"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Failed to list notes: {e}")
        raise DatabaseError(f"列出笔记失败: {str(e)}", e)


def insert_action_item(item_data: Dict[str, Any], note_id: Optional[int] = None) -> int:
    """插入单个行动项"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO action_items 
                (note_id, description, priority, assignee, deadline, category, estimated_time, done, extraction_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    item_data.get("description"),
                    item_data.get("priority"),
                    item_data.get("assignee"),
                    item_data.get("deadline"),
                    item_data.get("category"),
                    item_data.get("estimated_time"),
                    item_data.get("done", 0),
                    item_data.get("extraction_method", "rule_based")
                )
            )
            connection.commit()
            item_id = int(cursor.lastrowid)
            logger.debug(f"Inserted action item with ID: {item_id}")
            return item_id
            
    except sqlite3.Error as e:
        logger.error(f"Failed to insert action item: {e}")
        raise DatabaseError(f"插入行动项失败: {str(e)}", e)


def insert_action_items(items: List[Dict[str, Any]], note_id: Optional[int] = None) -> List[int]:
    """批量插入行动项"""
    ids: List[int] = []
    for item in items:
        item_id = insert_action_item(item, note_id)
        ids.append(item_id)
    return ids


def list_action_items(note_id: Optional[int] = None, done_only: bool = False) -> List[Dict[str, Any]]:
    """列出行动项（支持过滤）"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            
            if done_only:
                query = """
                    SELECT id, note_id, description, priority, assignee, deadline, 
                           category, estimated_time, done, created_at, extraction_method
                    FROM action_items 
                    WHERE done = 1 
                    ORDER BY id DESC
                """
                params: tuple = ()
            elif note_id is not None:
                query = """
                    SELECT id, note_id, description, priority, assignee, deadline, 
                           category, estimated_time, done, created_at, extraction_method
                    FROM action_items 
                    WHERE note_id = ? 
                    ORDER BY id DESC
                """
                params = (note_id,)
            else:
                query = """
                    SELECT id, note_id, description, priority, assignee, deadline, 
                           category, estimated_time, done, created_at, extraction_method
                    FROM action_items 
                    ORDER BY id DESC
                """
                params = ()
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row["id"],
                    "note_id": row["note_id"],
                    "description": row["description"],
                    "priority": row["priority"],
                    "assignee": row["assignee"],
                    "deadline": row["deadline"],
                    "category": row["category"],
                    "estimated_time": row["estimated_time"],
                    "done": bool(row["done"]),
                    "created_at": row["created_at"],
                    "extraction_method": row["extraction_method"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Failed to list action items: {e}")
        raise DatabaseError(f"列出行动项失败: {str(e)}", e)


def update_action_item_done(action_item_id: int, done: bool) -> Dict[str, Any]:
    """更新行动项完成状态"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            
            # 先检查是否存在
            cursor.execute(
                "SELECT id FROM action_items WHERE id = ?",
                (action_item_id,)
            )
            if cursor.fetchone() is None:
                raise DatabaseError(f"行动项 {action_item_id} 不存在")
            
            # 更新状态
            cursor.execute(
                "UPDATE action_items SET done = ? WHERE id = ?",
                (1 if done else 0, action_item_id)
            )
            connection.commit()
            
            logger.debug(f"Updated action item {action_item_id} done status to {done}")
            return {"id": action_item_id, "done": done}
            
    except sqlite3.Error as e:
        logger.error(f"Failed to update action item {action_item_id}: {e}")
        raise DatabaseError(f"更新行动项状态失败: {str(e)}", e)


def delete_action_item(action_item_id: int) -> bool:
    """删除行动项"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM action_items WHERE id = ?",
                (action_item_id,)
            )
            connection.commit()
            
            deleted_count = cursor.rowcount
            if deleted_count == 0:
                raise DatabaseError(f"行动项 {action_item_id} 不存在")
            
            logger.debug(f"Deleted action item {action_item_id}")
            return True
            
    except sqlite3.Error as e:
        logger.error(f"Failed to delete action item {action_item_id}: {e}")
        raise DatabaseError(f"删除行动项失败: {str(e)}", e)


def get_database_stats() -> Dict[str, int]:
    """获取数据库统计信息"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM notes")
            notes_count = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM action_items")
            items_count = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM action_items WHERE done = 1")
            completed_count = cursor.fetchone()["count"]
            
            return {
                "total_notes": notes_count,
                "total_action_items": items_count,
                "completed_items": completed_count,
                "pending_items": items_count - completed_count
            }
            
    except sqlite3.Error as e:
        logger.error(f"Failed to get database stats: {e}")
        raise DatabaseError(f"获取数据库统计信息失败: {str(e)}", e)


def check_connection() -> bool:
    """检查数据库连接是否正常"""
    try:
        with db_connection.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            return True
    except Exception:
        return False


def get_db() -> DatabaseConnection:
    """获取数据库连接实例（用于依赖注入）"""
    return db_connection