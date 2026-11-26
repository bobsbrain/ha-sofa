"""Report watching progress of Sofa videos played through Home Assistant.

When Home Assistant plays a Sofa video on a TV, Sofa itself does not see it.
The tracker remembers which stream URL belongs to which Sofa entry and
watches media players: while one of them plays such a URL, the position is
sent back to Sofa, so "Weiterschauen" and recommendations stay right.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .api import SofaClient

REPORT_EVERY = 15  # seconds of playback between reports
KEEP = 50  # how many started videos to remember


class ProgressTracker:
    """Follow media players that play a Sofa stream."""

    def __init__(self, hass: HomeAssistant, client: SofaClient) -> None:
        self.hass = hass
        self.client = client
        self._known: dict[str, dict] = {}  # stream URL -> {id, duration, reported}
        self._unsubs: list = []

    def remember(self, url: str, item_id: str, duration: float, entity_id: str | None) -> None:
        self._known[url] = {"id": item_id, "duration": duration, "reported": -1.0, "entity": entity_id, "at": time.time()}
        if len(self._known) > KEEP:
            oldest = min(self._known, key=lambda u: self._known[u]["at"])
            self._known.pop(oldest, None)

    def start(self) -> None:
        self._unsubs.append(self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._on_state, event_filter=self._is_ours))
        # some players only update their state on play/pause/seek: poll as well
        self._unsubs.append(async_track_time_interval(self.hass, self._poll, timedelta(seconds=30)))

    def stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _is_ours(self, event_data) -> bool:
        if not event_data["entity_id"].startswith("media_player."):
            return False
        new = event_data.get("new_state")
        old = event_data.get("old_state")
        return any(s is not None and s.attributes.get("media_content_id") in self._known for s in (new, old))

    @callback
    def _on_state(self, event: Event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        url = (new and new.attributes.get("media_content_id")) or (old and old.attributes.get("media_content_id"))
        info = self._known.get(url)
        if not info:
            return
        # stopped or switched to something else: report the last known position
        if new is None or new.attributes.get("media_content_id") != url or new.state in ("idle", "off", "standby"):
            self._report(info, old, final=True)
            return
        self._report(info, new, final=new.state == "paused")

    @callback
    def _poll(self, _now: datetime) -> None:
        for state in self.hass.states.async_all("media_player"):
            info = self._known.get(state.attributes.get("media_content_id"))
            if info and state.state == "playing":
                self._report(info, state, final=False)

    @callback
    def _report(self, info: dict, state, final: bool) -> None:
        if state is None:
            return
        attrs = state.attributes
        pos = attrs.get("media_position")
        if pos is None:
            return
        updated = attrs.get("media_position_updated_at")
        if state.state == "playing" and isinstance(updated, datetime):
            pos += (datetime.now(timezone.utc) - updated).total_seconds()
        duration = attrs.get("media_duration") or info["duration"] or 0
        if duration:
            pos = min(pos, duration)
        if not final and abs(pos - info["reported"]) < REPORT_EVERY:
            return
        if pos < 5:
            return
        info["reported"] = pos
        self.hass.async_create_task(self.client.progress(info["id"], round(pos, 1), duration))
