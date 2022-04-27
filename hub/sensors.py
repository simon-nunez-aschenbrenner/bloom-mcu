# BLOOM Hub
# Hub sensor management
# Author: Simon Aschenbrenner

import backend
import constants
import hub
from time import localtime, time

LOG = False

def check():
    # TODO write docstring

    print("Checking on sensors")
    activated_sensor_ids = backend.get_sensor_ids()
    sensor_ids_to_unpair = paired_sensor_ids() - activated_sensor_ids
    sensor_ids_to_deactivate = (activated_sensor_ids & silent_sensor_ids()) - sensor_ids_to_unpair
    for sensor_id in sensor_ids_to_deactivate:
        try:
            backend.delete_sensor(sensor_id)
        except Exception as e:
            print(e)
        else:  # Only unpair when successfully deactivated (deleted) in the backend
            sensor_ids_to_unpair.add(sensor_id)
    # print("Activated sensors:", activated_sensor_ids)
    # print("Silent sensors:", silent_sensor_ids())
    # print("Sensors to deactivate:", sensor_ids_to_deactivate)
    # print("Sensors to unpair:", sensor_ids_to_unpair)
    for sensor_id in sensor_ids_to_unpair:
        unpair_sensor(sensor_id)


def collect():
    # TODO write docstring

    # print("Collecting sensor data")
    for payload in hub.lora.received_data:
        received_preamble = payload.message.split()[0]
        if received_preamble != constants.LORA_PREAMBLE:
            log(payload)
            print("Wrong preamble, message will be ignored ('{}' != '{}')".format(received_preamble, constants.LORA_PREAMBLE))
        else:
            if (payload.header_flags & constants.LORA_BIT_MASK) == constants.LORA_FLAG_MEASUREMENT:
                handle_measurement(payload)
            elif (payload.header_flags & constants.LORA_BIT_MASK) == constants.LORA_FLAG_PAIRING_REQ:
                handle_pairing(payload)
            else:
                log(payload)
                print("Wrong flags, message will be ignored")
    hub.display_block = False


def handle_measurement(payload):
    """
    Handles a received measurement and appends it to the data cache.

    :param namedtuple payload: The LoRa message received, contains keys 'message', 'header_to', 'header_from', 'header_id', 'header_flags', 'rssi' and 'snr'
    """

    log(payload, message_type="Measurement")
    if (payload.header_from & ~constants.LORA_BIT_MASK) == (hub.lora.address & ~constants.LORA_BIT_MASK):  # sensor address matches hub address
        is_paired, sensor_id = is_paired_sensor(payload)
        if is_paired:
            message = payload.message.split()
            try:
                moisture = max(min(float(message[1][:-1].decode("utf-8")), 1.0), 0.0)
                battery = max(min(float(message[2][:-1].decode("utf-8")), 1.0), 0.0)
                backend.update_sensor({ "sensor_id": sensor_id, "moisture": moisture, "battery": battery })
            except Exception as e:
                # Log the exception but otherwise treat measurement as if not received
                print(e)
            else:
                _update_sensor_timestamp(sensor_id)
        else:
            print("Sensor #{} not paired, sending shutdown order".format(sensor_id))
            send_shutdown_order(payload.header_from)
    else:
        print("Sensor address {:08b} does not match hub address {:08b}, sending shutdown order".format(payload.header_from, hub.lora.address))
        send_shutdown_order(payload.header_from)


def handle_pairing(payload):
    """
    Handles a received pairing request by a sensor.

    :param namedtuple payload: The LoRa message received, contains keys 'message', 'header_to', 'header_from', 'header_id', 'header_flags', 'rssi' and 'snr'
    """

    log(payload, message_type="Pairing Request")
    if (payload.header_to == constants.LORA_BROADCAST_ADDRESS) and (payload.header_from & ~constants.LORA_BIT_MASK):
        if payload.rssi > constants.LORA_RSSI_PAIRING_THRESHOLD:
            print("Trying to pair sensor with address {:08b} to this hub, as the RSSI was high enough ({} > {})".format(payload.header_from, payload.rssi, constants.LORA_RSSI_PAIRING_THRESHOLD))
            hub.display_message(constants.MESSAGE_PAIRING_IN_PROGRESS.format(payload.header_from & constants.LORA_BIT_MASK))
            is_paired, sensor_id = is_paired_sensor(payload)
            if not is_paired:
                if hub.lora.send_reliably(constants.LORA_PREAMBLE, payload.header_from, constants.LORA_FLAG_PAIRING_ACK):
                    try:
                        backend.add_sensor(sensor_id)
                    except Exception as e:
                        # Log the exception but otherwise treat sensor as if not paired (will receive shutdown order on next transmit)
                        print(e)
                    else:
                        hub.display_message(constants.MESSAGE_PAIRING_SUCCESS.format(sensor_id))
                        _update_sensor_timestamp(sensor_id)
                else:
                    hub.display_message(constants.MESSAGE_PAIRING_FAIL.format(sensor_id))
                    print("Sensor #{} did not acknowledge the hubs PAIRING_ACK message".format(sensor_id))
            else:
                hub.display_message(constants.MESSAGE_PAIRING_ALREADY_PAIRED.format(sensor_id))
        else:
            hub.display_message(constants.MESSAGE_PAIRING_TOO_FAR.format(payload.header_from & constants.LORA_BIT_MASK, payload.rssi))
            print("Sensor with address {:08b} won't be paired to this hub, because the RSSI was too low ({} <= {})".format(payload.header_from, payload.rssi, constants.LORA_RSSI_PAIRING_THRESHOLD))
    else:
        print("Sensor with address {:08b} won't be paired to this hub, because its PAIRING_REQ was invalid".format(payload.header_from))
    hub.display_block = True


def send_shutdown_order(address):
    """
    Send a message to instruct a sensor to turn itself off. 

    :param int address: The address of the sensor that should receive this order.
    """

    if hub.lora.send_reliably(constants.LORA_PREAMBLE, address, constants.LORA_FLAG_SHUTDOWN_ORDER):
        print("Shutdown order acknowledged by sensor")
    else:
        print("Shutdown order not acknowledged by sensor")


def log(payload, message_type=None):
    """
    Log the received LoRa message to the console, including metadata.
    
    :param namedtuple payload: The LoRa message received, contains keys 'message', 'header_to', 'header_from', 'header_id', 'header_flags', 'rssi' and 'snr'
    :param str message_type: Optional string to define the type of message received, default is None
    """

    if not LOG:
        return

    if message_type is None:
        message_type = ""
    else:
        message_type = "(" + message_type + ") "
    try:
        message = payload.message.decode("utf-8")
    except:
        message = payload.message
    current_time = localtime()
    time_string = "{:4d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(current_time[0], current_time[1], current_time[2], current_time[3], current_time[4], current_time[5])
    string = '{}[{}] {:08b} -> {:08b} #{} [{:04b} {:04b}] (RSSI {}, SNR {}): "{}"'.format(
        message_type,
        time_string,
        payload.header_from,
        payload.header_to,
        payload.header_id,
        payload.header_flags & ~constants.LORA_BIT_MASK,
        payload.header_flags & constants.LORA_BIT_MASK,
        payload.rssi,
        payload.snr,
        message
        )
    print("LoRa reception:", string)


def is_paired_sensor(payload):
    """
    Checks if a sensor is already paired to this hub.

    :param namedtuple payload: The LoRa message received, contains keys 'message', 'header_to', 'header_from', 'header_id', 'header_flags', 'rssi' and 'snr'
    :return: Tuple containing a boolean indicating whether a sensor with the same ID is already paired to the hub and the sensor ID
    :rtype: (bool, int)
    """

    sensor_id = payload.header_from & constants.LORA_BIT_MASK
    is_paired = sensor_id in paired_sensor_ids()
    return is_paired, sensor_id


def paired_sensor_ids():
    # TODO write docstring

    return set(_paired_sensors().keys())


def silent_sensor_ids():
    # TODO write docstring

    silent_sensor_ids = set()
    current_time = time()
    for sensor_id, timestamp in _paired_sensors().items():
        if current_time - timestamp > constants.LORA_MAX_SILENT_TIME:
            silent_sensor_ids.add(sensor_id)  
    return silent_sensor_ids


def unpair_all_sensors():
    # TODO write docstring

    for sensor_id in paired_sensor_ids():
        unpair_sensor(sensor_id)


def unpair_sensor(sensor_id):
    # TODO write docstring

    hub.configuration.delete(constants.NVS_KEY_PAIRED_SENSOR_PREFIX + str(sensor_id))
    print("Unpaired sensor #{}".format(sensor_id))


def _paired_sensors():
    # TODO write docstring

    paired_sensors = {}
    for sensor_id in range(constants.LORA_MAX_PAIRED_SENSORS):
        timestamp = hub.configuration.read_int(constants.NVS_KEY_PAIRED_SENSOR_PREFIX + str(sensor_id))
        if timestamp is not None:
            paired_sensors[sensor_id] = timestamp
    return paired_sensors


def _update_sensor_timestamp(sensor_id):
    current_time = time()
    hub.configuration.write_int(constants.NVS_KEY_PAIRED_SENSOR_PREFIX + str(sensor_id), current_time)
