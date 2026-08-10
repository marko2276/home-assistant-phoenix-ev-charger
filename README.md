![GitHub all releases](https://img.shields.io/github/downloads/abrlox/home-assistant-phoenix-ev-charger/total) ![License](https://img.shields.io/github/license/abrlox/home-assistant-phoenix-ev-charger) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

# home-assistant-phoenix-ev-charger

Home Assistant Integration for communicating with Phoenix Contact EV Charge Controllers found in Wallbe Pro EV wallboxes. Communication is done via Modbus TCP, so no username/password is needed.

Currently only Phoenix Contact EV-CC-AC1-M3-xx charge controllers (Wallbe Pro) are tested (works for me).


![Wallbe Pro](/images/wallbe-pro_plus.png)

![EV-CC-AC1-M3](/images/pro.jpg)


Note: This is a fork from a [project with the same name](https://github.com/abrlox/home-assistant-phoenix-ev-charger)  by [@abrolox](https://github.com/abrlox) and is partialy rewritten to support some additonl monitored parameters, configurable setting for maximum charging current, switch to enable or disable charging and various other additions. The changes also include updated usege of pymodbus library (3.13.1) that is included in most recent HA docker container and includes some non-backward compatibility changes (due to which original code from abrolox is no longer working).

## Installation
To install via HACS, please add https://github.com/marko2276/home-assistant-phoenix-ev-charger as custom repository to HACS.
Now you can add the integration to HACS.

After Rebooting your system, you can search for "Phoenix EV Charger" on the HomeAssistant integration page and install it.

After reboot of Home-Assistant, this integration can be configured through the integration setup UI

