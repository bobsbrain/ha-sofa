"""Small async client for the Sofa server API."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import aiohttp


class SofaError(Exception):
    """Sofa could not be reached or answered with an error."""


class SofaClient:
    """Talks to a Sofa server (the discovery frontend for MediathekViewWeb)."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")

    async def _get(self, path: str, **params: Any) -> Any:
        try:
            async with self._session.get(
                f"{self.base_url}{path}",
                params={k: v for k, v in params.items() if v is not None},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status >= 400:
                    raise SofaError(f"{path}: HTTP {resp.status}")
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SofaError(f"{path}: {err}") from err

    async def health(self) -> dict:
        return await self._get("/api/health")

    async def home(self) -> dict:
        # same seed for five minutes, so random rows stay stable while browsing
        return await self._get("/api/home", seed=int(time.time() // 300))

    async def genres(self) -> list[dict]:
        return await self._get("/api/genres")

    async def genre(self, genre_id: str, limit: int = 100) -> dict:
        return await self._get(f"/api/genre/{quote(genre_id, safe='')}", limit=limit)

    async def show(self, channel: str, topic: str) -> dict:
        return await self._get("/api/show", channel=channel, topic=topic)

    async def shows(self) -> dict:
        return await self._get("/api/shows")

    async def item(self, item_id: str) -> dict:
        return await self._get(f"/api/item/{quote(item_id, safe='')}")

    async def progress(self, item_id: str, position: float, duration: float) -> None:
        try:
            async with self._session.post(
                f"{self.base_url}/api/progress",
                json={"id": item_id, "position": position, "duration": duration},
                timeout=aiohttp.ClientTimeout(total=10),
            ):
                pass
        except (aiohttp.ClientError, TimeoutError):
            pass  # best effort; the next update will try again

    def thumb_url(self, item_id: str) -> str:
        return f"{self.base_url}/api/thumb/{quote(item_id, safe='')}?w=card"
