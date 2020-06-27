import unittest
import protocol as domuino

TEST1 = {1: {"CONFIG": {"HBT": 1, "DHT": 50}}, }
TEST2 = {1: {"CONFIG": {"HBT": 1}}}
TEST3 = {1: "PROGRAM"}
TEST4 = {1: {"SETID": 1}}


class test_communicate(unittest.TestCase):
    def test_1(self):
        res = domuino.prepare_commands(TEST1)
        self.assertEqual(res, [{'id': 1, 'cmd': bytearray(b'\x88\x9f\x01')},
                               {'id': 1, 'cmd': bytearray(b'\x88\xa02')}])

    def test_2(self):
        res = domuino.prepare_commands(TEST2)
        self.assertEqual(res, [{'id': 1, 'cmd': bytearray(b'\x88\x9f\x01')}])

    def test_3(self):
        res = domuino.prepare_commands(TEST3)
        self.assertEqual(res, [{'id': 1, 'cmd': bytearray(b'\x82')}])

    def test_4(self):
        res = domuino.prepare_commands(TEST4)
        self.assertEqual(res, [{'id': 1, 'cmd': bytearray(b'\x85\x01')}])


if __name__ == "main":
    unittest.main()
