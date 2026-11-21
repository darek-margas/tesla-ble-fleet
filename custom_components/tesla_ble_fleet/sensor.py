"""Parking sensors: Location per car, Occupant per spot, Parking summary."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FleetConfigEntry
from .entity import FleetEntity, car_device, hub_device, spot_device
from .parking import Location, SpotKind, summary


async def async_setup_entry(
    hass: HomeAssistant, entry: FleetConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    fleet = entry.runtime_data
    async_add_entities([CarLocation(fleet, car) for car in fleet.cars.values()])
    async_add_entities([ParkingSummary(fleet)])
    for sid in fleet.spots:
        async_add_entities([SpotOccupant(fleet, sid)], config_subentry_id=sid)


class CarLocation(FleetEntity, SensorEntity):
    """Away / In spot / Outside / Home (place unclear)."""

    _attr_translation_key = "location"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [loc.value for loc in Location]

    def __init__(self, fleet, car) -> None:
        super().__init__(fleet)
        self.car = car
        self._attr_unique_id = f"{car.car_id}_location"
        self._attr_device_info = car_device(car)

    def _update(self) -> None:
        place = self.fleet.places.get(self.car.car_id)
        self._attr_native_value = place.location.value if place and place.location else None
        spot = self.fleet.spots.get(place.spot) if place and place.spot else None
        self._attr_extra_state_attributes = {"spot": spot.name if spot else None}


class ParkingSummary(FleetEntity, SensorEntity):
    """'2 in', '1 in, 1 out', '2 out', '1 out, 1 away'..."""

    _attr_translation_key = "parking"

    def __init__(self, fleet) -> None:
        super().__init__(fleet)
        self._attr_unique_id = f"{fleet.entry.entry_id}_parking"
        self._attr_device_info = hub_device(fleet)

    def _update(self) -> None:
        places = self.fleet.places
        self._attr_native_value = summary(places)
        names = {cid: car.name for cid, car in self.fleet.cars.items()}
        self._attr_extra_state_attributes = {
            loc.value: sorted(names[cid] for cid, p in places.items() if p.location is loc)
            for loc in Location
        }


class SpotOccupant(FleetEntity, SensorEntity):
    """What is in the spot: Empty, a car's name, Not a Tesla, or unsure which."""

    _attr_translation_key = "occupant"

    def __init__(self, fleet, subentry_id: str) -> None:
        super().__init__(fleet)
        self.spot = fleet.spots[subentry_id]
        self._attr_unique_id = f"{subentry_id}_occupant"
        self._attr_device_info = spot_device(self.spot)

    def _update(self) -> None:
        state = self.fleet.spot_states.get(self.spot.subentry_id)
        if state is None or state.kind is SpotKind.UNKNOWN:
            value = None
        elif state.kind is SpotKind.CAR:
            car = self.fleet.cars.get(state.car_id)
            value = car.name if car else state.car_id
        else:
            value = {
                SpotKind.EMPTY: "Empty",
                SpotKind.OTHER: "Not a Tesla",
                SpotKind.UNSURE: "Tesla, not sure which",
            }[state.kind]
        self._attr_native_value = value
        self._attr_extra_state_attributes = {
            "kind": state.kind.value if state else None,
            "car_id": state.car_id if state else None,
            "height_cm": round(state.height_cm) if state and state.height_cm is not None else None,
        }
