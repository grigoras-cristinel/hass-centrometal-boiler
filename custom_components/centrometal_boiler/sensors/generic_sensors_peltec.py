from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE, UnitOfTime


def build_unique_id(device_serial: str, param_name: str) -> str:
    """Return a stable Home Assistant unique_id for a Centrometal sensor."""
    return f"{device_serial}-{param_name}"


# Live measured temperatures from the boiler
PELTEC_SENSOR_TEMPERATURES = {
    "B_Tak1_1": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
        "Buffer Tank Temparature Up",
    ],
    "B_Tak2_1": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
        "Buffer Tank Temparature Down",
    ],
    "B_Tdpl1": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
        "Flue Gas",
    ],
    "B_Tpov1": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
        "Mixer Temperature",
    ],
    "B_Tk1": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
        "Boiler Temperature",
    ],
    "B_Ths1": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
        "Hydraulic Crossover Temperature",
    ],
    "B_Tkm1": [
        UnitOfTemperature.CELSIUS,
        "mdi:water-boiler",
        SensorDeviceClass.TEMPERATURE,
        "DHW Temperature",
    ],
}

# Runtime counters / statistics
PELTEC_SENSOR_COUNTERS = {
    "CNT_0": [UnitOfTime.MINUTES, "mdi:timer", None, "Burner Work"],
    "CNT_1": ["", "mdi:counter", None, "Number of Burner Start"],
    "CNT_2": [UnitOfTime.MINUTES, "mdi:timer", None, "Feeder Screw Work"],
    "CNT_3": [UnitOfTime.MINUTES, "mdi:timer", None, "Flame Duration"],
    "CNT_4": [UnitOfTime.MINUTES, "mdi:timer", None, "Fan Working Time"],
    "CNT_5": [UnitOfTime.MINUTES, "mdi:timer", None, "Electric Heater Working Time"],
    "CNT_6": [UnitOfTime.MINUTES, "mdi:timer", None, "Vacuum Turbine Working Time"],
    "CNT_7": ["", "mdi:counter", None, "Vacuum Turbine Cycles Number"],
    "CNT_8": [UnitOfTime.MINUTES, "mdi:timer", None, "Time on D6"],
    "CNT_9": [UnitOfTime.MINUTES, "mdi:timer", None, "Time on D5"],
    "CNT_10": [UnitOfTime.MINUTES, "mdi:timer", None, "Time on D4"],
    "CNT_11": [UnitOfTime.MINUTES, "mdi:timer", None, "Time on D3"],
    "CNT_12": [UnitOfTime.MINUTES, "mdi:timer", None, "Time on D2"],
    "CNT_13": [UnitOfTime.MINUTES, "mdi:timer", None, "Time on D1"],
    "CNT_14": [UnitOfTime.MINUTES, "mdi:timer", None, "Time on D0"],
    "CNT_15": [None, "mdi:counter", None, "Reserve Counter"],
}

# Miscellaneous status/config values from PelTec II Lambda
# NOTE:
# - We KEEP B_razP ("Pelet Level") -> pellet % left
# - We REMOVED:
#     * B_razina ("Tank Level" discrete Empty/Reserve/Full)
#     * B_Time (controller clock)
#     * PING (server ping)
PELTEC_SENSOR_MISC = {
    "B_Tva1": [
        UnitOfTemperature.CELSIUS,
        "mdi:thermometer",
        SensorDeviceClass.TEMPERATURE,
        "Outdoor Temperature",
    ],

    "B_cm2k": [None, "mdi:state-machine", None, "CM2K Status"],

    "B_addConf": [None, "mdi:note-plus", None, "Accessories"],
    "B_korNum": [None, "mdi:counter", None, "Working Phase"],

    # PelTec II Lambda pellet level percentage (the one we KEEP)
    "B_razP": [
        PERCENTAGE,
        "mdi:basket-fill",
        None,
        "Pelet Level",
    ],

    "B_STATE": [
        None,
        "mdi:state-machine",
        None,
        "Boiler State",
    ],

    "B_fireS": [
        None,
        "mdi:fire",
        None,
        "Firing State",
    ],

    # Heating circuit metadata / labels
    "K1B_CircType": [None, "mdi:view-list", None, "Circuit 1K Heating Type"],
    "K1B_korType": [None, "mdi:view-list", None, "Circuit 1K Correction Type"],
    "K1B_dayNight": [None, "mdi:view-list", None, "Circuit 1K Day Night Mode"],

    # Info / firmware / identity
    "B_KONF": [None, "mdi:state-machine", None, "Configuration"],
    "B_VER": [None, "mdi:information", None, "Firmware Version"],
    "B_INST": [None, "mdi:information", None, "Installation"],
    "B_sng": [None, "mdi:information", None, "Nominal Power"],
    "B_PRODNAME": [None, "mdi:information", None, "Product Name"],

    # Sensors
    "B_Oxy1": [PERCENTAGE, "mdi:lambda", None, "Lambda Probe Reading"],
    "B_signal": [PERCENTAGE, "mdi:wifi", None, "WiFi Signal"],

    # Reserved/diagnostic parameters
    "B_resInd": [None, "mdi:help-circle-outline", None, "Reserved Index"],
    "B_resDir": [None, "mdi:help-circle-outline", None, "Reserved Direction"],
    "B_resMax": [None, "mdi:help-circle-outline", None, "Reserved Max"],
    "PDEF_272_0": [None, "mdi:tune-variant", None, "Param Default 272/0"],
    "PMIN_272_0": [None, "mdi:tune-variant", None, "Param Min 272/0"],
    "PMAX_272_0": [None, "mdi:tune-variant", None, "Param Max 272/0"],

    "B_FILE": [None, "mdi:file-cog", None, "Firmware File"],
}

# Combined map for PelTec II Lambda
PELTEC_GENERIC_SENSORS = {
    **PELTEC_SENSOR_TEMPERATURES,
    **PELTEC_SENSOR_COUNTERS,
    **PELTEC_SENSOR_MISC,
}
