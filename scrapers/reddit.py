import logging
import time
from xml.etree import ElementTree as ET
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

REDDIT_RSS = "https://www.reddit.com/r/{sub}/.rss?limit=25"
ATOM_NS = "http://www.w3.org/2005/Atom"


class RedditScraper(BaseScraper):
    def __init__(self):
        super().__init__(use_proxy=True)
        self.session.headers.update({
            "User-Agent": "review-mining-bot/1.0 (personal use script)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        })

    def get(self, url: str, retries: int = 4, **kwargs):
        import requests
        delay = 2
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=15, **kwargs)
                if resp.status_code in (429, 503):
                    logger.warning("Rate limited (%s) — retrying in %ds", resp.status_code, delay)
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                logger.warning("Request failed (attempt %d/%d): %s", attempt + 1, retries, e)
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
        raise RuntimeError(f"All {retries} attempts failed for {url}")

    def scrape(self, subreddit_name: str, max_posts: int = 50) -> list[dict]:
        sub = subreddit_name.lstrip("r/")
        results = []
        url = REDDIT_RSS.format(sub=sub)

        try:
            resp = self.get(url)
            root = ET.fromstring(resp.content)
        except Exception as e:
            logger.error("Reddit RSS fetch failed for r/%s: %s", sub, e)
            return results

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            if len(results) >= max_posts:
                break

            title_el = entry.find(f"{{{ATOM_NS}}}title")
            link_el = entry.find(f"{{{ATOM_NS}}}link")
            updated_el = entry.find(f"{{{ATOM_NS}}}updated")
            content_el = entry.find(f"{{{ATOM_NS}}}content")

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link = link_el.get("href", "") if link_el is not None else ""
            date = updated_el.text.strip() if updated_el is not None and updated_el.text else ""
            content = content_el.text or "" if content_el is not None else ""

            # Strip HTML tags from content
            import re
            text = re.sub(r"<[^>]+>", " ", content).strip()
            text = re.sub(r"\s+", " ", text)
            if not text or len(text) < 10:
                text = title

            results.append({
                "source": "reddit",
                "title": title,
                "text": text,
                "rating": None,
                "date": date,
                "url": link,
                "subreddit": sub,
                "score": None,
            })

            time.sleep(0.3)

        logger.info("Reddit: collected %d posts from r/%s", len(results), sub)
        return results[:max_posts]
