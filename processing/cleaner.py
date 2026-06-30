import hashlib
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean(reviews: list[dict], week_id: str) -> list[dict]:
    seen_hashes = set()
    cleaned = []
    now = datetime.now(timezone.utc).isoformat()

    for r in reviews:
        text = _strip_html(r.get("text", ""))
        if not text:
            continue
        if len(text.split()) < 20:
            logger.debug("Skipping short review (%d words)", len(text.split()))
            continue

        h = _hash_text(text)
        if h in seen_hashes:
            logger.debug("Duplicate skipped")
            continue
        seen_hashes.add(h)

        cleaned.append({
            **r,
            "text": text,
            "text_hash": h,
            "scraped_at": now,
            "week_id": week_id,
            "processed": 0,
        })

    logger.info("Cleaned %d -> %d reviews (dupes/short removed)", len(reviews), len(cleaned))
    return cleaned
