#!/usr/bin/python

# import libraries
import logging
import time
from serial import rs485

STK_OK = 0x10
STK_FAILED = 0x11  # Not used
STK_UNKNOWN = 0x12  # Not used
STK_NODEVICE = 0x13  # Not used
STK_INSYNC = 0x14  # ' '
STK_NOSYNC = 0x15  # Not used
ADC_CHANNEL_ERROR = 0x16  # Not used
ADC_MEASURE_OK = 0x17  # Not used
PWM_CHANNEL_ERROR = 0x18  # Not used
PWM_ADJUST_OK = 0x19  # Not used
CRC_EOP = 0x20  # 'SPACE'
STK_GET_SYNC = 0x30  # '0'
STK_GET_SIGN_ON = 0x31  # '1'
STK_SET_PARAMETER = 0x40  # '@'
STK_GET_PARAMETER = 0x41  # 'A'
STK_SET_DEVICE = 0x42  # 'B'
STK_SET_DEVICE_EXT = 0x45  # 'E'
FLASH_MEMORY = 0x46  #'F'
STK_ENTER_PROGMODE = 0x50  # 'P'
STK_LEAVE_PROGMODE = 0x51  # 'Q'
STK_CHIP_ERASE = 0x52  # 'R'
STK_CHECK_AUTOINC = 0x53  # 'S'
STK_LOAD_ADDRESS = 0x55  # 'U'
STK_UNIVERSAL = 0x56  # 'V'
STK_PROG_FLASH = 0x60  # '`'
STK_PROG_DATA = 0x61  # 'a'
STK_PROG_FUSE = 0x62  # 'b'
STK_PROG_LOCK = 0x63  # 'c'
STK_PROG_PAGE = 0x64  # 'd'
STK_PROG_FUSE_EXT = 0x65  # 'e'
STK_READ_FLASH = 0x70  # 'p'
STK_READ_DATA = 0x71  # 'q'
STK_READ_FUSE = 0x72  # 'r'
STK_READ_LOCK = 0x73  # 's'
STK_READ_PAGE = 0x74  # 't'
STK_READ_SIGN = 0x75  # 'u'
STK_READ_OSCCAL = 0x76  # 'v'
STK_READ_FUSE_EXT = 0x77  # 'w'
STK_READ_OSCCAL_EXT = 0x78  # 'x'
STK_HARDWARE = 0x80  # ' '
STK_SW_MAJOR = 0x81  # ' '
STK_SW_MINOR = 0x82  # ' '

SYNC = [STK_GET_SYNC, CRC_EOP]
ENTER_PROG_MODE = [STK_ENTER_PROGMODE, CRC_EOP]
EXIT_PROG_MODE = [STK_LEAVE_PROGMODE, CRC_EOP]
GET_HARDWARE = [STK_GET_PARAMETER, STK_HARDWARE, CRC_EOP]
GET_SW_MAJOR = [STK_GET_PARAMETER, STK_SW_MAJOR, CRC_EOP]
GET_SW_MINOR = [STK_GET_PARAMETER, STK_SW_MINOR, CRC_EOP]
GET_SAFE_LFUSE = [STK_UNIVERSAL, 0x50, 0x00, 0x00, 0x00, CRC_EOP]
GET_SAFE_HFUSE = [STK_UNIVERSAL, 0x58, 0x08, 0x00, 0x00, CRC_EOP]
GET_SAFE_EFUSE = [STK_UNIVERSAL, 0x50, 0x08, 0x00, 0x00, CRC_EOP]
GET_SIGNATURE = [STK_READ_SIGN, CRC_EOP]
INSINK = [STK_INSYNC, STK_OK]

logging.basicConfig(format='%(message)s', level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


class SimpleDude(object):
    def __init__(self, sock, retry=9, hexfile="", mode485=False):
        self.sock = sock
        self.hexfile = hexfile
        self.retry = retry
        self.mode485 = mode485

    def spi_transaction(self, codes, bytesreply=0):
        n = 0
        retry = True
        tx_complete = len(codes) * 0.53 + 1
        while retry:
            _LOGGER.debug("Send %s", [hex(b) for b in codes])
            time.sleep(0.01)
            self.sock.setRTS(False)
            tx_start = time.time()
            self.sock.write(codes)
            while (time.time() - tx_start) < (tx_complete / 1000.0):
                pass
            self.sock.setRTS(True)
            _LOGGER.debug("Wait for reply")
            # Wait for bytesreply + INSYNC + OK
            reply = list(self.sock.read(size=bytesreply + 2))
            _LOGGER.debug("Received %s", [hex(b) for b in reply])
            if not reply or ([reply[0], reply[-1:][0]] != INSINK):
                if n < self.retry:
                    n += 1
                    _LOGGER.critical("Retry %s", n)
                    continue
                else:
                    _LOGGER.critical("Not in sync")
                    raise BaseException("Not in sync")
            if len(reply) == 3:
                return reply[1]
            elif len(reply) > 3:
                return reply[1:-1]
            return
    
    def sync(self):
        # get in self.sync with the AVR
        for i in range(3):
            _LOGGER.debug("Syncing")
            self.spi_transaction(SYNC)

    def get_info(self):
        self.sync()
    
        # get the MAJOR version of the bootloader
        _LOGGER.debug("Getting the HARDWARE version of arduino")
        hardware = self.spi_transaction(GET_HARDWARE, 1)
    
        _LOGGER.info("Hardware version: %s", hex(hardware))
    
        # get the MAJOR version of the bootloader
        _LOGGER.debug("Getting the MAJOR version of the bootloader")
        major = self.spi_transaction(GET_SW_MAJOR, 1)
    
        # get the MINOR version of the bootloader
        _LOGGER.debug("Getting the MINOR version of the bootloader")
        minor = self.spi_transaction(GET_SW_MINOR, 1)
    
        _LOGGER.info("Bootloader version %s.%s", hex(major), hex(minor))
    
        # enter programming mode
        _LOGGER.debug("Entering programming mode")
        self.spi_transaction(ENTER_PROG_MODE)
    
        # get device signature
        _LOGGER.debug("Getting device signature")
        signature = self.spi_transaction(GET_SIGNATURE, 3)
    
        _LOGGER.info("Device signature %s-%s-%s", hex(signature[0]), hex(signature[1]), hex(signature[2]))
    
        _LOGGER.debug("Get safe fuses")
        lfuse = self.spi_transaction(GET_SAFE_LFUSE, 1)
        hfuse = self.spi_transaction(GET_SAFE_HFUSE, 1)
        efuse = self.spi_transaction(GET_SAFE_EFUSE, 1)
    
        _LOGGER.info("FUSES E:%s H:%s L:%s", hex(efuse), hex(hfuse), hex(lfuse))
    
        # leave programming mode
        _LOGGER.debug("Leaving programming mode")
        self.spi_transaction(EXIT_PROG_MODE)
    
    def program(self):
        self.sync()
        # enter programming mode
        _LOGGER.debug("Entering programming mode")
        self.spi_transaction(ENTER_PROG_MODE)
    
        # start with page address 0
        address = 0
    
        # open the hex file
    
        with open(self.hexfile, "rb") as hexfile:
            while True:
                # calculate page address
                laddress = address % 256
                haddress = int(address / 256)
                address += 64
    
                # load page address
                _LOGGER.debug("Sending page address")
                self.spi_transaction([STK_LOAD_ADDRESS, laddress, haddress, CRC_EOP])
    
                data = list()
                # the hex in the file is represented in char
                # so we have to merge 2 chars into one byte
                # 16 bytes in a line, 16 * 8 = 128
                for i in range(8):
                    # just take the program data
                    hexrow = hexfile.readline()[9:][:-4]
                    data.extend([int(hexrow[b:b + 2], 16) for b in range(len(hexrow))[::2]])
    
                # half the size
                size = len(data)
                _LOGGER.info("Sending program page to write %s laddress %s haddress %s", size, laddress, haddress)
                self.spi_transaction([STK_PROG_PAGE, 0, size, FLASH_MEMORY] + data + [CRC_EOP])
    
                # when the whole program was uploaded
                if size != 0x80:
                    break
        # leave programming mode
        _LOGGER.debug("Leaving programming mode")
        self.spi_transaction(EXIT_PROG_MODE)
    
    def verify(self):
        self.sync()
        # enter programming mode
        _LOGGER.debug("Entering programming mode")
        self.spi_transaction(ENTER_PROG_MODE)
    
        # start with page address 0
        address = 0
    
        # open the hex file
    
        with open(self.hexfile, "rb") as hexfile:
            while True:
                # calculate page address
                laddress = address % 256
                haddress = int(address / 256)
                address += 64
    
                # load page address
                _LOGGER.debug("Sending page address")
                self.spi_transaction([STK_LOAD_ADDRESS, laddress, haddress, CRC_EOP])
    
                data = list()
                # the hex in the file is represented in char
                # so we have to merge 2 chars into one byte
                # 16 bytes in a line, 16 * 8 = 128
                for i in range(8):
                    # just take the program data
                    hexrow = hexfile.readline()[9:][:-4]
                    data.extend([int(hexrow[b:b + 2], 16) for b in range(len(hexrow))[::2]])
    
                size = len(data)
                # half the size
                _LOGGER.info("Reading program page %s:%s", haddress, laddress)
                page = self.spi_transaction([STK_READ_PAGE, 0, 0x80, FLASH_MEMORY, CRC_EOP], 0x80)
    
                if data != page[:len(data)]:
                    _LOGGER.error("Error! Page %s:%s differ from Hex file", haddress, laddress)
                    # leave programming mode
                    _LOGGER.debug("Leaving programming mode")
                    self.spi_transaction(EXIT_PROG_MODE)
                    return False
                if size != 0x80:
                    _LOGGER.info("Program check OK.")
                    # leave programming mode
                    _LOGGER.debug("Leaving programming mode")
                    self.spi_transaction(EXIT_PROG_MODE)
                    return True


if __name__ == '__main__':
    ser = rs485.RS485('/dev/ttyUSB0', baudrate=19200, timeout=2)
    dude = SimpleDude(ser, hexfile="/home/sebastiano/Programs/sloeber/workspace/testportddrb/Release/testportddrb.hex", mode485=True)
    dude.get_info()
    # dude.program()
    # dude.verify()
