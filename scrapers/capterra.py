import logging
import re
import cloudscraper
from bs4 import BeautifulSoup
from config import PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.capterra.com/search/?query={query}"


def _make_scraper(use_proxy: bool = False):
    s = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    # DataImpulse proxy: enable on cloud servers where Cloudflare would block
    # datacenter IPs. Disabled by default — home residential IPs pass without it.
    if use_proxy and all([PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS]):
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        s.proxies = {"http": proxy_url, "https": proxy_url}
        logger.info("Capterra: DataImpulse proxy attached (%s:%s)", PROXY_HOST, PROXY_PORT)
    return s


class CapterraScraper:
    def scrape(self, query: str, max_products: int = 3) -> list[dict]:
        scraper = _make_scraper(use_proxy=True)
        url = _SEARCH_URL.format(query=query.replace(" ", "+"))
        logger.info("Capterra: fetching search results for '%s'", query)

        try:
            resp = scraper.get(url, timeout=25)
        except Exception as e:
            logger.error("Capterra: request failed: %s", e)
            return []

        if resp.status_code >= 400:
            logger.warning("Capterra: HTTP %s for query '%s'", resp.status_code, query)
            return []

        html = resp.text
        lower = html.lower()
        if "just a moment" in lower or "datadome" in lower or "captcha" in lower:
            logger.warning("Capterra: bot challenge detected")
            return []

        return self._parse(html, query, max_products)

    def _parse(self, html: str, query: str, max_products: int) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # All metric panels share data-testid containing "review"
        panels = soup.select("[data-testid*='review']")

        # Walk panels: the first matching "X.XX ( N,NNN )" starts a new product block
        overall_rating = None
        overall_count = None
        sub_ratings: list[tuple[str, str]] = []

        def _flush(q: str) -> dict | None:
            if overall_rating is None:
                return None
            parts = [
                f"{q.title()} on Capterra has an overall rating of {overall_rating} out of 5 stars"
            ]
            if overall_count:
                parts[0] += f", based on {overall_count} verified user reviews"
            parts[0] += "."
            if sub_ratings:
                sub_str = ", ".join(f"{k}: {v}" for k, v in sub_ratings[:6])
                parts.append(f"Category breakdown — {sub_str}.")
            parts.append(
                f"Capterra is a leading software review platform where verified buyers "
                f"rate products on ease of use, features, value for money, and support."
            )
            return {
                "source": "capterra",
                "title": f"{q.title()} — Capterra rating",
                "text": " ".join(parts),
                "rating": float(overall_rating),
                "review_count": int(overall_count.replace(",", "")) if overall_count else None,
                "date": "",
                "url": _SEARCH_URL.format(query=q.replace(" ", "+")),
            }

        for panel in panels:
            text = panel.get_text(separator=" ", strip=True)

            # Detect overall rating panel: "4.72 ( 2,771 )" or "4.72(2,771)"
            m_overall = re.match(r"^([\d\.]+)\s*\(?\s*([\d,]+)\s*\)?$", text.strip())
            if m_overall:
                # Save previous product block
                flushed = _flush(query)
                if flushed and len(results) < max_products:
                    results.append(flushed)
                overall_rating = m_overall.group(1)
                overall_count = m_overall.group(2)
                sub_ratings = []
                continue

            # Sub-rating panel: "Ease of Use 4.36"
            m_sub = re.match(r"^(.+?)\s+([\d]\.\d{1,2})$", text.strip())
            if m_sub and overall_rating is not None:
                label = m_sub.group(1).strip()
                value = m_sub.group(2)
                if len(label) <= 30:
                    sub_ratings.append((label, value))

        # Flush last block
        flushed = _flush(query)
        if flushed and len(results) < max_products:
            results.append(flushed)

        logger.info("Capterra: extracted %d product entries for '%s'", len(results), query)
        return results
