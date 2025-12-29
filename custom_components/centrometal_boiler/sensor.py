# -*- coding: utf-8 -*-
"""Support for Centrometal Boiler System sensors."""

import logging
import time
from datetime import timedelta

from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .sensors.WebBoilerDeviceTypeSensor import WebBoilerDeviceTypeSensor
from .sensors.WebBoilerGenericSensor import WebBoilerGenericSensor
from .sensors.WebBoilerConfigurationSensor import WebBoilerConfigurationSensor
from .sensors.WebBoilerWorkingTableSensor import WebBoilerWorkingTableSensor
from .sensors.WebBoilerFireGridSensor import WebBoilerFireGridSensor
from .sensors.WebBoilerHeatingCircuitSensor import (
    WebBoilerHeatingCircuitSensor,
)
from .sensors.WebBoilerBinaryOnOffSensor import (
    create_binary_state_entities,
)

from .const import DOMAIN, WEB_BOILER_CLIENT

_LOGGER = logging.getLogger(__name__)

# ---- Watchdog tuning ----
_WATCHDOG_INTERVAL = timedelta(minutes=2)   # how often to check
_STALE_SECONDS = 10 * 60                    # consider data stale after 10 minutes
_RELOAD_COOLDOWN_SECONDS = 15 * 60          # don't spam reloads


def _latest_param_ts(web_boiler_client) -> int | None:
    """
    Return the latest 'timestamp' across all known parameters, as epoch seconds.
    If none found, return None.
    """
    latest = None
    try:
        for device in web_boiler_client.data.values():
            params = device.get("parameters", {})
            for p in params.values():
                ts = p.get("timestamp")
                if ts is None:
                    continue
                try:
                    ts_int = int(ts)
                except (ValueError, TypeError):
                    continue
                if latest is None or ts_int > latest:
                    latest = ts_int
    except Exception as ex:
        _LOGGER.debug("Watchdog: failed to scan timestamps: %s", ex)
    return latest


def _start_or_replace_watchdog(
    hass: HomeAssistant, config_entry, username: str
) -> None:
    """
    Start a single watchdog per username; if one already exists, cancel and replace it.
    The watchdog auto-reloads the config entry if websocket is down or data is stale.
    """
    store = hass.data.setdefault(DOMAIN, {}).setdefault(username, {})

    # Cancel previous watchdog if present
    old_unsub = store.pop("_watchdog_unsub", None)
    if old_unsub:
        try:
            old_unsub()
        except Exception:
            pass

    store.setdefault("_last_reload_ts", 0)

    async def _tick(now) -> None:
        client = store.get(WEB_BOILER_CLIENT)
        if not client:
            return

        now_ts = int(time.time())

        # 1) If websocket is disconnected -> reload
        try:
            connected = client.is_websocket_connected()
        except Exception:
            connected = False

        reload_reason = None

        if not connected:
            reload_reason = "websocket disconnected"

        # 2) If connected but no data change in too long -> reload
        if reload_reason is None:
            latest_ts = _latest_param_ts(client)
            if latest_ts is None:
                # If we never saw any timestamp after 2 full intervals, treat as stale
                if now_ts - store.get("_watchdog_started_ts", now_ts) > (
                    _WATCHDOG_INTERVAL.total_seconds() * 2
                ):
                    reload_reason = "no timestamps available"
            else:
                if (now_ts - latest_ts) > _STALE_SECONDS:
                    reload_reason = f"stale data ({now_ts - latest_ts}s > {_STALE_SECONDS}s)"

        if reload_reason is None:
            return

        # Cooldown: avoid reload storms
        last_reload = int(store.get("_last_reload_ts", 0))
        if (now_ts - last_reload) < _RELOAD_COOLDOWN_SECONDS:
            _LOGGER.warning(
                "Centrometal watchdog: would reload (%s) but in cooldown (%ss remaining)",
                reload_reason,
                _RELOAD_COOLDOWN_SECONDS - (now_ts - last_reload),
            )
            return

        store["_last_reload_ts"] = now_ts
        _LOGGER.warning(
            "Centrometal watchdog: reloading config entry due to %s", reload_reason
        )

        # Important: cancel our own watchdog before reloading, to avoid duplicates
        unsub = store.pop("_watchdog_unsub", None)
        if unsub:
            try:
                unsub()
            except Exception:
                pass

        # Schedule the reload (don't await inside the timer callback)
        hass.async_create_task(
            hass.config_entries.async_reload(config_entry.entry_id)
        )

    # Start
    unsub = async_track_time_interval(hass, _tick, _WATCHDOG_INTERVAL)
    store["_watchdog_unsub"] = unsub
    store["_watchdog_started_ts"] = int(time.time())


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up Centrometal boiler sensors from a config entry."""
    all_entities = []

    username = config_entry.data[CONF_EMAIL]
    web_boiler_client = hass.data[DOMAIN][username][WEB_BOILER_CLIENT]

    # Start/refresh watchdog (one per username)
    _start_or_replace_watchdog(hass, config_entry, username)

    for device in web_boiler_client.data.values():
        #
        # 1. Claim bool-like params first (B_CMD, pumps, fan active, DHW pump, etc.)
        #
        all_entities.extend(create_binary_state_entities(hass, device))

        #
        # 2. Common / normal sensors
        #
        all_entities.extend(WebBoilerGenericSensor.create_common_entities(hass, device))
        all_entities.extend(WebBoilerConfigurationSensor.create_entities(hass, device))

        # We intentionally DO NOT create WebBoilerCurrentTimeSensor anymore
        # (we don't expose B_Time).
        #
        # We also do not auto-expose the old pellet tank level ("Tank Level"
        # from B_razina); that class is stubbed out now.

        # Working table (schedule) sensor - may return [] depending on firmware.
        # On PelTec II Lambda this usually returns [], but keeping it here
        # does not hurt stability.
        all_entities.extend(WebBoilerWorkingTableSensor.create_entities(hass, device))

        # Boiler/device type info sensor
        all_entities.extend(WebBoilerDeviceTypeSensor.create_entities(hass, device))

        # Heating circuit info (K1 etc.)
        all_entities.extend(
            WebBoilerHeatingCircuitSensor.create_heating_circuits_entities(
                hass, device
            )
        )

        #
        # 3. PelTec II Lambda extras
        #
        if device["type"] == "peltec2":
            # Fire grid / grate position sensor (if firmware exposes it)
            all_entities.extend(WebBoilerFireGridSensor.create_entities(hass, device))

        #
        # 4. PelTec-specific generic/conf sensors and temperature setpoints
        #
        all_entities.extend(WebBoilerGenericSensor.create_conf_entities(hass, device))
        all_entities.extend(
            WebBoilerGenericSensor.create_temperatures_entities(hass, device)
        )

        #
        # 5. We intentionally do NOT expose generic "unknown" params anymore
        #
        all_entities.extend(
            WebBoilerGenericSensor.create_unknown_entities(hass, device)
        )

    # ---- de-dupe pass based on unique_id ----
    deduped_entities = []
    seen_ids = set()

    for entity in all_entities:
        uid = getattr(entity, "unique_id", None)

        if uid is None:
            deduped_entities.append(entity)
            continue

        if uid in seen_ids:
            _LOGGER.debug(
                "Skipping duplicate entity with unique_id %s (%s)",
                uid,
                getattr(entity, "name", "<no name>"),
            )
            continue

        seen_ids.add(uid)
        deduped_entities.append(entity)

    # We no longer create B_Time at all, so we don't need to filter it here.

    async_add_entities(deduped_entities, True)
