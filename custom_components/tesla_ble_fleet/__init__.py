"""Tesla BLE Fleet: one Home Assistant device per car across several ESP32s.

Each ESP32 runs esphome-tesla-ble-multi with its own key per car. This
integration groups their entities by car (Car ID). See DESIGN.md.

Built so far: parking. Each parking spot (a config subentry) is an occupancy
sensor, optionally its distance, and each car's advert RSSI at that spot. From
those and the cars' Present state the fleet tells, per car, In spot / Outside /
Away, plus a summary and a "Tesla outside" sensor (see parking.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON, Platform
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .cars import CAR_ID_RE, Car, discover_cars
from .const import (
    CONF_DISTANCE,
    CONF_FLOOR_CM,
    CONF_MAX_HEIGHT_CM,
    CONF_MIN_HEIGHT_CM,
    CONF_OCCUPIED,
    CONF_RSSI,
    CONF_RSSI_MARGIN,
    CONF_RSSI_MIN,
    DOMAIN,
    SUBENTRY_SPOT,
    signal_update,
)
from .parking import CarPlace, SpotConfig, SpotState, SpotTracker, locate_cars

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type FleetConfigEntry = ConfigEntry[Fleet]


@dataclass
class Spot:
    subentry_id: str
    name: str
    occupied: str
    distance: str | None
    rssi: dict[str, str]                      # car_id -> entity_id
    tracker: SpotTracker


@dataclass
class Fleet:
    hass: HomeAssistant
    entry: ConfigEntry
    cars: dict[str, Car]
    pending_car_ids: list[str]
    spots: dict[str, Spot]
    store: Store[dict[str, str]]
    saved_latches: dict[str, str] = field(default_factory=dict)
    spot_states: dict[str, SpotState] = field(default_factory=dict)
    places: dict[str, CarPlace] = field(default_factory=dict)

    def watched_entities(self) -> set[str]:
        ids = {e for car in self.cars.values() for e in car.present_entities}
        for spot in self.spots.values():
            ids.add(spot.occupied)
            if spot.distance:
                ids.add(spot.distance)
            ids.update(spot.rssi.values())
        return ids

    @callback
    def recalculate(self) -> None:
        present = {
            car_id: _any_on(self.hass, car.present_entities) for car_id, car in self.cars.items()
        }
        now = time.monotonic()
        for sid, spot in self.spots.items():
            self.spot_states[sid] = spot.tracker.update(
                _bool(self.hass, spot.occupied),
                _float(self.hass, spot.distance),
                {car_id: _float(self.hass, ent) for car_id, ent in spot.rssi.items()},
                present,
                now,
            )
        latches = {
            sid: spot.tracker.latched for sid, spot in self.spots.items() if spot.tracker.latched
        }
        if latches != self.saved_latches:
            # Kept across restarts and reloads: until the adverts are heard again
            # a parked car would otherwise read as "Not a Tesla", and so outside.
            self.saved_latches = latches
            self.hass.async_create_task(self.store.async_save(latches))
        self.places = locate_cars(present, self.spot_states)      # CarPlace.spot = subentry id
        async_dispatcher_send(self.hass, signal_update(self.entry.entry_id))


def _bool(hass: HomeAssistant, entity_id: str | None) -> bool | None:
    state = hass.states.get(entity_id) if entity_id else None
    if state is None or state.state not in (STATE_ON, STATE_OFF):
        return None
    return state.state == STATE_ON


def _float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    state = hass.states.get(entity_id) if entity_id else None
    try:
        return float(state.state) if state is not None else None
    except ValueError:
        return None


def _any_on(hass: HomeAssistant, entity_ids: list[str]) -> bool | None:
    values = [_bool(hass, e) for e in entity_ids]
    if True in values:
        return True
    if False in values:
        return False
    return None


def _spots(entry: ConfigEntry) -> dict[str, Spot]:
    spots = {}
    for sid, sub in entry.subentries.items():
        if sub.subentry_type != SUBENTRY_SPOT:
            continue
        d = sub.data
        defaults = SpotConfig()
        config = SpotConfig(
            floor_cm=d.get(CONF_FLOOR_CM, defaults.floor_cm),
            min_height_cm=d.get(CONF_MIN_HEIGHT_CM, defaults.min_height_cm),
            max_height_cm=d.get(CONF_MAX_HEIGHT_CM, defaults.max_height_cm),
            rssi_min=d.get(CONF_RSSI_MIN, defaults.rssi_min),
            rssi_margin=d.get(CONF_RSSI_MARGIN, defaults.rssi_margin),
        )
        spots[sid] = Spot(
            sid, d.get(CONF_NAME, sub.title), d[CONF_OCCUPIED], d.get(CONF_DISTANCE),
            dict(d.get(CONF_RSSI, {})), SpotTracker(config),
        )
    return spots


async def async_setup_entry(hass: HomeAssistant, entry: FleetConfigEntry) -> bool:
    """Find the cars, set up the spots, follow their entities."""
    cars, pending = discover_cars(hass)
    store: Store[dict[str, str]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.latches")
    fleet = Fleet(hass, entry, cars, pending, _spots(entry), store)
    fleet.saved_latches = {
        sid: car_id for sid, car_id in (await store.async_load() or {}).items()
        if sid in fleet.spots
    }
    for sid, car_id in fleet.saved_latches.items():
        fleet.spots[sid].tracker.restore(car_id)
    entry.runtime_data = fleet

    @callback
    def _changed(event: Event[EventStateChangedData]) -> None:
        fleet.recalculate()

    # Listen before the first calculation, so no change falls in between.
    entry.async_on_unload(
        async_track_state_change_event(hass, sorted(fleet.watched_entities()), _changed)
    )
    fleet.recalculate()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if pending:
        # A Car ID without a value yet (its ESP32 isn't connected): reload once
        # it has one, so the car is added.
        @callback
        def _car_id_seen(event: Event[EventStateChangedData]) -> None:
            new = event.data["new_state"]
            if new is not None and CAR_ID_RE.match(new.state):
                hass.config_entries.async_schedule_reload(entry.entry_id)

        entry.async_on_unload(async_track_state_change_event(hass, pending, _car_id_seen))

    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """A spot was added or changed."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FleetConfigEntry) -> bool:
    """Unload the fleet."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the saved latches with the fleet."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.latches").async_remove()
