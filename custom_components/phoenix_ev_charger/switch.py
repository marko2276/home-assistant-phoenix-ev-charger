import logging
from homeassistant.components.switch import SwitchEntity

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import DeviceInfo

from .const import ATTR_MANUFACTURER, DOMAIN, SWITCHES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Phoenix ev Sensor setup platform."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    _LOGGER.debug("Phoenix ev charger Switch component running ...")
    device_info = DeviceInfo(
        identifiers={(DOMAIN, hub_name)},
        name=hub_name,
        manufacturer=ATTR_MANUFACTURER,
    )

    async_add_entities(
        [
            PhoenixEvSwitch(hub_name, hub, device_info, sw, SWITCHES[sw][0], SWITCHES[sw][1])
            for sw in SWITCHES
        ]
    )


class PhoenixEvSwitch(SwitchEntity):
    """Representation of Switch Sensor."""

    _attr_has_entity_name = True

    def __init__(self, hub_name, hub, device_info, switch_key, name, icon):
        """Initialize the sensor."""
        self._attr_unique_id = f"{hub_name}_switch_{switch_key}"
        self._attr_name = name
        self._attr_device_info = device_info
        self._attr_icon = icon
        self._hub = hub
        self._attr_is_on = False
        self._attr_available = True

    @property
    def is_on(self):
        """Return is_on status."""
        return self._attr_is_on

    async def async_turn_on(self):
        """Turn On method."""
        _LOGGER.debug(
            "Sending ON request to SWITCH device %s", self.name
        )
        if not self._hub.ensure_connected():
            _LOGGER.error("Unable to turn on %s because charger is disconnected", self.name)
            return
        response = self._hub.write_coil(unit=255, address=400, value=True)
        if response is None or response.isError():
            _LOGGER.error("Write coil failed while turning on %s", self.name)
            return
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn Off method."""
        _LOGGER.debug(
            "Sending OFF request to SWITCH device %s",  self.name
        )
        if not self._hub.ensure_connected():
            _LOGGER.error("Unable to turn off %s because charger is disconnected", self.name)
            return
        response = self._hub.write_coil(unit=255, address=400, value=False)
        if response is None or response.isError():
            _LOGGER.error("Write coil failed while turning off %s", self.name)
            return
        self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """polling needed."""
        return True

    @property
    def available(self):
        """Return availability."""
        _LOGGER.debug("Device %s - availability: %s", self.name, self._attr_available)
        return self._attr_available

    async def async_update(self):
        _LOGGER.debug("REFRESHING SWITCH via async_update %s", self.name)
        self._attr_available = False
        if self._hub.is_connected() or self._hub.ensure_connected():
            self._attr_available = True
            chargestate_data = self._hub.read_coils(unit=255, address=400, count=1)
            if chargestate_data is None or chargestate_data.isError():
                _LOGGER.warning("Failed reading switch state for %s", self.name)
                self._attr_available = False
                return False
            charging = bool(chargestate_data.bits[0]) if getattr(chargestate_data, "bits", None) else False
            if charging:
                _LOGGER.debug("Charging by Switch %s", self.name)

            self._attr_is_on = charging
            _LOGGER.debug(self._attr_is_on)
            return self._attr_is_on

        _LOGGER.debug("Hub not connected - SWITCH %s - %s", self.name, self)
        self._attr_available = False
        return False
