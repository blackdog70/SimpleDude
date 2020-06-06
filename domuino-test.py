import unittest
import multi_serial_port
import yaml
import collections

CONFIG_LCDPRINT = yaml.load("""
ARDUINO_TEST:
  net: 36097
  DHT:
    "ARDUINO_TEST": {"LCDPRINT": [0, 0, 0, "Temp:{temperature}"]}
""")


CONFIG_LCDPRINT_SUBLIST = yaml.load("""
ARDUINO_TEST:
  net: 36097
  DHT:
    "ARDUINO_TEST": [{"LCDPRINT": [0, 0, 0, "Temp:{temperature}"]},
                     {"LCDPRINT": [0, 1, 0, "Hum:{humidity}"]}]
""")


CONFIG_LCDPRINT_LIST = yaml.load("""
ARDUINO_TEST:
  net: 36097
  DHT:
    ["ARDUINO_TEST": {"LCDPRINT": [0, 0, 0, "Temp:{temperature}"]},
    "ARDUINO_TEST": {"LCDPRINT": [0, 1, 0, "Hum:{humidity}"]}]
""")


CONFIG_SWITCH = yaml.load("""
ARDUINO_TEST:
  net: 36097
  SWITCH:
    1: [
    {"ARDUINO_TEST": {"LIGHT": [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0]}}
    ]
    2: [
    {"ARDUINO_TEST": {"LIGHT": [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0]}}
    ]
""")

class TestDomuino(unittest.TestCase):
    def test_execute_lcdprint(self):
        result = multi_serial_port.execute({'type': '->HUB',
                                   'time': '28/12/2019 11:02:21',
                                   'node': 36097,
                                   'msg': 'DHT',
                                   'reply': b'~',
                                   'temperature': 0.0,
                                   'humidity': 0.0},
                                  CONFIG_LCDPRINT)
        self.assertIsInstance(result, collections.deque)
        self.assertIsInstance(result[0], multi_serial_port.Packet)
        self.assertEqual(result[0].crc, None)
        self.assertEqual(result[0].data, b'\x92\x00\x00\x00Temp:0.0')

    def test_execute_lcdprint_sublist(self):
        result = multi_serial_port.execute({'type': '->HUB',
                                   'time': '28/12/2019 11:02:21',
                                   'node': 36097,
                                   'msg': 'DHT',
                                   'reply': b'~',
                                   'temperature': 0.0,
                                   'humidity': 0.0},
                                  CONFIG_LCDPRINT_SUBLIST)
        self.assertIsInstance(result, collections.deque)
        self.assertIsInstance(result[0], multi_serial_port.Packet)
        self.assertEqual(result[0].crc, None)
        self.assertEqual(result[0].data, b'\x92\x00\x00\x00Temp:0.0')
        self.assertIsInstance(result[1], multi_serial_port.Packet)
        self.assertEqual(result[1].crc, None)
        self.assertEqual(result[1].data, b'\x92\x00\x01\x00Hum:0.0')

    def test_execute_lcdprint_list(self):
        result = multi_serial_port.execute({'type': '->HUB',
                                   'time': '28/12/2019 11:02:21',
                                   'node': 36097,
                                   'msg': 'DHT',
                                   'reply': b'~',
                                   'temperature': 0.0,
                                   'humidity': 0.0},
                                  CONFIG_LCDPRINT_LIST)
        self.assertIsInstance(result, collections.deque)
        self.assertIsInstance(result[0], multi_serial_port.Packet)
        self.assertEqual(result[0].crc, None)
        self.assertEqual(result[0].data, b'\x92\x00\x00\x00Temp:0.0')
        self.assertIsInstance(result[1], multi_serial_port.Packet)
        self.assertEqual(result[1].crc, None)
        self.assertEqual(result[1].data, b'\x92\x00\x01\x00Hum:0.0')

    def test_execute_switch(self):
        result = multi_serial_port.execute({'type': '->HUB',
                                   'time': '28/12/2019 11:02:21',
                                   'node': 36097,
                                   'msg': 'SWITCH',
                                   'reply': b'~',
                                   'state': [1, 0, 0, 0, 0, 0, 0]},
                                  CONFIG_SWITCH)
        self.assertIsInstance(result, collections.deque)
        self.assertIsInstance(result[0], multi_serial_port.Packet)
        self.assertEqual(result[0].crc, None)
        self.assertEqual(result[0].data, b'\xa4\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00')

    def test_preparecommand_simple(self):
        result = multi_serial_port.prepare_commands("ARDUINO_TEST", 'MEM', CONFIG_LCDPRINT)
        self.assertIsInstance(result[0], multi_serial_port.Packet)
        self.assertEqual(result[0].crc, None)
        self.assertEqual(result[0].data, b'\x90')

    def test_preparecommand_single_dict(self):
        result = multi_serial_port.prepare_commands("ARDUINO_TEST",
                                                    {'LCDPRINT': [0, 0, 0, 'Temp:0.0']},
                                                    CONFIG_LCDPRINT)
        self.assertIsInstance(result[0], multi_serial_port.Packet)
        self.assertEqual(result[0].crc, None)
        self.assertEqual(result[0].data, b'\x92\x00\x00\x00Temp:0.0')

    def test_preparecommand_listof_dict(self):
        result = multi_serial_port.prepare_commands("ARDUINO_TEST", [
            {'LCDPRINT': [0, 0, 0, 'Temp:0.0']},
            {'LCDPRINT': [0, 0, 0, 'Temp:10.0']},
        ], CONFIG_LCDPRINT)
        self.assertIsInstance(result[0], multi_serial_port.Packet)
        self.assertIsInstance(result[1], multi_serial_port.Packet)
        self.assertEqual(result[0].crc, None)
        self.assertEqual(result[0].data, b'\x92\x00\x00\x00Temp:0.0')
        self.assertEqual(result[1].crc, None)
        self.assertEqual(result[1].data, b'\x92\x00\x00\x00Temp:10.0')


if __name__ == '__main__':
    unittest.main()
