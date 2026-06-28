import logging
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.trustpilot.com"


class TrustpilotScraper(BaseScraper):
    def scrape(self, query: str, max_reviews: int = 50) -> list[dict]:
        reviews = []
        search_url = f"{BASE_URL}/search?query={quote_plus(query)}"
        try:
            resp = self.get(search_url)
        except RuntimeError as e:
            logger.error("Trustpilot search failed for '%s': %s", query, e)
            return reviews

        soup = BeautifulSoup(resp.text, "lxml")
        company_links = self._extract_company_links(soup)
        if not company_links:
            logger.warning("No companies found for query: %s", query)
            return reviews

        for company_url in company_links[:3]:
            if len(reviews) >= max_reviews:
                break
            reviews.extend(self._scrape_company(company_url, max_reviews - len(reviews)))
            time.sleep(1)

        logger.info("Trustpilot: collected %d reviews for '%s'", len(reviews), query)
        return reviews

    def _extract_company_links(self, soup: BeautifulSoup) -> list[str]:
        links = []
        for a in soup.select("a[href^='/review/']"):
            href = a.get("href", "")
            if href and href not in links:
                links.append(f"{BASE_URL}{href}")
        return links

    def _scrape_company(self, url: str, max_reviews: int) -> list[dict]:
        reviews = []
        page = 1
        while len(reviews) < max_reviews:
            page_url = f"{url}?page={page}"
            try:
                resp = self.get(page_url)
            except RuntimeError as e:
                logger.warning("Failed to fetch %s: %s", page_url, e)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            page_reviews = self._parse_reviews(soup, url)
            if not page_reviews:
                break

            reviews.extend(page_reviews)
            page += 1
            time.sleep(0.5)

        return reviews[:max_reviews]

    def _parse_reviews(self, soup: BeautifulSoup, source_url: str) -> list[dict]:
        reviews = []
        for card in soup.select("[data-service-review-card-paper]"):
            try:
                text_el = card.select_one("[data-service-review-text-typography]")
                title_el = card.select_one("[data-service-review-title-typography]")
                rating_el = card.select_one("[data-service-review-rating]")
                date_el = card.select_one("time")

                text = text_el.get_text(strip=True) if text_el else ""
                title = title_el.get_text(strip=True) if title_el else ""
                date = date_el.get("datetime", "") if date_el else ""

                rating = None
                if rating_el:
                    star_img = rating_el.select_one("img[alt]")
                    if star_img:
                        alt = star_img.get("alt", "")
                        try:
                            rating = int(alt.split()[0])
                        except (ValueError, IndexError):
                            pass

                if text:
                    reviews.append({
                        "source": "trustpilot",
                        "title": title,
                        "text": text,
                        "rating": rating,
                        "date": date,
                        "url": source_url,
                    })
            except Exception as e:
                logger.debug("Error parsing review card: %s", e)

        return reviews
