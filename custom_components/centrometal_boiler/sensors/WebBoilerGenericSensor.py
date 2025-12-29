import logging
from typing import List, Dict, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from ..const import DOMAIN, WEB_BOILER_CLIENT, WEB_BOILER_SYSTEM
from ..common import format_name, format_time, create_device_info

from .generic_sensors_all import (
    GENERIC_SENSORS_COMMON,
    get_generic_temperature_settings_sensors,
)
from .generic_sensors_peltec import PELTEC_GENERIC_SENSORS

_LOGGER = logging.getLogger(__name__)


class WebBoilerGenericSensor(SensorEntity):
    """
    Generic Centrometal boiler sensor, backed by a single boiler parameter.

    - Subscribes to (and unsubscribes from) parameter websocket updates
    - Adds "Last updated" / "Original name" in attributes
    - Uses a unique callback id per entity so callbacks never stomp each other
    - Marks claimed parameters as 'used' so we don't create dup sensors
    """

    def __init__(self, hass: HomeAssistant, device, sensor_data, parameter) -> None:
        """
        sensor_data: [unit, icon, device_class, description, optional attributes_map]
        parameter:   boiler param object (value, timestamp, set_update_callback, ...)
        """
        self.hass = hass
        self.web_boiler_client = hass.data[DOMAIN][device.username][WEB_BOILER_CLIENT]
        self.web_boiler_system = hass.data[DOMAIN][device.username][WEB_BOILER_SYSTEM]

        self.device = device
        self.parameter = parameter

        self._unit = sensor_data[0]
        self._icon = sensor_data[1]
        self._device_class = sensor_data[2]
        self._description = sensor_data[3]
        self._attributes_map = sensor_data[4] if len(sensor_data) == 5 else {}

        self._serial = device["serial"]
        self._param_name = parameter["name"]
        self._product = device["product"]

        self._name = format_name(hass, device, f"{self._product} {self._description}")
        self._unique_id = f"{self._serial}-{self._param_name}"

        # Unique callback ID per entity so two entities pointing to the same
        # boiler parameter cannot stomp each other's callback. This fixed the
        # "B_STATE only updates on restart" freeze we saw originally.
        self._callback_id = f"{self._unique_id}-generic"

        self.added_to_hass = False

        # Mark this parameter (and any attribute parameters) as "used"
        # so we don't create multiple entities for the same physical value.
        self.parameter["used"] = True
        for attr_param_name in self._attributes_map:
            attr_param = self.device.get_parameter(attr_param_name)
            attr_param["used"] = True

    def __del__(self):
        # Clean up websocket callback on entity removal.
        if hasattr(self.parameter, "set_update_callback"):
            self.parameter.set_update_callback(None, self._callback_id)

    async def async_added_to_hass(self):
        """Subscribe to updates for this parameter."""
        self.added_to_hass = True
        self.async_schedule_update_ha_state(False)
        if hasattr(self.parameter, "set_update_callback"):
            self.parameter.set_update_callback(self.update_callback, self._callback_id)

    @property
    def should_poll(self) -> bool:
        return False

    async def update_callback(self, _param) -> None:
        """Called by boiler lib when this parameter changes."""
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def icon(self) -> str | None:
        return self._icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._unit

    @property
    def device_class(self) -> str | None:
        return self._device_class

    @property
    def native_value(self) -> Any:
        return self.parameter["value"]

    @property
    def available(self) -> bool:
        return self.web_boiler_client.is_websocket_connected()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Expose boiler timestamp + any linked attributes."""
        attrs: Dict[str, Any] = {}

        # Boiler-provided timestamp
        if "timestamp" in self.parameter:
            try:
                last_updated = format_time(self.hass, int(self.parameter["timestamp"]))
                attrs["Last updated"] = last_updated
            except Exception:
                pass

        # Original internal param name
        attrs["Original name"] = self.parameter["name"]

        # Attributes mapped in sensor_data[4]
        for key_param_name, nice_label in self._attributes_map.items():
            p = self.device.get_parameter(key_param_name)
            attrs[nice_label] = p["value"] or "None"

        return attrs

    @property
    def device_info(self):
        return create_device_info(self.device)

    #
    # ---- helpers used by other sensor classes ----
    #

    @staticmethod
    def _device_has_parameter(device, param_name: str) -> bool:
        """Return True if device has param_name at all."""
        params = device.get("parameters", {})
        return param_name in params

    #
    # ---- factories that build groups of entities ----
    #

    @staticmethod
    def create_common_entities(hass: HomeAssistant, device) -> List[SensorEntity]:
        """
        Create sensors for generic/identity params that are common.

        We SKIP any params that are handled as On/Off in WebBoilerBinaryOnOffSensor
        (like B_CMD) so we don't double-create and stomp callbacks.
        """
        skip_params = {
            "B_CMD",  # handled as "Command Active" On/Off
        }

        entities: List[SensorEntity] = []
        for param_id, sensor_data in GENERIC_SENSORS_COMMON.items():
            if param_id in skip_params:
                continue
            if not WebBoilerGenericSensor._device_has_parameter(device, param_id):
                continue
            parameter = device.get_parameter(param_id)
            if parameter.get("used"):
                continue
            entities.append(WebBoilerGenericSensor(hass, device, sensor_data, parameter))
        return entities

    @staticmethod
    def create_temperatures_entities(hass: HomeAssistant, device) -> List[SensorEntity]:
        """
        Create sensors for configurable temperature setpoints / limits (PVAL_xxx_0).
        """
        entities: List[SensorEntity] = []
        temp_sensors = get_generic_temperature_settings_sensors(device)
        for param_id, sensor_data in temp_sensors.items():
            if not WebBoilerGenericSensor._device_has_parameter(device, param_id):
                continue
            parameter = device.get_parameter(param_id)
            if parameter.get("used"):
                continue
            entities.append(WebBoilerGenericSensor(hass, device, sensor_data, parameter))
        return entities

    @staticmethod
    def create_conf_entities(hass: HomeAssistant, device) -> List[SensorEntity]:
        """
        Return configuration/status sensors based on boiler type.

        We are only interested in PelTec II Lambda ("peltec2"). All other boiler
        types are out of scope and will just produce no extra sensors.
        """
        entities: List[SensorEntity] = []

        if device["type"] == "peltec2":
            generic_map = PELTEC_GENERIC_SENSORS

            # We skip params that are either:
            # - handled by other dedicated sensor classes
            # - removed on purpose (clock, ping, legacy tank level)
            # - not meant to become standalone sensors
            skip_params = {
                # handled by binary on/off:
                "B_CMD",
                "K1B_onOff",
                "K1B_P",

                # handled by WebBoilerConfigurationSensor:
                "B_KONF",

                # handled by WebBoilerFireGridSensor:
                "B_resInd",
                "B_resDir",
                "B_resMax",

                # legacy / removed:
                "B_Time",
                "B_razina",
                "PING",
            }
        else:
            # non-peltec devices => no extras in our build
            generic_map = {}
            skip_params = set()

        for param_id, sensor_data in generic_map.items():
            if param_id in skip_params:
                continue
            if not WebBoilerGenericSensor._device_has_parameter(device, param_id):
                continue
            parameter = device.get_parameter(param_id)
            if parameter.get("used"):
                continue
            entities.append(WebBoilerGenericSensor(hass, device, sensor_data, parameter))

        return entities

    @staticmethod
    def create_unknown_entities(hass: HomeAssistant, device) -> List[SensorEntity]:
        """
        We do NOT create "Unknown ..." catch-all sensors anymore.
        Keep HA device list clean.
        """
        return []
