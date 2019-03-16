#!venv/bin/python3

import subprocess
import tkinter as tk
import os

from serial import rs485
from simpledude import SimpleDude

#BASE = "/home/sebastiano/Programs/sloeber/arduinoPlugin/packages/arduino/tools/avrdude/6.3.0-arduino14/"
#AVRDUDE = BASE + "bin/avrdude "
#AVRCONF = BASE + "etc/avrdude.conf "
BASE = os.path.dirname(__file__)
if os.name == 'nt':
    BASE += "/avrdude/win/"
    AVRDUDE = BASE + "/avrdude.exe"
    AVRCONF = BASE + "/avrdude.conf "
else:
    BASE += "/avrdude/linux/"
    AVRDUDE = BASE + "/avrdude"
    AVRCONF = BASE + "/avrdude.conf "
PROGRAMMER = "USBasp"
CPU = "m168p"
WORKSPACE = "/home/sebastiano/Documents/sloeber-workspace/"
BOOTLOADER = WORKSPACE + "optiboot485/optiboot/bootloaders/optiboot/optiboot_pro_8MHz.hex"
DOMUINO = WORKSPACE + "domuino/Release/domuino.hex"

cmd = "{} -c {} -p {} -C {}".format(AVRDUDE, PROGRAMMER, CPU, AVRCONF)


def get_info():
    p = subprocess.Popen([AVRDUDE, "-c", PROGRAMMER, "-p", CPU],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE,
                         shell=True)
    stdout, stderr = p.communicate()
    stderr = stderr.decode("UTF-8")
    info = stderr.split("\r")
    print(info)
    if stderr.find("failed") > 0:
        print(info[4])
    elif info:
        print(info[4])
        print(info[6].split(":")[1][1:])


def update_fuses():
    print("Clock interno 8Mhz con tempo avvio Ck/14Ck+65ms")
    print("Boot flash section size 512 words Boot start address=$1E00 [BOOTSZ=01]")
    print("Serial program downloading (SPI) enabled; [SPIEN=0]")
    print("Brounout VCC=4.3V; [BODLEVEL=100]")
    subprocess.call(cmd + "-U lfuse:w:0xE2:m -U hfuse:w:0xDC:m -U efuse:w:0xFA:m -vvv", shell=True)


def upload_bootloader():
    subprocess.call(cmd + "-u -U flash: w:""{}"": i".format(BOOTLOADER))


def upload_domuino():
    ser = rs485.RS485('/dev/ttyUSB1', baudrate=38400, timeout=2)
    dude = SimpleDude(ser, hexfile= DOMUINO, mode485=True)
    dude.program()
    print("Program RS485")


if __name__ == '__main__':
    root = tk.Tk()
    root.title("Domuino")

    btn_getinfo = tk.Button(root, text="Info", width=25, command=get_info)
    btn_fuses = tk.Button(root, text="Fuses", width=25, command=update_fuses)
    btn_program = tk.Button(root, text="Program", width=25, command=upload_domuino)
    btn_stop = tk.Button(root, text="Cancel", width=25, command=root.destroy)

    btn_getinfo.pack()
    btn_fuses.pack()
    btn_program.pack()
    btn_stop.pack()

    root.mainloop()

