import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

from .WebBoilerGenericSensor import WebBoilerGenericSensor

_LOGGER = logging.getLogger(__name__)


class WebBoilerHeatingCircuitSensor:
    """
    Creates a bundle of sensors per heating circuit prefix (C1B, K1B, ...).
    Each circuit can have:
      - heating type
      - day/night mode
      - correction type
      - pump demand/state
      - flow / room temperatures
    """

    @staticmethod
    def create_heating_circuits_entities(
        hass: HomeAssistant, device
    ) -> list[SensorEntity]:
        """Scan for circuit prefixes and build sensor entities."""
        entities: list[SensorEntity] = []

        # Classic circuits C1B..C4B
        for i in range(1, 5):
            prefix = f"C{i}B"
            name = f"Circuit {i}"
            if WebBoilerHeatingCircuitSensor.device_has_prefix(device, prefix):
                entities.extend(
                    WebBoilerHeatingCircuitSensor.create_heating_circuit_entities(
                        hass, device, prefix, name
                    )
                )

        # 'K' circuits (e.g. K1B) used in PelTec II Lambda for DHW / mixers etc.
        for i in range(1, 5):
            prefix = f"K{i}B"
            name = f"Circuit {i}K"
            if WebBoilerHeatingCircuitSensor.device_has_prefix(device, prefix):
                entities.extend(
                    WebBoilerHeatingCircuitSensor.create_heating_circuit_entities(
                        hass, device, prefix, name
                    )
                )

        return entities

    @staticmethod
    def device_has_prefix(device, prefix):
        """Returns True if the boiler exposes any parameters starting with this prefix."""
        for param in device["parameters"].keys():
            if param.startswith(prefix):
                return True
        return False

    @staticmethod
    def create_heating_circuit_entities(
        hass: HomeAssistant, device, prefix, name
    ) -> list[SensorEntity]:
        """
        Create WebBoilerGenericSensor entities for a single heating circuit.
        We skip parameters that:
        - don't exist on this device,
        - or are already 'used' (claimed by BinaryOnOffSensor etc.)
        """
        entities: list[SensorEntity] = []

        items: dict[str, list] = {}
        items[prefix + "_CircType"] = [
            None,
            "mdi:view-list",
            None,
            name + " Heating Type",
        ]
        items[prefix + "_dayNight"] = [
            None,
            "mdi:view-list",
            None,
            name + " Day Night Mode",
        ]
        items[prefix + "_kor"] = [
            UnitOfTemperature.CELSIUS,
            "mdi:thermometer",
            SensorDeviceClass.TEMPERATURE,
            name + " Room Target Correction",
        ]
        items[prefix + "_korType"] = [
            None,
            "mdi:view-list",
            None,
            name + " Correction Type",
        ]
        items[prefix + "_onOff"] = [
            None,
            "mdi:pump",
            None,
            name + " Pump Demand",
        ]
        items[prefix + "_P"] = [
            None,
            "mdi:pump",
            None,
            name + " Pump",
        ]
        items[prefix + "_Tpol"] = [
            UnitOfTemperature.CELSIUS,
            "mdi:thermometer",
            SensorDeviceClass.TEMPERATURE,
            name + " Flow Target Temperature",
        ]
        items[prefix + "_Tpol1"] = [
            UnitOfTemperature.CELSIUS,
            "mdi:thermometer",
            SensorDeviceClass.TEMPERATURE,
            name + " Flow Measured Temperature",
        ]
        items[prefix + "_Tsob"] = [
            UnitOfTemperature.CELSIUS,
            "mdi:thermometer",
            SensorDeviceClass.TEMPERATURE,
            name + " Room Target Temperature",
        ]
        items[prefix + "_Tsob1"] = [
            UnitOfTemperature.CELSIUS,
            "mdi:thermometer",
            SensorDeviceClass.TEMPERATURE,
            name + " Room Measured Temperature",
        ]

        for param_id, sensor_data in items.items():
            if not WebBoilerGenericSensor._device_has_parameter(device, param_id):
                continue

            parameter = device.get_parameter(param_id)

            # If already claimed by a dedicated sensor (binary On/Off, etc.), skip.
            if parameter.get("used"):
                continue

            entities.append(
                WebBoilerGenericSensor(hass, device, sensor_data, parameter)
            )

        return entities
