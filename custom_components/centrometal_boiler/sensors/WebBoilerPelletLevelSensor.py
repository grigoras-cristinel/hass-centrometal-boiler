from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .WebBoilerGenericSensor import WebBoilerGenericSensor


class WebBoilerPelletLevelSensor(WebBoilerGenericSensor):
    """
    LEGACY / DISABLED.

    This used to expose B_razina ("Tank Level") as a discrete sensor with states
    like Empty / Reserve / Full.

    We now prefer B_razP ("Pelet Level") which gives an actual percentage.
    So we intentionally DO NOT create this sensor anymore.
    """

    @property
    def native_value(self):
        """Never actually used now, but kept for safety."""
        configurations = ["Empty", "Reserve", "Full"]
        try:
            return configurations[int(self.parameter["value"])]
        except Exception:
            pass
        return self.parameter["value"]

    @staticmethod
    def create_entities(hass: HomeAssistant, device) -> list[SensorEntity]:
        """
        Old behavior:
            if device had B_razina, we created sensor.peltec_ii_lambda_tank_level.

        New behavior:
            return [] so that sensor never exists.
        """
        return []
