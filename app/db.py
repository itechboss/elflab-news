"""SQLite storage for news items."""

import sqlite3
from pathlib import Path

_db_path = None


def init_db(data_dir: str):
    global _db_path
    _db_path = Path(data_dir) / "news.db"
    conn = sqlite3.connect(str(_db_path), timeout=10)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id           INTEGER PRIMARY KEY,
            source       TEXT NOT NULL,
            source_id    TEXT NOT NULL,
            url          TEXT NOT NULL,
            title        TEXT NOT NULL,
            description  TEXT,
            score        REAL DEFAULT 0,
            velocity     REAL DEFAULT 0,
            category     TEXT,
            language     TEXT,
            stars        INTEGER,
            collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            published_at DATETIME,
            UNIQUE(source, source_id)
        );
        CREATE TABLE IF NOT EXISTS digests (
            id           INTEGER PRIMARY KEY,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            item_count   INTEGER
        );
    """)
    conn.close()


def _conn():
    return sqlite3.connect(str(_db_path), timeout=10)


def insert_item(*, source, source_id, url, title, description=None,
                score=0, velocity=0, category=None, language=None,
                stars=None, published_at=None):
    conn = _conn()
    conn.execute(
        """INSERT OR IGNORE INTO items
           (source, source_id, url, title, description, score, velocity,
            category, language, stars, published_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (source, source_id, url, title, description, score, velocity,
         category, language, stars, published_at))
    conn.commit()
    conn.close()


def update_score(item_id, score, velocity):
    conn = _conn()
    conn.execute(
        "UPDATE items SET score=?, velocity=? WHERE id=?",
        (score, velocity, item_id))
    conn.commit()
    conn.close()


def get_items_for_digest(limit=60, hours=72):
    conn = _conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM items
           WHERE collected_at > datetime('now', ?)
           ORDER BY score DESC LIMIT ?""",
        (f"-{hours} hours", limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_digest(item_count):
    conn = _conn()
    conn.execute("INSERT INTO digests (item_count) VALUES (?)", (item_count,))
    conn.commit()
    conn.close()
