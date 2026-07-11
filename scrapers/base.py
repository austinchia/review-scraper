import time
import logging
from curl_cffi import requests as cffi_requests
from config import PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS

logger = logging.getLogger(__name__)


class BaseScraper:
    def __init__(self, use_proxy: bool = True):
        self.session = cffi_requests.Session(impersonate="chrome120")
        self._setup_proxy(use_proxy)

    def _setup_proxy(self, use_proxy: bool):
        if not use_proxy or not all([PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS]):
            if use_proxy:
                logger.warning("Proxy credentials not set — running without proxy")
            return
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        self.session.proxies = {"http": proxy_url, "https": proxy_url}
        logger.info("Proxy configured: %s:%s", PROXY_HOST, PROXY_PORT)

    def get(self, url: str, retries: int = 4, **kwargs) -> cffi_requests.Response:
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
            except cffi_requests.RequestsError as e:
                logger.warning("Request failed (attempt %d/%d): %s", attempt + 1, retries, e)
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
        raise RuntimeError(f"All {retries} attempts failed for {url}")
