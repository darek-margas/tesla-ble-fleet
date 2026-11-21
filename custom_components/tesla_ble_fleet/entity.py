"""Shared entity base: refresh on every fleet recalculation."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, signal_update


class FleetEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, fleet) -> None:
        self.fleet = fleet

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self.fleet.entry.entry_id), self._refresh
            )
        )
        self._refresh()

    @callback
    def _refresh(self) -> None:
        self._update()
        self.async_write_ha_state()

    def _update(self) -> None:
        raise NotImplementedError


def hub_device(fleet) -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, fleet.entry.entry_id)}, name="Tesla BLE Fleet")


def spot_device(spot) -> DeviceInfo:
    """Own device per spot: a device belongs to one config subentry."""
    return DeviceInfo(identifiers={(DOMAIN, spot.subentry_id)}, name=spot.name,
                      model="Parking spot")


def car_device(car) -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, car.car_id)}, name=car.name, manufacturer="Tesla")
