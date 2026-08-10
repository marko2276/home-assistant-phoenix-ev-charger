
# home-assistant-phoenix-ev-charger

Home Assistant custom component for communicating with Phoenix Contact EV Charge Controllers via ModBus TCP.
These Charge controllers for electric vehicles are found in some wallboxes like Wallbe Pro EV.

Features:

* Installation through Config Flow UI
* Configurable polling interval
* No password protected acces (works via ModBus TCP)
* Support for EV-CC-AC1-M3-xx controllers

Configuration

* Add https://github.com/marko2276/home-assistant-phoenix-ev-charger as custom repository to HACS
* Add Phoenix EV Charger to HACS integrations
* Go to the integrations page in your configuration and click on new integration -> Phoenix EV Charger

Comments and Remarks are always welcome!