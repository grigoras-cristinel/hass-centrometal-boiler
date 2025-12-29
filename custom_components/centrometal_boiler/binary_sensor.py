"""Support for Centrometal Boiler System websocket connection status."""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_EMAIL

from .common import format_name
from .const import DOMAIN, WEB_BOILER_CLIENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Centrometal connection status binary_sensor entities."""
    entities = []

    unique_id = config_entry.data[CONF_EMAIL]
    web_boiler_client = hass.data[DOMAIN][unique_id][WEB_BOILER_CLIENT]

    for device in web_boiler_client.data.values():
        entities.append(WebBoilerWebsocketStatus(hass, web_boiler_client, device))

    async_add_entities(entities, True)


class WebBoilerWebsocketStatus(BinarySensorEntity):
    """Binary sensor that reports if the websocket to Centrometal is connected."""

    def __init__(self, hass: HomeAssistant, web_boiler_client, device) -> None:
        """Initialize the connectivity sensor."""
        super().__init__()
        self.hass = hass
        self.web_boiler_client = web_boiler_client
        self.device = device

        self._serial = device["serial"]
        self._unique_id = f"{self._serial}_websocket_status"
        self._name = format_name(
            hass,
            device,
            "Centrometal Boiler System connection",
        )

    async def async_added_to_hass(self):
        """Subscribe to connectivity events from the client."""
        self.web_boiler_client.set_connectivity_callback(self.update_callback)

    @property
    def name(self) -> str:
        """Return entity name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this connection sensor."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return True if the websocket is currently connected."""
        return self.web_boiler_client.is_websocket_connected()

    @property
    def should_poll(self) -> bool:
        """No polling; updates are pushed."""
        return False

    async def update_callback(self, status):
        """Called by the client on connectivity changes."""
        # We just write our new state immediately.
        self.async_write_ha_state()

    @property
    def device_class(self):
        """Expose this entity as a 'connectivity' binary sensor."""
        return BinarySensorDeviceClass.CONNECTIVITY
