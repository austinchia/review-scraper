import logging
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from config import PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS

logger = logging.getLogger(__name__)

BASE_URL = "https://www.trustpilot.com"
_TIMEOUT = 30_000  # ms


def _proxy_config() -> dict | None:
    if all([PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS]):
        return {
            "server":   f"http://{PROXY_HOST}:{PROXY_PORT}",
            "username": PROXY_USER,
            "password": PROXY_PASS,
        }
    return None


class TrustpilotScraper:
    def scrape(self, query: str, max_reviews: int = 50) -> list[dict]:
        reviews = []
        proxy = _proxy_config()
        if not proxy:
            logger.warning("No proxy configured — Trustpilot will likely block the request")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy=proxy)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = ctx.new_page()

            try:
                search_url = f"{BASE_URL}/search?query={quote_plus(query)}"
                logger.info("Trustpilot: fetching search page for '%s'", query)
                page.goto(search_url, wait_until="load", timeout=_TIMEOUT)
                page.wait_for_timeout(3000)  # let DataDome resolve

                company_links = self._extract_company_links(page.content())
                if not company_links:
                    logger.warning("No companies found for query: %s", query)
                    return reviews

                for company_url in company_links[:3]:
                    if len(reviews) >= max_reviews:
                        break
                    page.goto(company_url, wait_until="load", timeout=_TIMEOUT)
                    page.wait_for_timeout(2000)
                    page_reviews = self._parse_reviews(page.content(), company_url)
                    reviews.extend(page_reviews)
                    time.sleep(1)

            except PlaywrightTimeout as e:
                logger.error("Trustpilot playwright timeout: %s", e)
            except Exception as e:
                logger.error("Trustpilot scrape error: %s", e)
            finally:
                browser.close()

        logger.info("Trustpilot: collected %d reviews for '%s'", len(reviews), query)
        return reviews

    def _extract_company_links(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.select("a[href^='/review/']"):
            href = a.get("href", "")
            if href and href not in links:
                links.append(f"{BASE_URL}{href}")
        return links

    def _parse_reviews(self, html: str, source_url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        reviews = []
        for card in soup.select("[data-service-review-card-paper]"):
            try:
                text_el   = card.select_one("[data-service-review-text-typography]")
                title_el  = card.select_one("[data-service-review-title-typography]")
                rating_el = card.select_one("[data-service-review-rating]")
                date_el   = card.select_one("time")

                text  = text_el.get_text(strip=True)  if text_el  else ""
                title = title_el.get_text(strip=True) if title_el else ""
                date  = date_el.get("datetime", "")   if date_el  else ""

                rating = None
                if rating_el:
                    img = rating_el.select_one("img[alt]")
                    if img:
                        try:
                            rating = int(img.get("alt", "").split()[0])
                        except (ValueError, IndexError):
                            pass

                if text:
                    reviews.append({
                        "source": "trustpilot",
                        "title":  title,
                        "text":   text,
                        "rating": rating,
                        "date":   date,
                        "url":    source_url,
                    })
            except Exception as e:
                logger.debug("Error parsing review card: %s", e)
        return reviews
