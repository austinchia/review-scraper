import time
import random
import logging
import requests
from fake_useragent import UserAgent
from config import PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BaseScraper:
    def __init__(self, use_proxy: bool = True):
        self.session = requests.Session()
        self._setup_proxy(use_proxy)
        self._rotate_user_agent()

    def _setup_proxy(self, use_proxy: bool):
        if not use_proxy or not all([PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS]):
            if use_proxy:
                logger.warning("Proxy credentials not set — running without proxy")
            return
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        self.session.proxies = {"http": proxy_url, "https": proxy_url}
        logger.info("Proxy configured: %s:%s", PROXY_HOST, PROXY_PORT)

    def _rotate_user_agent(self):
        try:
            ua = UserAgent()
            agent = ua.random
        except Exception:
            agent = random.choice(USER_AGENTS)
        self.session.headers.update({"User-Agent": agent})

    def get(self, url: str, retries: int = 4, **kwargs) -> requests.Response:
        delay = 2
        for attempt in range(retries):
            try:
                self._rotate_user_agent()
                resp = self.session.get(url, timeout=15, **kwargs)
                if resp.status_code in (429, 503):
                    logger.warning("Rate limited (%s) on %s — retrying in %ds", resp.status_code, url, delay)
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
