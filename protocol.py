import datetime
import time
import struct
import logging
import argparse
import subprocess
import os
import yaml
import collections
import ast

from PyCRC.CRC16 import CRC16
import serial

from simpledude import SimpleDude
from nbstreamreader import NonBlockingStreamReader as NBSR


PACKET_HEADER = b'\x08\x70'
NODE_ID = 1
MAX_PAYLOAD_SIZE = 13
MAX_PACKET_SIZE = 8 + MAX_PAYLOAD_SIZE  # 2 HEADER + 2 SOURCE + 2 DEST + 2 CRC
PACKET_TIMEOUT = 1
SEND_RETRY = 3

BASEDIR = os.path.dirname(__file__)
if os.name == 'nt':
    AVRDUDE = BASEDIR + "/avrdude/win/avrdude.exe"
    #    AVRDUDE = "C:\\sloeber\\arduinoPlugin\\packages\\arduino\\tools\\avrdude\\6.3.0-arduino14\\bin\\avrdude.exe"
    AVRCONF = BASEDIR + "/avrdude/win/avrdude.conf"
else:
    AVRDUDE = BASEDIR + "/avrdude/linux/avrdude"
    AVRCONF = BASEDIR + "/avrdude/linux/avrdude.conf"

CONFIG = BASEDIR + "/ms-config.yaml"
DOMUINO_SOFTWARE = "/home/sebastiano/Documents/sloeber-workspace/domuino/Release/domuino.hex"

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
    "VERSION": 0x94,
    "HBT": 0x9f,
    "DHT": 0xA0,
    "EMS": 0xA1,
    "BINARY_OUT": 0xA2,
    "SWITCH": 0xA3,
    "LIGHT": 0xA4,
    "PIR": 0xA5,
    "LUX": 0xA6,
    "LCD": 0xA7,
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
    0x94: "VERSION",
    0x9f: "HBT",
    0xA0: "DHT",
    0xA1: "EMS",
    0xA2: "BINARY_OUT",
    0xA3: "SWITCH",
    0xA4: "LIGHT",
    0xA5: "PIR",
    0xA6: "LUX",
    0xA7: "LCD",
}

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

NET_REVERSEID = dict()
NET_ID = dict()
with open(CONFIG) as f:
    NET_CONFIG = yaml.load(f, Loader=yaml.FullLoader)

# DEVICES = dict()

for port, config in NET_CONFIG.items():
    for dest, settings in config.items():
        if settings.get('config'):
            if settings['config'].get('LIGHT'):
                NET_CONFIG[port][dest]['state'] = [0] * 11
        NET_ID[dest] = settings['net']
        NET_REVERSEID[settings['net']] = dest
        # if settings.get('lights'):
        #     DEVICES['LIGHT'] = settings['lights']
    NET_CONFIG[port]['writer'] = None
    NET_CONFIG[port]['reader'] = None


def get_device(name):
    device = dict()
    for value in NET_CONFIG.values():
        device = value.get(name)
        if device is not None:
            break
    return device


class Packet(object):
    def __init__(self, data=None, source=1, dest=255, bus=None):
        self.header = PACKET_HEADER
        self.bus = bus
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
        if len(data) == MAX_PACKET_SIZE - 2:
            self.source = struct.unpack("H", data[0:2])[0]
            self.dest = struct.unpack("H", data[2:4])[0]
            self.data = data[4:-2] if data is not None else 0
            self.crc = data[-2:]

            if self.crc == self.CRC(PACKET_HEADER + data[:-2]):
                if self.dest == NODE_ID:
                    if data != 0:
                        return self
                    LOGGER.error("Packet is unrecognized.")
                else:
                    LOGGER.error("Destination error.")
            else:
                LOGGER.debug("CRC error.")
        else:
            LOGGER.debug("Message incomplete.")
        return None

    def serialize(self):
        r = self.header
        r += struct.pack('H', self.source)
        r += struct.pack('H', self.dest)
        r += self.data + bytes(MAX_PAYLOAD_SIZE - len(self.data))
        r += self.CRC(r)
        return r


def parse_packet(packet):
    try:
        if packet is None or packet.data[0] not in QUERIES:
            # self.logger.error("Error packet: %s", packet.serialize(), extra=self.logextra)
            return None
        # self.logger.info("Parsing command %s", QUERIES[packet.data[0]])
        value = {'type': f"{packet.source}->{packet.dest}",
                 'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                 'node': packet.source,
                 'msg': QUERIES[packet.data[0]],
                 'reply': bytes([QUERIES['ACK'], ])}
        if value['msg'] == "MEM":
            value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
        # elif value['msg'] == "EMS":  # ems
        #     value.update({'value': struct.unpack("ff", packet.data[1:8])})
        elif value['msg'] == "DHT":  # TEMP & HUM
            temperature = struct.unpack("h", packet.data[1:3])[0] / 10.0
            humidity = struct.unpack("h", packet.data[3:5])[0] / 10.0
            value.update({'temperature': temperature if temperature < 60.0 else 60.0,
                          'humidity': humidity if humidity < 100.0 else 100.0})
        elif value['msg'] == "PIR":
            value.update({'value': struct.unpack("b", packet.data[1:2])[0]})
        elif value['msg'] == "LUX":
            value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
        elif value['msg'] == "SWITCH":
            value.update({'state': list(packet.data[1:7])})
        elif value['msg'] == "LIGHT":
            device = get_device(NET_REVERSEID[packet.source])
            device['state'] = list(packet.data[1:12])
            value.update({'state': device['state']})
        elif value['msg'] == "HBT":
            pass
        elif value['msg'] == "VERSION":
            value.update({'version': struct.unpack("h", packet.data[1:3])[0]})
        elif value['msg'] == "PROGRAM":
            dude.program()
        LOGGER.info(value)
    except Exception as e:
        raise Exception(f'PARSE: {e} - {packet.serialize()}')
    return value


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


# def mdelay(value):
#     """ Delay in milliseconds"""
#     if value > 200:
#         raise BaseException(f"{value} too long for udelay. Max value accepted is 200!")
#     start = time.time()
#     while time.time() < (start + (value / 1000)):
#         pass
#     return time.time()


def prepare_commands(dest, commands, format_values={}):
    def append(msg, packets):
        if len(msg) < MAX_PAYLOAD_SIZE:
            if not type(msg["id"]) is int:
                msg["id"] = NET_ID[msg["id"]]
            packets.append(Packet(msg["cmd"], dest=msg["id"]))
        else:
            LOGGER.critical(f"The command exceeds the maximum size of {MAX_PAYLOAD_SIZE} characters.")

    def parse_cmd(msg, packets):
        if type(msg) is dict:
            for k1, v1 in msg.items():  # command with 1 arg
                device = get_device(dest)
                if device["config"].get("LIGHT", 0) and type(v1) is str:
                    v1 = device.get("lights", {}).get(v1, [0] * 11)

                if format_values:
                    v1 = ast.literal_eval(str(v1).format(**format_values))
                if type(v1) is dict:
                    for k2, v2 in v1.items():  # series of commands with 1 arg
                        append({"id": dest, "cmd": bytearray((QUERIES[k1], QUERIES[k2], v2))}, packets)
                else:
                    if type(v1) is list:
                        args = b"".join([bytes([i]) if type(i) is int else bytearray(i, "UTF-8") for i in v1])
                        append({"id": dest, "cmd": bytearray([QUERIES[k1]]) + args}, packets)
                    else:
                        append({"id": dest, "cmd": bytearray([QUERIES[k1], v1])}, packets)
        else:
            append({"id": dest, "cmd": bytearray([QUERIES[msg], ])}, packets)
        return packets

    packet_queue = collections.deque()
    try:
        # for cmd in commands:
        #     parse_cmd(cmd, packet_queue)

        if type(commands) is dict:
            parse_cmd(commands, packet_queue)
        else:
            if type(commands) is list:
                for cmd in commands:
                    parse_cmd(cmd, packet_queue)
            else:
                append({"id": dest, "cmd": bytearray([QUERIES[commands], ])}, packet_queue)
    except Exception as e:
        LOGGER.error(f"PREPARE: {e}")

    return packet_queue


def execute(value):
    cmds = collections.deque()
    for config in NET_CONFIG.values(): # todo:ottimizzare
        node = config.get(NET_REVERSEID.get(value.get('node')), None)
        if node:
            break
    if node:
        try:
            node_commands = node.get(value['msg'])
            if value['msg'] == 'SWITCH':
                for idx, switch in enumerate(value['state'], 1):
                    if switch == 1:
                        for commands in node_commands.get(idx, []):
                            for dest, cmd in commands.items():
                                cmds.extend(prepare_commands(dest, cmd))
            elif value['msg'] == 'DHT':
                if type(node_commands) is dict:
                    dest = list(node_commands.keys())[0]
                    cmds.extend(prepare_commands(dest, node_commands.get(dest), value))
                else:
                    for commands in node_commands:
                        for dest, cmd in commands.items():
                            cmds.extend(prepare_commands(dest, cmd, value))
        except Exception as e:
            LOGGER.critical(f"EXECUTE: {e}")
            value.update({'type': "[UNCONFIGURED]->HUB",
                          'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
    else:
        value.update({'type': "[UNKNOWN]->HUB",
                      'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
        LOGGER.error(value)
    return cmds


# todo: sezione update software domuino da sistemare
dude = None

# TODO: Gestire eventuali segmentation fault, vedi sotto
# Mar 05 02:09:10 orangepipc kernel: Modules linked in: npreal2(O) zstd zram snd_soc_hdmi_codec sun4i_i2s mt7601u sun8i_codec_analog sun8i_adda_pr_regmap snd_s
# Mar 05 02:09:10 orangepipc kernel: CPU: 3 PID: 947 Comm: python3 Tainted: G           O      4.19.62-sunxi #5.92
# Mar 05 02:09:10 orangepipc kernel: Hardware name: Allwinner sun8i Family
# Mar 05 02:09:10 orangepipc kernel: PC is at 0xebb4c0c0
# Mar 05 02:09:10 orangepipc kernel: LR is at tty_ioctl+0x35/0x88c
# Mar 05 02:09:10 orangepipc kernel: pc : [<ebb4c0c0>]    lr : [<c0603859>]    psr: 600f0013
# Mar 05 02:09:10 orangepipc kernel: sp : ebba1e6c  ip : 00000003  fp : 00000080
# Mar 05 02:09:10 orangepipc kernel: r10: 00000036  r9 : bed9a04c  r8 : c0e04d48
# Mar 05 02:09:10 orangepipc kernel: r7 : ebb4c0c0  r6 : c0e04d48  r5 : 0000541b  r4 : ed04d600
# Mar 05 02:09:10 orangepipc kernel: r3 : 8801183c  r2 : c0bd8440  r1 : ed625c30  r0 : 00000000
# Mar 05 02:09:10 orangepipc kernel: Flags: nZCv  IRQs on  FIQs on  Mode SVC_32  ISA ARM  Segment none
# Mar 05 02:09:10 orangepipc kernel: Control: 50c5387d  Table: 6bbe406a  DAC: 00000051
# Mar 05 02:09:10 orangepipc kernel: Process python3 (pid: 947, stack limit = 0xc6ec9119)
# Mar 05 02:09:10 orangepipc domuino.sh[944]: Segmentation fault
# Mar 05 02:09:10 orangepipc systemd[1]: domuino.service: Main process exited, code=exited, status=139/n/a
# Mar 05 02:09:10 orangepipc systemd[1]: domuino.service: Failed with result 'exit-code'.
