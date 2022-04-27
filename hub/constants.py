# BLOOM Hub
# Constants and configuration
# Author: Simon Aschenbrenner 

from micropython import const


# SOFTWARE
# Backend communication
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 443
SSL_KEY = "key"
SSL_CERT = "cert"
ENDPOINT_REGISTER_HUB = ("POST", "hubRegistration/postHubRegistration")
ENDPOINT_GET_HUB = ("GET", "hub/getHub")
ENDPOINT_UPDATE_HUB = ("PUT", "hub/updateHub")
ENDPOINT_GET_ALL_ZONES = ("GET", "zone/getAllZonesByHubId")
ENDPOINT_GET_ALL_PENDING_ZONES = ("GET", "zone/getAllPendingZones")
ENDPOINT_UPDATE_ZONE = ("PUT", "zone/updateZone")
ENDPOINT_ADD_SENSOR = ("POST", "sensor/addSensor")
ENDPOINT_GET_ALL_SENSORS = ("GET", "sensor/getAllSensorsByHubId")
ENDPOINT_UPDATE_SENSOR = ("PUT", "sensor/updateSensor")
ENDPOINT_DELETE_SENSOR = ("DELETE", "sensor/")

# LoRa
LORA_PREAMBLE = b"BLOOM"
LORA_MAX_PAIRED_SENSORS = const(15)
LORA_BROADCAST_ADDRESS = const(255)
LORA_FREQUENCY = const(868)
LORA_POWER = const(23)
LORA_RSSI_PAIRING_THRESHOLD = const(-50)
LORA_FLAG_MEASUREMENT = const(0b0000)
LORA_FLAG_PAIRING_REQ = const(0b0001)
LORA_FLAG_PAIRING_ACK = const(0b0010)
LORA_FLAG_ADDRESS_AVL = const(0b0100)
LORA_FLAG_SHUTDOWN_ORDER = const(0b1000)
LORA_BIT_MASK = const(0b00001111)
LORA_DATA_CACHE_SIZE = const(10)

# NVS
NVS_NAMESPACE = "configuration"
NVS_MAX_BUFFER_SIZE = const(32)
NVS_KEY_WLAN_ESSID = "wlan_essid"
NVS_KEY_WLAN_PASSWORD = "wlan_password"
NVS_KEY_LORA_HUB_ID = "lora_hub_id"
NVS_KEY_PAIRED_SENSOR_PREFIX = "lora_sens_id_"
NVS_KEY_REBOOT_COUNTER = "reboot_counter"
NVS_KEY_LAST_REBOOT_TIMESTAMP = "last_reboot"

# Times
BACKEND_CALL_DELAY = const(2000)        #  2 seconds
MAX_FAILED_REQUESTS = const(3)          #  3 times
EMPTY_DELAY = const(3)                  #  3 seconds
LORA_MAX_SILENT_TIME = const(7260)      #  2 hours 1 minute (2 transmits may be missed)

WLAN_TIMEOUT = const(30000)             # 30 seconds
USER_KEY_TIMEOUT = const(60000)         # 60 seconds
USER_KEY_DELAY = const(1000)            #  1 second

REBOOT_TIMEOUT = const(30000)           # 30 seconds
MAX_REBOOT_ATTEMPTS = const(3)          #  3 times
REBOOT_COUNTER_RESET_TIME = const(1800) # 30 minutes
BUTTON_DEBOUNCE_TIME = const(20)        # 20 milliseconds

# Display
# A = RST button, B = PRG button
BLOOM_LOGO = "logo"

MESSAGE_USER_KEY_LOOP = "Hi Bloomer!\nGib diesen Code\nin der Bloom App\nein: {}\n\nB: Abbrechen"
MESSAGE_USER_KEY_PAUSE = "Registrierung\nabbrechen und\nBox neustarten?\n\nA: Ja\nB: Nein"

MESSAGE_WATERING_TANK_EMPTY = "\n\nWassertank leer!\nBitte auffuellen!"
MESSAGE_WATERING_TANK_FULL = "\n\nWassertank ist\nwieder gefuellt,\nDanke!"
MESSAGE_WATERING_ZONES = "\n\nBloom bewaessert\ngerade Zone(n)\n{}"
MESSAGE_WATERING_NONE = "\n\nBloom bewaessert\ngerade nichts"

MESSAGE_PAIRING_IN_PROGRESS = "\nVerbinde Sensor {}\nmit Bloom Box"
MESSAGE_PAIRING_TOO_FAR = "\nBitte Sensor {}\nzum Verbinden\nnaeher an die\nBloom Box halten"
MESSAGE_PAIRING_ALREADY_PAIRED = "\nEin Sensor Nr. {}\nwurde schon mit\ndieser Bloom Box\nverbunden"
MESSAGE_PAIRING_FAIL = "\nSensor {}\nkonnte nicht\nverbunden werden"
MESSAGE_PAIRING_SUCCESS = "\nSensor {}\nerfolgreich mit\ndieser Bloom Box\nverbunden"

MESSAGE_RESET_LOOP = "{}\nA: Neustart\nB: {}\nNeustart in {}s"
MESSAGE_RESET_NONE = "Neustart\n"
MESSAGE_RESET_WLAN_CONFIG = "WLAN Konfig.\n   zuruecksetzen"
MESSAGE_RESET_LORA_CONFIG = "LoRa Konfig.\n   zuruecksetzen"
MESSAGE_RESET_FACTORY_CONFIG = "Alle Konfig.\n   zuruecksetzen"
MESSAGE_RESET_WLAN_DONE = "\nWLAN Konfigurat.\ngeloescht & auf\nWerkseinstellung\nzurueckgesetzt"
MESSAGE_RESET_LORA_DONE = "\nLoRa Konfigurat.\ngelöscht & auf\nWerkseinstellung\nzurueckgesetzt"
MESSAGE_RESET_FACTORY_DONE = "\nAlle Konfigurat.\ngeloescht & auf\nWerkseinstellung\nzurueckgesetzt"
MESSAGE_ERROR_WLAN = "Fehler bei der\nWLAN Verbindung"
MESSAGE_ERROR_TIME = "Fehler beim \nUhrzeitstellen"
MESSAGE_ERROR_REGISTRATION = "Fehler bei der\nRegistrierung"
MESSAGE_ERROR_LORA = "Fehler bei der\nLoRa-Einrichtung"
MESSAGE_ERROR_BACKEND = "Fehler mit dem\nServerbackend"

# MCU
# General
LED_PIN = const(25)
PRG_PIN = const(0)

# Display
SSD1306_SCL_PIN = const(15)
SSD1306_SDA_PIN = const(4)
SSD1306_RST_PIN = const(16)
SSD1306_FREQ = const(400000)

# LoRa Radio
LORA_SPI_MODE = const(1)
LORA_CS_PIN = const(18)
LORA_SCK_PIN = const(5)
LORA_MOSI_PIN = const(27)
LORA_MISO_PIN = const(19)
LORA_IRQ_PIN = const(26)
LORA_RST_PIN = const(14)
LORA_BAUDRATE = const(5000000)

# External devices (sensors and relays)
PUMP_PIN = const(13)    # J17
EMPTY_PIN = const(36)   # J04 and other lead to 3.3V
OUTLET0_PIN = const(17) # A17
OUTLET1_PIN = const(22) # A09
OUTLET2_PIN = const(23) # A11
OUTLET3_PIN = const(3)  # A05
OUTLET_PINS = [ OUTLET0_PIN, OUTLET1_PIN, OUTLET2_PIN, OUTLET3_PIN ]  # Outlets will be indexed according to their position in this array


# INDIVIDUAL HUB CONFIGURATION
HUB_ID = 1  # Must be unique for each hub
FACTORY_KEY = "0123456789"  # Should be unique for each hub
