import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reviews.db")

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    query       TEXT,
    title       TEXT,
    text        TEXT NOT NULL,
    text_hash   TEXT UNIQUE NOT NULL,
    rating      INTEGER,
    date        TEXT,
    url         TEXT,
    scraped_at  TEXT,
    week_id     TEXT,
    processed   INTEGER DEFAULT 0
)
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_TABLE)
    conn.commit()
    return conn


def save_reviews(reviews: list[dict], query: str = "") -> int:
    if not reviews:
        return 0
    conn = _connect()
    inserted = 0
    with conn:
        for r in reviews:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO reviews
                       (source, query, title, text, text_hash, rating, date, url, scraped_at, week_id, processed)
                       VALUES (:source, :query, :title, :text, :text_hash, :rating, :date, :url, :scraped_at, :week_id, :processed)""",
                    {
                        "source": r.get("source", ""),
                        "query": query,
                        "title": r.get("title", ""),
                        "text": r["text"],
                        "text_hash": r["text_hash"],
                        "rating": r.get("rating"),
                        "date": r.get("date", ""),
                        "url": r.get("url", ""),
                        "scraped_at": r.get("scraped_at", ""),
                        "week_id": r.get("week_id", ""),
                        "processed": r.get("processed", 0),
                    },
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning("DB insert error: %s", e)
    conn.close()
    logger.info("Saved %d new reviews to DB (query: %s)", inserted, query)
    return inserted


def fetch_unprocessed(week_id: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM reviews WHERE week_id = ? AND processed = 0", (week_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_processed(ids: list[int]):
    if not ids:
        return
    conn = _connect()
    with conn:
        conn.executemany(
            "UPDATE reviews SET processed = 1 WHERE id = ?", [(i,) for i in ids]
        )
    conn.close()
