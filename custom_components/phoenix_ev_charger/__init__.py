"""The PEVC Modbus Integration."""
import asyncio
import logging
import threading
from datetime import timedelta
from typing import Optional
from .const import DATA_UPDATED
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_HOST, CONF_NAME, CONF_PORT,
                                 CONF_SCAN_INTERVAL)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
)
from homeassistant.helpers.entity import Entity
from pymodbus import __version__ as PYMODBUS_VERSION
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException


class BinaryPayloadDecoder:
    """Minimal register decoder used by this integration."""

    def __init__(self, payload: bytes):
        self._payload = payload
        self._offset = 0

    @classmethod
    def fromRegisters(cls, registers, byteorder="big"):
        payload = bytearray()
        for reg in registers:
            payload.extend(int(reg).to_bytes(2, byteorder=byteorder, signed=False))
        return cls(bytes(payload))

    def decode_16bit_uint(self):
        value = int.from_bytes(self._payload[self._offset:self._offset + 2], byteorder="big", signed=False)
        self._offset += 2
        return value

    def decode_string(self, size):
        data = self._payload[self._offset:self._offset + size]
        self._offset += size
        return data

    def skip_bytes(self, count):
        self._offset += count

from .const import (DEFAULT_NAME, DEFAULT_SCAN_INTERVAL, DEVICE_STATUSSES,
                    DOMAIN, CONF_DEVICE_MODEL, DEFAULT_DEVICE_MODEL,
                    DIGITAL_OUT_FUNCTIONS, DIGITAL_IN_FUNCTIONS, DIGITAL_STATUS,
                    )

_LOGGER = logging.getLogger(__name__)


PEVC_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Required(CONF_DEVICE_MODEL, default=DEFAULT_DEVICE_MODEL): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: PEVC_MODBUS_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["sensor", "binary_sensor", "switch", "number"]


async def async_setup(hass, config):
    """Set up the PEVC modbus component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a PEVC mobus."""

    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    model = entry.data[CONF_DEVICE_MODEL]

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = PEVCModbusHub(
        hass, name, host, port, scan_interval
    )
    """Register the hub."""
    hass.data[DOMAIN][name] = {"hub": hub}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload PEVC mobus entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(
                    entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    hass.data[DOMAIN].pop(entry.data["name"])
    return True


class PEVCModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(
            self,
            hass,
            name,
            host,
            port,
            scan_interval,
    ):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusTcpClient(host=host, port=port, timeout=5)
        self._lock = threading.Lock()
        self._name = name
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_interval_method = None
        self._sensors = []
        self._binary_sensors = []
        self._switches = []
        self.data = {}

    @callback
    def async_add_pevc_sensor(self, update_callback):
        """Listen for data updates."""
        # This is the first sensor, set up interval.
        if not self._sensors:
            self.connect()
            self._unsub_interval_method = async_track_time_interval(
                self._hass, self.async_refresh_modbus_data, self._scan_interval
            )

        self._sensors.append(update_callback)

    @callback
    def async_remove_pevc_sensor(self, update_callback):
        """Remove data update."""
        self._sensors.remove(update_callback)

        if not self._sensors:
            """stop the interval timer upon removal of last sensor"""
            self._unsub_interval_method()
            self._unsub_interval_method = None
            self.close()

    @callback
    def async_add_pevc_binary_sensor(self, update_callback):
        """Listen for data updates."""
        # This is the first sensor, set up interval.
        if not self._binary_sensors:
            self.connect()
            self._unsub_interval_method = async_track_time_interval(
                self._hass, self.async_refresh_modbus_data, self._scan_interval
            )

        self._binary_sensors.append(update_callback)

    @callback
    def async_remove_pevc_binary_sensor(self, update_callback):
        """Remove data update."""
        self._binary_sensors.remove(update_callback)

        if not self._binary_sensors:
            """stop the interval timer upon removal of last sensor"""
            self._unsub_interval_method()
            self._unsub_interval_method = None
            self.close()

    async def async_refresh_modbus_data(self, _now: Optional[int] = None) -> None:
        """Time to update."""
        if not self._sensors:
            if not self._binary_sensors:
                return

        update_result = self.read_modbus_data()

        if update_result:
            for update_callback in self._sensors:
                update_callback()
            for update_callback in self._binary_sensors:
                update_callback()


    @property
    def name(self):
        """Return the name of this hub."""
        return self._name

    def close(self):
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def is_connected(self) -> bool:
        """Return connection state across pymodbus versions."""
        connected = getattr(self._client, "connected", None)
        if isinstance(connected, bool):
            return connected

        is_socket_open = getattr(self._client, "is_socket_open", None)
        if callable(is_socket_open):
            return bool(is_socket_open())

        return False

    def connect(self):
        """Connect client."""
        with self._lock:
            self._client.connect()

    def ensure_connected(self) -> bool:
        """Ensure a modbus connection exists."""
        if self.is_connected():
            return True
        self.connect()
        return self.is_connected()

    def _modbus_call(self, method_name, address, count=None, unit=None, values=None, value=None):
        """Call pymodbus 3.13.1 methods using keyword-only params where required."""
        method = getattr(self._client, method_name)

        args = [address]

        call_kwargs = {}
        if count is not None:
            call_kwargs["count"] = count

        if values is not None:
            call_kwargs["values"] = values

        if value is not None:
            call_kwargs["value"] = value

        if unit is not None:
            call_kwargs["device_id"] = unit

        return method(*args, **call_kwargs)

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        with self._lock:
            return self._modbus_call("read_holding_registers", address=address, count=count, unit=unit)

    def read_input_registers(self, unit, address, count):
        """Read input registers."""
        with self._lock:
            return self._modbus_call("read_input_registers", address=address, count=count, unit=unit)

    def read_discrete_inputs(self, unit, address, count):
        """Read discrete registers."""
        with self._lock:
            return self._modbus_call("read_discrete_inputs", address=address, count=count, unit=unit)

    def read_coils(self, unit, address, count):
        """Read coil registers."""
        with self._lock:
            return self._modbus_call("read_coils", address=address, count=count, unit=unit)

    def write_coil(self, unit, address, value):
        """Write a single coil."""
        with self._lock:
            return self._modbus_call("write_coil", address=address, value=value, unit=unit)

    def write_registers(self, unit, address, values):
        """Write one or more holding registers."""
        with self._lock:
            return self._modbus_call("write_registers", address=address, values=values, unit=unit)

    def calculate_value(self, value, sf):
        return value * 10 ** sf

    def swap_ascii(self, istr, length):
        ostr = ''
        for i in range(int(length / 2)):
            ostr = ostr + istr[i * 2 + 1]
            ostr = ostr + istr[i * 2]
        return ostr

    def read_modbus_data(self):
        if not self.ensure_connected():
            _LOGGER.error("Unable to connect to charger at %s", self._name)
            return False

        return (
            self.read_modbus_holding_data()
            and self.read_modbus_input_data()
            and self.read_modbus_coil_data()
            and self.read_modbus_discrete_data()
        )

    def read_modbus_holding_data(self):
        connected = False
        try:
            holdingreg_data = self.read_holding_registers(unit=255, address=300, count=32)
            connected = True
        except ConnectionException as ex:
            _LOGGER.error('Reading holding data failed! Inverter is unreachable.')
            connected = False

        if connected:
            if not holdingreg_data.isError():
                decoder = BinaryPayloadDecoder.fromRegisters(
                    holdingreg_data.registers, byteorder="big"
                )
                #read value for actual charging current is in 100mA units
                actual_charging_current = decoder.decode_16bit_uint()/10
                self.data["chargecurrentsetting"] = actual_charging_current
                macstring = ''
                for by in range(3):
                    addr = '{0:04x}'.format(decoder.decode_16bit_uint())
                    macstring = macstring + addr[2:4] + ':' + addr[0:2] + ':'
                self.data["macaddress"] = str(macstring)[:-1]

                sn = decoder.decode_string(12).decode('ascii')
                self.data["serialnr"] = str(self.swap_ascii(sn, 12))

                dev_name = decoder.decode_string(10).decode('ascii')
                self.data["devicename"] = str(self.swap_ascii(dev_name, 10))

                # ip address
                decoder.skip_bytes(4 * 2)
                # subnet mask
                decoder.skip_bytes(4 * 2)
                # gateway
                decoder.skip_bytes(4 * 2)

                dig_out = decoder.decode_16bit_uint()
                if dig_out in DIGITAL_OUT_FUNCTIONS:
                    self.data["digouter"] = str( DIGITAL_OUT_FUNCTIONS[dig_out])
                else:
                    self.data["digouter"] = str(hex(dig_out))

                dig_out = decoder.decode_16bit_uint()
                if dig_out in DIGITAL_OUT_FUNCTIONS:
                    self.data["digoutlr"] = str( DIGITAL_OUT_FUNCTIONS[dig_out])
                else:
                    self.data["digoutlr"] = str(hex(dig_out))

                dig_out = decoder.decode_16bit_uint()
                if dig_out in DIGITAL_OUT_FUNCTIONS:
                    self.data["digoutvr"] = str( DIGITAL_OUT_FUNCTIONS[dig_out])
                else:
                    self.data["digoutvr"] = str(hex(dig_out))

                dig_out = decoder.decode_16bit_uint()
                if dig_out in DIGITAL_OUT_FUNCTIONS:
                    self.data["digoutcr"] = str( DIGITAL_OUT_FUNCTIONS[dig_out])
                else:
                    self.data["digoutcr"] = str(hex(dig_out))

                # read second block of holding registers
                connected = False
                try:
                    holdingreg_data = self.read_holding_registers(unit=255, address=520, count=9)
                    connected = True
                except ConnectionException as ex:
                    _LOGGER.error('Reading holding data failed! Inverter is unreachable.')
                    connected = False

                if connected:
                    if not holdingreg_data.isError():
                        decoder = BinaryPayloadDecoder.fromRegisters(
                            holdingreg_data.registers, byteorder="big"
                        )

                        dig_in = decoder.decode_16bit_uint()
                        if dig_in in DIGITAL_IN_FUNCTIONS:
                            self.data["diginld"] = str(DIGITAL_IN_FUNCTIONS[dig_in])
                        else:
                            self.data["diginld"] = str(hex(dig_in))

                        dig_in = decoder.decode_16bit_uint()
                        if dig_in in DIGITAL_IN_FUNCTIONS:
                            self.data["diginen"] = str(DIGITAL_IN_FUNCTIONS[dig_in])
                        else:
                            self.data["diginen"] = str(hex(dig_in))

                        dig_in = decoder.decode_16bit_uint()
                        if dig_in in DIGITAL_IN_FUNCTIONS:
                            self.data["diginml"] = str(DIGITAL_IN_FUNCTIONS[dig_in])
                        else:
                            self.data["diginml"] = str(hex(dig_in))

                        dig_in = decoder.decode_16bit_uint()
                        if dig_in in DIGITAL_IN_FUNCTIONS:
                            self.data["diginxr"] = str(DIGITAL_IN_FUNCTIONS[dig_in])
                        else:
                            self.data["diginxr"] = str(hex(dig_in))

                        dig_in = decoder.decode_16bit_uint()
                        if dig_in in DIGITAL_IN_FUNCTIONS:
                            self.data["diginin"] = str(DIGITAL_IN_FUNCTIONS[dig_in])
                        else:
                            self.data["diginin"] = str(hex(dig_in))

                        # Ansteuerungszeit Verriegelung
                        dummy = decoder.decode_16bit_uint()

                        # Ansteuerungszeit Entriegelung
                        dummy = decoder.decode_16bit_uint()

                        # Delay Verriegelungs-Wiederholung
                        dummy = decoder.decode_16bit_uint()

                        #max charging current limit value read is in 100mA Units
                        chargecurrentlimit = decoder.decode_16bit_uint()/10
                        self.data["maxchargecurrentlimit"] = chargecurrentlimit



        else:
            mpvmode = '0'
            self.data["devstate"] = mpvmode

            if mpvmode in DEVICE_STATUSSES:
                self.data["devstate"] = DEVICE_STATUSSES[mpvmode]
            else:
                self.data["devstate"] = "Unknown"
        return connected

    def read_modbus_input_data(self):
        connected = False
        try:
            inputreg_data = self.read_input_registers(unit=255, address=100, count=36)
            connected = True
        except ConnectionException as ex:
            _LOGGER.error('Reading input registers failed! Inverter is unreachable.')
            connected = False

        if connected:
            if not inputreg_data.isError():
                decoder = BinaryPayloadDecoder.fromRegisters(
                    inputreg_data.registers, byteorder="big"
                )
                devstatus = decoder.decode_string(1).decode('ascii')
                devstatus = decoder.decode_string(1).decode('ascii')
                self.data["devstate"] = str(devstatus)

                if devstatus in DEVICE_STATUSSES:
                    self.data["devstate"] = DEVICE_STATUSSES[devstatus]

                max_cable_current = decoder.decode_16bit_uint()
                self.data["cablecapability"] = str(max_cable_current)


                charging_time_low = decoder.decode_16bit_uint()
                charging_time_high = decoder.decode_16bit_uint()
                minutes, secs = divmod(( charging_time_high << 16 ) + charging_time_low, 60)
                hours, minutes = divmod(minutes, 60)
                self.data["chargingduration"] = str("%d:%02d:%02d" % (hours, minutes, secs))

                dip_switches = decoder.decode_16bit_uint()

                fw_version = decoder.decode_string(4).decode('ascii')
                self.data["fwvers"] = str(self.swap_ascii(fw_version, 4))

                #error codes
                error_code = decoder.decode_16bit_uint()

                #voltage sensors
                for phase in range(3):
                    voltage_low = decoder.decode_16bit_uint()
                    voltage_high = decoder.decode_16bit_uint()
                    voltage = ( voltage_high << 16 ) + voltage_low
                    self.data["voltage"+str(phase)]=str(voltage)

                #current sensors
                for phase in range(3):
                    current_low = decoder.decode_16bit_uint()
                    current_high = decoder.decode_16bit_uint()
                    current = ( current_high << 16 ) + current_low
                    self.data["current"+str(phase)]=str(current)

                decoder.skip_bytes(4*4)

                total_charged_energy_low = decoder.decode_16bit_uint()
                total_charged_energy_high = decoder.decode_16bit_uint()
                total_charged_energy = ( total_charged_energy_high << 16 ) + total_charged_energy_low
                self.data["totalchargedenergy"] = str(total_charged_energy)

                decoder.skip_bytes(1*4)

                charging_energy_low = decoder.decode_16bit_uint()
                charging_energy_high = decoder.decode_16bit_uint()
                charging_energy = ( charging_energy_high << 16 ) + charging_energy_low
                self.data["chargingenergy"] = str(charging_energy)

                grid_frequency_low = decoder.decode_16bit_uint()
                grid_frequency_high = decoder.decode_16bit_uint()
                grid_frequency = ( grid_frequency_high << 16 ) + grid_frequency_low
                self.data["gridfrequency"] = str(grid_frequency)

                return True
            else:
                _LOGGER.warning('Reading input data FAILED')
                return True
        else:
            mpvmode = '0'
            self.data["devstate"] = str(mpvmode)

            if str(mpvmode) in DEVICE_STATUSSES:
                self.data["devstate"] = DEVICE_STATUSSES[str(mpvmode)]

            return True

    def read_modbus_coil_data(self):
        return True

    def read_modbus_discrete_data(self):
        connected = False
        try:
            discretereg_data = self.read_discrete_inputs(unit=255, address=200, count=9)
            connected = True
        except ConnectionException as ex:
            _LOGGER.error('Reading discrete registers failed! Inverter is unreachable.')
            connected = False

        if connected:
            if not discretereg_data.isError():
                bits = list(getattr(discretereg_data, "bits", []) or [])

                def _bit(index):
                    return bool(bits[index]) if len(bits) > index else False

                self.data["statdiginld"] = str(DIGITAL_STATUS[_bit(0)])
                self.data["statdiginen"] = str(DIGITAL_STATUS[_bit(1)])
                self.data["statdiginml"] = str(DIGITAL_STATUS[_bit(2)])
                self.data["statdiginxr"] = str(DIGITAL_STATUS[_bit(3)])
                self.data["statdiginin"] = str(DIGITAL_STATUS[_bit(8)])
                self.data["statdigouter"] = str(DIGITAL_STATUS[_bit(4)])
                self.data["statdigoutlr"] = str(DIGITAL_STATUS[_bit(5)])
                self.data["statdigoutvr"] = str(DIGITAL_STATUS[_bit(6)])
                self.data["statdigoutcr"] = str(DIGITAL_STATUS[_bit(7)])

                return True
            else:
                _LOGGER.warning('Reading discrete data FAILED')
                return False
        else:
            mpvmode = '0'
            self.data["devstate"] = mpvmode

            if mpvmode in DEVICE_STATUSSES:
                self.data["devstate"] = DEVICE_STATUSSES[mpvmode]

            return True

class PhoenixEvDevice(Entity):
    """PhoenixEvDevice Device Common Object."""

    def __init__(self):
        """Log PhoenixEvDevice initialization."""
        _LOGGER.error("PhoenixEvDevice %s", )

    async def async_added_to_hass(self):
        """Add Callbacks for update."""
        device_id = str(self._pre) + str(self._name)
        _LOGGER.debug(
            "Callback added for %s, %s",
            DATA_UPDATED.format(device_id),
            DATA_UPDATED.format(self._name),
        )
        async_dispatcher_connect(self.hass, DATA_UPDATED.format(device_id), self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(True)