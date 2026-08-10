from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import ATTR_MANUFACTURER, DOMAIN, BINARY_SENSOR_TYPES, DIGITAL_STATUS


@dataclass(frozen=True, kw_only=True)
class PhoenixEvBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Phoenix EV binary sensor entities."""

    value_key: str
    is_digital_input: bool


BINARY_SENSOR_DESCRIPTIONS: tuple[PhoenixEvBinarySensorEntityDescription, ...] = tuple(
    PhoenixEvBinarySensorEntityDescription(
        key=sensor_info[1],
        name=sensor_info[0],
        icon=sensor_info[3],
        value_key=sensor_info[1],
        is_digital_input=sensor_info[4],
    )
    for sensor_info in BINARY_SENSOR_TYPES.values()
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Phoenix EV binary sensors from a config entry."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, hub_name)},
        name=hub_name,
        manufacturer=ATTR_MANUFACTURER,
    )

    async_add_entities(
        [
            PhoenixEvBinarySensor(hub_name, hub, device_info, description)
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )
    return True


class PhoenixEvBinarySensor(BinarySensorEntity):
    """Representation of an PEVC Modbus binary_sensor."""

    _attr_has_entity_name = True

    def __init__(self, platform_name, hub, device_info, description: PhoenixEvBinarySensorEntityDescription):
        """Initialize the binary_sensor."""
        self._hub = hub
        self.entity_description = description
        self._value_key = description.value_key
        self._is_digital_input = description.is_digital_input
        self._attr_unique_id = f"{platform_name}_{description.key}"
        self._attr_device_info = device_info

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._hub.async_add_pevc_binary_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_pevc_binary_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self):
        self.async_write_ha_state()

    @property
    def icon(self):
        """Return the binary_sensor icon."""
        if self._value_key in self._hub.data:
            if self._hub.data[self._value_key] == DIGITAL_STATUS[True]:
                if self._is_digital_input:
                    return "mdi:electric-switch-closed"
                return "mdi:lightbulb-on"
            if self._is_digital_input:
                return "mdi:electric-switch"
            return "mdi:lightbulb-outline"
        return self.entity_description.icon

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._hub.is_connected()

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False

    @property
    def is_on(self) -> bool:
        """Return binary sensor on/off state."""
        return self._hub.data.get(self._value_key) == DIGITAL_STATUS[True]
