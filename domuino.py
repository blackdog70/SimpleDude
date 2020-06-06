# coding=utf8

import argparse
import os
import subprocess

from builtins import bytes

from serial import serial_for_url, rs485
import time
import datetime
import struct
import logging

from simpledude import SimpleDude
from mm485 import DomuNet

import yaml
from nbstreamreader import NonBlockingStreamReader as NBSR, UnexpectedEndOfStream

# define ACK (uint8_t)0x7d
# define ERR (uint8_t)0x7e

BASEDIR = os.path.dirname(__file__)

FORMAT = '%(asctime)-15s %(levelname)-8s [%(module)s:%(funcName)s:%(lineno)s] [%(node)s] : %(message)s'
logging.basicConfig(level=logging.CRITICAL, format=FORMAT)

if os.name == 'nt':
    AVRDUDE = BASEDIR + "/avrdude/win/avrdude.exe"
    #    AVRDUDE = "C:\\sloeber\\arduinoPlugin\\packages\\arduino\\tools\\avrdude\\6.3.0-arduino14\\bin\\avrdude.exe"
    AVRCONF = BASEDIR + "/avrdude/win/avrdude.conf"
else:
    AVRDUDE = BASEDIR + "/avrdude/linux/avrdude"
    AVRCONF = BASEDIR + "/avrdude/linux/avrdude.conf"

AVRCMD = "{} -c USBasp -p m168p -C {}".format(AVRDUDE, AVRCONF)

LOGO = [
    0x08, 0x40,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0xc0, 0xe0, 0xf0, 0xf8, 0xfc, 0xfe, 0xff, 0xff, 0xfe, 0xfc, 0xf8, 0xf0, 0xe0,
    0xc0, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0xc0, 0xe0,
    0xf0, 0xf8, 0xfc, 0xfe, 0xff, 0xff, 0xff, 0xbf, 0x5f, 0x5f, 0x1f, 0xff, 0xff, 0xff, 0xff, 0xff, 0x1f, 0x5f, 0x1f,
    0xff, 0xff, 0xff, 0xfe, 0xfc, 0xf8, 0xf0, 0xe0, 0xfc, 0xfc, 0xfc, 0xfc, 0xfc, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0xc0, 0xe0, 0xf0, 0xf8, 0xfc, 0xfe, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xf8, 0x02, 0x78, 0xff, 0xff, 0x1f, 0x5f, 0x1f, 0xff, 0xfe, 0xfc, 0xf9, 0x03, 0xfd, 0xfe, 0xff, 0x1f, 0x5f,
    0x1f, 0xff, 0xf8, 0x02, 0xf8, 0xff, 0x1f, 0x5f, 0x1f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0xe0, 0xc0, 0x80, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xe7, 0xdb, 0xc7, 0xe6, 0xe4, 0xe1, 0xe3, 0xe0, 0xcf, 0x9f, 0x3f, 0x7f, 0xff, 0x00, 0xff, 0xff, 0xcf, 0x37, 0x87,
    0xfe, 0x7c, 0x39, 0x80, 0xfd, 0xfe, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xf1, 0xf5, 0x71, 0xef, 0xdf, 0xbf, 0x77, 0xeb, 0x0b, 0xe3, 0xfe, 0xfc, 0x00, 0x9f, 0xcf, 0xe7, 0xf0, 0xf9,
    0xf8, 0xfa, 0xfb, 0xfb, 0xfb, 0xfb, 0xf1, 0xed, 0xf1, 0xff, 0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f,
    0x1f, 0x1f, 0x18, 0x1a, 0x18, 0x1d, 0x1d, 0x1d, 0x1c, 0x1c, 0x1b, 0x17, 0x2f, 0x00, 0x07, 0x13, 0x19, 0x1d, 0x1d,
    0x1d, 0x1d, 0x1d, 0x18, 0x1b, 0x1c, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]

# TODO: Test corrispondenza valori TEST == NUMERO
# PARAMETERS MUST BE VALUE <= 0x7f
# PARAMETERS = {
#     "SWITCH": 0x01,
#     "LIGHT": 0x02,
#     "BINARY_OUT": 0x03,
#     "EMS": 0x04,
#     "DHT": 0x05,
#     "PIR": 0x06,
#     "LUX": 0x07,
#     "START": 0x7a,
#     "HBT": 0x7b,
#     "RAM": 0x7c,
#     "PONG": 0x7d,
#     "ACK": 0x7e,
#     "ERR": 0x7f,
#     0x01: "SWITCH",
#     0x02: "LIGHT",
#     0x03: "BINARY_OUT",
#     0x04: "EMS",
#     0x05: "DHT",
#     0x06: "PIR",
#     0x07: "LUX",
#     0x7a: "START",
#     0x7b: "HBT",
#     0x7c: "RAM",
#     0x7d: "PONG",
#     0x7e: "ACK",
#     0x7f: "ERR",
# }
#
# ANSWERS = PARAMETERS

# TODO: Test corrispondenza valori TEST == NUMERO
# QUERIES MUST BE VALUE > 0x7f

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


class Domuino(DomuNet):
    def parse_query(self, packet):
        try:
            if packet.data[0] not in QUERIES:
                self.logger.error("Error packet: %s", packet.serialize(), extra=self.logextra)
                return 0
            msg = bytes([QUERIES['ACK'], ])
            with self.lock:
                # self.logger.info("Parsing command %s", QUERIES[packet.data[0]])
                now = datetime.datetime.now()
                value = {'type': "Query",
                         'time': now.strftime("%d/%m/%Y %H:%M:%S"),
                         'node': packet.source,
                         'msg': QUERIES[packet.data[0]]}
                # value = {'node': packet.source, 'type': QUERIES[packet.data[0]]}
                if packet.data[0] == QUERIES["MEM"]:
                    value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
                elif packet.data[0] == QUERIES['EMS']:  # ems
                    value.update({'value': struct.unpack("ff", packet.data[1:8])})
                elif packet.data[0] == QUERIES['DHT']:  # TEMP & HUM
                    # value.update({'temperature': struct.unpack("h", packet.data[1:3])[0] / 10.0,
                    #               'humidity': struct.unpack("h", packet.data[3:5])[0] / 10.0})
                    pass
                elif packet.data[0] == QUERIES['PIR']:
                    value.update({'value': struct.unpack("b", packet.data[1:2])[0]})
                elif packet.data[0] == QUERIES['LUX']:
                    value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
                elif packet.data[0] == QUERIES["SWITCH"]:
                    state = list(packet.data[1:7])
                    value.update({'state': state})
                    if packet.source == 3 or packet.source == 5:
                       self.send(4, bytearray((QUERIES["LIGHT"], state[0], 0, 0)))
                elif packet.data[0] == QUERIES["HBT"]:
                    pass
            self.logger.info(value, extra=self.logextra)
        except Exception as e:
            raise Exception('{}'.format(value))
        return msg

    def parse_answer(self, packet):
        try:
            # logging.info("Parsing command %s", str(ANSWERS[packet.data[0]]))
            now = datetime.datetime.now()
            value = {'type': "Answer",
                     'time': now.strftime("%d/%m/%Y %H:%M:%S"),
                     'node': packet.source,
                     'msg': QUERIES[packet.data[0]]}
            if packet.data[0] == QUERIES["MEM"]:
                value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
            # elif packet.data[0] == QUERIES['START']:
            #     # value.update({'value': struct.unpack("h", packet.data[1:3])[0]})
            #     pass
            # elif packet.data[0] == QUERIES["SETID"]:
            #     pass
            elif packet.data[0] == QUERIES["LIGHT"]:
                value.update({'state': list(packet.data[1:7])})
            elif packet.data[0] == QUERIES["PROGRAM"]:
                dude = SimpleDude(self.port,
                                  hexfile=self.hexfile,
                                  mode485=True)
                dude.logger = self.logger
                time.sleep(1)
                dude.program()
                pass
            # if packet.data[0] == PARAMETERS['PONG']:
            #     print("PONG")
            elif packet.data[0] == QUERIES["ACK"]:
                pass
            self.logger.info(value, extra=self.logextra)
        except Exception as e:
            raise Exception('{}'.format(value))

    def _run(self, command, work_dir=""):
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

    def compile_bootloader(self, make, env, address, workdir):
        make = "{} " \
               "ENV={} BAUD_RATE=38400 LED=D2 LED_START_FLASHES=5 " \
               "SN_MAJOR={} SN_MINOR={} pro8".format(make, env, address // 0xff, address % 0xff)
        #        cp_command = "cp" if os.name == "posix" else "copy"
        #        cp = "{} {} {}".format(cp_command, source, destination)
        self._run("{}".format(make), work_dir=workdir)

    def flash_bootloader(self, bootloader):
        self._run(AVRCMD + " -u -U flash:w:\"{}\":i -vv".format(bootloader))

    def update_fuses(self, low=0xDE, high=0xDC, extend=0xFA):
        self._run(AVRCMD + " -U lfuse:w:{}:m -U hfuse:w:{}:m -U efuse:w:{}:m".format(low, high, extend))


def prepare_commands(commands=""):
    def parse_cmd(cmd):
        _cmd_list = []
        if type(cmd) is dict:
            for k1, v1 in cmd.items():                # command with 1 arg
                if type(v1) is dict:
                    for k2, v2 in v1.items():       # series of commands with 1 arg
                        _cmd_list.append({"id": k, "cmd": bytearray((QUERIES[k1], QUERIES[k2], v2))})
                else:
                    if type(v1) is list:
                        _cmd_list.append({"id": k, "cmd": bytearray([QUERIES[k1], ] + v1)})
                    else:
                        _cmd_list.append({"id": k, "cmd": bytearray([QUERIES[k1], v1])})
        else:
            cmd_list.append({"id": k, "cmd": bytearray([QUERIES[cmd], ])})
        return _cmd_list

    cmd_list = []
    for k, v in commands.items():                   # simple commands
        if type(v) is list:
            for cmd in v:
                cmd_list.extend(parse_cmd(cmd))
        else:
            if type(v) is dict:
                cmd_list.extend(parse_cmd(v))
            else:
                cmd_list.append({"id": k, "cmd": bytearray([QUERIES[v], ])})
    return cmd_list


def domuino_communicate(instance, commands=""):
    try:
        print("Use Ctrl-C to exit.")
        instance.start()
        if commands:
            cmds = prepare_commands(commands)
        else:
            cmds = None
        a.pause()
        while cmds:
            cmd = cmds.pop(0)
            a.send(cmd["id"], cmd["cmd"])
        a.resume()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        instance.stop()
        exit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-id", type=int, help="Address RS485 of device")
    parser.add_argument("-p", "--port", help="Communication port for RS485")
    parser.add_argument("-f", "--flash", help="Filename to flash software")
    parser.add_argument("-c", "--config", help="upload configuration file")
    parser.add_argument("-L", "--loop", action="store_true", help="Run Domuino loop")
    parser.add_argument("-I", "--info", action="store_true", help="Get firmware info")
    parser.add_argument("-a", "--address", type=int, help="Change address of device")
    parser.add_argument("-d", "--demo", help="Show demo info on LCD")
    parser.add_argument("-m", "--make", help="Make bootloader")
    parser.add_argument("-b", "--boot", help="Filename to flash bootloader")
    parser.add_argument("-u", "--update", help="Update an already programmed device")
    parser.add_argument("--light", help="Set light [1=ON/0=OFF]")
    parser.add_argument("-E", "--env", help="Environment to build optiboot: (sloeber, sloeberwin, etc..)")
    parser.add_argument("-W", "--workdir", help="Working directory")
    parser.add_argument("-F", "--fuses", help="Update fuses")
    parser.add_argument("-S", "--setstate", help="Update device state. valid value = [RUN|STANDBY]")
    args = parser.parse_args()

    # ser = serial_for_url('/dev/ttyUSB0', rtscts=True, baudrate=38400)
    ser = serial_for_url(args.port, baudrate=38400, timeout=0.1) if args.port else None
    #ser = rs485.RS485(args.port, baudrate=38400)

    a = Domuino(1, ser)
    a.daemon = True
    try:
        if args.info:
            # a.start()
            # a.send(args.id, bytearray((QUERIES["PROGRAM"],)))
            dude = SimpleDude(ser,
                              hexfile="",
                              mode485=True)
            dude.get_info()
        elif args.loop:
            domuino_communicate(a)
        elif args.make:
            a.compile_bootloader(args.make, args.env, args.id, args.workdir)
        elif args.update:
            a.hexfile = args.update
            domuino_communicate(a, {args.id: "PROGRAM"})
        elif args.flash:
            dude = SimpleDude(ser,
                              hexfile=args.flash,
                              mode485=True)
            dude.program()
        elif args.fuses:
            low, high, extend = map(lambda l: int(l, 16), args.fuses.split())
            a.update_fuses(low, high, extend)
        elif args.boot:
            a.flash_bootloader(args.boot)
        elif args.address:
            domuino_communicate(a, {args.id: {"SETID": [args.address % 0xff, args.address // 0xff]}})
        elif args.config:
            with open(args.config) as f:
                data = yaml.load(f, Loader=yaml.FullLoader)
                domuino_communicate(a, data)
        elif args.setstate:
            domuino_communicate(a, {args.id: args.setstate})
        elif args.light:
            L1, L2, L3 = map(lambda l: int(l, 16), args.light.split())
            domuino_communicate(a, {args.id: {"LIGHT": [L1, L2, L3]}})
        elif args.demo:
            a.start()
            a.send(args.id, bytearray((QUERIES["LCDCLEAR"],)))

            data = list()
            row = 0
            col = 30
            for i, value in enumerate(LOGO[2:]):
                data.append(value)
                i += 1
                if not i % 8 and i % LOGO[1]:
                    a.send(args.id, bytearray((QUERIES["LCDWRITE"], row, col, len(data)) + tuple(data)))
                    # time.sleep(0.01)
                    col += 8
                    data.clear()
                if not i % LOGO[1]:
                    a.send(args.id, bytearray((QUERIES["LCDWRITE"], row, col, len(data)) + tuple(data)))
                    # time.sleep(0.01)
                    row += 1
                    col = 30
                    data.clear()

            a.send(args.id, bytearray((QUERIES["LCDPRINT"], 0, 5, 0) + tuple(ord(c) for c in str("Start\0"))))
            a.send(args.id, bytearray((QUERIES["LCDPRINT"], 7, 0, 0) + tuple(ord(c) for c in str("Temp: \0"))))
            a.send(args.id, bytearray((QUERIES["LCDPRINT"], 7, 70, 0) + tuple(ord(c) for c in str("Hum: \0"))))
            count = 0
    except KeyboardInterrupt:
        pass
    a.stop()
