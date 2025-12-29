"""Support for Centrometal Boiler devices."""

import logging
import datetime
import time
from typing import Optional, Callable

from centrometal_web_boiler import WebBoilerClient

# ---------------------------------------------------------------------
# Monkey patch: avoid blocking SSL certificate loading in the event loop.
# ---------------------------------------------------------------------
try:
    import asyncio
    import ssl
    from centrometal_web_boiler.WebBoilerWsClient import WebBoilerWsClient  # type: ignore
    from centrometal_web_boiler.const import WEB_BOILER_STOMP_URL  # type: ignore

    async def _patched_ws_start(self, username: str) -> None:
        """Patched non-blocking websocket start."""
        self.username = username
        self.logger.info(f"WebBoilerWsClient connecting... ({self.username})")

        loop = asyncio.get_running_loop()
        ssl_ctx = await loop.run_in_executor(None, ssl.create_default_context)

        # Kick off the internal websocket connection task using the prebuilt SSL context.
        self.client.loop.create_task(
            self.client._ClientSocket__main(WEB_BOILER_STOMP_URL, ssl=ssl_ctx)
        )

    if not getattr(WebBoilerWsClient.start, "_patched_by_centrometal_boiler", False):
        WebBoilerWsClient.start = _patched_ws_start  # type: ignore[assignment]
        WebBoilerWsClient.start._patched_by_centrometal_boiler = True
except Exception:
    # If something changes upstream and this import/patch fails, skip it safely.
    pass

# ---------------------------------------------------------------------
# Monkey patch: quiet noisy "parameter XYZ does not exist, creating one".
# ---------------------------------------------------------------------
try:
    from centrometal_web_boiler.WebBoilerDeviceCollection import (  # type: ignore
        WebBoilerDevice,
    )

    def _patched_get_parameter(self, name):
        """Patched version of WebBoilerDevice.get_parameter()."""
        if name not in self["parameters"]:
            # Downgrade from WARNING to DEBUG and still create the parameter.
            self.logger.debug(
                "WebBoilerDevice::get_parameter parameter %s does not exist, "
                "creating one (%s)",
                name,
                self.username,
            )
            return self.create_parameter(name)
        return self["parameters"][name]

    if not getattr(WebBoilerDevice.get_parameter, "_patched_by_centrometal_boiler", False):
        WebBoilerDevice.get_parameter = _patched_get_parameter  # type: ignore[assignment]
        WebBoilerDevice.get_parameter._patched_by_centrometal_boiler = True
except Exception:
    # Safe to ignore if the import/module name is different in this version.
    pass

# ---------------------------------------------------------------------

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PREFIX,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    WEB_BOILER_CLIENT,
    WEB_BOILER_SYSTEM,
    WEB_BOILER_LOGIN_RETRY_INTERVAL,
    WEB_BOILER_REFRESH_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Centrometal Boiler integration namespace."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single Centrometal account / boiler system from a config entry."""
    _LOGGER.debug("Setting up Centrometal Boiler System component")

    prefix = entry.data.get(CONF_PREFIX, "") or ""

    web_boiler_system = WebBoilerSystem(
        hass=hass,
        username=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        prefix=prefix,
    )

    unique_id = entry.data[CONF_EMAIL]
    hass.data[DOMAIN][unique_id] = {}
    hass.data[DOMAIN][unique_id][WEB_BOILER_SYSTEM] = web_boiler_system
    hass.data[DOMAIN][unique_id][WEB_BOILER_CLIENT] = web_boiler_system.web_boiler_client

    # Login, get configuration, open websocket, initial refresh
    ok = await web_boiler_system.start()
    if not ok:
        _LOGGER.error(
            "Got Access Denied Error when setting up Centrometal Boiler System: %s",
            entry.data[CONF_EMAIL],
        )

    # Clean shutdown when HA stops.
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        web_boiler_system.stop,  # accepts optional event
    )

    # Start periodic maintenance loop (tick) - drives refresh/reconnect.
    web_boiler_system.start_tick()

    # Load sensor / switch / binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "Centrometal Boiler System component setup finished %s",
        web_boiler_system.username,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Centrometal account cleanly (called on reload/remove)."""
    unique_id = entry.data[CONF_EMAIL]
    store = hass.data.get(DOMAIN, {}).get(unique_id)
    system: Optional["WebBoilerSystem"] = None
    if store:
        system = store.get(WEB_BOILER_SYSTEM)

    # Stop tick + websocket before unloading platforms to avoid callbacks into removed entities
    if system:
        try:
            system.cancel_tick()
        except Exception:
            pass
        try:
            await system.stop()
        except Exception:
            pass

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup hass.data
    try:
        hass.data[DOMAIN].pop(unique_id, None)
    except Exception:
        pass

    return unload_ok


class WebBoilerSystem:
    """Wrapper around one Centrometal account / boiler system session."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        username: str,
        password: str,
        prefix: str,
    ) -> None:
        self._hass = hass
        self.username = username
        self.password = password

        prefix = prefix.rstrip()
        self.prefix = (prefix + " ") if prefix else ""

        self.web_boiler_client = WebBoilerClient()

        now_ts = datetime.datetime.now().timestamp()
        self.last_relogin_timestamp = now_ts
        self.last_refresh_timestamp = now_ts

        self._tick_unsub: Optional[Callable[[], None]] = None

    async def on_parameter_updated(self, device, param, create: bool = False):
        """Called by the library when a parameter changes via websocket push."""
        action = "Create" if create else "update"
        serial = device["serial"]
        name = param["name"]
        value = param["value"]

        _LOGGER.info(
            "%s %s %s = %s (%s)",
            action,
            serial,
            name,
            value,
            self.web_boiler_client.username,
        )

    async def start(self) -> bool:
        """Log in, pull config, open websocket, and take initial snapshot."""
        _LOGGER.debug("Starting Centrometal Boiler System %s", self.username)

        try:
            logged_in = await self.web_boiler_client.login(
                self.username, self.password
            )
            if not logged_in:
                raise Exception(
                    f"Cannot login to Centrometal web boiler server {self.username}"
                )

            got_configuration = await self.web_boiler_client.get_configuration()
            if not got_configuration:
                raise Exception(
                    f"Cannot get configuration from Centrometal server {self.username}"
                )

            if len(self.web_boiler_client.data) == 0:
                raise Exception(
                    f"No device found to Centrometal web boiler server {self.username}"
                )

            # Start the websocket (monkey patched to avoid blocking SSL work).
            await self.web_boiler_client.start_websocket(
                self.on_parameter_updated
            )

            # Pull initial "working table" data after websocket start.
            await self.web_boiler_client.refresh()
            self.last_refresh_timestamp = time.time()

            return True

        except Exception as ex:
            _LOGGER.error("Authentication failed : %s", str(ex))
            return False

    def start_tick(self) -> None:
        """Start the periodic maintenance loop; safe to call multiple times."""
        # Cancel previous if exists
        self.cancel_tick()

        async def _on_interval(_now) -> None:
            try:
                await self.tick()
            except Exception as ex:
                _LOGGER.warning("WebBoilerSystem.tick raised: %s", ex)

        # Run tick every second (lightweight logic; intervals control actual actions)
        self._tick_unsub = async_track_time_interval(self._hass, _on_interval, datetime.timedelta(seconds=1))

    def cancel_tick(self) -> None:
        """Cancel the periodic maintenance loop if running."""
        if self._tick_unsub:
            try:
                self._tick_unsub()
            except Exception:
                pass
            self._tick_unsub = None

    async def stop(self, event=None):
        """Close the websocket when Home Assistant shuts down or unloads."""
        _LOGGER.debug(
            "Stopping Centrometal WebBoilerSystem %s",
            self.web_boiler_client.username,
        )
        # Close WS; HTTP session closed by library on relogin/teardown as needed
        return await self.web_boiler_client.close_websocket()

    async def tick(self):
        """Periodic check.

        - If websocket disconnected and long enough passed -> relogin().
        - If websocket connected and refresh interval passed -> refresh().
        """
        now = datetime.datetime.now().timestamp()

        # If we're offline, try to relogin occasionally
        try:
            connected = self.web_boiler_client.is_websocket_connected()
        except Exception:
            connected = False

        if not connected:
            if now - self.last_relogin_timestamp > WEB_BOILER_LOGIN_RETRY_INTERVAL:
                _LOGGER.info(
                    "Centrometal WebBoilerSystem::tick trying to relogin %s",
                    self.web_boiler_client.username,
                )
                await self.relogin()
            return

        # If we're online and it's time to refresh, do it
        if now - self.last_refresh_timestamp > WEB_BOILER_REFRESH_INTERVAL:
            self.last_refresh_timestamp = now
            _LOGGER.info(
                "WebBoilerSystem::tick refresh data %s",
                self.web_boiler_client.username,
            )
            refresh_successful = await self.web_boiler_client.refresh()
            if not refresh_successful:
                await self.relogin()

    async def relogin(self):
        """Try to restore the websocket session after disconnect or bad refresh."""
        self.last_relogin_timestamp = time.time()

        try:
            await self.web_boiler_client.close_websocket()
        except Exception:
            pass
        try:
            await self.web_boiler_client.http_client.close_session()
        except Exception:
            pass

        relogin_successful = await self.web_boiler_client.relogin()
        if relogin_successful:
            await self.web_boiler_client.start_websocket(
                self.on_parameter_updated
            )
            ok = await self.web_boiler_client.refresh()
            if ok:
                self.last_refresh_timestamp = time.time()
        else:
            _LOGGER.warning(
                "WebBoilerSystem::tick failed to relogin %s",
                self.web_boiler_client.username,
            )
