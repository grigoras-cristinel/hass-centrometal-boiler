import asyncio
from datetime import datetime
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity

from ..common import create_device_info, format_name
from ..const import DOMAIN, WEB_BOILER_CLIENT, WEB_BOILER_SYSTEM


def _value_is_on(v: Any) -> bool:
    """
    Helper: interpret boiler values (B_CMD etc.) as boolean 'on'.

    We treat obvious "on" cases as True, obvious "off" cases as False.
    This matches the mapping we use in WebBoilerBinaryOnOffSensor.
    """
    # Explicit ON cases
    if v in (1, "1", "ON", "On", "on", True, "TRUE", "True", "true"):
        return True

    # Explicit OFF cases
    if v in (0, "0", "OFF", "Off", "off", False, "FALSE", "False", "false"):
        return False

    # Try int fallback
    try:
        intval = int(str(v))
        if intval == 1:
            return True
        if intval == 0:
            return False
    except (ValueError, TypeError):
        pass

    # If it's some other string like "CLEANING", that's basically "not actively commanded"
    # but for safety we'll treat anything non-"OFF" as on in fallback situations.
    return str(v) != "OFF"


class WebBoilerPowerSwitch(SwitchEntity):
    """Representation of the main boiler power switch (ON/OFF)."""

    def __init__(self, hass: HomeAssistant, device) -> None:
        """Initialize the Boiler Power Switch."""
        self.hass = hass
        self.web_boiler_client = hass.data[DOMAIN][device.username][WEB_BOILER_CLIENT]
        self.web_boiler_system = hass.data[DOMAIN][device.username][WEB_BOILER_SYSTEM]

        self._device = device
        self._product = device["product"]

        # Friendly name like "Peltec II Boiler Switch" with prefix/serial as needed
        self._name = format_name(hass, device, f"{self._product} Boiler Switch")
        self._unique_id = device["serial"]

        self._error_message = ""

        # We keep references to BOTH parameters:
        # - B_CMD  : "Command Active" (what the controller is told to do NOW)
        # - B_STATE: "Boiler State"   (what it's physically doing / cooling / etc.)
        #
        # Home Assistant should show switch 'on' based on B_CMD,
        # because that's what the Web UI calls "On/Off".
        # If B_CMD doesn't exist for some reason, we fall back to B_STATE.
        self._param_cmd = device.get_parameter("B_CMD")
        self._param_state = device.get_parameter("B_STATE")

        # For convenience in attributes
        self._all_params = [p for p in (self._param_cmd, self._param_state) if p]

    def __del__(self):
        """Detach callbacks when HA unloads the entity."""
        try:
            if self._param_cmd:
                self._param_cmd.set_update_callback(None, "switch")
        except Exception:
            pass
        try:
            if self._param_state:
                self._param_state.set_update_callback(None, "switch")
        except Exception:
            pass

    async def async_added_to_hass(self):
        """Subscribe to events for live updates."""
        self.async_schedule_update_ha_state(False)

        # Subscribe to both so UI refreshes ASAP on command changes OR physical state changes.
        if self._param_cmd:
            self._param_cmd.set_update_callback(self.update_callback, "switch")
        if self._param_state:
            self._param_state.set_update_callback(self.update_callback, "switch")

    @property
    def should_poll(self) -> bool:
        """No polling needed; we get updates via websocket."""
        return False

    async def update_callback(self, _device):
        """Called by the library when either B_CMD or B_STATE changes."""
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the switch name as shown in the UI."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a stable unique ID for this entity."""
        return self._unique_id

    def _current_cmd_on(self) -> bool | None:
        """
        Return True/False if we can interpret B_CMD.
        Return None if B_CMD is missing or unreadable.
        """
        if not self._param_cmd:
            return None
        try:
            return _value_is_on(self._param_cmd["value"])
        except Exception:
            return None

    def _current_state_on(self) -> bool:
        """
        Fallback interpretation from B_STATE if B_CMD wasn't usable.
        Original behavior was: consider it ON unless it's literally "OFF".
        """
        try:
            val = self._param_state["value"]
            return val != "OFF"
        except Exception:
            return False

    @property
    def is_on(self) -> bool:
        """
        Return True if HA should consider the boiler 'on'.

        We now define "on" as:
        - Is the controller actively commanding heat/run? (B_CMD interpreted)
          → This matches what the Centrometal web UI shows.
        - Otherwise, fall back to the older B_STATE logic.
        """
        cmd_val = self._current_cmd_on()
        if cmd_val is not None:
            return cmd_val
        return self._current_state_on()

    @property
    def available(self) -> bool:
        """Expose entity as unavailable if websocket is down."""
        return self.web_boiler_client.is_websocket_connected()

    def _compute_last_updated_str(self) -> str:
        """
        Return 'Last updated' timestamp for attributes in local HA tz.

        We'll prefer B_CMD timestamp (because that's what we're displaying as state),
        and fallback to B_STATE if needed.
        """
        tzinfo = dt_util.get_time_zone(self.hass.config.time_zone)

        # pick first param that actually has a usable timestamp
        for param in (self._param_cmd, self._param_state):
            if not param:
                continue
            try:
                raw_ts = param.get("timestamp") if hasattr(param, "get") else param["timestamp"]
                ts_int = int(raw_ts)
                dt_obj = datetime.fromtimestamp(ts_int)
                return dt_obj.astimezone(tzinfo).strftime("%d.%m.%Y %H:%M:%S")
            except Exception:
                continue

        return "?"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Extra debug info:
        - Last updated (local time)
        - Raw command value (B_CMD)
        - Raw state value (B_STATE)
        """
        attrs: dict[str, Any] = {
            "Last updated": self._compute_last_updated_str(),
        }

        try:
            attrs["Command Active (B_CMD)"] = (
                self._param_cmd["value"] if self._param_cmd else "N/A"
            )
        except Exception:
            attrs["Command Active (B_CMD)"] = "N/A"

        try:
            attrs["Boiler State (B_STATE)"] = (
                self._param_state["value"] if self._param_state else "N/A"
            )
        except Exception:
            attrs["Boiler State (B_STATE)"] = "N/A"

        return attrs

    # Backwards compatibility for very old HA versions
    @property
    def device_state_attributes(self) -> dict[str, Any]:
        """Alias to extra_state_attributes for legacy HA."""
        return self.extra_state_attributes

    async def _async_turn_and_refresh(self, power_on: bool) -> None:
        """
        Send on/off command to boiler, then ask the client to refresh.

        We keep the same control API: web_boiler_client.turn(serial, True/False).
        After calling turn(), we try a refresh() to pull updated values for B_CMD/B_STATE,
        then push those new values through callbacks.
        """
        await self.web_boiler_client.turn(self._device["serial"], power_on)

        refreshed = await self.web_boiler_client.refresh()
        if refreshed:
            await self.web_boiler_client.data.notify_all_updated()

    def turn_on(self, **kwargs) -> None:
        """HA sync service call -> turn boiler ON."""
        asyncio.run_coroutine_threadsafe(
            self._async_turn_and_refresh(True),
            self.hass.loop,
        )

    def turn_off(self, **kwargs) -> None:
        """HA sync service call -> turn boiler OFF."""
        asyncio.run_coroutine_threadsafe(
            self._async_turn_and_refresh(False),
            self.hass.loop,
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry info so HA groups this switch with the boiler."""
        return create_device_info(self._device)
