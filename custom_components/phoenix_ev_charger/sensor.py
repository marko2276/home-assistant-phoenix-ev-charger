from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import ATTR_MANUFACTURER, DOMAIN, SENSOR_TYPES


@dataclass(frozen=True, kw_only=True)
class PhoenixEvSensorEntityDescription(SensorEntityDescription):
    """Describes Phoenix EV sensor entities."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[PhoenixEvSensorEntityDescription, ...] = tuple(
    PhoenixEvSensorEntityDescription(
        key=sensor_info[1],
        name=sensor_info[0],
        native_unit_of_measurement=sensor_info[2],
        icon=sensor_info[3],
        value_key=sensor_info[1],
    )
    for sensor_info in SENSOR_TYPES.values()
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Phoenix EV sensors from a config entry."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, hub_name)},
        name=hub_name,
        manufacturer=ATTR_MANUFACTURER,
    )

    async_add_entities(
        [
            PhoenixEvSensor(hub_name, hub, device_info, description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )
    return True


class PhoenixEvSensor(SensorEntity):
    """Representation of an PEVC Modbus sensor."""

    _attr_has_entity_name = True

    def __init__(self, platform_name, hub, device_info, description: PhoenixEvSensorEntityDescription):
        """Initialize the sensor."""
        self._hub = hub
        self.entity_description = description
        self._value_key = description.value_key
        self._attr_unique_id = f"{platform_name}_{description.key}"
        self._attr_device_info = device_info

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._hub.async_add_pevc_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_pevc_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self):
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the native sensor value."""
        value = self._hub.data.get(self._value_key)

        if value is None:
            return None

        if self.entity_description.native_unit_of_measurement is None:
            return value

        if isinstance(value, (int, float)):
            return value

        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return None

        return value

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._hub.is_connected()

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False
