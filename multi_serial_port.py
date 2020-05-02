import datetime
import time
import struct
import logging
import argparse
import subprocess
import os
import yaml
import collections

from PyCRC.CRC16 import CRC16
import serial

from simpledude import SimpleDude
from nbstreamreader import NonBlockingStreamReader as NBSR

PACKET_HEADER = b'\x08\x70'
NODE_ID = 1
MAX_PAYLOAD_SIZE = 13
MAX_PACKET_SIZE = 8 + MAX_PAYLOAD_SIZE  # 2 HEADER + 2 SOURCE + 2 DEST + 2 CRC
PACKET_TIMEOUT = 0.5

#PORTS = ['COM1', 'COM2']
PORTS = ['COM13']

BASEDIR = os.path.dirname(__file__)
if os.name == 'nt':
    AVRDUDE = BASEDIR + "/avrdude/win/avrdude.exe"
    #    AVRDUDE = "C:\\sloeber\\arduinoPlugin\\packages\\arduino\\tools\\avrdude\\6.3.0-arduino14\\bin\\avrdude.exe"
    AVRCONF = BASEDIR + "/avrdude/win/avrdude.conf"
else:
    AVRDUDE = BASEDIR + "/avrdude/linux/avrdude"
    AVRCONF = BASEDIR + "/avrdude/linux/avrdude.conf"

CONFIG = BASEDIR + "./ms-config.yaml"
AVRCMD = "{} -c USBasp -p m168p -C {}".format(AVRDUDE, AVRCONF)

QUERIES = {
    "ACK": 0x7e,
    "START": 0x80,
    "PING": 0x81,
    "PROGRAM": 0x82,
    "STANDBY": 0x83,
    "RUN": 0x84,
    "SETID": 0x85,
    "CONFIG": 0x88,
    "HUB": 0x89,
    "MEM": 0x90,
    "LCDCLEAR": 0x91,
    "LCDPRINT": 0x92,
    "LCDWRITE": 0x93,
    "LCDINIT": 0x94,
    "HBT": 0x9f,
    "DHT": 0xA0,
    "EMS": 0xA1,
    "BINARY_OUT": 0xA2,
    "SWITCH": 0xA3,
    "LIGHT": 0xA4,
    "PIR": 0xA5,
    "LUX": 0xA6,
    "OUT": 0xA7,
    0x7e: "ACK",
    0x80: "START",
    0x81: "PING",
    0x82: "PROGRAM",
    0x83: "STANDBY",
    0x84: "RUN",
    0x85: "SETID",
    0x88: "CONFIG",
    0x89: "HUB",
    0x90: "MEM",
    0x91: "LCDCLEAR",
    0x92: "LCDPRINT",
    0x93: "LCDWRITE",
    0x94: "LCDINIT",
    0x9f: "HBT",
    0xA0: "DHT",
    0xA1: "EMS",
    0xA2: "BINARY_OUT",
    0xA3: "SWITCH",
    0xA4: "LIGHT",
    0xA5: "PIR",
    0xA6: "LUX",
    0xA7: "OUT",
}

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


class Packet(object):
    def __init__(self, data=None, source=1, dest=255):
        self.header = PACKET_HEADER
        self.source = source
        self.dest = dest
        self.data = data
        self.crc = None

    def CRC(self, data):
        return CRC16(modbus_flag=True).calculate(bytes(data)).to_bytes(2, byteorder='little')

    @staticmethod
    def _serialize(data):
        if isinstance(data, bytes) or isinstance(data, bytearray):
            ret = data
        else:
            ret = bytes([data])
        return ret

    def deserialize(self, data):
        self.source = struct.unpack("H", data[0:2])[0]
        self.dest = struct.unpack("H", data[2:4])[0]
        self.data = data[4:-2] if data is not None else 0
        self.crc = data[-2:]
        return self

    def serialize(self):
        r = self.header
        r += struct.pack('H', self.source)
        r += struct.pack('H', self.dest)
        r += self.data + bytes(MAX_PAYLOAD_SIZE - len(self.data))
        r += self.CRC(r)
        return r


def parse_packet(packet):
    try:
        if packet.data[0] not in QUERIES:
            # self.logger.error("Error packet: %s", packet.serialize(), extra=self.logextra)
            return 0
        # self.logger.info("Parsing command %s", QUERIES[packet.data[0]])
        value = {'type': "->HUB",
                 'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                 'node': packet.source,
                 'msg': QUERIES[packet.data[0]],
                 'reply': bytes([QUERIES['ACK'], ])}
        if value['msg'] == "MEM":
            value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
        # elif value['msg'] == "EMS":  # ems
        #     value.update({'value': struct.unpack("ff", packet.data[1:8])})
        elif value['msg'] == "DHT":  # TEMP & HUM
            value.update({'temperature': struct.unpack("h", packet.data[1:3])[0] / 10.0,
                          'humidity': struct.unpack("h", packet.data[3:5])[0] / 10.0})
        elif value['msg'] == "PIR":
            value.update({'value': struct.unpack("b", packet.data[1:2])[0]})
        elif value['msg'] == "LUX":
            value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
        elif value['msg'] == "SWITCH":
            state = list(packet.data[1:7])
            value.update({'state': state})
            # if packet.source == 3 or packet.source == 5:
            #    self.send(4, bytearray((QUERIES["LIGHT"], state[0], 0, 0)))
        elif value['msg'] == "LIGHT":
            value.update({'state': list(packet.data[1:12])})
        elif value['msg'] == "HBT":
            pass
        # elif packet.data[0] == QUERIES["PROGRAM"]:
        #     dude = SimpleDude(self.port,
        #                       hexfile=self.hexfile,
        #                       mode485=True)
        #     dude.program()
        LOGGER.info(value)
    except Exception as e:
        raise Exception(f'{e} - {value}')
    return value


def check_msg(data):
    if len(data) == MAX_PACKET_SIZE - 2:
        a = Packet().deserialize(data)
        if a.crc == a.CRC(PACKET_HEADER + data[:-2]):
            if a.dest == NODE_ID:
                if data != 0:
                    return a
                LOGGER.error("Packet is unrecognized")
            else:
                LOGGER.error("Destination error.")
        else:
            LOGGER.debug("CRC error.")
    else:
        LOGGER.debug("Message incomplete.")
    return None


def shell(command, work_dir=""):
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE,
                         shell=True,
                         )
    out = NBSR(p.stdout)
    err = NBSR(p.stderr)
    while p.poll() is None:
        output = out.readline(0.01)
        error = err.readline(0.01)
        if output:
            print(output.decode("UTF-8"), end="")
        if error:
            print(error.decode("UTF-8"), end="")


def compile_bootloader(make, env, address, workdir):
    make = f"{make} " \
        f"ENV={env} BAUD_RATE=38400 LED=D2 LED_START_FLASHES=5 " \
        f"SN_MAJOR={address // 0xff} SN_MINOR={address % 0xff} pro8"
    #        cp_command = "cp" if os.name == "posix" else "copy"
    #        cp = "{} {} {}".format(cp_command, source, destination)
    shell("{make}", work_dir=workdir)


def flash_bootloader(bootloader):
    shell(AVRCMD + f" -u -U flash:w:\"{bootloader}\":i -vv")


def update_fuses(low=0xDE, high=0xDC, extend=0xFA):
    shell(AVRCMD + f" -U lfuse:w:{low}:m -U hfuse:w:{high}:m -U efuse:w:{extend}:m")


def mdelay(value):
    """ Delay in milliseconds"""
    if value > 200:
        raise BaseException(f"{value} too long for udelay. Max value accepted is 200!")
    start = time.time()
    while time.time() < (start + (value / 1000)):
        pass
    return time.time()


def prepare_commands(commands={}):
    def append(msg, packets):
        if len(msg) < MAX_PAYLOAD_SIZE:
            if not type(msg["id"]) is int :
                msg["id"] = config[msg["id"]]['net']
            packets.append(Packet(msg["cmd"], dest=msg["id"]))
        else:
            LOGGER.critical(f"The command exceeds the maximum size of {MAX_PAYLOAD_SIZE} characters.")

    def parse_cmd(msg):
        packets = collections.deque()

        if type(msg) is dict:
            for k1, v1 in msg.items():  # command with 1 arg
                if type(v1) is dict:
                    for k2, v2 in v1.items():  # series of commands with 1 arg
                        append({"id": k, "cmd": bytearray((QUERIES[k1], QUERIES[k2], v2))}, packets)
                else:
                    if type(v1) is list:
                        append({"id": k, "cmd": bytearray([QUERIES[k1], ] + v1)}, packets)
                    else:
                        append({"id": k, "cmd": bytearray([QUERIES[k1], v1])}, packets)
        else:
            append({"id": k, "cmd": bytearray([QUERIES[msg], ])}, packets)
        return packets

    packet_queue = collections.deque()
    for k, v in commands.items():  # simple commands
        if type(v) is list:
            for cmd in v:
                packet_queue.extend(parse_cmd(cmd))
        else:
            if type(v) is dict:
                packet_queue.extend(parse_cmd(v))
            else:
                append({"id": k, "cmd": bytearray([QUERIES[v], ])}, packet_queue)
    return packet_queue


def execute(value):
    cmds = collections.deque()
    node_command = config[net_reverseid[value['node']]].get(value['msg'])
    if node_command:
        if value['msg'] == 'SWITCH':
            for idx, switch in enumerate(value['state']):
                if switch == 1:
                    for light in node_command.get(idx + 1, []):
                        cmds.extend(prepare_commands(light))
    return cmds


net_reverseid = dict()
with open(CONFIG) as f:
    config = yaml.load(f, Loader=yaml.FullLoader)
for k, v in config.items():
    net_reverseid[v['net']] = k


def run(packets_to_send=None, com_ports=PORTS, delay_send_s=0, delay_retry_ms=10, timeout=PACKET_TIMEOUT):
    packets_queue = collections.deque()
    if packets_to_send:
        packets_queue.extend(packets_to_send)
    ports = list()
    if type(com_ports) is list:
        for port in com_ports:
            ports.append(serial.serial_for_url(port, baudrate=38400, timeout=0.1))
    else:
        ports = [serial.serial_for_url(com_ports, baudrate=38400, timeout=0.1)]
    sent_packet = None
    sent_timeout = 0
    sent_again = 0
    buffer = b''
    while True:
        for port in ports:
            # buffer = port.read_all()
            # if buffer:
            buffer += port.read_all()
            if buffer.find(PACKET_HEADER) >= 0 and len(buffer) >= MAX_PACKET_SIZE:
                for msg in buffer.split(PACKET_HEADER)[1:]:
                    received = check_msg(msg)
                    if received:
                        result = parse_packet(received)
                        if not sent_packet or \
                                (sent_packet.dest, sent_packet.data[0]) != (received.source, received.data[0]):
                            packet = Packet(result['reply'], dest=received.source)
                            port.write(packet.serialize())
                            value = {'type': "HUB->",
                                     'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                     'node': packet.dest,
                                     'msg': QUERIES[packet.data[0]],
                                     'data': packet.data[1:]
                                     }
                            LOGGER.info(value)
                            packets_queue.extend(execute(result))
                        else:
                            # Got a Reply for a previous write from this node
                            sent_packet = None
                            sent_again = 0
                buffer = b''
            if port.inWaiting() == 0:
                if sent_packet:
                    if time.time() - sent_timeout < timeout:
                        # This packet has not reached destination so retry to send it
                        mdelay(delay_retry_ms)
                        port.write(sent_packet.serialize())
                        sent_again += 1
                        value = {'type': f"HUB->+{sent_again}",
                                 'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                 'node': sent_packet.dest,
                                 'msg': QUERIES[sent_packet.data[0]],
                                 'data': sent_packet.data[1:]
                                 }
                        LOGGER.debug(value)
                    else:
                        value = {'type': "HUB->TIMEOUT",
                                 'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                 'node': sent_packet.dest,
                                 'msg': QUERIES[sent_packet.data[0]],
                                 'data': sent_packet.data[1:]
                                 }
                        LOGGER.info(value)
                        sent_packet = None
                        sent_again = 0
                elif packets_queue:
                    # If all packets has reached destination pop another one from queue
                    if delay_send_s:
                        time.sleep(delay_send_s)

                    sent_packet = packets_queue.pop()
                    port.write(sent_packet.serialize())
                    value = {'type': "HUB->",
                             'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                             'node': sent_packet.dest,
                             'msg': QUERIES[sent_packet.data[0]],
                             'data': sent_packet.data[1:]
                             }
                    LOGGER.info(value)
                    sent_timeout = time.time()


if __name__ == "__main__":
    cmds = collections.deque()

    #    LOGGER.setLevel(logging.DEBUG)
    # cmds.extend(prepare_commands({"CU-1M": {"CONFIG": {"SWITCH": 1}}}))
    # cmds.extend(prepare_commands({"CU-1M": {"CONFIG": {"HBT": 0}}}))
    # cmds.extend(prepare_commands({"CU-9": {"CONFIG": {"HBT": 0}}}))
    # cmds.extend(prepare_commands({"CU-8": {"CONFIG": {"SWITCH": 1}}}))
    # cmds.extend(prepare_commands({"SC-1": {"CONFIG": {"HBT": 0}}}))
    # cmds.extend(prepare_commands({"LIGHT1": {"CONFIG": {"HBT": 0}}}))
    # cmds.extend(prepare_commands({"SA-2": {"CONFIG": {"HBT": 0}}}))
    # cmds.extend(prepare_commands({"C2-4": {"CONFIG": {"HBT": 0}}}))
    # cmds.extend(prepare_commands({"C2-3H": {"CONFIG": {"HBT": 0}}}))
    cmds.extend(prepare_commands({"LIGHT1": {"LIGHT": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}}))
    # cmds.extend(prepare_commands({"LIGHT1": "MEM"}))
    parser = argparse.ArgumentParser()
    parser.add_argument("-L", "--loop", action="store_true", help="Run Domuino loop")
    parser.add_argument("-S", "--scan", action="store_true", help="Scan Domuino net")
    parser.add_argument('-C', "--config", action="store_true", help="Upload configuration to nodes")
    parser.add_argument("-p", "--ports", help="Communication ports")
    args = parser.parse_args()

    com_ports = args.ports if args.ports else PORTS
    if args.loop:
        run(packets_to_send=cmds, com_ports=com_ports)
    if args.config:
        for k, v in config.items():
            parameters = v.get('config')
            if parameters:
                cmds.extend(prepare_commands({k: {"CONFIG": parameters}}))
        run(packets_to_send=cmds, com_ports=com_ports)
    elif args.scan:
        for i in net_reverseid.keys():
            cmds.extend(prepare_commands({i: "MEM"}))
        run(packets_to_send=cmds, com_ports=com_ports)
