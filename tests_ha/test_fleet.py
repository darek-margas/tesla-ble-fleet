"""Home Assistant tests: discovery, the parking spot subentry flow, entities.

Needs pytest-homeassistant-custom-component; run from the repo root:
  pytest tests_ha
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tesla_ble_fleet.const import DOMAIN

BLUEY, SZARIK = "S8389a4cc897fdc45C", "Sf7915e6da7f90655C"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _esphome_car(hass, esp_entry, name, car_id):
    dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=esp_entry.entry_id, identifiers={("esphome", name)}, name=name)
    ent = er.async_get(hass)
    cid = ent.async_get_or_create(
        "sensor", "esphome", f"{name}-car_id", device_id=dev.id, original_name="Car ID",
        config_entry=esp_entry, suggested_object_id=f"{name.lower()}_car_id")
    pres = ent.async_get_or_create(
        "binary_sensor", "esphome", f"{name}-present", device_id=dev.id, original_name="Present",
        config_entry=esp_entry, suggested_object_id=f"{name.lower()}_present")
    hass.states.async_set(cid.entity_id, car_id)
    return pres.entity_id


SPOT = {
    "name": "Garage",
    "occupied": "binary_sensor.spot_car_present",
    "distance": "sensor.spot_distance",
    "floor_cm": 280, "min_height_cm": 135, "max_height_cm": 195,
    "rssi_min": -85, "rssi_margin": 6,
    "rssi": {BLUEY: "sensor.spot_bluey_rssi", SZARIK: "sensor.spot_szarik_rssi"},
}


@pytest.fixture
async def setup(hass: HomeAssistant):
    esp = MockConfigEntry(domain="esphome")
    esp.add_to_hass(hass)
    bluey = _esphome_car(hass, esp, "Bluey", BLUEY)
    szarik = _esphome_car(hass, esp, "Szarik", SZARIK)
    hass.states.async_set(bluey, "on")
    hass.states.async_set(szarik, "on")
    hass.states.async_set("binary_sensor.spot_car_present", "on")
    hass.states.async_set("sensor.spot_distance", "113")
    hass.states.async_set("sensor.spot_bluey_rssi", "-60")
    hass.states.async_set("sensor.spot_szarik_rssi", "-90")
    entry = MockConfigEntry(domain=DOMAIN, title="Tesla BLE Fleet", data={}, subentries_data=[
        ConfigSubentryData(data=SPOT, subentry_type="spot", title="Garage", unique_id=None)])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, bluey, szarik


def _state(hass, unique_id, domain="sensor"):
    eid = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert eid, unique_id
    return hass.states.get(eid)


async def test_one_in_one_out(hass, setup):
    entry, _, _ = setup
    assert _state(hass, f"{BLUEY}_location").state == "in_spot"
    assert _state(hass, f"{BLUEY}_location").attributes["spot"] == "Garage"
    assert _state(hass, f"{SZARIK}_location").state == "outside"
    assert _state(hass, f"{entry.entry_id}_parking").state == "1 in, 1 out"
    out = _state(hass, f"{entry.entry_id}_tesla_outside", "binary_sensor")
    assert out.state == "on"
    assert out.attributes["cars"] == ["Szarik"]
    sid = next(iter(entry.subentries))
    occ = _state(hass, f"{sid}_occupant")
    assert occ.state == "Bluey"
    assert occ.attributes["height_cm"] == 167


async def test_ladder_with_one_car_home(hass, setup):
    entry, bluey, _ = setup
    hass.states.async_set("binary_sensor.spot_car_present", "off")       # Bluey leaves
    await hass.async_block_till_done()
    hass.states.async_set(bluey, "off")
    hass.states.async_set("sensor.spot_distance", "210")                 # ladder: 70 cm
    hass.states.async_set("sensor.spot_szarik_rssi", "-62")
    hass.states.async_set("binary_sensor.spot_car_present", "on")
    await hass.async_block_till_done()
    sid = next(iter(entry.subentries))
    assert _state(hass, f"{sid}_occupant").state == "Not a Tesla"
    assert _state(hass, f"{SZARIK}_location").state == "outside"
    assert _state(hass, f"{BLUEY}_location").state == "away"
    assert _state(hass, f"{entry.entry_id}_parking").state == "1 out, 1 away"


async def test_both_out(hass, setup):
    entry, _, _ = setup
    hass.states.async_set("binary_sensor.spot_car_present", "off")
    await hass.async_block_till_done()
    assert _state(hass, f"{entry.entry_id}_parking").state == "2 out"
    out = _state(hass, f"{entry.entry_id}_tesla_outside", "binary_sensor")
    assert sorted(out.attributes["cars"]) == ["Bluey", "Szarik"]


async def test_spot_subentry_flow(hass, setup):
    entry, _, _ = setup
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "spot"), context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    keys = {str(k) for k in result["data_schema"].schema}
    assert {"Bluey RSSI", "Szarik RSSI"} <= keys
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {
        "name": "Driveway spot", "occupied": "binary_sensor.spot_car_present",
        "floor_cm": 300, "min_height_cm": 135, "max_height_cm": 195,
        "rssi_min": -85, "rssi_margin": 6, "Bluey RSSI": "sensor.spot_bluey_rssi"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    sub = next(s for s in entry.subentries.values() if s.title == "Driveway spot")
    assert sub.data["rssi"] == {BLUEY: "sensor.spot_bluey_rssi"}
    assert "Bluey RSSI" not in sub.data


async def test_latch_survives_reload_without_adverts(hass, setup):
    """After a reload the parked car is still in the spot, though no advert is heard yet."""
    entry, _, _ = setup
    await hass.async_block_till_done()
    hass.states.async_set("sensor.spot_bluey_rssi", "unknown")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, f"{BLUEY}_location").state == "in_spot"
    out = _state(hass, f"{entry.entry_id}_tesla_outside", "binary_sensor")
    assert out.attributes["cars"] == ["Szarik"]


async def test_quick_swap(hass, setup):
    """Bluey leaves and Szarik takes the spot before the occupancy sensor turns off."""
    entry, bluey, _ = setup
    hass.states.async_set("sensor.spot_bluey_rssi", "unknown")
    hass.states.async_set(bluey, "off")
    await hass.async_block_till_done()
    assert _state(hass, f"{BLUEY}_location").state == "in_spot"      # last reading still held
    later = time.monotonic() + 60
    with patch("custom_components.tesla_ble_fleet.time.monotonic", return_value=later):
        hass.states.async_set("sensor.spot_szarik_rssi", "-58")
        await hass.async_block_till_done()
    assert _state(hass, f"{SZARIK}_location").state == "in_spot"
    assert _state(hass, f"{BLUEY}_location").state == "away"


async def test_reconfigure_keeps_rssi_of_a_car_that_is_offline(hass, setup):
    entry, _, _ = setup
    sid = next(iter(entry.subentries))
    szarik_id = er.async_get(hass).async_get_entity_id("sensor", "esphome", "Szarik-car_id")
    hass.states.async_set(szarik_id, "unavailable")
    result = await entry.start_subentry_reconfigure_flow(hass, sid)
    assert result["type"] is FlowResultType.FORM
    keys = {str(k) for k in result["data_schema"].schema}
    assert "Bluey RSSI" in keys and "Szarik RSSI" not in keys
    user_input = {
        "name": "Garage", "occupied": "binary_sensor.spot_car_present",
        "floor_cm": 280, "min_height_cm": 195, "max_height_cm": 135,
        "rssi_min": -85, "rssi_margin": 6, "Bluey RSSI": "sensor.spot_bluey_rssi"}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    assert result["errors"] == {"base": "height_band"}
    user_input.update(min_height_cm=135, max_height_cm=195)
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[sid].data["rssi"] == SPOT["rssi"]
