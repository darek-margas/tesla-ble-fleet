"""Tesla outside: on while any car is home but not in a spot (e.g. on the driveway)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FleetConfigEntry
from .entity import FleetEntity, hub_device
from .parking import Location


async def async_setup_entry(
    hass: HomeAssistant, entry: FleetConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([TeslaOutside(entry.runtime_data)])


class TeslaOutside(FleetEntity, BinarySensorEntity):
    """For automations such as honking a car on the driveway: which car is in `cars`."""

    _attr_translation_key = "tesla_outside"

    def __init__(self, fleet) -> None:
        super().__init__(fleet)
        self._attr_unique_id = f"{fleet.entry.entry_id}_tesla_outside"
        self._attr_device_info = hub_device(fleet)

    def _update(self) -> None:
        outside = [cid for cid, p in self.fleet.places.items() if p.location is Location.OUTSIDE]
        self._attr_is_on = bool(outside)
        self._attr_extra_state_attributes = {
            "cars": [self.fleet.cars[cid].name for cid in outside],
            "car_ids": outside,
        }
