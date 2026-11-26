"""Config flow: ask for the address of the Sofa server."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SofaClient, SofaError
from .const import CONF_URL, DOMAIN


class SofaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Sofa."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if not url.startswith(("http://", "https://")):
                url = f"http://{url}"
            await self.async_set_unique_id(url.lower())
            self._abort_if_unique_id_configured()
            try:
                await SofaClient(async_get_clientsession(self.hass), url).health()
            except SofaError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Sofa", data={CONF_URL: url})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL): str}),
            errors=errors,
        )
