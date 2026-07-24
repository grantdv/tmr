import sqlite3
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

DB_PATH = "data/queue.db"

@dataclass
class QueueTask:
    id: Optional[int]
    task_type: str
    payload: str
    status: str
    priority: int
    source_doc_id: str
    retries: int
    provider_used: Optional[str] = None
    created_at: Optional[str] = None
    processed_at: Optional[str] = None

def init_db():
    """Initialize the SQLite database for the extraction queue."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                source_doc_id TEXT NOT NULL,
                retries INTEGER DEFAULT 0,
                provider_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
        """)
        conn.commit()

def add_task(task_type: str, payload: str, source_doc_id: str, priority: int = 3) -> int:
    """Add a new task to the queue."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO extraction_queue (task_type, payload, status, priority, source_doc_id, retries) \
             VALUES (?, ?, ?, ?, ?, ?)",
            (task_type, payload, "pending", priority, source_doc_id, 0)
        )
        conn.commit()
        return cursor.lastrowid

def get_next_task(batch_size: int = 1) -> List[Dict[str, Any]]:
    """Fetch the next set of pending tasks, ordered by priority (lowest number first)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM extraction_queue WHERE status = 'pending' \
             ORDER BY priority ASC, created_at ASC LIMIT ?",
            (batch_size,)
        )
        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            tasks.append(dict(row))
            # Mark as processing so other workers don't grab it
            cursor.execute(
                "UPDATE extraction_queue SET status = 'processing' WHERE id = ?",
                (row['id'],)
            )
            conn.commit()
        return tasks

def update_task_status(task_id: int, status: str, provider: Optional[str] = None, retries: Optional[int] = None):
    """Update the status of a task."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if retries is not None:
            cursor.execute(
                "UPDATE extraction_queue SET status = ?, provider_used = ?, retries = ? WHERE id = ?",
                (status, provider, retries, task_id)
            )
        else:
            cursor.execute(
                "UPDATE extraction_queue SET status = ?, provider_used = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, provider, task_id)
            )
        conn.commit()

def get_queue_depth() -> int:
    """Return the number of pending tasks."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM extraction_queue WHERE status = 'pending'")
        return cursor.fetchone()[0]

# Initialize the DB immediately on import
init_db()
