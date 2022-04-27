# BLOOM Hub
# Hub LoRa radio
# Author: Simon Aschenbrenner

# Adapted from ulora.py by martynwheeler
# https://github.com/martynwheeler/u-lora
# (12.12.21, GNU GPL v3)

import constants
from machine import Pin, SPI
from math import ceil
from collections import namedtuple, deque
from micropython import schedule
from random import getrandbits
from time import time, sleep


# Constants
FLAGS_ACK = 0x80
BROADCAST_ADDRESS = 255

REG_00_FIFO = 0x00
REG_01_OP_MODE = 0x01
REG_06_FRF_MSB = 0x06
REG_07_FRF_MID = 0x07
REG_08_FRF_LSB = 0x08
REG_0E_FIFO_TX_BASE_ADDR = 0x0e
REG_0F_FIFO_RX_BASE_ADDR = 0x0f
REG_10_FIFO_RX_CURRENT_ADDR = 0x10
REG_12_IRQ_FLAGS = 0x12
REG_13_RX_NB_BYTES = 0x13
REG_1D_MODEM_CONFIG1 = 0x1d
REG_1E_MODEM_CONFIG2 = 0x1e
REG_19_PKT_SNR_VALUE = 0x19
REG_1A_PKT_RSSI_VALUE = 0x1a
REG_20_PREAMBLE_MSB = 0x20
REG_21_PREAMBLE_LSB = 0x21
REG_22_PAYLOAD_LENGTH = 0x22
REG_26_MODEM_CONFIG3 = 0x26

REG_4D_PA_DAC = 0x4d
REG_40_DIO_MAPPING1 = 0x40
REG_0D_FIFO_ADDR_PTR = 0x0d

PA_DAC_ENABLE = 0x07
PA_DAC_DISABLE = 0x04
PA_SELECT = 0x80

CAD_DETECTED_MASK = 0x01
RX_DONE = 0x40
TX_DONE = 0x08
CAD_DONE = 0x04
CAD_DETECTED = 0x01

LONG_RANGE_MODE = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RXCONTINUOUS = 0x05
MODE_CAD = 0x07

REG_09_PA_CONFIG = 0x09
FXOSC = 32000000.0
FSTEP = (FXOSC / 524288)


class ModemConfig():

    Bw125Cr45Sf128 = (0x72, 0x74, 0x04)   # Bw = 125 kHz, Cr = 4/5, Sf = 7 (128 chips/symbol), CRC on. Default medium range (Default RadioHead settings)
    Bw500Cr45Sf128 = (0x92, 0x74, 0x04)   # Bw = 500 kHz, Cr = 4/5, Sf = 7 (128 chips/symbol), CRC on. Fast + short range
    Bw31_25Cr48Sf512 = (0x48, 0x94, 0x04) # Bw = 31.25 kHz, Cr = 4/8, Sf = 9 (512 chips/symbol), CRC on. Slow + long range
    Bw125Cr48Sf4096 = (0x78, 0xc4, 0x0c)  # Bw = 125 kHz, Cr = 4/8, Sf = 12 (4096 chips/symbol), CRC on. Slow + long range
    Bw125Cr45Sf2048 = (0x72, 0xb4, 0x04)  # Bw = 125 kHz, Cr = 4/5, Sf = 11 (2048 chips/symbol), CRC on. Slow + long range


class LoRa(object):

    def __init__(
        self,
        address=constants.LORA_BROADCAST_ADDRESS,
        freq=constants.LORA_FREQUENCY,
        tx_power=constants.LORA_POWER,
        modem_config=ModemConfig.Bw125Cr45Sf128,
        receive_all=False,
        acknowledge=True,
        crypto=None
        ):
        """
        :param int address: address for this device [0-255], default constants.LORA_BROADCAST_ADDRESS
        :param float freq: frequency in MHz, default is constants.LORA_FREQUENCY
        :param int tx_power: transmit power in dBm, default is constants.LORA_POWER
        :param ModemConfig modem_config: see ModemConfig, default is ModemConfig.Bw125Cr45Sf128
        :param bool receive_all: if True, don't filter packets on address, default is False
        :param bool acknowledge: if True, acknowledge received messages (only those addressed to us and except broadcasts), default is True
        :param AES crypto: if desired, an instance of ucrypto AES (https://docs.pycom.io/firmwareapi/micropython/ucrypto/), default is None
        """

        # Public attributes (change values at will)
        self.address = address
        self.receive_all = receive_all
        self.acknowledge = acknowledge
        self.crypto = crypto
        self.send_retries = 3
        self.cad_timeout = 0
        self.wait_packet_sent_timeout = 0.2
        self.receive_timeout = 0.2
        
        # Constant attributes (do not change values)
        self._spi_mode = constants.LORA_SPI_MODE
        self._cs_pin = constants.LORA_CS_PIN
        self._sck_pin = constants.LORA_SCK_PIN
        self._mosi_pin = constants.LORA_MOSI_PIN
        self._miso_pin = constants.LORA_MISO_PIN
        self._interrupt_pin = constants.LORA_IRQ_PIN
        self._reset_pin = constants.LORA_IRQ_PIN
        self._baudrate = constants.LORA_BAUDRATE

        # Private attributes (do not change values after initialization)
        self._freq = freq
        self._tx_power = tx_power
        self._modem_config = modem_config
        self._receive_continuously = False
        self._mode = None
        self._cad = None
        self._last_header_id = 0
        self._last_payload = None
        self._prepare_payload_ref = self._prepare_payload
        self._new_payload = False
        self._data_cache = deque((), constants.LORA_DATA_CACHE_SIZE)
        
        
        # MODULE SETUP
        self._reset()

        # Set interrupt
        self._interrupt = Pin(self._interrupt_pin, Pin.IN)
        self._interrupt.irq(trigger=Pin.IRQ_RISING, handler=self._handle_interrupt)

        # Set SPI
        self._spi = SPI(self._spi_mode, self._baudrate, sck=Pin(self._sck_pin), mosi=Pin(self._mosi_pin), miso=Pin(self._miso_pin))

        # Set CS
        self._cs = Pin(self._cs_pin, Pin.OUT, value=1)

        # Set mode
        self._spi_write(REG_01_OP_MODE, MODE_SLEEP | LONG_RANGE_MODE)
        sleep(0.1)
        assert self._spi_read(REG_01_OP_MODE) == (MODE_SLEEP | LONG_RANGE_MODE), \
            "LoRa initialization failed"

        # Set address
        self._spi_write(REG_0E_FIFO_TX_BASE_ADDR, 0)
        self._spi_write(REG_0F_FIFO_RX_BASE_ADDR, 0)
        
        # Set modem configuration
        self._spi_write(REG_1D_MODEM_CONFIG1, self._modem_config[0])
        self._spi_write(REG_1E_MODEM_CONFIG2, self._modem_config[1])
        self._spi_write(REG_26_MODEM_CONFIG3, self._modem_config[2])

        # Set preamble length to 8
        self._spi_write(REG_20_PREAMBLE_MSB, 0)
        self._spi_write(REG_21_PREAMBLE_LSB, 8)

        # Set frequency
        frf = int((self._freq * 1000000.0) / FSTEP)
        self._spi_write(REG_06_FRF_MSB, (frf >> 16) & 0xff)
        self._spi_write(REG_07_FRF_MID, (frf >> 8) & 0xff)
        self._spi_write(REG_08_FRF_LSB, frf & 0xff)
        
        # Set TX power
        if self._tx_power < 5:
            self._tx_power = 5
        if self._tx_power > 23:
            self._tx_power = 23
        if self._tx_power < 20:
            self._spi_write(REG_4D_PA_DAC, PA_DAC_ENABLE)
            self._tx_power -= 3
        else:
            self._spi_write(REG_4D_PA_DAC, PA_DAC_DISABLE)
        self._spi_write(REG_09_PA_CONFIG, PA_SELECT | (self._tx_power - 5))

        # Set continuous mode
        self._set_continuous_mode()

    # PUBLIC METHODS

    def send_reliably(self, data, header_to, header_flags=0, retries=None):
        self._set_mode_idle()
        if retries is not None:
            self.send_retries = retries
        self._last_header_id += 1
        if self._last_header_id > 0xff:  # RadioHead reliable datagram protocol only supports 8 bit unsigned int as header ID
            self._last_header_id = 0
        acknowledged = False
        for _ in range(self.send_retries):
            if self.send(data, header_to, header_id=self._last_header_id, header_flags=header_flags):
                if header_to == BROADCAST_ADDRESS:  # Don't wait for acknowledgements on broadcasts
                    acknowledged = True
                    break
                else:  # Wait for acknowledgement
                    acknowledged = self._receive_timeout(receive_acknowledgements=True) is not None
                    if acknowledged:
                        break  # else retry
        self._set_continuous_mode()
        return acknowledged

    def send(self, data, header_to, header_id=0, header_flags=0):
        self._set_mode_idle()
        header = [header_to, self.address, header_id, header_flags]
        if type(data) == int:
            data = [data]
        elif type(data) == bytes:
            data = [p for p in data]
        elif type(data) == str:
            data = [ord(s) for s in data]
        if self.crypto:
            data = [b for b in self._encrypt(bytes(data))]
        payload = header + data
        self._spi_write(REG_0D_FIFO_ADDR_PTR, 0)
        self._spi_write(REG_00_FIFO, payload)
        self._spi_write(REG_22_PAYLOAD_LENGTH, len(payload))
        self._wait_cad()
        self._set_mode_tx()
        success = self._wait_packet_sent()
        self._set_continuous_mode()
        return success

    def receive(self, receive_all=None, acknowledge=None, receive_acknowledgements=False):
        if receive_all is not None:
            self.receive_all = receive_all
        if acknowledge is not None:
            self.acknowledge = acknowledge
        if bool(self._data_cache) and self._receive_continuously:
            return self._data_cache.popleft()
        else:
            payload = self._receive_timeout(receive_acknowledgements=receive_acknowledgements)
            if bool(self._data_cache):
                return self._data_cache.popleft()
            else:
                return payload

    @property
    def received_data(self):
        for _ in range(len(self._data_cache)):
            yield self._data_cache.popleft()

    def receive_continuously(self, receive_all=None, acknowledge=None):
        self._set_mode_idle()
        if receive_all is not None:
            self.receive_all = receive_all
        if acknowledge is not None:
            self.acknowledge = acknowledge
        self._receive_continuously = True
        self._set_continuous_mode()

    def idle(self):
        self._receive_continuously = False
        self._set_mode_idle()

    def sleep(self):
        self._receive_continuously = False
        if self._mode != MODE_SLEEP:
            self._spi_write(REG_01_OP_MODE, MODE_SLEEP)
            self._mode = MODE_SLEEP

    def close(self):
        self._interrupt.irq(trigger=0, handler=None)
        self._data_cache = deque((), constants.LORA_DATA_CACHE_SIZE)
        self._spi.deinit()
        self._reset()

    # PRIVATE METHODS

    # Mode setting
    def _set_mode_tx(self):
        if self._mode != MODE_TX:
            self._spi_write(REG_01_OP_MODE, MODE_TX)
            self._spi_write(REG_40_DIO_MAPPING1, 0x40)  # Interrupt on TxDone
            self._mode = MODE_TX

    def _set_mode_rx(self):
        if self._mode != MODE_RXCONTINUOUS:
            self._spi_write(REG_01_OP_MODE, MODE_RXCONTINUOUS)
            self._spi_write(REG_40_DIO_MAPPING1, 0x00)  # Interrupt on RxDone
            self._mode = MODE_RXCONTINUOUS
            
    def _set_mode_cad(self):
        if self._mode != MODE_CAD:
            self._spi_write(REG_01_OP_MODE, MODE_CAD)
            self._spi_write(REG_40_DIO_MAPPING1, 0x80)  # Interrupt on CadDone
            self._mode = MODE_CAD

    def _set_mode_idle(self):
        if self._mode != MODE_STDBY:
            self._spi_write(REG_01_OP_MODE, MODE_STDBY)
            self._mode = MODE_STDBY

    def _set_continuous_mode(self):
        if self._receive_continuously:
            self._set_mode_rx()
        else:
            self._set_mode_idle()

    # Writing and reading registers
    def _spi_write(self, register, payload):
        if type(payload) == int:
            payload = [payload]
        elif type(payload) == bytes:
            payload = [p for p in payload]
        elif type(payload) == str:
            payload = [ord(s) for s in payload]
        self._cs.value(0)
        self._spi.write(bytearray([register | 0x80] + payload))
        self._cs.value(1)

    def _spi_read(self, register, length=1):
        self._cs.value(0)
        if length == 1:
            data = self._spi.read(length + 1, register)[1]
        else:
            data = self._spi.read(length + 1, register)[1:]
        self._cs.value(1)
        return data

    # Resetting
    def _reset(self):
        gpio_reset = Pin(self._reset_pin, Pin.OUT)
        gpio_reset.value(0)
        sleep(0.01)
        gpio_reset.value(1)
        sleep(0.01)
    
    # Encrypting and Decrypting
    def _decrypt(self, message):
        decrypted_msg = self.crypto.decrypt(message)
        msg_length = decrypted_msg[0]
        return decrypted_msg[1:msg_length + 1]

    def _encrypt(self, message):
        msg_length = len(message)
        padding = bytes(((ceil((msg_length + 1) / 16) * 16) - (msg_length + 1)) * [0])
        msg_bytes = bytes([msg_length]) + message + padding
        encrypted_msg = self.crypto.encrypt(msg_bytes)
        return encrypted_msg

    # Channel activity detection
    def _is_channel_active(self):
        self._set_mode_cad()
        while self._mode == MODE_CAD:  # wait for _handle_interrupt to switch the mode
            yield
        return self._cad
    
    def _wait_cad(self):
        if not self.cad_timeout:
            return True
        start = time()
        for status in self._is_channel_active():
            if time() - start < self.cad_timeout:
                return False
            if status is None:
                sleep(0.1)
                continue
            else:
                return status

    # Sending utils
    def _wait_packet_sent(self):
        start = time()
        while time() - start < self.wait_packet_sent_timeout:
            if self._mode != MODE_TX:  # wait for _handle_interrupt to switch the mode
                return True
        return False

    # Receiving utils
    def _receive_timeout(self, receive_acknowledgements):
        payload = None
        self._set_mode_rx()
        start = time()
        while time() - start < self.receive_timeout + (self.receive_timeout * (getrandbits(16) / (2**16 - 1))):
            if self._new_payload:
                payload = self._last_payload
                self._new_payload = False
                if receive_acknowledgements and self._is_acknowledgement(payload):
                    break 
                elif not receive_acknowledgements and self._is_of_interest(payload):
                    self._acknowledge(payload)
                    break
                else:  # Continue listening
                    payload = None
                    self._set_mode_rx()
        self._set_continuous_mode()
        return payload

    def _is_acknowledgement(self, payload):
        return payload.header_flags & FLAGS_ACK and payload.header_to == self.address and not payload.header_to == BROADCAST_ADDRESS and payload.header_id == self._last_header_id

    def _is_of_interest(self, payload):
        return not payload.header_flags & FLAGS_ACK and (payload.header_to == self.address or payload.header_to == BROADCAST_ADDRESS or self.receive_all is True)

    def _acknowledge(self, payload):
        if self.acknowledge and payload.header_to == self.address and not payload.header_flags & FLAGS_ACK:
            self.send(b'!', payload.header_from, payload.header_id, FLAGS_ACK)

    # Interrupt handler
    def _handle_interrupt(self, channel):
        irq_flags = self._spi_read(REG_12_IRQ_FLAGS)
        # print("In _handle_interrupt() MODE: {:02x} FLAGS: {:02x}".format(self._mode, irq_flags))
        if self._mode == MODE_RXCONTINUOUS and (irq_flags & RX_DONE):
            self._set_mode_idle()
            schedule(self._prepare_payload_ref, 0)
        elif self._mode == MODE_TX and (irq_flags & TX_DONE):
            self._set_continuous_mode()
        elif self._mode == MODE_CAD and (irq_flags & CAD_DONE):
            self._cad = irq_flags & CAD_DETECTED
            self._set_continuous_mode()
        self._spi_write(REG_12_IRQ_FLAGS, 0xff)  # Clear all IRQ flags
        
    def _prepare_payload(self, _):
        packet_len = self._spi_read(REG_13_RX_NB_BYTES)
        self._spi_write(REG_0D_FIFO_ADDR_PTR, self._spi_read(REG_10_FIFO_RX_CURRENT_ADDR))
        packet = self._spi_read(REG_00_FIFO, packet_len)
        snr = self._spi_read(REG_19_PKT_SNR_VALUE) / 4
        rssi = self._spi_read(REG_1A_PKT_RSSI_VALUE)
        if snr < 0:
            rssi = snr + rssi
        else:
            rssi = rssi * 16 / 15
        if self._freq >= 779:
            rssi = round(rssi - 157, 2)
        else:
            rssi = round(rssi - 164, 2)
        if packet_len >= 4:
            header_to = packet[0]
            header_from = packet[1]
            header_id = packet[2]
            header_flags = packet[3]
            message = bytes(packet[4:]) if packet_len > 4 else b''
            if self.crypto and len(message) % 16 == 0:
                message = self._decrypt(message)
            self._last_payload = namedtuple(
                "Payload",
                ['message', 'header_to', 'header_from', 'header_id', 'header_flags', 'rssi', 'snr']
                )(message, header_to, header_from, header_id, header_flags, rssi, snr)    
            self._new_payload = True
            if self._receive_continuously and not header_flags & FLAGS_ACK:
                self._data_cache.append(self._last_payload)
                self._acknowledge(self._last_payload)
        self._set_continuous_mode()
