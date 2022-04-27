# BLOOM Hub
# Backend communication
# Author: Simon Aschenbrenner

from binascii import b2a_base64
import constants
import http


# HUB

def register_hub():
    """
    Log in this hub using basic authentication to retrieve the first token and the user_key.
    
    :return: This hub as it is persisted on the backend, should include the user_key
    :rtype: dictionary
    :raises BackendError: If the HTTP request fails or the response is not a dictionary (or None)
    """

    auth_string = str(constants.HUB_ID) + ":" + str(constants.FACTORY_KEY)
    auth_header = { "Authorization": "Basic {}".format(b2a_base64(auth_string)[:-1].decode('utf-8')) }
    hub = http.request_handler(constants.ENDPOINT_REGISTER_HUB, auth_header=auth_header)
    if hub is None:
        raise http.BackendError("hub is None")
    elif not isinstance(hub, dict):
        raise http.BackendError("hub is not a dictionary")
    else:
        print("backend.register_hub():", hub)
        return hub


def get_hub():
    """ 
    :return: This hub as it is persisted on the backend
    :rtype: dictionary
    :raises BackendError: If the HTTP request fails or the response is not a dictionary (or None)
    """

    hub = http.request_handler(constants.ENDPOINT_GET_HUB, [constants.HUB_ID])
    if hub is None:
        raise http.BackendError("hub is None")
    elif not isinstance(hub, dict):
        raise http.BackendError("hub is not a dictionary")
    else:
        print("backend.get_hub():", hub)
        return hub


def update_hub(is_empty, outlet_count=None):
    """
    Update this hub's bucket_empty value and (optinally) it's outlet count
    
    :param bool is_empty: Should be True if this hub's bucket is empty, False if it's full
    :param int outlet_count: This hub's outlet count, may be ommitted so no key/value pair will be passed to the backend
    :return: None
    :raises BackendError: if the HTTP request fails (e.g. the hub does not get updated on the backend)
    """

    payload = { "bucket_empty": is_empty }
    if outlet_count is not None:
        payload["outlet_count"] = outlet_count
    http.request_handler(constants.ENDPOINT_UPDATE_HUB, [constants.HUB_ID], json_dict=payload)
    print("backend.update_hub({}, {})".format(is_empty, outlet_count))


# ZONES

def get_zone_ids():
    """
    :return: The activated zone IDs associated with this hub as persisted on the backend - 1 (zone 1 on the backend is zone 0 on the hub).
    :rtype: set of ints
    :raises BackendError: If the HTTP request fails or the response is erroneous (see _handle_list)
    """

    zones = http.request_handler(constants.ENDPOINT_GET_ALL_ZONES, [constants.HUB_ID])
    return _handle_list(zones)


def get_pending_zone_ids():
    """
    :return: The pending zone IDs associated with this hub as persisted on the backend - 1 (zone 1 on the backend is zone 0 on the hub).
    :rtype: set of ints
    :raises BackendError: If the HTTP request fails or the response is not a list (or None)
    """

    pending_zones = http.request_handler(constants.ENDPOINT_GET_ALL_PENDING_ZONES, [constants.HUB_ID])
    if pending_zones is None:
        raise http.BackendError("pending_zones is None")
    elif not isinstance(pending_zones, list):
        raise http.BackendError("pending_zones is not a list")
    else:
        return set(map(_transform_id_from_backend, pending_zones))


def update_zone(zone_id, is_watering):
    """
    Update the is_watering status of a zone of this hub.
    
    :param int zone_id: The ID of the zone that should be updated as this hub refers to it (0 will update zone 1 on the backend)
    :param bool is_watering: Should be True if this hub is currrently watering this zone, False if not
    :return: None
    :raises BackendError: if the HTTP request fails (e.g. the zone does not get updated on the backend)
    """
    
    query_dict = { "hub_id": constants.HUB_ID, "zone_id": _transform_id_to_backend(zone_id) }
    payload = { "is_watering": is_watering }
    http.request_handler(constants.ENDPOINT_UPDATE_ZONE, query_dict=query_dict, json_dict=payload)


# SENSORS

def add_sensor(sensor_id):
    # TODO write docstring

    payload = { "hub_id": constants.HUB_ID, "zone_id": _transform_id_to_backend(sensor_id) }
    http.request_handler(constants.ENDPOINT_ADD_SENSOR, json_dict=payload)


def get_sensor_ids():
    # TODO write docstring

    sensors = http.request_handler(constants.ENDPOINT_GET_ALL_SENSORS, [constants.HUB_ID])
    return _handle_list(sensors)



def update_sensor(data):
    """
    # TODO rewrite docstring
    Send received sensor data to the backend.
    Uses the data cache in sensors.py, a list of namedtuples containing the keys 'sensor_id', 'moisture' and 'battery'

    :raises BackendError: if the HTTP request fails
    """

    query_dict = { "hub_id": constants.HUB_ID, "zone_id": _transform_id_to_backend(data["sensor_id"]) }
    payload = { "moisture_value": data["moisture"], "battery": data["battery"] }
    http.request_handler(constants.ENDPOINT_UPDATE_SENSOR, query_dict=query_dict, json_dict=payload)


def delete_sensor(sensor_id):
    # TODO write docstring

    query_dict = { "hub_id": constants.HUB_ID, "zone_id": _transform_id_to_backend(sensor_id) }
    http.request_handler(constants.ENDPOINT_DELETE_SENSOR, query_dict=query_dict)


def _handle_list(input):
    # TODO write docstring

    if input is None:
        raise http.BackendError("_zone_list_handler: input is None")
    if not isinstance(input, list):
        raise http.BackendError("_zone_list_handler: input is not a list")
    zone_ids = set()
    for element in input:
        if not isinstance(element, dict):
            raise http.BackendError("_zone_list_handler: element in input is not a dictionary")
        try:
            zone_id = element["zone_id"]
        except KeyError as e:
            raise http.BackendError("_zone_list_handler: zone dictionary does not contain key {}".format(e))
        else:
            if not isinstance(zone_id, int):
                raise http.BackendError("_zone_list_handler: zone_id is not an integer")
            zone_ids.add(_transform_id_from_backend(zone_id))
    return zone_ids


def _transform_id_from_backend(zone_id):
    # TODO write docstring

    return zone_id - 1


def _transform_id_to_backend(zone_id):
    # TODO write docstring

    return zone_id + 1