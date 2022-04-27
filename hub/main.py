# BLOOM Hub
# Main
# Author: Simon Aschenbrenner

from http import BackendError
from time import ticks_diff, ticks_ms
import constants
import hub
import reset
import sensors
import watering



def main_loop():
    """
    Hub will enter this loop after setup and stay in it for eternity if not powercycled or rebooted.
    Exception safe, will automatically enter reset.ask() if more than constants.MAX_FAILED_REQUESTS requests to the backend fail.
    """

    print("ENTER MAIN LOOP")
    hub.led.on()
    failed_request_counter = 0
    last_backend_call = 0

    while True:

        try:
            sensors.collect()
            time_since_last_backend_call = ticks_diff(ticks_ms(), last_backend_call)

            if (time_since_last_backend_call > constants.BACKEND_CALL_DELAY) or (time_since_last_backend_call < 0):  # overflow protection
                if hub.has_user():
                    print("Hub has user")
                    watering.water()
                    sensors.check()
                else:  # Remote reset happened
                    print("Hub has no user, remote factory reset")
                    reset.reset(wlan=True, lora=True)
                last_backend_call = ticks_ms()
                failed_request_counter = 0

        except BackendError as e:
            watering.stop_water()
            print(e)
            failed_request_counter += 1
            print("Failed request #", failed_request_counter)

        except Exception as e:
            print(e)
            reset.reset(wlan=False, lora=False)  # Reboot

        if failed_request_counter >= constants.MAX_FAILED_REQUESTS:
            print("Too many failed requests, asking for WLAN reset")
            reset.ask(constants.MESSAGE_ERROR_BACKEND, wlan=True, lora=False)


if __name__ == "__main__":
    hub.setup()
    main_loop()
