from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .WebBoilerGenericSensor import WebBoilerGenericSensor
from centrometal_web_boiler.WebBoilerDeviceCollection import WebBoilerParameter


class WebBoilerDeviceTypeSensor(WebBoilerGenericSensor):
    """Expose boiler type (peltec2, cmpelet, biotec, biopl, etc.)."""

    @property
    def available(self):
        """Device type is static, not tied to websocket state."""
        return True

    @staticmethod
    def create_entities(hass: HomeAssistant, device) -> list[SensorEntity]:
        parameter = WebBoilerParameter()
        parameter["name"] = "Device_Type"
        parameter["value"] = device["type"]
        entities: list[SensorEntity] = [
            WebBoilerDeviceTypeSensor(
                hass,
                device,
                [None, "mdi:star-circle", None, "Device Type"],
                parameter,
            )
        ]
        return entities
