# BLOOM Hub
# Reset routines
# Author: Simon Aschenbrenner

from machine import deepsleep, reset as reboot
from sensors import unpair_all_sensors
from time import ticks_add, ticks_diff, ticks_ms, time, sleep_ms
from watering import stop_water
import constants
import hub


def ask(message: str, wlan=False, lora=False):
    """
    Put the hub in a loop and await user interaction to either factory reset or reboot the hub. Will automatically reboot after constants.REBOOT_TIMEOUT.

    :param str message: Error message to be displayed above the reboot/reset instructions (No more than 16 characters including white spaces)
    :param bool wlan: True if WLAN configuration should be deleted (needs to be True for factory reset and False for reboot without reset), default is False
    :param bool lora: True if LoRa configuration should be deleted (needs to be True for factory reset and False for reboot without reset), default is False
    """

    try:
        hub.display_init()
    except Exception as e:
        print("Display reinitialization failed:", e)
        reset(wlan=False, lora=False)  # Reboot
    else:
        scope = constants.MESSAGE_RESET_NONE
        if wlan:
            scope = constants.MESSAGE_RESET_WLAN_CONFIG
        if lora:
            scope = constants.MESSAGE_RESET_LORA_CONFIG
        if wlan and lora:
            scope = constants.MESSAGE_RESET_FACTORY_CONFIG
        deadline = ticks_add(ticks_ms(), constants.REBOOT_TIMEOUT)
        button_active_time = 0
        while button_active_time < constants.BUTTON_DEBOUNCE_TIME:
            if hub.button_is_pressed():
                button_active_time += 1
                sleep_ms(1)
            else:
                button_active_time = 0
                difference = ticks_diff(deadline, ticks_ms())
                if difference % 1000 == 0:
                    hub.display_message(constants.MESSAGE_RESET_LOOP.format(message, scope, int(difference/1000)))
                if difference < 0:
                    reset(wlan=False, lora=False)  # Just reboot
        reset(wlan=wlan, lora=lora)


def reset(wlan=False, lora=False):
    """
    Reset the hub to factory conditions, just delete WLAN or LoRa configuration or simply reboot the hub.
    Clears the corresponding entries in the NVS and reboots afterwards.
    To prevent endless reboot loops the number of reboots and the timestamp of the last reboot are stored in the NVS and evaluated.
    This may cause the hub to enter an eternal deepsleep, if constants.MAX_REBOOT_ATTEMPTS are exceeded within constants.REBOOT_COUNTER_RESET_TIME.

    :param bool wlan: True if WLAN configuration should be deleted (needs to be True for factory reset and False for reboot without reset), default is False
    :param bool lora: True if LoRa configuration should be deleted (needs to be True for factory reset and False for reboot without reset), default is False
    """

    print("Resetting")

    hub.led.off()
    stop_water()
    hub.lora.close()

    reboot_counter = hub.configuration.read_int(constants.NVS_KEY_REBOOT_COUNTER)
    last_reboot = hub.configuration.read_int(constants.NVS_KEY_LAST_REBOOT_TIMESTAMP)
    if (reboot_counter is None) or (last_reboot is None) or (time() - last_reboot > constants.REBOOT_COUNTER_RESET_TIME):
        reboot_counter = 1
    else:
        reboot_counter += 1

    if wlan:
        hub.display_message(constants.MESSAGE_RESET_WLAN_DONE)
        hub.configuration.delete(constants.NVS_KEY_WLAN_ESSID)
        hub.configuration.delete(constants.NVS_KEY_WLAN_PASSWORD)
    if lora:
        hub.display_message(constants.MESSAGE_RESET_LORA_DONE)
        hub.configuration.delete(constants.NVS_KEY_LORA_HUB_ID)
        unpair_all_sensors()
    if wlan and lora:
        hub.display_message(constants.MESSAGE_RESET_FACTORY_DONE)
        reboot_counter = 0
    
    print("Reboot #{}".format(reboot_counter))
    if reboot_counter > constants.MAX_REBOOT_ATTEMPTS:
        hub.configuration.delete(constants.NVS_KEY_REBOOT_COUNTER)
        print("Too many reboots ({} > {}), entering eternal deepsleep".format(reboot_counter, constants.MAX_REBOOT_ATTEMPTS))
        deepsleep()
    else:
        hub.configuration.write_int(constants.NVS_KEY_REBOOT_COUNTER, reboot_counter)
        hub.configuration.write_int(constants.NVS_KEY_LAST_REBOOT_TIMESTAMP, time())
        print("Rebooting")
        reboot()
