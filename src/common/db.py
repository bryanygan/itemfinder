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


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Add new columns/tables to existing databases without data loss."""
    # Check if raw_messages exists before trying to migrate it
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "raw_messages" in tables:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(raw_messages)").fetchall()}
        if "source_platform" not in cols:
            conn.execute(
                "ALTER TABLE raw_messages ADD COLUMN source_platform TEXT DEFAULT 'discord'"
            )
            conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    # Run migrations for existing databases BEFORE index creation
    _migrate_db(conn)

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
            reaction_count INTEGER DEFAULT 0,
            source_platform TEXT DEFAULT 'discord'
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

        CREATE TABLE IF NOT EXISTS reddit_metadata (
            message_id    TEXT PRIMARY KEY,
            post_type     TEXT NOT NULL,
            subreddit     TEXT NOT NULL,
            flair         TEXT,
            score         INTEGER DEFAULT 0,
            upvote_ratio  REAL,
            num_comments  INTEGER DEFAULT 0,
            awards        INTEGER DEFAULT 0,
            parent_id     TEXT,
            permalink     TEXT,
            is_op         INTEGER DEFAULT 0,
            author_karma  INTEGER DEFAULT 0,
            FOREIGN KEY (message_id) REFERENCES raw_messages(id)
        );

        CREATE INDEX IF NOT EXISTS idx_raw_timestamp ON raw_messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_raw_channel ON raw_messages(channel);
        CREATE INDEX IF NOT EXISTS idx_raw_platform ON raw_messages(source_platform);
        CREATE INDEX IF NOT EXISTS idx_pm_brand ON processed_mentions(brand);
        CREATE INDEX IF NOT EXISTS idx_pm_item ON processed_mentions(item);
        CREATE INDEX IF NOT EXISTS idx_pm_intent ON processed_mentions(intent_type);
        CREATE INDEX IF NOT EXISTS idx_pm_timestamp ON processed_mentions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_pm_channel ON processed_mentions(channel);
        CREATE INDEX IF NOT EXISTS idx_reddit_subreddit ON reddit_metadata(subreddit);
        CREATE INDEX IF NOT EXISTS idx_reddit_flair ON reddit_metadata(flair);
        CREATE INDEX IF NOT EXISTS idx_reddit_score ON reddit_metadata(score);
        CREATE INDEX IF NOT EXISTS idx_reddit_post_type ON reddit_metadata(post_type);
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


def insert_raw_messages_reddit(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    """Batch insert Reddit messages into raw_messages. Returns number inserted."""
    cur = conn.executemany(
        """INSERT OR IGNORE INTO raw_messages
           (id, channel, channel_category, guild, author, author_id,
            timestamp, content, source_file, has_attachment, reaction_count,
            source_platform)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reddit')""",
        rows,
    )
    conn.commit()
    return cur.rowcount


def insert_reddit_metadata(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    """Batch insert Reddit-specific metadata."""
    cur = conn.executemany(
        """INSERT OR IGNORE INTO reddit_metadata
           (message_id, post_type, subreddit, flair, score, upvote_ratio,
            num_comments, awards, parent_id, permalink, is_op, author_karma)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    return cur.rowcount


def raw_message_count(conn: sqlite3.Connection, since: str | None = None,
                      platform: str | None = None) -> int:
    clauses, params = [], []
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    if platform:
        clauses.append("source_platform = ?")
        params.append(platform)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return conn.execute(f"SELECT COUNT(*) FROM raw_messages{where}", params).fetchone()[0]


def processed_mention_count(conn: sqlite3.Connection, since: str | None = None,
                            platform: str | None = None) -> int:
    clauses, params = [], []
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    if platform:
        clauses.append("message_id IN (SELECT id FROM raw_messages WHERE source_platform = ?)")
        params.append(platform)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return conn.execute(f"SELECT COUNT(*) FROM processed_mentions{where}", params).fetchone()[0]
