![alt text](/img/logo.png "Bloom logo")

**Automated irrigation system**  
**Exercise project of fall/winter semester 2021 (5th study plan semester)**

*Berlin University of Applied Sciences and Technology*  
*Project advisor: Dipl.-Ing. Erhard Buchberger*  
*Team members: Albert Kaminski, Dominik Domonell, Jelena Mirceta, Sahiram Ravikumar, Simon Aschenbrenner*

We aimed to design an easy to use but still flexible and scalable irrigation system while learning about technologies and processes that were new to us.  
Over the course of 17 weeks we defined goals through technology research and customer analysis, developed a system architecture, build functioning hard- and software prototypes and designed UX, UI and CI.

Please refer to our (german) [presentation](/doc/bloom_presentation.pdf) for an overview of the project or just keep on reading.

>This repository only contains source code and documentation regarding my own work, which centered around micro controller programming. The complete repository is private at the time of writing, but may be found [here](https://github.com/Alfonsomckenzy/Bloom) eventually.

------------------------

## Overview

The area to be watered gets divided into dedicated watering zones that each are outfitted with a wireless soil moisture sensor and a (porous) hose. This allows for different use cases ranging from balconies, indoor and outdoor gardens, greenhouses to farms.  
For our prototype we settled on a balcony with four zones, as well as a water tank and pump. The latter could easily be substituted with a magnetic valve connected to a mains water supply, however.

On a high level our system consists of a server backend (MERN stack), an Android app frontend plus the irrigation hardware: Wireless soil moisture sensors and hubs ("Bloom Boxes") that manage these sensors through [LoRa](https://en.wikipedia.org/wiki/LoRa). They also control the connected pump and valves that are attached to the hoses as well as communicate with the backend.

![alt text](/img/high_level_system_architecture.png "Illustration of the high level system architecture")

The software inside a Bloom Box and a Bloom Sensor is designed to be as simple, open, reliable, resilient and efficient as possible. The business logic (e.g. an automatic pouring decision or a battery warning) is left with the backend. This encapsulation helps with compatibility to the other components, expendability by future features, adaptability to other systems and security.

------------------------

## Hardware

For the hub (Bloom Box) we settled on the [Heltec WIFI LoRa 32 (V2)](https://heltec.org/project/wifi-lora-32/) development board (based on Espressif Systems' ESP32) with integrated LoRa radio (Semtech SX1276/SX1278) and display (128x64px SSD1306 OLED) running [MicroPython](https://github.com/micropython/micropython) v1.17. It also features two buttons, one of which always reboots the system (Through persistence of configuration data a hub can reboot quite fast).

![alt text](/img/hub_ext.png "Bloom Box")

The sensor is built around an [Adafruit Feather 32u4 RFM95 (868/915 MHz variant)](https://www.adafruit.com/product/3078) development board with a Semtech SX1276 LoRa radio and uses a capacitive soil moisture sensor, for better corrosion resistance than conductive sensors. Only version v2.0 of this unbranded, but popular sensor with the [TLC555](https://www.ti.com/lit/ds/symlink/tlc555.pdf) timing chip is compatible with the 3V logic on the Adafruit board. The 3.7V 2Ah LiPo battery is chargeable trough the Adafruit’s mini USB port and charging circuit.

![alt text](/img/sensor_ext.png "Bloom Sensor")

A user controls their irrigation system through an Android app. A minimal setup consists of a water source, one hose, one Bloom Box and one Bloom Sensor. With our prototype hardware the hub still needs to be connected to a mains power supply to drive the 12V magnetic valves, but this could be substituted with solar power in the future. To warn the user in case the water tank runs empty, a float switch is integrated at the bottom and connected to the hub's micro controller.  
The sensors are completely wireless. In a production environment the integrated battery should last at least a whole irrigation period (9 months) on a single charge by only measuring the moisture level once every hour and sleeping the rest of the time.

------------------------

## Setup and Use

Minimal user data is required during setup. After setting up their Bloom Box with their water source (e.g. pump and water tank), the user registers it through the app on the backend (linking themselves to their Bloom Box). They enter their email address to setup an account and a nine digit `user_key` displayed on the hub‘s display. Each Bloom Box obtains this code from the backend through our custom API (please refer to [`backend.py`](/hub/backend.py) and [`constants.py`](/hub/constants.py) for the API calls used by the hub).  
To authenticate itself with the backend each Bloom Box gets assigned an unique `hub_id` and a random (and perhaps in the future changeable) `factory_key` during manufacturing (like an username and password).  
The [setup activity diagram](/doc/setup_activity_diagram.png) explains this process in further detail.

Afterwards the user can setup watering zones through the app and by pairing a sensor to their Bloom Box. For details on this process please refer to this [specification](/doc/lora_address_scheme_and_setup.txt), as well as the [LoRa activity diagram](/doc/lora_activity_diagram.png), which also illustrates the devices' radio communication during normal operation.

The user can then see the zone's moisture level (as well as the sensor's battery level) and either water the zone manually or automatically when a specific threshold is reached.

Some screenshots of our app can be seen in the (german) [presentation](/doc/bloom_presentation.pdf) of our project. Below is a picture of our final prototype / test setup.

![alt text](/img/prototype.png "Bloom prototype")

------------------------

## Bloom Box (Hub)

The Bloom Boxes' software is written in Python and can be found in the [`hub`](/hub/) directory. It is complete (except for WPS, see blockquote below) and working. Most functions feature dedicated commentary, but some docstrings are still missing at the moment.

Hubs will continuously listen for sensor measurement data, pass it on to the backend and ask the server for watering instructions. The following features of a Bloom Box are implemented:

- Controls a pump and as many magnetic valves as configured in [`constants.py`](/hub/constants.py)
- Senses an empty water tank, stops watering and messages the backend 
- Displays messages directed at the user (e.g. a key for connecting with the user's account)
- Has means of user interaction through two buttons (although one will always reboot the system)
- Can be reset to factory conditions on the device itself or via the backend
- Will automatically connect to the user's WiFi

> Currently there is no possibility for a WiFi setup by the user, as WPS is not yet supported by MicroPython's ESP32 port and a customized firmware with modified `modnetwork.c` and `network_wlan.c` files adapted from [this pull request](https://github.com/micropython/micropython/pull/4464) did not work as expected. Other solutions to setup the Hub's WiFi (e.g. via the user's phone) were not tried.  
The present workaround can be found in lines 200 and 201 in [`hub.py`](/hub/hub.py): A predefined SSID and password get written to the NVS during setup, so they are always available, even after a reset. **Please change these two strings to your own SSID and password.**

- Sets its system time to UTC using `ntptime`
- Authenticates and registers itself with the backend, asks which zones it should water and continuously updates its status on the server
- Sets its LoRa address depending on availability (up to 15 Bloom Boxes on one LoRa channel, see [this specification](/doc/lora_address_scheme_and_setup.txt) and [activity diagram](/doc/lora_activity_diagram.png) for further details)
- Manages up to 15 Bloom Sensors via LoRa
- Continuously listens for a paired sensor's moisture and battery measurements and passes them to the backend
- Continuously listens for sensor pairing request and informs the backend in case a pairing was successful
- Automatically unpairs silent sensors and deletes them on the backend
- Compares its list of paired sensors with the backend, so sensors may be unpaired remotely as well
- Sends deactivation orders to unpaired or faulty sensors

![alt text](/img/hub_int.png "Bloom Box")

### Source code structure

After (re)boot the MicroPyton firmware calls [`main.py`](/hub/main.py). This will initialize the Bloom Box through the scripts in [`hub.py`](/hub/hub.py) and enter the main loop afterwards.  
Though defensive programming was practiced, various (manual and automatic) reboot/reset routines are implemented in [`reset.py`](/hub/reset.py) and called in case an error occurs. A minimum amount of user interaction should be required.

The MicroPython LoRa radio driver in [`radio.py`](/hub/radio.py) is based on [Martyn Wheeler's incredibly helpful port](https://github.com/martynwheeler/u-lora) of [raspi-lora](https://pypi.org/project/raspi-lora/) for the RFM95 LoRa radio module (which is based on the SX1276) and although written for this system, this driver may easily be adapted or integrated into other systems due to its universality and flexibility.  
It is written for compatibility with the popular [RadioHead packet radio library](http://www.airspayce.com/mikem/arduino/RadioHead/index.html) (that the sensor uses as well) and handles the Layer 3 routing and Layer 4 transport aspects of the LoRa communication according to RadioHead‘s reliable datagram implementation. Unacknowledged or encrypted datagrams can be used as well, but the latter one is untested.  
[`sensors.py`](/hub/sensors.py) on the other hand defines Bloom-specific presentation and application level aspects of the LoRa communication.

The backend calls operate on the same encapsulation principle: The HTTPS request handler (adapted from [urequests.py by Paul Sokolovsky](https://github.com/micropython/micropython-lib/blob/master/python-ecosys/urequests)) is universal and gets called by the functions in [`backend.py`](/hub/backend.py) that prepare the payloads before transmit. **Please replace the files `key` and `cert` with your own SSL keys.**

The water control logic can be found in [`watering.py`](/hub/watering.py), persistence through the ESP32's NVS is handled in [`nvs.py`](/hub/nvs.py) and all configuration data is stored in [`constants.py`](/hub/constants.py) (**Please enter your server's IP address there).**
`logo` contains a representation of the Bloom logo suitable for the buffer used by the display driver in [`ssd1306.py`](/hub/ssd1306.py). The driver is virtually identical to [this one](https://github.com/micropython/micropython/blob/master/drivers/display/ssd1306.py) in the MicroPython repository.

Below is a heavily simplified diagram of the hub's source code structure, that omits any cross connections.
```
main.py
│
├─ watering.py
│  └─ backend.py
│     └─ http.py
│        ├─ cert
│        └─ key
│
├─ sensors.py
│     └─ radio.py
│
├─ hub.py
│  ├─ nvs.py
│  ├─ reset.py
│  └─ ssd1306.py
│     └─ logo
│
└─ constants.py
```

------------------------

## Bloom Sensor

The Bloom Sensors' software is written as an Arduino Sketch in C++ and can be found here: [`sensor/sensor.ino`](/sensor/sensor.ino)  
While fully functional the code is not yet matured and particularly misses solutions for better energy efficiency (e.g. deep sleep).  
It utilizes the [RadioHead packet radio library](http://www.airspayce.com/mikem/arduino/RadioHead/index.html) (using `RHReliableDatagram` and the `RH_RF95` driver). All configuration data is defined on top of the script.  
Sensors can be reset by power cycling and will automatically try to pair themselves to a hub after being turned on. Please refer to [this specification](/doc/lora_address_scheme_and_setup.txt) and [activity diagram](/doc/lora_activity_diagram.png) for further information regarding the setup using a lean custom protocol.

![alt text](/img/sensor_int.png "Bloom Sensor")

------------------------

## Miscellaneous

- [`doc`](/doc/) has all the mentioned detailed specifications as well as an [installation guide](/doc/hub_setup.txt) to setup an ESP32 as a Bloom Box. It contains useful information for compiling the MicroPython firmware and flashing it on to the ESP32, as well as using [Ampy](https://learn.adafruit.com/micropython-basics-load-files-and-run-code/overview) and [REPL](https://docs.micropython.org/en/latest/reference/repl.html).
- [`img`](/img/) contains the images used in this README.
- [`misc`](/misc/) has a [script](/misc/hub_display_image_conversion.py) to convert a monochromatic image (like [`logo.png`](/misc/logo.png)) for the hub's display.

------------------------

###### By Simon Aschenbrenner, 6/1/22