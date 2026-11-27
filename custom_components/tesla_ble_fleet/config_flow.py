"""Config flow for Tesla BLE Fleet: one entry; parking spots are subentries."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .cars import discover_cars
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
)
from .parking import SpotConfig


class TeslaBleFleetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add the fleet once; cars are found from the ESPHome devices."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm adding the fleet."""
        if user_input is not None:
            return self.async_create_entry(title="Tesla BLE Fleet", data={})
        return self.async_show_form(step_id="user")

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_SPOT: SpotSubentryFlow}


def _cm(minimum: float, maximum: float) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(
        min=minimum, max=maximum, step=1, unit_of_measurement="cm", mode=NumberSelectorMode.BOX))


def _db(minimum: float, maximum: float) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(
        min=minimum, max=maximum, step=1, unit_of_measurement="dB", mode=NumberSelectorMode.BOX))


class SpotSubentryFlow(ConfigSubentryFlow):
    """A parking spot: occupancy, distance, and each car's RSSI at the spot."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        current: dict[str, Any] = {}
        if user_input is not None:
            current = self._data(user_input, {})
            if not (errors := _errors(current)):
                return self.async_create_entry(title=current[CONF_NAME], data=current)
        return self.async_show_form(
            step_id="user", data_schema=self._schema(current), errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        current = dict(subentry.data)
        if user_input is not None:
            current = self._data(user_input, subentry.data.get(CONF_RSSI, {}))
            if not (errors := _errors(current)):
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=current[CONF_NAME], data=current)
        return self.async_show_form(
            step_id="reconfigure", data_schema=self._schema(current), errors=errors)

    def _rssi_fields(self) -> dict[str, str]:
        """Form field per car ('Bluey RSSI') -> Car ID."""
        cars, _ = discover_cars(self.hass)
        return {f"{car.name} RSSI": car.car_id for car in cars.values()}

    def _schema(self, current: dict[str, Any]) -> vol.Schema:
        d = SpotConfig()
        rssi = current.get(CONF_RSSI, {})

        def opt(key: str, value: Any) -> vol.Optional:
            return vol.Optional(key, description={"suggested_value": value})

        fields: dict[Any, Any] = {
            vol.Required(CONF_NAME, default=current.get(CONF_NAME, "Garage")): TextSelector(),
            vol.Required(CONF_OCCUPIED, description={"suggested_value": current.get(CONF_OCCUPIED)}):
                EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
            opt(CONF_DISTANCE, current.get(CONF_DISTANCE)):
                EntitySelector(EntitySelectorConfig(domain="sensor", device_class="distance")),
            vol.Required(CONF_FLOOR_CM, default=current.get(CONF_FLOOR_CM, d.floor_cm)): _cm(50, 600),
            vol.Required(CONF_MIN_HEIGHT_CM, default=current.get(CONF_MIN_HEIGHT_CM, d.min_height_cm)): _cm(0, 300),
            vol.Required(CONF_MAX_HEIGHT_CM, default=current.get(CONF_MAX_HEIGHT_CM, d.max_height_cm)): _cm(0, 300),
            vol.Required(CONF_RSSI_MIN, default=current.get(CONF_RSSI_MIN, d.rssi_min)): _db(-127, 0),
            vol.Required(CONF_RSSI_MARGIN, default=current.get(CONF_RSSI_MARGIN, d.rssi_margin)): _db(0, 40),
        }
        for label, car_id in self._rssi_fields().items():
            fields[opt(label, rssi.get(car_id))] = EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="signal_strength"))
        return vol.Schema(fields)

    def _data(self, user_input: dict[str, Any], saved_rssi: dict[str, str]) -> dict[str, Any]:
        labels = self._rssi_fields()
        data = {k: v for k, v in user_input.items() if k not in labels}
        # A car that isn't found right now (its ESP32 is offline) has no field in
        # the form: keep the sensor it had.
        shown = set(labels.values())
        rssi = {car_id: ent for car_id, ent in saved_rssi.items() if car_id not in shown}
        rssi.update({car_id: user_input[label] for label, car_id in labels.items()
                     if user_input.get(label)})
        data[CONF_RSSI] = rssi
        return data


def _errors(data: dict[str, Any]) -> dict[str, str]:
    if data[CONF_MIN_HEIGHT_CM] >= data[CONF_MAX_HEIGHT_CM]:
        return {"base": "height_band"}
    return {}
