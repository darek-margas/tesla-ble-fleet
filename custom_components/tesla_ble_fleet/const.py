"""Constants for Tesla BLE Fleet."""

DOMAIN = "tesla_ble_fleet"

SUBENTRY_SPOT = "spot"

CONF_OCCUPIED = "occupied"
CONF_DISTANCE = "distance"
CONF_FLOOR_CM = "floor_cm"
CONF_MIN_HEIGHT_CM = "min_height_cm"
CONF_MAX_HEIGHT_CM = "max_height_cm"
CONF_RSSI_MIN = "rssi_min"
CONF_RSSI_MARGIN = "rssi_margin"
CONF_RSSI = "rssi"                    # {car_id: rssi entity at this spot}


def signal_update(entry_id: str) -> str:
    """Dispatcher signal sent after every recalculation."""
    return f"{DOMAIN}_{entry_id}_update"
