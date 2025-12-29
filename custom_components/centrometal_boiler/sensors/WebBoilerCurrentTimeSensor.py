from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import UTC

from .WebBoilerGenericSensor import WebBoilerGenericSensor
from ..common import format_time


class WebBoilerCurrentTimeSensor(WebBoilerGenericSensor):
    """Sensor that exposes the boiler's internal clock as a readable time."""

    @property
    def native_value(self):
        """
        Return the formatted boiler time.

        B_Time can arrive as:
        - hex string (e.g. "6715F74C")
        - decimal string (e.g. "1730024286")
        - "None"/invalid

        We try hex, then decimal, then fall back to raw so the entity never crashes.
        """
        raw_val = self.parameter["value"]

        if raw_val is None or raw_val == "None":
            return raw_val

        timestamp_seconds = None

        # Try HEX -> int
        try:
            timestamp_seconds = int(raw_val, 16)
        except (ValueError, TypeError):
            timestamp_seconds = None

        # Try DECIMAL -> int
        if timestamp_seconds is None:
            try:
                timestamp_seconds = int(raw_val)
            except (ValueError, TypeError):
                timestamp_seconds = None

        if timestamp_seconds is None:
            # Can't parse? Just show raw.
            return raw_val

        # Format as human time in UTC for consistency
        return format_time(self.hass, timestamp_seconds, UTC)

    @staticmethod
    def create_entities(hass: HomeAssistant, device) -> list[SensorEntity]:
        """Factory for the Clock entity (B_Time)."""
        entities: list[SensorEntity] = []
        if WebBoilerGenericSensor._device_has_parameter(device, "B_Time"):
            parameter = device.get_parameter("B_Time")
            if not parameter.get("used"):
                entities.append(
                    WebBoilerCurrentTimeSensor(
                        hass,
                        device,
                        [None, "mdi:clock-outline", None, "Clock"],
                        parameter,
                    )
                )
        return entities
