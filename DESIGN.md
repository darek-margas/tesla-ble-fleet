# Design

## Goal

Several ESP32s run [esphome-tesla-ble-multi](https://github.com/darek-margas/esphome-tesla-ble-multi), for example one in the garage and one by the street, each handling the cars near it with turn-taking. Home Assistant then sees each car once per ESP32 that knows it. Tesla BLE Fleet turns that into **one device per car**:
- commands go to the ESP32 that hears the car best right now;
- sensors come from whichever ESP32 read the car last;
- composite entities are built that ESPHome can't provide.

It is a pure Home Assistant integration: it uses the entities the ESPHome integration already creates, and talks to no car itself.

## Why not one ESP32, or Bluetooth proxies

- **One ESP32** covers one area. Cars parked elsewhere are out of range, or at −90 dBm.
- **Bluetooth proxies** (yoziru's ha-tesla-ble) scale coverage, but run the protocol in Home Assistant through general-purpose proxies:
  - there's no coordination between cars on one proxy (two Tesla links starve each other on a classic ESP32);
  - nothing runs while Home Assistant restarts.
- Here, each ESP32 stays a self-contained Tesla client with turn-taking. The fleet only adds the single view and the routing.

## Identity: the Car ID

- Each car must be recognisable across ESP32s without publishing its VIN. The component exposes a diagnostic text sensor **Car ID** per car: the `S<16 hex>C` advert name derived from the VIN.
- The car broadcasts that name over Bluetooth anyway, so it reveals nothing new.
- Cars that advertise the 2023+ `Tesla <last 6>` name still have the hash-based name computed from the VIN, so the Car ID is the same either way.
- **In the component** since commit a1e548a (multicar-v2): the diagnostic text sensor **Car ID** (`car_id`), published at boot with the discovery state.

## Picking the ESP32 for a car

From each ESP32's entities for that car:
1. **Connected now** (the car holds that ESP32's link): use that one.
2. Otherwise **Present**, the best **BLE Advert RSSI**, with a few dB of hysteresis so it doesn't flip between two similar ESP32s.
3. Otherwise the one that last had the car present.

Shown as a sensor on the fleet car: **Serving ESP32**.

## Entities

- **Mirrored:** every sensor, binary sensor and text sensor of the car, taken from the ESP32 with the freshest update.
- **Routed:** buttons, switches, numbers, selects, locks, covers, climate. A call goes to the serving ESP32's entity.
- **Composite** (ESPHome can't do these):
  - one **media player** per car with play/pause, volume, title, artist, source and next/previous;
  - climate including seat and steering heat levels, later.

## Presence and location

The same model as [Wi-Fi Association Presence](https://github.com/darek-margas/wifi-association-presence), with ESP32s instead of access points:
- **Device tracker per car:** *home* while any ESP32 reports the car **Present**, *not_home* when none does.
  - Each ESP32 already applies its own grace period (`presence_timeout`, 5 min by default), so turn-taking or a short gap causes no flapping. The fleet combines them; no second grace period by default.
- **Area sensor:** the Home Assistant area of the ESP32 device that serves the car (same choice as for commands). An ESP32 in area *Garage* puts a car heard best there in the garage. Unknown while away.
- **Arrived at / departed at** as tracker attributes: a visit continues across gaps shorter than the grace period, as in Wi-Fi Association Presence.
- Works with Home Assistant persons, zones and "arrived home" automations.
- **Limit:** Bluetooth range around each ESP32, not GPS. *Away* means out of range of all of them. Best with an ESP32 where the car actually parks.

## Keys (later, opt-in)

Key provisioning from Home Assistant, so ESP32s are replaceable:
- a build option in the component (off by default) exposes an API action **"set key for car"** (PEM + MAC), and requires API encryption;
- the fleet creates a key per car per ESP32, stores it in Home Assistant, and pushes it;
- the ESP32 pairs it (one key-card tap);
- a replacement ESP32 receives the same key and is paired at once.

Rule: **one active device per key**. Per-key counters would collide if two devices used one key at the same time.

## Order

1. ~~Component: `car_id` text sensor.~~ Done (esphome-tesla-ble-multi a1e548a).
2. Fleet: discover ESPHome devices with Car IDs, one fleet device per car, mirrored sensors and **Serving ESP32**.
3. Presence: device tracker, Area sensor, arrival and departure times.
4. Routed controls.
5. Composite media player.
6. Key provisioning (component + fleet).
