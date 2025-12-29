import asyncio
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
import homeassistant.util.dt as dt_util

# pylint: disable=relative-beyond-top-level
from ..const import DOMAIN, WEB_BOILER_CLIENT
from ..common import create_device_info, format_name


class WebBoilerCircuitSwitch(SwitchEntity):
    """Representation of an individual heating circuit on/off switch."""

    def __init__(self, hass: HomeAssistant, device, naslov, dbindex) -> None:
        """Initialize the circuit switch."""
        self.hass = hass
        self.web_boiler_client = hass.data[DOMAIN][device.username][WEB_BOILER_CLIENT]
        self._device = device
        self._product = device["product"]
        self._serial = device["serial"]

        # UI/HA identity
        self._name = format_name(hass, device, naslov)
        self._unique_id = f"{self._serial}_switch_{dbindex}"

        # Internal state tracking
        self._state = None
        self._error_message = ""
        self._dbindex = dbindex
        self._table_key = f"table_{dbindex}_switch"

        # Parameter names for this circuit
        self._param_name_def = f"PDEF_{dbindex}_0"
        self._param_name_state = f"PVAL_{dbindex}_0"
        self._param_name_off = f"PMIN_{dbindex}_0"
        self._param_name_on = f"PMAX_{dbindex}_0"

        # Live parameter objects from the device
        self._param_def = self._device.get_parameter(self._param_name_def)
        self._param_state = self._device.get_parameter(self._param_name_state)
        self._param_off = self._device.get_parameter(self._param_name_off)
        self._param_on = self._device.get_parameter(self._param_name_on)

        # Mark these parameters as "used" so they don't get exposed as "unknown sensors"
        self._param_def["used"] = True
        self._param_state["used"] = True
        self._param_off["used"] = True
        self._param_on["used"] = True

    def __del__(self):
        """Detach callbacks when HA unloads the entity.

        Wrapped in try/except so object cleanup during shutdown never raises.
        """
        try:
            self._param_def.set_update_callback(None, self._table_key)
            self._param_state.set_update_callback(None, self._table_key)
            self._param_off.set_update_callback(None, self._table_key)
            self._param_on.set_update_callback(None, self._table_key)
        except Exception:
            # We don't want teardown noise or crashes if HA is shutting down.
            pass

    async def async_added_to_hass(self):
        """Subscribe to updates from the boiler parameters."""
        self.async_schedule_update_ha_state(False)
        self._param_def.set_update_callback(self.update_callback, self._table_key)
        self._param_state.set_update_callback(self.update_callback, self._table_key)
        self._param_off.set_update_callback(self.update_callback, self._table_key)
        self._param_on.set_update_callback(self.update_callback, self._table_key)

    @property
    def should_poll(self) -> bool:
        """No polling needed; we get push updates via websocket."""
        return False

    async def update_callback(self, _device):
        """Called by the device library when any tracked param changes."""
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name shown in the UI."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique and stable ID for this entity."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return True if this circuit is currently 'on'."""
        try:
            return int(self._param_state["value"]) == int(self._param_on["value"])
        except (ValueError, KeyError, TypeError):
            # If we can't parse, assume it's off instead of throwing.
            return False

    @property
    def available(self) -> bool:
        """Return True if the device is connected."""
        return self.web_boiler_client.is_websocket_connected()

    def error(self) -> str:
        """Return any last error message (not exposed to HA state)."""
        return self._error_message

    def _compute_last_updated_str(self) -> str:
        """Return a human-presentable 'Last updated' timestamp string."""
        tzinfo = dt_util.get_time_zone(self.hass.config.time_zone)
        last_updated = "?"
        try:
            if "timestamp" in self._param_state.keys():
                raw_ts = self._param_state["timestamp"]
                if raw_ts is not None:
                    ts_int = int(raw_ts)
                    last_dt = datetime.fromtimestamp(ts_int)
                    last_updated = last_dt.astimezone(tzinfo).strftime(
                        "%d.%m.%Y %H:%M:%S"
                    )
        except Exception:
            # If anything goes sideways, we just leave last_updated as "?"
            pass
        return last_updated

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes shown in HA."""
        return {
            "Last updated": self._compute_last_updated_str(),
        }

    # Backwards-compat for older HA versions that still look for this name
    @property
    def device_state_attributes(self) -> dict[str, Any]:
        """Alias to extra_state_attributes for legacy HA."""
        return self.extra_state_attributes

    async def turn_circuit_on_off(self, value: bool):
        """Internal helper to call the API for this circuit."""
        ok = await self.web_boiler_client.turn_circuit(
            self._device["serial"], self._dbindex, value
        )
        if not ok:
            # Ask the client to relogin if the call failed
            self.web_boiler_client.relogin()

    async def turn_circuit_off(self):
        """Explicit async off helper."""
        await self.web_boiler_client.turn_circuit(
            self._device["serial"], self._dbindex, False
        )

    def turn_on(self, **kwargs) -> None:
        """HA sync service call to turn on."""
        asyncio.run_coroutine_threadsafe(
            self.turn_circuit_on_off(True),
            self.hass.loop,
        )

    def turn_off(self, **kwargs) -> None:
        """HA sync service call to turn off."""
        asyncio.run_coroutine_threadsafe(
            self.turn_circuit_on_off(False),
            self.hass.loop,
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry info to group this switch under the boiler device."""
        return create_device_info(self._device)
