# BLOOM Hub
# HTTP utilities
# Author: Simon Aschenbrenner

# Adapted from urequests.py by Paul Sokolovsky
# https://github.com/micropython/micropython-lib/blob/master/python-ecosys/urequests
# (15.12.21, MIT License)

import constants
import ujson
import socket
import ssl


class BackendError(Exception):
    pass

class UnauthorizedError(BackendError):
    pass

_current_session_token = ""

        
def request_handler(endpoint, params_list=None, query_dict=None, json_dict=None, auth_header=None):
    """
    Outside facing general HTTP request handler. Use this function to make any requests to the backend.

    :param str endpoint: A tuple containing the HTTP method and the path without leading and trailing '/', e.g. ("GET", "hub/getHub")
    :param list params_list: Optional list of parameters (e.g. IDs) to be added to the URL seperated by '/', default is None
    :param dict query_dict: Optional dictionary of paramaters as key/value-pairs to be added to the URL using a query string (see make_query_string() for more details)
    :param dict json_dict: Optional dictionary that should be encoded as a JSON string and added in the request body, default is None
    :param dict auth_header: Optional dictionary of headers (e.g. for basic authentication), will be overriden with a Authorization header for token based authentication with the current session token if not specified, default is None
    :return: The dictionary of the JSON in the HTTP response body or None if the response status code was 200 but there was no (valid) JSON in the body
    :rtype: dict or None
    :raises UnauthorizedError:
    :raises BackendError:
    
    """

    global _current_session_token

    method = endpoint[0]
    path = endpoint[1]
    if params_list:
        for param in params_list:
            path += "/" + str(param)
    if query_dict:
        path += make_query_string(query_dict)
    # print("Trying HTTP {} {}".format(method, path))
    # print("Payload:", json_dict)
    if auth_header is None:
        auth_header = { "Authorization": "Bearer {}".format(_current_session_token) }
    try:
        response = request(method, path, json=json_dict, headers=auth_header)
        if response.status_code == 200:
            new_session_token = response.token()
            if new_session_token is not None:
                _current_session_token = new_session_token
            try:
                data = response.json()
                # print("Success:", data)
                return data
            except ValueError:
                # print("Status 200, but no valid JSON in response body:\n", response.text())
                return None
        elif response.status_code == 401:
            raise UnauthorizedError("Error 401: Not authorized")
        else:
            message = "Error " + str(response.status_code) + " " + response.reason.decode(response.encoding)
            raise BackendError(message)
    except Exception as e:
        raise BackendError(e)


def make_query_string(dictionary):
    """
    :param dict dictionary: Dictionary of the key/value pairs that should be added to the URL
    :return: Valid WWW query string to be added to an URL
    """

    query_string = "?"
    for key, value in dictionary.items():
        query_string = query_string + str(key) + "=" + str(value) + "&"
    return query_string[:-1]


def request(method, path, json=None, headers={}):
    """
    Makes the HTTPS request using a ssl-wrapped socket with an optional JSON payload.
    Do not call this function directly, use request_handler() instead.

    :param str method: HTTP method of the request ('GET', 'PUT', 'POST', etc.)
    :param str path: The full path for the requested endpoint on the webserver (without the host)
    :param dict json: Optional dictionary that should be encoded as a JSON string and added in the request body, default is None
    :param dict headers: Optional dictionary containing headers (key as header key and value as header value), default is an empty dictionary, meaning no additional headers
    :return: response containing the fields 'status_code' and 'reason'. The body may be accessed via text() or json() and the (new) session token may be accessed via token()
    :rtype: Response
    :raises OSError:
    """    
    
    host = constants.BACKEND_HOST
    port = constants.BACKEND_PORT

    ai = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    ai = ai[0]

    body = b""
    sckt = socket.socket(ai[0], ai[1], ai[2])
    try:
        sckt.connect(ai[-1])

        with open(constants.SSL_KEY, 'rb') as f:
            key = f.read()
        with open(constants.SSL_CERT, 'rb') as f:
            cert = f.read()
        sckt = ssl.wrap_socket(sckt, server_hostname=host, key=key, cert=cert)

        sckt.write(b"%s /%s HTTP/1.0\r\n" % (method, path))
        if not "Host" in headers:
            sckt.write(b"Host: %s\r\n" % host)
        for k in headers:
            sckt.write(k)
            sckt.write(b": ")
            sckt.write(headers[k])
            sckt.write(b"\r\n")
        if json is not None:
            body = ujson.dumps(json)
            sckt.write(b"Content-Type: application/json\r\n")
            sckt.write(b"Content-Length: %d\r\n" % len(body))
        sckt.write(b"\r\n")
        sckt.write(body)

        line = sckt.readline()
        # print(line)
        status = line.split(None, 2)
        status_code = int(status[1])
        reason = ""
        if len(status) > 2:
            reason = status[2].rstrip()
        session_token = ""
        while True:
            line = sckt.readline()
            # print(line)
            if not line or line == b"\r\n":
                break
            else:
                header = line.split(None, 2)
                if len(header) == 3 and header[0] == b"Authorization:":
                    # print("New token in response")
                    session_token = header[2].rstrip()

    except OSError:
        sckt.close()
        raise

    resp = Response(sckt)
    resp.status_code = status_code
    resp.reason = reason
    resp.session_token = session_token
    return resp


class Response:
    def __init__(self, sckt):
        self.sckt = sckt
        self.encoding = "utf-8"
        self.session_token = ""
        self._cached = None

    @property
    def content(self):
        """
        Access the body of the HTTP response, will close the socket after all data has been read.
        Do not use this funktion directly, use text() or json() instead.
        """

        if self._cached is None:
            try:
                self._cached = self.sckt.read()
                # print(self._cached)
            finally:
                self.sckt.close()
                self.sckt = None
        return self._cached

    def text(self):
        """
        :return: The body of the HTTP response as a string, decoded with self.encoding
        :rtype: str
        """

        return str(self.content, self.encoding)

    def json(self):
        """
        :return: The body of the HTTP response as a dictionary if it was encoded in valid JSON
        :rtype: dict
        :raises ValueError: if the JSON is invalid or the body empty
        """

        return ujson.loads(self.content)

    def token(self):
        """
        :return: The session token sent or None if there was no corresponding header in the HTTP response
        :rtype: str or None
        """

        if len(self.session_token) > 0:
            return str(self.session_token, self.encoding)
        else:
            return None
