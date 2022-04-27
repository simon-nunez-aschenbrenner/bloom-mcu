# BLOOM Hub
# Watering routines
# Author: Simon Aschenbrenner

from time import ticks_diff, ticks_ms
import backend
import constants
import hub

_bucket_was_empty = False

def water(update=True):
    """
    Outside facing watering routine: Checks if the bucket is full, requests the pending zones from the backend and calls water().

    :raises BackendError: if any HTTP request fails
    """

    global _bucket_was_empty

    if hub.bucket_is_empty():
        # print("Water Sensor: Bucket is empty, waiting {}s to debounce".format(constants.EMPTY_DELAY))
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) > constants.EMPTY_DELAY:
            pass
        hub.display_message(constants.MESSAGE_WATERING_TANK_EMPTY)
        stop_water()
        backend.update_hub(is_empty=True)
        _bucket_was_empty = True

    elif _bucket_was_empty:
        # print("Water Sensor: Bucket is full, waiting {}s to debounce".format(constants.EMPTY_DELAY))
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) > constants.EMPTY_DELAY:
            pass
        hub.display_message(constants.MESSAGE_WATERING_TANK_FULL)
        backend.update_hub(is_empty=False)
        _bucket_was_empty = False

    else:
        pending_zones = backend.get_pending_zone_ids()
        # print("Pending zone IDs:", pending_zones)
        _water(pending_zones, update)


def stop_water(update=False):
    # TODO write docstring: Call water() without any pending zones, thus closing all outlets and stopping the pump

    _water([], update)


def _water(pending_zones, update):
    """
    Internal watering routine (Do not call this function directly, use water() instead): Starts the pump if zones are pending and opens the corresponding outlets.
    # TODO rewrite docstring with params
    """

    new_outlets_mask = [False] * len(hub.outlets)
    watered_zones = []

    if len(pending_zones) > 0:
        for index in pending_zones:
            if index > -1 and index < len(new_outlets_mask):
                new_outlets_mask[index] = True

    if hub.outlets_mask != new_outlets_mask:
        hub.outlets_mask = new_outlets_mask
        _run_pump(any(hub.outlets_mask))
        for index, bool in enumerate(hub.outlets_mask):
            if bool:
                watered_zones.append(backend._transform_id_to_backend(index))
                _open_outlet(index)
            else:
                _close_outlet(index)
        if update:
            _update_zones()

    if update:
        if len(watered_zones) > 0:
            hub.display_message(constants.MESSAGE_WATERING_ZONES.format(str(watered_zones)[1:-1]))
        else:
            hub.display_message(constants.MESSAGE_WATERING_NONE)


def _open_outlet(index):
    # print("Opening outlet {}".format(index))
    hub.outlets[index].off()  # Opens outlet


def _close_outlet(index):
    # print("Closing outlet {}".format(index))
    hub.outlets[index].on()  # Closes outlet


def _run_pump(bool):
    if bool:
        # print("Turning pump on")
        hub.pump.on()
    else:
        # print("Turning pump off")
        hub.pump.off()


def _update_zones():
    # TODO write docstring

    zone_ids = backend.get_zone_ids()
    for zone_id in zone_ids:
        is_watering = hub.outlets_mask[zone_id]
        backend.update_zone(zone_id, is_watering)