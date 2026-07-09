import html
import logging
import re
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_COMMENTS_URL = (
    "https://hn.algolia.com/api/v1/search"
    "?query={query}&tags=comment&hitsPerPage={limit}"
)
_STORIES_URL = (
    "https://hn.algolia.com/api/v1/search"
    "?query={query}&tags=story&hitsPerPage={limit}"
)


def _clean_html(raw: str) -> str:
    text = html.unescape(raw or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_relevant(text: str, title: str, query: str, require_title: bool = False) -> bool:
    """For comments, require the story title to name the product (not just the body),
    since short product names like 'notion' are also common English words."""
    needle = query.lower()
    if require_title:
        return needle in title.lower()
    return needle in (text + " " + title).lower()


class HackerNewsScraper(BaseScraper):
    """Fetches HN comments and stories via the free Algolia API.

    DataImpulse proxy (attached at BaseScraper) prevents IP rate-limiting
    when running at scale from a cloud server.
    """

    def scrape(self, query: str, max_items: int = 50) -> list[dict]:
        results = []
        half = max_items // 2

        comments = self._fetch(_COMMENTS_URL.format(query=query.replace(" ", "+"), limit=half * 2))
        for hit in comments:
            raw = hit.get("comment_text") or ""
            text = _clean_html(raw)
            title = hit.get("story_title") or ""
            if len(text) < 30 or not _is_relevant(text, title, query, require_title=True):
                continue
            results.append({
                "source": "hackernews",
                "title": title or query,
                "text": text,
                "rating": None,
                "date": hit.get("created_at", ""),
                "url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "author": hit.get("author", ""),
            })
            if len(results) >= half:
                break

        stories = self._fetch(_STORIES_URL.format(query=query.replace(" ", "+"), limit=half * 2))
        added = 0
        for hit in stories:
            title = hit.get("title") or ""
            raw_text = hit.get("story_text") or ""
            text = _clean_html(raw_text) or title
            if len(text) < 20 or not _is_relevant(text, title, query):
                continue
            results.append({
                "source": "hackernews",
                "title": title,
                "text": text,
                "rating": None,
                "date": hit.get("created_at", ""),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "author": hit.get("author", ""),
            })
            added += 1
            if added >= half:
                break

        logger.info("HackerNews: collected %d items for '%s'", len(results), query)
        return results[:max_items]

    def _fetch(self, url: str) -> list[dict]:
        try:
            resp = self.get(url)
            return resp.json().get("hits", [])
        except Exception as e:
            logger.error("HackerNews fetch failed: %s", e)
            return []
