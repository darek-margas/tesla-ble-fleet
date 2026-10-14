"""Tesla BLE Fleet: one Home Assistant device per car across several ESP32s.

Each ESP32 runs esphome-tesla-ble-multi with its own key per car. This
integration groups their entities by car (Car ID) and presents each car once,
routing commands to the ESP32 that hears it best. See DESIGN.md.

Skeleton: sets up and unloads, no entities yet.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the fleet (nothing to do yet)."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the fleet."""
    return True
