"""Compatibility shim.

This module just re-exports the canonical binary On/Off sensor logic
from WebBoilerBinaryOnOffSensor, so we don't end up with two slightly
different implementations fighting over the same parameters.
"""

from .WebBoilerBinaryOnOffSensor import (
    WebBoilerBinaryOnOffSensor,
    create_binary_state_entities,
)

__all__ = ["WebBoilerBinaryOnOffSensor", "create_binary_state_entities"]
