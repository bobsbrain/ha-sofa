"""Sofa as a media source: browse rows, genres and series, play on any player."""

from __future__ import annotations

from urllib.parse import quote, unquote

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .api import SofaClient, SofaError
from .const import DOMAIN


async def async_get_media_source(hass: HomeAssistant) -> SofaMediaSource:
    """Set up the Sofa media source."""
    return SofaMediaSource(hass)


def _entry_data(hass: HomeAssistant) -> dict:
    entries = hass.data.get(DOMAIN) or {}
    if not entries:
        raise BrowseError("Sofa ist nicht eingerichtet")
    return next(iter(entries.values()))


def _episode_label(ep: dict | None) -> str:
    if not ep:
        return ""
    if ep.get("season") and ep.get("episode"):
        return f"S{ep['season']} F{ep['episode']}"
    if ep.get("of"):
        return f"Teil {ep['episode']}/{ep['of']}"
    if ep.get("episode"):
        return f"Folge {ep['episode']}"
    return ""


def _folder(identifier: str, title: str, children_class: str = MediaClass.VIDEO) -> BrowseMediaSource:
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier,
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.VIDEO,
        title=title,
        can_play=False,
        can_expand=True,
        children_media_class=children_class,
    )


class SofaMediaSource(MediaSource):
    """Browse Sofa and hand out playable stream URLs."""

    name = "Sofa"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    # ---- playing -------------------------------------------------------------

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        kind, _, arg = (item.identifier or "").partition("/")
        if kind != "item" or not arg:
            raise Unresolvable(f"Nicht abspielbar: {item.identifier}")
        data = _entry_data(self.hass)
        client: SofaClient = data["client"]
        try:
            details = await client.item(arg)
        except SofaError as err:
            raise Unresolvable(str(err)) from err
        it = details["item"]
        if it.get("geo"):
            raise Unresolvable("Diese Sendung ist nur im Heimatland des Senders abrufbar")
        video = it.get("video") or {}
        url = video.get("master") or video.get("hd") or video.get("sd") or video.get("low")
        if not url:
            raise Unresolvable("Kein Video vorhanden")
        mime = "application/x-mpegurl" if ".m3u8" in url.lower() else "video/mp4"
        # remember it, so the progress tracker can report back to Sofa
        data["tracker"].remember(url, it["id"], it.get("duration") or 0, item.target_media_player)
        return PlayMedia(url, mime)

    # ---- browsing ------------------------------------------------------------

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        client: SofaClient = _entry_data(self.hass)["client"]
        ident = item.identifier or ""
        kind, _, arg = ident.partition("/")
        try:
            if not ident:
                return await self._root(client)
            if kind == "row":
                return await self._row(client, arg)
            if kind == "genres":
                return await self._genres(client)
            if kind == "genre":
                return await self._genre(client, arg)
            if kind == "followed":
                return await self._followed(client)
            if kind == "show":
                channel, _, topic = arg.partition("/")
                return await self._show(client, unquote(channel), unquote(topic))
            if kind == "item":
                details = await client.item(arg)
                return self._item(client, details["item"])
        except SofaError as err:
            raise BrowseError(f"Sofa nicht erreichbar: {err}") from err
        raise BrowseError(f"Unbekannter Eintrag: {ident}")

    def _item(self, client: SofaClient, it: dict, with_show: bool = True) -> BrowseMediaSource:
        show = it.get("show") or it.get("topic") or ""
        title = it.get("title") or ""
        label = _episode_label(it.get("episode"))
        parts = []
        if with_show and show and show != title:
            parts.append(show)
        if label and label not in title:
            parts.append(label)
        parts.append(title)
        progress = it.get("progress") or {}
        if progress.get("finished"):
            parts.append("✓")
        if it.get("episode"):
            media_class = MediaClass.EPISODE
        elif it.get("genre") == "film":
            media_class = MediaClass.MOVIE
        else:
            media_class = MediaClass.VIDEO
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"item/{it['id']}",
            media_class=media_class,
            media_content_type=MediaType.VIDEO,
            title=" · ".join(parts),
            can_play=not it.get("geo"),
            can_expand=False,
            thumbnail=client.thumb_url(it["id"]),
        )

    async def _root(self, client: SofaClient) -> BrowseMediaSource:
        home = await client.home()
        root = _folder("", "Sofa", MediaClass.DIRECTORY)
        root.children = [_folder(f"row/{row['id']}", row["title"]) for row in home["rows"] if row["items"]]
        root.children.append(_folder("genres", "Alle Genres", MediaClass.DIRECTORY))
        shows = await client.shows()
        if shows.get("follow"):
            root.children.append(_folder("followed", "Gefolgte Sendungen", MediaClass.TV_SHOW))
        return root

    async def _row(self, client: SofaClient, row_id: str) -> BrowseMediaSource:
        home = await client.home()
        row = next((r for r in home["rows"] if r["id"] == row_id), None)
        if row is None:
            raise BrowseError("Diese Reihe gibt es gerade nicht mehr")
        node = _folder(f"row/{row_id}", row["title"])
        node.children = [self._item(client, it) for it in row["items"]]
        return node

    async def _genres(self, client: SofaClient) -> BrowseMediaSource:
        node = _folder("genres", "Alle Genres", MediaClass.DIRECTORY)
        node.children = [_folder(f"genre/{g['id']}", g["label"]) for g in await client.genres()]
        return node

    async def _genre(self, client: SofaClient, genre_id: str) -> BrowseMediaSource:
        data = await client.genre(genre_id)
        node = _folder(f"genre/{genre_id}", (data.get("genre") or {}).get("label") or genre_id)
        node.children = [self._item(client, it) for it in data["items"]]
        return node

    async def _followed(self, client: SofaClient) -> BrowseMediaSource:
        shows = await client.shows()
        node = _folder("followed", "Gefolgte Sendungen", MediaClass.TV_SHOW)
        node.children = [
            _folder(f"show/{quote(s['channel'], safe='')}/{quote(s['topic'], safe='')}", s["topic"], MediaClass.EPISODE)
            for s in shows.get("follow", [])
        ]
        return node

    async def _show(self, client: SofaClient, channel: str, topic: str) -> BrowseMediaSource:
        data = await client.show(channel, topic)
        items = data["items"]
        numbered = sum(1 for i in items if (i.get("episode") or {}).get("episode")) >= max(2, len(items) / 2)
        if numbered:  # series: in watching order
            items = sorted(items, key=lambda i: ((i.get("episode") or {}).get("season") or 0, (i.get("episode") or {}).get("episode") or 0, i["timestamp"]))
        node = _folder(f"show/{quote(channel, safe='')}/{quote(topic, safe='')}", data.get("topic") or topic, MediaClass.EPISODE)
        node.children = [self._item(client, it, with_show=False) for it in items[:300]]
        return node
