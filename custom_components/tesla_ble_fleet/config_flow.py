"""Config flow for Tesla BLE Fleet: one entry, no settings yet."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class TeslaBleFleetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add the fleet once; cars are found from the ESPHome devices."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm adding the fleet."""
        if user_input is not None:
            return self.async_create_entry(title="Tesla BLE Fleet", data={})
        return self.async_show_form(step_id="user")
