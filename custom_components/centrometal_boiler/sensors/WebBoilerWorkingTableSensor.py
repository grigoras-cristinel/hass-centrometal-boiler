import collections

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .WebBoilerGenericSensor import WebBoilerGenericSensor
from centrometal_web_boiler.WebBoilerDeviceCollection import WebBoilerParameter


class WebBoilerWorkingTableSensor(WebBoilerGenericSensor):
    """
    Exposes the boiler's schedule tables (PVAL_x_y groups) as one
    human-readable sensor with attributes for each weekday.
    """

    def __init__(
        self, hass: HomeAssistant, device, sensor_data, param_status, param_tables
    ) -> None:
        super().__init__(hass, device, sensor_data, param_status)
        self.param_tables = param_tables

        # Mark all PVAL_* parameters as "used" so they don't get exposed
        # later as separate generic sensors.
        for key in self.param_tables:
            for val in self.param_tables[key]:
                name = f"PVAL_{key}_{val}"
                parameter = self.device.get_parameter(name)
                parameter["used"] = True

    def __del__(self):
        super().__del__()
        # Remove callbacks on GC/unload for each PVAL entry
        self.set_callback_to_all_table_parameters(None)

    def set_callback_to_all_table_parameters(self, callback):
        """Subscribe/unsubscribe to all table parameters for live updates."""
        for key in self.param_tables:
            for val in self.param_tables[key]:
                name = f"PVAL_{key}_{val}"
                parameter = self.device.get_parameter(name)
                parameter.set_update_callback(callback, f"table_{key}")

    async def async_added_to_hass(self):
        """Subscribe to sensor events."""
        await super().async_added_to_hass()
        # When any PVAL_* value changes, update this entity
        self.set_callback_to_all_table_parameters(self.update_callback)

    def getValue(self, table_key, dayIndex, i):
        """Return a single minute-of-day value from a PVAL_* slot."""
        name = "PVAL_" + table_key + "_" + str(dayIndex * 6 + i)
        parameter = self.device.get_parameter(name)
        if "value" in parameter.keys():
            value = parameter["value"]
            return int(value)
        return 0

    def format_time(self, val):
        """Convert minutes-from-midnight to HH:MM."""
        return "%02d:%02d" % (int(val / 60), val % 60)

    def get_range(self, tableIndex, dayIndex, i, j):
        """Return a human-readable range like 06:00-08:30, or ' - ' if disabled."""
        val1 = self.getValue(tableIndex, dayIndex, i)
        val2 = self.getValue(tableIndex, dayIndex, j)
        # 1440/1440 = disabled slot in Centrometal's schedule format
        if val1 == 1440 and val2 == 1440:
            return " - "
        return self.format_time(val1) + "-" + self.format_time(val2)

    @property
    def extra_state_attributes(self):
        """
        Return schedule tables as attributes.

        We merge in:
        - base attributes from parent (Last updated, Original name)
        - for each weekday, up to 3 active ranges
        """
        base = super().extra_state_attributes or {}
        attributes = dict(base)

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for key in self.param_tables:
            for day_idx in range(0, 7):
                day_name = days[day_idx]
                ranges = [
                    self.get_range(key, day_idx, 0, 1),
                    self.get_range(key, day_idx, 2, 3),
                    self.get_range(key, day_idx, 4, 5),
                ]
                attributes[f"Table{key} {day_name}"] = " / ".join(ranges)

        return attributes

    @staticmethod
    def get_pval_data(device):
        """
        Group PVAL_x_y parameters by x, and collect/sort all y values for each x.
        Returns an OrderedDict of {table_key: [slot_indexes...]}.
        """
        pval = {}
        for key in device["parameters"].keys():
            if key.startswith("PVAL_"):
                data = key[5:].split("_")
                if len(data) == 2:
                    if data[0] not in pval:
                        pval[data[0]] = []
                    if data[1] not in pval[data[0]]:
                        pval[data[0]].append(data[1])
                        pval[data[0]].sort(key=int)
        return collections.OrderedDict(sorted(pval.items()))

    @staticmethod
    def create_entities(hass: HomeAssistant, device) -> list[SensorEntity]:
        """
        Create one WorkingTableSensor per full 42-slot schedule table.
        "42 slots" = 7 days * 6 slots/day.
        """
        pval_data = WebBoilerWorkingTableSensor.get_pval_data(device)
        entities: list[SensorEntity] = []
        for key, value in pval_data.items():
            if len(value) == 42:
                parameter = WebBoilerParameter()
                parameter["name"] = "Table " + key
                parameter["value"] = "See attributes"
                entities.append(
                    WebBoilerWorkingTableSensor(
                        hass,
                        device,
                        [None, "mdi:state-machine", None, "Table " + key],
                        parameter,
                        {key: value},
                    )
                )
        return entities
