import logging
import os
import sys
from datetime import datetime

from config import SEARCH_QUERIES, MAX_REVIEWS_PER_SOURCE, ANALYSIS_TOPIC
from scrapers.capterra import CapterraScraper
from scrapers.hackernews import HackerNewsScraper
from scrapers.reddit import RedditScraper
from processing.cleaner import clean
from processing.storage import save_reviews, fetch_unprocessed, mark_processed, fetch_source_counts
from ai.analyser import analyse
from output.formatter import write_digest
from output.html_generator import write_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

DIGESTS_DIR = os.path.join(os.path.dirname(__file__), "digests")


def get_week_id() -> str:
    return datetime.now().strftime("%Y-W%W")


def _last_digest() -> str | None:
    """Return the most recent digest text, or None if none exist."""
    if not os.path.isdir(DIGESTS_DIR):
        return None
    files = sorted(f for f in os.listdir(DIGESTS_DIR) if f.endswith(".md"))
    if not files:
        return None
    with open(os.path.join(DIGESTS_DIR, files[-1]), encoding="utf-8") as fh:
        return fh.read()


def run_scrapers(week_id: str) -> dict:
    stats = {"sources": {}, "total": 0}
    reddit = RedditScraper()
    capterra = CapterraScraper()
    hn = HackerNewsScraper()

    for subreddit in SEARCH_QUERIES.get("reddit", []):
        logger.info("Scraping Reddit: %s", subreddit)
        raw = reddit.scrape(subreddit, max_posts=MAX_REVIEWS_PER_SOURCE)
        cleaned = clean(raw, week_id)
        saved = save_reviews(cleaned, query=subreddit)
        stats["sources"]["reddit"] = stats["sources"].get("reddit", 0) + saved

    for query in SEARCH_QUERIES.get("capterra", []):
        logger.info("Scraping Capterra for: %s", query)
        raw = capterra.scrape(query, max_products=10)
        cleaned = clean(raw, week_id)
        saved = save_reviews(cleaned, query=query)
        stats["sources"]["capterra"] = stats["sources"].get("capterra", 0) + saved

    for query in SEARCH_QUERIES.get("hackernews", []):
        logger.info("Scraping Hacker News for: %s", query)
        raw = hn.scrape(query, max_items=MAX_REVIEWS_PER_SOURCE)
        cleaned = clean(raw, week_id)
        saved = save_reviews(cleaned, query=query)
        stats["sources"]["hackernews"] = stats["sources"].get("hackernews", 0) + saved

    stats["total"] = sum(stats["sources"].values())
    return stats


def _build_display_stats() -> dict:
    """DB totals per source — always reflects the full collected dataset."""
    db_totals = fetch_source_counts()
    return {"sources": db_totals, "total": sum(db_totals.values())}


def main():
    logger.info("=== Review Mining Pipeline starting ===")

    week_id = get_week_id()
    logger.info("Week ID: %s", week_id)

    run_stats = run_scrapers(week_id)
    logger.info("Scraping complete. New items this run: %s", run_stats)

    reviews = fetch_unprocessed(week_id)
    logger.info("Fetched %d unprocessed reviews for %s", len(reviews), week_id)

    display_stats = _build_display_stats()

    if not reviews:
        logger.info("No new reviews — refreshing dashboard with existing data")
        last = _last_digest()
        if last:
            dashboard_path = write_dashboard(week_id, last, display_stats)
            logger.info("Dashboard refreshed: %s", dashboard_path)
        else:
            logger.warning("No digest found — skipping dashboard update")
        _print_summary(week_id, run_stats, display_stats)
        return

    logger.info("Sending to Gemini for analysis...")
    analysis = analyse(reviews, topic=ANALYSIS_TOPIC)

    digest_path = write_digest(week_id, analysis, run_stats)
    logger.info("Digest saved: %s", digest_path)

    dashboard_path = write_dashboard(week_id, analysis, display_stats)
    logger.info("Dashboard written: %s", dashboard_path)

    mark_processed([r["id"] for r in reviews])
    logger.info("Marked %d reviews as processed", len(reviews))

    _print_summary(week_id, run_stats, display_stats, digest_path, dashboard_path)


def _print_summary(week_id, run_stats, display_stats, digest_path="", dashboard_path=""):
    print(f"\n=== Pipeline complete ===")
    print(f"Week:         {week_id}")
    print(f"New this run: {run_stats['total']}")
    print(f"DB totals:")
    for source, count in sorted(display_stats["sources"].items()):
        print(f"  {source}: {count}")
    if digest_path:
        print(f"Digest:       {digest_path}")
    if dashboard_path:
        print(f"Dashboard:    {dashboard_path}")


if __name__ == "__main__":
    main()
