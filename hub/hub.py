# BLOOM Hub
# Hub utilities and setup routines
# Author: Simon Aschenbrenner

from http import BackendError
from machine import Pin, SoftI2C
from network import WLAN, STA_IF
from ntptime import settime
from nvs import NVS
from radio import LoRa
import backend
import constants
import reset
import ssd1306
import time


class TimeoutError(Exception):
    pass

class LoRaAddressUnavailableError(Exception):
    pass


# UTILITIES

def has_user() -> bool:
    """
    :return: True if the backend has paired a user to this hub, False if not.
    :rtype: bool
    :raises BackendError: if any HTTP request fails
    """

    hub = backend.get_hub()
    try:
        user = hub["user"]
    except KeyError as e:
        raise BackendError("hub dictionary does not contain key {}".format(e))
    else:
        return user is not None  # The backend has paired a user to this hub


def bucket_is_empty() -> bool:
    """    
    :return: True if the bucket is empty, False if not.
    :rtype: bool
    """

    return not bool(empty.value())


def button_is_pressed() -> bool:
    """        
    :return: True if the button is pressed, False if not.
    :rtype: bool
    """

    return not bool(button.value())


def display_message(message=None):
    """
    Display any message string on the display or clear the display if function is called without a parameter.
    The string must feature a line break after no more than 16 characters (including white spaces).
    A maximum of 6 lines can be displayed.
    """

    if not display_block:
        display.fill(0)
        if message and isinstance(message, str):
            print("----------------\n" + message + "\n----------------")
            lines = message.split("\n")
            for index, content in enumerate(lines):
                display.text(content, 0, index*11, 1)
        display.show()


# SETUP ROUTINES

def setup():
    """
    Main routine to completely setup the hub after boot so it is able to enter the main loop afterwards.
    Exception safe, will automatically reboot or reset.ask() if any of the steps fail.
    """

    global button, configuration, display, display_block, empty, led, lora, outlets, outlets_mask, pump

    print("BEGIN SETUP")

    try:
        # Pin setup
        empty = Pin(constants.EMPTY_PIN, Pin.IN, Pin.PULL_DOWN)
        pump = Pin(constants.PUMP_PIN, Pin.OUT, value=0)
        outlets = []
        for pin in constants.OUTLET_PINS:
            outlets.append(Pin(pin, Pin.OUT, value=1))
        outlets_mask = [False] * len(outlets)
        button = Pin(constants.PRG_PIN, Pin.IN)
        led = Pin(constants.LED_PIN, Pin.OUT, value=0)
        Pin(constants.SSD1306_RST_PIN, Pin.OUT, value=1)

        # Display setup
        display_init()

        # Initial LoRa setup
        lora = LoRa()

        # NVS setup
        configuration = NVS()

        print("Hardware setup finished")

    except Exception as e:
        print("Hardware setup failed:", e)
        reset.reset(wlan=False, lora=False)  # Reboot

    if button_is_pressed():
        led.on()
        print("Manual factory reset")
        reset.reset(wlan=True, lora=True)  # Factory reset

    else:
        display.rotate(True)
        with open(constants.BLOOM_LOGO, "rb") as logo_file:
            logo_buffer = bytearray(1024)
            logo_file.readinto(logo_buffer)
            display.buffer = logo_buffer
        display.show()

        # WLAN Setup
        try:
            _wlan_connect()
        except Exception as e:
            print("WLAN setup failed: {}, asking for WLAN reset".format(e))
            reset.ask(constants.MESSAGE_ERROR_WLAN, wlan=True, lora=False)  # WLAN reset
        else:
            print("WLAN setup finished")

        # Set UTC
        try:
            settime()
        except Exception as e:  # May indicate no connection to the internet
            print("Time setting failed: {}, asking for WLAN reset".format(e))
            reset.ask(constants.MESSAGE_ERROR_TIME, wlan=True, lora=False)  # WLAN reset
        else:
            current_time = time.localtime()
            time_string = "{:4d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(current_time[0], current_time[1], current_time[2], current_time[3], current_time[4], current_time[5])
            print("Time set to", time_string)

        # Hub Registration
        try:
            _register()
        except Exception as e:
            print("Hub registration failed: {}, asking for factory reset".format(e))
            reset.ask(constants.MESSAGE_ERROR_REGISTRATION, wlan=True, lora=True)  # Factory reset
        else:
            print("Hub registration finished")

        # LoRa Setup
        try:
            _lora_setup()
        except Exception as e:
            print("LoRa setup failed: {}, asking for LoRa reset".format(e))
            reset.ask(constants.MESSAGE_ERROR_LORA, wlan=False, lora=True)  # LoRa reset
        else:
            print("LoRa setup finished")

        # Display reinitialization
        try:
            display_init()
        except Exception as e:
            print("Display reinitialization failed:", e)
            reset.reset(wlan=False, lora=False)  # Reboot
        else:
            print("SETUP FINISHED")


def display_init():
    # TODO write docstring

    global display, display_block

    display_i2c = SoftI2C(
        scl = Pin(constants.SSD1306_SCL_PIN, Pin.IN, Pin.PULL_UP),
        sda = Pin(constants.SSD1306_SDA_PIN, Pin.IN, Pin.PULL_UP),
        freq = constants.SSD1306_FREQ)
    display = ssd1306.SSD1306_I2C(128, 64, display_i2c)
    display.rotate(False)
    display_block = False


def _wlan_connect():
    """
    Connects the hub to a known WLAN with ESSID and password stored in NVS or starts WPS and learns a new wireless network.

    :raises TimeoutError: if no connection is made after constants.WLAN_TIMEOUT
    """

    # Debug wlan config TODO delete
    configuration.write_str(constants.NVS_KEY_WLAN_ESSID, "ssid")
    configuration.write_str(constants.NVS_KEY_WLAN_PASSWORD, "password")

    print("WLAN SETUP")
    wlan_essid = configuration.read_str(constants.NVS_KEY_WLAN_ESSID)
    wlan_password = configuration.read_str(constants.NVS_KEY_WLAN_PASSWORD)
    
    wlan = WLAN(STA_IF)
    wlan.active(True)

    if wlan_essid and wlan_password:
        if wlan.isconnected():
            print("Reconnecting to known WLAN")
        else:
            print("Connecting to WLAN with known ESSID and password")
            wlan.connect(wlan_essid, wlan_password)
        deadline = time.ticks_add(time.ticks_ms(), constants.WLAN_TIMEOUT)
        while not wlan.isconnected() or time.ticks_diff(deadline, time.ticks_ms()) > 0:
            pass
        if wlan.isconnected():
            # print("WLAN connection successfull\nNetwork configuration:", wlan.ifconfig())
            return
        else:
            raise TimeoutError("WLAN connection failed")
    else:
        # TODO WPS (https://github.com/micropython/micropython/pull/4464#issue-406874786)
        raise NotImplementedError("WPS not yet implemented")


def _register():
    """
    Registers a hub with the backend to obtain the first session token.
    If the hub has not been paired to a user before, the backend will provide a user key for pairing and user_key_loop() will be called.
    To finish up registration backend.update_hub() is called.
    
    :raises BackendError: if any HTTP request fails
    """

    print("HUB REGISTRATION")
    hub = backend.register_hub()
    try:
        user_key = hub["user_key"]
        user = hub["user"]
    except KeyError as e:
        raise BackendError("hub dictionary does not contain key {}".format(e))
    else:
        if user_key is not None:
            display_init()
            _user_key_loop(user_key)
        elif user is None:
            print("Hub has no user, remote factory reset")
            reset.reset(wlan=True, lora=True)
        backend.update_hub(bucket_is_empty(), len(outlets))  # Initial hub update after boot
        return


def _user_key_loop(user_key):
    """
    # TODO rewrite
    Displays the user_key and periodically checks if the backend has paired a user to this hub.
    Will pause the loop after constants.USER_KEY_TIMEOUT or button press and reenter the loop after another button press.

    :param user_key: The 9 character long user key (obtained from the backend) will be shown on the display using str(user_key)
    :raises BackendError: if more than constants.MAX_FAILED_REQUESTS requests to the backend fail
    """

    user_key_with_spaces = str(user_key)[:3] + " " + str(user_key)[3:6] + " " + str(user_key)[6:]
    display_message(constants.MESSAGE_USER_KEY_LOOP.format(user_key_with_spaces))
    deadline = time.ticks_add(time.ticks_ms(), constants.USER_KEY_TIMEOUT)
    failed_request_counter = 0
    button_active_time = 0
    while button_active_time < constants.BUTTON_DEBOUNCE_TIME:
        if button_is_pressed():
            button_active_time += 1
            time.sleep_ms(1)
        else:
            button_active_time = 0
            ticks_diff = time.ticks_diff(deadline, time.ticks_ms())
            if ticks_diff % constants.USER_KEY_DELAY == 0:
                try:
                    is_paired = has_user()
                except Exception as e:
                    print(e)
                    failed_request_counter += 1
                    print("Failed request #", failed_request_counter)
                    if failed_request_counter >= constants.MAX_FAILED_REQUESTS:
                        raise
                else:
                    failed_request_counter = 0
                    if is_paired:
                        return
            if ticks_diff < 0:
                    break
    display_message(constants.MESSAGE_USER_KEY_PAUSE)
    button_active_time = 0
    while button_active_time < constants.BUTTON_DEBOUNCE_TIME:
        if button_is_pressed():
            button_active_time += 1
        else:
            button_active_time = 0
        time.sleep_ms(1)
    _user_key_loop(user_key)


def _lora_setup():
    """
    # TODO rewrite docstring
    Sets up the hub with a persisted and/or free LoRa address

    :raises LoRaAddressUnavailableError: if no address is available on the channel or the persisted address is unavailable
    """

    print("LORA SETUP")
    hub_id = configuration.read_int(constants.NVS_KEY_LORA_HUB_ID)
    address_increment = 0b10000
    first_address = 0b1111
    lora_address = None
    
    if hub_id is not None:
        configured_address = (hub_id << 4) + first_address
        print("Trying configured Hub ID #{}".format(hub_id))
        if not lora.send_reliably(constants.LORA_PREAMBLE, configured_address, constants.LORA_FLAG_ADDRESS_AVL):
            print("Configured Hub ID still available")
            lora_address = configured_address
        else:
            raise LoRaAddressUnavailableError("Configured Hub ID in NVS #{} is unavailable".format(hub_id))
    
    else:
        potential_address = first_address
        while potential_address < constants.LORA_BROADCAST_ADDRESS:
            hub_id = potential_address >> 4
            print("Trying Hub ID #{}".format(hub_id))
            if not lora.send_reliably(constants.LORA_PREAMBLE, potential_address, constants.LORA_FLAG_ADDRESS_AVL):
                print("Hub ID is available")
                configuration.write_int(constants.NVS_KEY_LORA_HUB_ID, hub_id)
                lora_address = potential_address
                break
            else:
                potential_address += address_increment
        if lora_address is None:
            raise LoRaAddressUnavailableError("No Hub ID/address is available on the channel")

    lora.address = lora_address
    print("LoRa address successfully set to {:08b}\nNow continuously listening for packets".format(lora.address))
    lora.receive_continuously()
