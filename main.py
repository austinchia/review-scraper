import logging
import sys
from datetime import datetime

from config import SEARCH_QUERIES, MAX_REVIEWS_PER_SOURCE
from scrapers.trustpilot import TrustpilotScraper
from scrapers.reddit import RedditScraper
from processing.cleaner import clean
from processing.storage import save_reviews, fetch_unprocessed, mark_processed
from ai.analyser import analyse
from output.formatter import write_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def get_week_id() -> str:
    now = datetime.now()
    return now.strftime("%Y-W%W")


def run_scrapers(week_id: str) -> dict:
    stats = {"sources": {}, "total": 0}
    trustpilot = TrustpilotScraper()
    reddit = RedditScraper()

    for query in SEARCH_QUERIES.get("trustpilot", []):
        logger.info("Scraping Trustpilot for: %s", query)
        raw = trustpilot.scrape(query, max_reviews=MAX_REVIEWS_PER_SOURCE)
        cleaned = clean(raw, week_id)
        saved = save_reviews(cleaned, query=query)
        stats["sources"]["trustpilot"] = stats["sources"].get("trustpilot", 0) + saved

    for subreddit in SEARCH_QUERIES.get("reddit", []):
        logger.info("Scraping Reddit: %s", subreddit)
        raw = reddit.scrape(subreddit, max_posts=MAX_REVIEWS_PER_SOURCE)
        cleaned = clean(raw, week_id)
        saved = save_reviews(cleaned, query=subreddit)
        stats["sources"]["reddit"] = stats["sources"].get("reddit", 0) + saved

    stats["total"] = sum(stats["sources"].values())
    return stats


def main():
    logger.info("=== Review Mining Pipeline starting ===")

    week_id = get_week_id()
    logger.info("Week ID: %s", week_id)

    stats = run_scrapers(week_id)
    logger.info("Scraping complete. Stats: %s", stats)

    reviews = fetch_unprocessed(week_id)
    logger.info("Fetched %d unprocessed reviews for %s", len(reviews), week_id)

    if not reviews:
        logger.warning("No reviews to analyse — exiting early")
        return

    logger.info("Sending reviews to Claude for analysis...")
    analysis = analyse(reviews, topic="data analytics tools and communities")

    digest_path = write_digest(week_id, analysis, stats)
    logger.info("Digest saved: %s", digest_path)

    mark_processed([r["id"] for r in reviews])
    logger.info("Marked %d reviews as processed", len(reviews))

    print(f"\n=== Pipeline complete ===")
    print(f"Week:       {week_id}")
    print(f"Collected:  {stats['total']} items")
    for source, count in stats["sources"].items():
        print(f"  {source}: {count}")
    print(f"Digest:     {digest_path}")


if __name__ == "__main__":
    main()
