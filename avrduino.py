#!venv/bin/python3

import subprocess
import tkinter as tk
import os
from textwrap import wrap

from serial import rs485
from simpledude import SimpleDude


BASE = os.path.dirname(__file__)
if os.name == 'nt':
    BASE += "/avrdude/win"
    AVRDUDE = BASE + "/avrdude.exe"
    AVRCONF = BASE + "/avrdude.conf"
else:
    BASE += "/avrdude/linux"
    AVRDUDE = BASE + "/avrdude"
    AVRCONF = BASE + "/avrdude.conf"
PROGRAMMER = "USBasp"
CPU = "m168p"

AVRCMD = "{} -c {} -p {} -C {} -vv ".format(AVRDUDE, PROGRAMMER, CPU, AVRCONF)

WORKSPACE = "/home/sebastiano/Documents/sloeber-workspace/"
BOOTLOADER = "optiboot_pro_8MHz.hex"
DOMUINO = "domuino.hex"



class AvrDuino(object):
    def __init__(self, root):
        self.lbl_info = tk.Text(root)
        btn_getinfo = tk.Button(root, text="Info", width=25, command=self.get_info)
        btn_fuses = tk.Button(root, text="Fuses", width=25, command=self.update_fuses)
        btn_bootloader = tk.Button(root, text="Flash Bootloader RS485", width=25, command=self.flash_bootloader)
        btn_program = tk.Button(root, text="Upload Domuino", width=25, command=self.upload_domuino)
        btn_stop = tk.Button(root, text="Cancel", width=25, command=root.destroy)
        self.dry_run = tk.BooleanVar()
        chk_dry = tk.Checkbutton(root, text="Dry run", variable=self.dry_run)
        self.spinbox_id = tk.Spinbox(root, from_=0, to=65535)

        btn_getinfo.pack()
        btn_fuses.pack()
        btn_bootloader.pack()
        btn_program.pack()
        btn_stop.pack()
        self.spinbox_id.pack()
        chk_dry.pack()

        self.lbl_info.config(state=tk.DISABLED)
        self.lbl_info.pack()

    def _show_info(self, infos):
        self.lbl_info.config(state=tk.NORMAL)
        self.lbl_info.delete("1.0", tk.END)
        self.lbl_info.insert(tk.END, infos)
        self.lbl_info.config(state=tk.DISABLED)
        self.lbl_info.pack()

    def _run(self, command):
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             shell=True)
#        stdout, stderr = p.communicate()
#        stderr = stderr.decode("UTF-8")
        self.lbl_info.config(state=tk.NORMAL)
        self.lbl_info.delete("1.0", tk.END)
        while True:
            retcode = p.poll()
            line = p.stderr.readline()
            self.lbl_info.config(state=tk.NORMAL)
            self.lbl_info.insert(tk.END, line)
            self.lbl_info.config(state=tk.DISABLED)
            self.lbl_info.pack()
            if retcode is not None:
                break
#        return stderr.split("\n")

    @staticmethod
    def _find_info(infos, substring):
        return [s for s in infos if substring in s]

    def get_info(self):
        full = self._run(AVRCMD)
#        info = self._find_info(full, "Version")
#        info.extend(self._find_info(full, "Reading"))
#        info.extend(self._find_info(full, "Device signature"))
#        info.extend(self._find_info(full, "Fuses OK"))
#        self._show_info("\n".join(info))

    def update_fuses(self):
        info = ["Clock interno 8Mhz con tempo avvio Ck/14Ck+65ms",
                "Serial program downloading (SPI) enabled; [SPIEN=0]",
                "Boot flash section size 512 words Boot start address=$1E00 [BOOTSZ=01]",
                "Brounout VCC=4.3V; [BODLEVEL=100]"]
        cmd = AVRCMD + "-U lfuse:w:0xE2:m -U hfuse:w:0xDC:m -U efuse:w:0xFA:m"
        cmd += " -n" if self.dry_run.get() else ""
        full = self._run(cmd)
        errors = self._find_info(full, "error:")
        if errors:
            self._show_info("\n".join(errors))
        else:
            info.extend(self._find_info(full, "Reading"))
            info.extend(self._find_info(full, "Device signature"))
            info.extend(self._find_info(full, "input file 0x"))
            self._show_info("\n".join(info))

    def flash_bootloader(self):
        lines = list()
        with open(BOOTLOADER) as f:
            lines = f.read().splitlines()
        id = int(self.spinbox_id.get())
        id_remainder = "{0:02X}".format(id // 0xff)
        id_modulo = "{0:02X}".format(id % 0xff)
        idline = lines[-3][1:13] + id_modulo + id_remainder
        chksum = hex(0x100 - sum([int(i, 16) for i in wrap(idline, 2)]) & 0xFF)[2:]
        lines[-3] = ":" + idline + chksum
        with open("id_boot.hex","w") as f:
            f.write("\n".join(lines))

 #       full = self._run(AVRCMD + "-u -U flash:w:{}".format(BOOTLOADER))
        pass

    def upload_domuino(self):
        ser = rs485.RS485('/dev/ttyUSB1', baudrate=38400, timeout=2)
        dude = SimpleDude(ser, hexfile= DOMUINO, mode485=True)
        dude.program()
        print("Program RS485")


if __name__ == '__main__':
    root = tk.Tk()
    root.title("Domuino")

    avr = AvrDuino(root)

    root.mainloop()

