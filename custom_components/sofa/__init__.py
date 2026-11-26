"""Sofa: browse and play the German public-broadcaster media libraries via Sofa."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SofaClient, SofaError
from .const import CONF_URL, DOMAIN
from .tracker import ProgressTracker


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to Sofa and start reporting progress."""
    client = SofaClient(async_get_clientsession(hass), entry.data[CONF_URL])
    try:
        await client.health()
    except SofaError as err:
        raise ConfigEntryNotReady(f"Sofa nicht erreichbar: {err}") from err
    tracker = ProgressTracker(hass, client)
    tracker.start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"client": client, "tracker": tracker}
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop the tracker and forget the client."""
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data:
        data["tracker"].stop()
    return True
