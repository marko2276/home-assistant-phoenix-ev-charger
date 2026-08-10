import logging
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    NumberEntity
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import DeviceInfo

from .const import ATTR_MANUFACTURER, DOMAIN, MIN_CHARGE_CURRENT, MAX_CHARGE_CURRENT

_LOGGER = logging.getLogger(__name__)



async def async_setup_entry(hass, entry, async_add_entities):
    """Wallbe setup entry."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    _LOGGER.debug("Wallbe EV charger number component running ...")

    device_info = DeviceInfo(
        identifiers={(DOMAIN, hub_name)},
        name=hub_name,
        manufacturer=ATTR_MANUFACTURER,
    )

    async_add_entities(
        [
            PhoenixEvChargeCurrentNumber(hub_name, hub, device_info)
        ]
    )


class PhoenixEvChargeCurrentNumber(NumberEntity):
    """Charge current setting entity."""

    _attr_has_entity_name = True
    _attr_name = "Charging current"
    _attr_icon = "mdi:ev-station"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = "A"
    _attr_native_step = 1
    _attr_native_min_value = MIN_CHARGE_CURRENT
    _attr_native_max_value = MAX_CHARGE_CURRENT
    _attr_mode = NumberMode.BOX

    def __init__(self, hub_name, hub, device_info):
        """Initialize the number entity"""
        self._attr_unique_id = f"{hub_name}_chargecurrentsetting"
        self._attr_device_info = device_info
        self._value = MAX_CHARGE_CURRENT
        self._hub = hub

    @property
    def native_value(self) -> float | None:
        """Return the value of the entity."""
        if "maxchargecurrentlimit" in self._hub.data:
            return float(self._hub.data["maxchargecurrentlimit"])
        return self._value

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._hub.is_connected()

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""

        if not self._hub.ensure_connected():
            _LOGGER.error("Failed to set charging current because charger is disconnected")
            return
        # value that needs to be written is in 100mA units
        value_to_write = [int(value * 10)]
        _LOGGER.debug("Value to be written to reg 528: %d", value_to_write[0])
        response = self._hub.write_registers(unit=255, address=528, values=value_to_write)
        if response is None or response.isError():
            _LOGGER.error("Writing charging current to register 528 failed")
            return
        self._value = value
        self.async_write_ha_state()

