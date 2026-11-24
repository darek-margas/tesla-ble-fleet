# Tesla BLE Fleet

**Status: 0.1.0, parking only.** Finds the cars and tells, per car, whether it's in a garage spot, outside or away. The rest below is still design.

A Home Assistant integration that shows **each Tesla once**, however many ESP32s running [esphome-tesla-ble-multi](https://github.com/darek-margas/esphome-tesla-ble-multi) can reach it:

- **one device per car**, matched by its Car ID (derived from the VIN; nothing new is published);
- **commands go to the ESP32 that hears the car best**, so a car parked in the garage and later on the street keeps working from the nearest ESP32;
- **sensors from whichever ESP32 read the car last**;
- **presence and location** come from [Wi-Fi Association Presence](https://github.com/darek-margas/wifi-association-presence), which will read the same ESP32s as Bluetooth "access points": home / away, and the car's area (Garage, Driveway…) even in a home with a single access point;
- **combined entities** ESPHome can't make, such as one media player with titles and track skipping.

Each ESP32 stays a complete, independent Tesla client: its own key per car, turn-taking between cars, and it keeps running while Home Assistant restarts. This integration only adds the single view on top.

See [DESIGN.md](DESIGN.md) for how it will work and in which order it's built.

## Parking (0.1.0)

What it needs:
- the cars' **Car ID** and **Present** entities from esphome-tesla-ble-multi (found automatically);
- per parking spot, an **occupancy** sensor over the space, ideally its **distance** sensor, and each car's **advert RSSI** at the spot. An ESP32 with an ultrasonic sensor in the ceiling and `ble_rssi` for each car's BLE MAC does all three. The RSSI sensors may be disabled by default in ESPHome; enable them.

Add the integration, then **Add parking spot** on it. The form asks for the floor distance (what the sensor reads with the spot empty), the car height band, and one RSSI field per car, named after the car.

What you get:
- per car, **Location**: `in_spot` (attribute `spot`), `outside`, `away`, or `home` when it's home but the spot can't tell (sensor unavailable, or two cars too close in RSSI);
- per spot, **Occupant**: the car's name, Empty, Not a Tesla (wrong height, or no car heard near it), or Tesla, not sure which;
- **Parking**: `2 in`, `1 in, 1 out`, `2 out`, `1 out, 1 away`… with the car names per state as attributes;
- **Tesla outside**: on while any car is home but in no spot, with the cars in `cars`.

A ladder in the empty spot with one car at home reads Not a Tesla, so that car is Outside.

[Wi-Fi Association Presence](https://github.com/darek-margas/wifi-association-presence) 0.13.0 has the same parking logic (`parking.py` is one file shared by both). There a car in its spot is also home, in the spot's area, while it sleeps off the Wi-Fi. Set up each spot in one of the two, not both: the two Location sensors would disagree for a few minutes after a car leaves. Which car to honk stays here.

Honk the car on the driveway when Frigate sees it blocked:

```yaml
actions:
  - condition: state
    entity_id: binary_sensor.tesla_ble_fleet_tesla_outside
    state: "on"
  - action: button.press
    target:
      entity_id: >-
        button.{{ state_attr('binary_sensor.tesla_ble_fleet_tesla_outside', 'cars')[0] | lower }}_sound_horn
```

`Sound Horn` is the esphome-tesla-ble-multi button; check your entity ids.

## Related

- [esphome-tesla-ble-multi](https://github.com/darek-margas/esphome-tesla-ble-multi): the ESP32 firmware component.
- [tesla-ble](https://github.com/darek-margas/tesla-ble): the protocol library it uses.

## License

AGPL-3.0, as esphome-tesla-ble-multi.
