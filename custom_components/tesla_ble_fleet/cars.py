"""Find the cars: every ESPHome "Car ID" text sensor, grouped by its value.

The component (esphome-tesla-ble-multi) publishes a Car ID per car, the
S<16 hex>C advert name derived from the VIN. The same car seen by two ESP32s
has the same Car ID, so it becomes one fleet car with two Present entities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

CAR_ID_RE = re.compile(r"^S[0-9a-f]{16}C$")


@dataclass
class Car:
    car_id: str
    name: str
    present_entities: list[str] = field(default_factory=list)


def discover_cars(hass: HomeAssistant) -> tuple[dict[str, Car], list[str]]:
    """Return the cars by Car ID, and Car ID entities that have no value yet."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    cars: dict[str, Car] = {}
    pending: list[str] = []
    for entry in ent_reg.entities.values():
        if (
            entry.platform != "esphome"
            or entry.domain != "sensor"
            or entry.original_name != "Car ID"
            or entry.disabled_by is not None
            or entry.device_id is None
        ):
            continue
        state = hass.states.get(entry.entity_id)
        if state is None or not CAR_ID_RE.match(state.state):
            pending.append(entry.entity_id)        # ESP32 not connected yet
            continue
        device = dev_reg.async_get(entry.device_id)
        name = (device.name_by_user or device.name) if device else state.state
        car = cars.setdefault(state.state, Car(state.state, name or state.state))
        car.present_entities += [
            e.entity_id
            for e in er.async_entries_for_device(ent_reg, entry.device_id)
            if e.domain == "binary_sensor" and e.original_name == "Present"
        ]
    return cars, pending
