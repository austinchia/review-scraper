import os
import sqlite3
import pytest
from unittest.mock import patch

# Point at a temp DB so tests don't touch the real one
TEST_DB = ":memory:"


def _seed_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, query TEXT, title TEXT, text TEXT NOT NULL,
            text_hash TEXT UNIQUE NOT NULL, rating INTEGER, date TEXT,
            url TEXT, scraped_at TEXT, week_id TEXT, processed INTEGER DEFAULT 0
        )
    """)
    conn.executemany(
        "INSERT INTO reviews (source, text, text_hash, week_id) VALUES (?, ?, ?, ?)",
        [
            ("reddit", "text1", "h1", "2026-W25"),
            ("reddit", "text2", "h2", "2026-W25"),
            ("trustpilot", "text3", "h3", "2026-W26"),
        ]
    )
    conn.commit()


def test_fetch_weekly_counts_returns_sorted_weeks(tmp_path):
    db_path = str(tmp_path / "reviews.db")
    conn = sqlite3.connect(db_path)
    _seed_db(conn)
    conn.close()

    with patch("processing.storage.DB_PATH", db_path):
        from processing.storage import fetch_weekly_counts
        result = fetch_weekly_counts()

    assert len(result) == 2
    assert result[0] == {"week_id": "2026-W25", "count": 2}
    assert result[1] == {"week_id": "2026-W26", "count": 1}


def test_fetch_weekly_counts_empty_db(tmp_path):
    db_path = str(tmp_path / "reviews.db")
    conn = sqlite3.connect(db_path)
    _seed_db(conn)
    conn.execute("DELETE FROM reviews")
    conn.commit()
    conn.close()

    with patch("processing.storage.DB_PATH", db_path):
        from processing.storage import fetch_weekly_counts
        result = fetch_weekly_counts()

    assert result == []
