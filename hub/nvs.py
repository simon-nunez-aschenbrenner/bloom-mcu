# BLOOM Hub
# Hub NVS utilities
# Author: Simon Aschenbrenner

import constants
import esp32


class NVS(object):

    def __init__(self):
        self.nvs_instance = esp32.NVS(constants.NVS_NAMESPACE)


    def read_int(self, key):
        try:
            value = self.nvs_instance.get_i32(str(key))
        except OSError as e:
            # print(e)
            return None
        else:
            return value


    def read_str(self, key):
        buffer = bytearray(constants.NVS_MAX_BUFFER_SIZE)
        try:
            self.nvs_instance.get_blob(str(key), buffer)
        except OSError as e:
            # print(e)
            return None
        else:
            return buffer.decode()


    def write_int(self, key, value):
        self.nvs_instance.set_i32(str(key), value)
        self.nvs_instance.commit()


    def write_str(self, key, value):
        self.nvs_instance.set_blob(str(key), str(value))
        self.nvs_instance.commit()


    def delete(self, key):
        try:
            self.nvs_instance.erase_key(str(key))
            self.nvs_instance.commit()
            return True
        except OSError as e:
            # print(e)
            return False
