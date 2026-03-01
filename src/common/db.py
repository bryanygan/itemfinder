"""SQLite database helpers."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from src.common.config import DB_PATH


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    _ensure_dir(path)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64 MB
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS raw_messages (
            id            TEXT PRIMARY KEY,
            channel       TEXT NOT NULL,
            channel_category TEXT,
            guild         TEXT,
            author        TEXT NOT NULL,
            author_id     TEXT,
            timestamp     TEXT NOT NULL,
            content       TEXT NOT NULL,
            source_file   TEXT,
            has_attachment INTEGER DEFAULT 0,
            reaction_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS processed_mentions (
            mention_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id    TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            channel       TEXT NOT NULL,
            author        TEXT NOT NULL,
            brand         TEXT,
            item          TEXT,
            variant       TEXT,
            intent_type   TEXT NOT NULL,
            intent_score  REAL NOT NULL DEFAULT 0,
            text_norm     TEXT,
            FOREIGN KEY (message_id) REFERENCES raw_messages(id)
        );

        CREATE INDEX IF NOT EXISTS idx_raw_timestamp ON raw_messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_raw_channel ON raw_messages(channel);
        CREATE INDEX IF NOT EXISTS idx_pm_brand ON processed_mentions(brand);
        CREATE INDEX IF NOT EXISTS idx_pm_item ON processed_mentions(item);
        CREATE INDEX IF NOT EXISTS idx_pm_intent ON processed_mentions(intent_type);
        CREATE INDEX IF NOT EXISTS idx_pm_timestamp ON processed_mentions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_pm_channel ON processed_mentions(channel);
    """)


def insert_raw_messages(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    """Batch insert raw messages. Returns number inserted (skips duplicates)."""
    cur = conn.executemany(
        """INSERT OR IGNORE INTO raw_messages
           (id, channel, channel_category, guild, author, author_id,
            timestamp, content, source_file, has_attachment, reaction_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    return cur.rowcount


def insert_processed_mentions(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    cur = conn.executemany(
        """INSERT INTO processed_mentions
           (message_id, timestamp, channel, author, brand, item, variant,
            intent_type, intent_score, text_norm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    return cur.rowcount


def raw_message_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM raw_messages").fetchone()[0]


def processed_mention_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM processed_mentions").fetchone()[0]
