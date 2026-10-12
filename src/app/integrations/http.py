"""A polite HTTP client for fetching government sources."""

import asyncio
import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

# Sent as-is. Canada.ca serves an identifying agent and rejects one posing as a browser.
USER_AGENT = "immicite-ingest/0.1 (+https://github.com/jhanvi0905/immicite)"
SECONDS_BETWEEN_REQUESTS = 1.0
ATTEMPTS = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchNotAllowed(Exception):
    """robots.txt disallows the URL."""


class PoliteClient:
    """Identifies itself, obeys robots.txt, spaces requests per host, and retries."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, url: str) -> bytes:
        if not (await self._robots_for(url)).can_fetch(USER_AGENT, url):
            raise FetchNotAllowed(url)
        return (await self._request(url)).content

    async def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        host = parts.netloc
        if host not in self._robots:
            robots = RobotFileParser()
            response = await self._request(f"{parts.scheme}://{host}/robots.txt", check=False)
            # No robots.txt means no restrictions.
            robots.parse(response.text.splitlines() if response.status_code == 200 else [])
            self._robots[host] = robots
        return self._robots[host]

    async def _request(self, url: str, *, check: bool = True) -> httpx.Response:
        host = urlsplit(url).netloc
        for attempt in range(1, ATTEMPTS + 1):
            wait = self._last_request.get(host, 0) + SECONDS_BETWEEN_REQUESTS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                response = await self._client.get(url)
            except httpx.TransportError:
                if attempt == ATTEMPTS:
                    raise
            else:
                if response.status_code not in RETRY_STATUSES or attempt == ATTEMPTS:
                    if check:
                        response.raise_for_status()
                    return response
            finally:
                self._last_request[host] = time.monotonic()
            logger.warning("retrying %s (attempt %d of %d)", url, attempt, ATTEMPTS)
            await asyncio.sleep(2**attempt)
        raise AssertionError("unreachable")
