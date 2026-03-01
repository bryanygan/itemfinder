"""Main processing pipeline: normalize → classify → extract → store.

Usage: python -m src.process.pipeline
"""

import sqlite3

from src.common.config import BATCH_SIZE
from src.common.db import get_connection, insert_processed_mentions, raw_message_count
from src.common.log_util import get_logger
from src.process.classify import classify_intent_from_channel
from src.process.extract import extract_all, extract_items_from_listing
from src.process.normalize import is_listing, is_spam_or_empty, normalize_text

log = get_logger("pipeline")


def _process_batch(conn: sqlite3.Connection, messages: list[sqlite3.Row]) -> int:
    """Process a batch of raw messages and insert processed mentions."""
    rows_to_insert: list[tuple] = []

    for msg in messages:
        raw_content = msg["content"]
        text_norm = normalize_text(raw_content)

        if is_spam_or_empty(text_norm):
            continue

        channel = msg["channel"]
        author = msg["author"]
        timestamp = msg["timestamp"]
        message_id = msg["id"]

        # Check if this is a multi-item listing
        if is_listing(raw_content):
            items = extract_items_from_listing(normalize_text(raw_content))
            for item_data in items:
                intent, score = classify_intent_from_channel(channel, text_norm)
                rows_to_insert.append((
                    message_id, timestamp, channel, author,
                    item_data["brand"], item_data["item"], item_data["variant"],
                    intent, score, text_norm[:500],
                ))
        else:
            entities = extract_all(text_norm)
            intent, score = classify_intent_from_channel(channel, text_norm)

            # Only store if we extracted something or have a non-neutral intent
            if entities["brand"] or entities["item"] or intent != "neutral":
                rows_to_insert.append((
                    message_id, timestamp, channel, author,
                    entities["brand"], entities["item"], entities["variant"],
                    intent, score, text_norm[:500],
                ))

    if rows_to_insert:
        return insert_processed_mentions(conn, rows_to_insert)
    return 0


def run_pipeline() -> int:
    """Run the full processing pipeline on all raw messages."""
    conn = get_connection()
    total_raw = raw_message_count(conn)
    log.info(f"Processing {total_raw:,} raw messages")

    # Clear previous processed data
    conn.execute("DELETE FROM processed_mentions")
    conn.commit()

    offset = 0
    total_processed = 0

    while True:
        messages = conn.execute(
            "SELECT * FROM raw_messages ORDER BY timestamp LIMIT ? OFFSET ?",
            (BATCH_SIZE, offset),
        ).fetchall()

        if not messages:
            break

        inserted = _process_batch(conn, messages)
        total_processed += inserted
        offset += len(messages)

        if offset % 10000 == 0:
            log.info(f"  processed {offset:,}/{total_raw:,} messages => {total_processed:,} mentions")

    log.info(f"Pipeline complete: {total_processed:,} mentions from {total_raw:,} messages")
    conn.close()
    return total_processed


if __name__ == "__main__":
    run_pipeline()
