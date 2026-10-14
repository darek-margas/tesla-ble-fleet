# Tesla BLE Fleet

**Status: design / skeleton.** Not usable yet.

A Home Assistant integration that shows **each Tesla once**, however many ESP32s running [esphome-tesla-ble-multi](https://github.com/darek-margas/esphome-tesla-ble-multi) can reach it:

- **one device per car**, matched by its Car ID (derived from the VIN; nothing new is published);
- **commands go to the ESP32 that hears the car best**, so a car parked in the garage and later on the street keeps working from the nearest ESP32;
- **sensors from whichever ESP32 read the car last**;
- **combined entities** ESPHome can't make, such as one media player with titles and track skipping.

Each ESP32 stays a complete, independent Tesla client: its own key per car, turn-taking between cars, and it keeps running while Home Assistant restarts. This integration only adds the single view on top.

See [DESIGN.md](DESIGN.md) for how it will work and in which order it's built.

## Related

- [esphome-tesla-ble-multi](https://github.com/darek-margas/esphome-tesla-ble-multi): the ESP32 firmware component.
- [tesla-ble](https://github.com/darek-margas/tesla-ble): the protocol library it uses.

## License

AGPL-3.0, as esphome-tesla-ble-multi.
