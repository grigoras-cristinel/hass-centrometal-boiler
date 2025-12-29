"""Expose 0/1-style boiler parameters as human-friendly 'On' / 'Off' sensors.

These are parameters that PelTec II Lambda reports as bit-like values:
- pumps
- heater element
- fan active
- command active
- DHW pump demand/state

We present them as "On" / "Off" instead of raw 0/1, and we also expose the
raw_value attribute so you can inspect if the boiler ever sends richer data.
"""

from typing import List

from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity

from .WebBoilerGenericSensor import WebBoilerGenericSensor


class WebBoilerBinaryOnOffSensor(WebBoilerGenericSensor):
    """Sensor that reports 'On' / 'Off' instead of raw 0/1, with debug."""

    @property
    def native_value(self):
        raw = self.parameter["value"]

        # Normalize obvious ON cases
        if raw in (1, "1", "ON", "On", "on", True, "TRUE", "True", "true"):
            return "ON"

        # Normalize obvious OFF cases
        if raw in (0, "0", "OFF", "Off", "off", False, "FALSE", "False", "false"):
            return "OFF"

        # Try integer cast fallback (covers "2", etc.)
        try:
            intval = int(str(raw))
            if intval == 1:
                return "ON"
            if intval == 0:
                return "OFF"
        except (ValueError, TypeError):
            pass

        # Fallback: expose whatever came from the boiler
        return str(raw)

    @property
    def extra_state_attributes(self):
        """
        Extend base attributes from WebBoilerGenericSensor with raw_value for debugging.
        """
        base = super().extra_state_attributes or {}
        base["raw_value"] = self.parameter.get("value")
        return base


def create_binary_state_entities(
    hass: HomeAssistant,
    device,
) -> List[SensorEntity]:
    """
    Create 'On'/'Off' sensors for specific boiler parameters.

    We:
    - claim these parameters (mark them 'used' so they won't spawn duplicates),
    - expose them via WebBoilerBinaryOnOffSensor,
    - don't change control semantics.
    """

    entities: List[SensorEntity] = []

    binary_map = {
        # Boiler run command / "command active"
        "B_CMD": [
            None,
            "mdi:state-machine",
            None,
            "Command Active",
        ],

        # PWM circulation pump
        "B_Ppwm": [
            None,
            "mdi:pump",
            None,
            "PWM Pump",
        ],

        # Main boiler / DHW circulation pump
        "B_P1": [
            None,
            "mdi:pump",
            None,
            "Hot Water Flow",
        ],

        # Electric backup heater
        "B_gri": [
            None,
            "mdi:meter-electric",
            None,
            "Electric Heater",
        ],

        # Fan activity flag from PelTec2 (web UI shows just running/not running)
        "B_fan01": [
            None,
            "mdi:fan",
            None,
            "Fan Active",
        ],

        # DHW / K1 circuit demand and pump state
        "K1B_onOff": [
            None,
            "mdi:pump",
            None,
            "DHW Pump Demand",
        ],
        "K1B_P": [
            None,
            "mdi:pump",
            None,
            "DHW Pump State",
        ],
    }

    params = device.get("parameters", {})

    for param_name, sensor_data in binary_map.items():
        if param_name not in params:
            continue

        parameter = device.get_parameter(param_name)

        # If this parameter is already claimed, skip it
        if parameter.get("used"):
            continue

        # Claim this parameter so other factories don't double-create it
        parameter["used"] = True

        entities.append(
            WebBoilerBinaryOnOffSensor(
                hass,
                device,
                sensor_data,
                parameter,
            )
        )

    return entities
