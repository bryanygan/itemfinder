"""Ingest DiscordChatExporter JSON files into SQLite.

Handles large files via ijson streaming. Falls back to stdlib json for small files.
Usage: python -m src.ingest.discord_ingest
"""

import json
import sys
from pathlib import Path

from src.common.config import BATCH_SIZE, DATA_DIRS, SKIP_CHANNELS
from src.common.db import get_connection, init_db, insert_raw_messages
from src.common.log_util import get_logger

log = get_logger("ingest")

try:
    import ijson
    HAS_IJSON = True
except ImportError:
    HAS_IJSON = False
    log.warning("ijson not installed – falling back to stdlib json (slower for large files)")


def _channel_name_clean(name: str) -> str:
    """Strip emoji prefixes and arrows from channel names."""
    for ch in "↠🌐⭐💼📊🪪🎁🛒👔👟🌭🎙❗❌📔🔍✨🌠💫🌟📈":
        name = name.replace(ch, "")
    return name.strip().strip("-").strip()


def _should_skip(channel_name: str) -> bool:
    cleaned = _channel_name_clean(channel_name).lower()
    return cleaned in SKIP_CHANNELS


def _total_reactions(reactions: list) -> int:
    return sum(r.get("count", 0) for r in reactions) if reactions else 0


def _parse_file_streaming(filepath: Path, guild_name: str, channel_name: str,
                          category: str, source: str):
    """Stream messages from a large JSON file using ijson."""
    batch: list[tuple] = []
    count = 0
    with open(filepath, "rb") as f:
        for msg in ijson.items(f, "messages.item"):
            content = msg.get("content", "")
            if not content or not content.strip():
                continue
            author_obj = msg.get("author", {})
            row = (
                msg["id"],
                channel_name,
                category,
                guild_name,
                author_obj.get("nickname") or author_obj.get("name", "unknown"),
                author_obj.get("id"),
                msg.get("timestamp", ""),
                content,
                source,
                1 if msg.get("attachments") else 0,
                _total_reactions(msg.get("reactions", [])),
            )
            batch.append(row)
            count += 1
            if len(batch) >= BATCH_SIZE:
                yield batch
                batch = []
    if batch:
        yield batch
    log.info(f"  streamed {count:,} messages from {filepath.name}")


def _parse_file_stdlib(filepath: Path, guild_name: str, channel_name: str,
                       category: str, source: str):
    """Parse entire JSON file into memory (for smaller files)."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    messages = data.get("messages", [])
    batch: list[tuple] = []
    count = 0
    for msg in messages:
        content = msg.get("content", "")
        if not content or not content.strip():
            continue
        author_obj = msg.get("author", {})
        row = (
            msg["id"],
            channel_name,
            category,
            guild_name,
            author_obj.get("nickname") or author_obj.get("name", "unknown"),
            author_obj.get("id"),
            msg.get("timestamp", ""),
            content,
            source,
            1 if msg.get("attachments") else 0,
            _total_reactions(msg.get("reactions", [])),
        )
        batch.append(row)
        count += 1
        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch
    log.info(f"  parsed {count:,} messages from {filepath.name}")


def _read_channel_meta(filepath: Path) -> tuple[str, str, str]:
    """Read guild, channel, and category from the file header without loading all messages."""
    guild_name = ""
    channel_name = ""
    category = ""
    if HAS_IJSON:
        with open(filepath, "rb") as f:
            parser = ijson.parse(f)
            for prefix, event, value in parser:
                if prefix == "guild.name":
                    guild_name = value or ""
                elif prefix == "channel.name":
                    channel_name = value or ""
                elif prefix == "channel.category":
                    category = value or ""
                if guild_name and channel_name:
                    break
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            # Read just enough to get the header
            chunk = ""
            for line in f:
                chunk += line
                if '"messages"' in line:
                    break
            try:
                # Parse partial JSON by closing it
                partial = chunk.rstrip().rstrip(",").rstrip("[")
                if not partial.endswith("}"):
                    partial += '"messages":[]}'
                data = json.loads(partial)
                guild_name = data.get("guild", {}).get("name", "")
                channel_name = data.get("channel", {}).get("name", "")
                category = data.get("channel", {}).get("category", "")
            except json.JSONDecodeError:
                pass
    return guild_name, channel_name, category


def _file_size_mb(p: Path) -> float:
    return p.stat().st_size / (1024 * 1024)


def ingest_all() -> int:
    conn = get_connection()
    init_db(conn)
    total = 0

    json_files: list[Path] = []
    for d in DATA_DIRS:
        if d.exists():
            json_files.extend(sorted(d.glob("*.json")))

    log.info(f"Found {len(json_files)} JSON files across {len(DATA_DIRS)} directories")

    for filepath in json_files:
        guild_name, channel_name, category = _read_channel_meta(filepath)
        clean_name = _channel_name_clean(channel_name)

        if _should_skip(clean_name.lower()):
            log.info(f"  SKIP {clean_name} (non-item channel)")
            continue

        log.info(f"Ingesting: {clean_name} ({category}) [{_file_size_mb(filepath):.1f} MB]")

        use_streaming = HAS_IJSON and _file_size_mb(filepath) > 5
        source = filepath.name
        parser = (_parse_file_streaming if use_streaming else _parse_file_stdlib)

        file_count = 0
        for batch in parser(filepath, guild_name, clean_name, category, source):
            inserted = insert_raw_messages(conn, batch)
            file_count += inserted

        total += file_count
        log.info(f"  => {file_count:,} new messages inserted")

    conn.close()
    log.info(f"Ingestion complete: {total:,} total messages inserted")
    return total


if __name__ == "__main__":
    ingest_all()
