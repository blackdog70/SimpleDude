#!venv/bin/python3

import subprocess
import tkinter as tk
import os
from textwrap import wrap

from serial import rs485
from simpledude import SimpleDude


BASEDIR = os.path.dirname(__file__)
MAKEDIR = "/home/sebastiano/Documents/sloeber-workspace/optiboot485/optiboot/bootloaders/optiboot/"

if os.name == 'nt':
    AVRDUDE = BASEDIR + "/avrdude/win/avrdude.exe"
    AVRCONF = BASEDIR + "/avrdude/win/avrdude.conf"
else:
    AVRDUDE = BASEDIR + "/avrdude/linux/avrdude"
    AVRCONF = BASEDIR + "/avrdude/linux/avrdude.conf"

PROGRAMMER = "USBasp"
CPU = "m168p"

AVRCMD = "{} -c {} -P usb -p {} -C {} -vv ".format(AVRDUDE, PROGRAMMER, CPU, AVRCONF)
WORKSPACE = "/home/sebastiano/Documents/sloeber-workspace/"
BOOTLOADER = "optiboot_pro_8MHz.hex"
DOMUINO = "domuino.hex"



class AvrDuino(object):
    def __init__(self, root):
        self.txt_info = tk.Text(root)
        btn_getinfo = tk.Button(root, text="AVR Info", width=25, command=self.get_info)
        btn_fuses = tk.Button(root, text="Set fuses", width=25, command=self.update_fuses)
        btn_bootloader = tk.Button(root, text="Flash Bootloader RS485", width=25, command=self.flash_bootloader)
        btn_program = tk.Button(root, text="Upload Domuino", width=25, command=self.upload_domuino)
        btn_stop = tk.Button(root, text="Cancel", width=25, command=root.destroy)
        self.dry_run = tk.BooleanVar()
        chk_dry = tk.Checkbutton(root, text="Dry run", variable=self.dry_run)

        self.number = tk.StringVar()
        try:
            with open("backup.cfg", "r") as f:
                self.number.set(f.read())
        except IOError:
            pass
        label_id = tk.Label(root, text = "Next ID")
        self.spinbox_id = tk.Spinbox(root, from_=0, to=65535, textvariable=self.number)

        btn_getinfo.grid(row=0, columnspan=2, padx=5)
        btn_fuses.grid(row=1, columnspan=2, padx=5)
        btn_bootloader.grid(row=2, columnspan=2, padx=5)
        btn_program.grid(row=3, columnspan=2, padx=5)
        btn_stop.grid(row=4, columnspan=2, padx=5)
        label_id.grid(row=5, column=0, padx=5)
        self.spinbox_id.grid(row=5, column=1, padx=5)
        chk_dry.grid(row=6, columnspan=2, padx=5)

        self.txt_info.grid(row=0, column=2, rowspan=7, padx=5, pady=5)
        self.txt_info.config(state=tk.DISABLED)

    def _show_info(self, infos):
        self.txt_info.config(state=tk.NORMAL)
        self.txt_info.delete("1.0", tk.END)
        self.txt_info.insert(tk.END, infos)
        self.txt_info.config(state=tk.DISABLED)
        self.txt_info.pack()

    def _run(self, command, io="stderr", work_dir=BASEDIR):
        run_ok = True
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             shell=True,
                             cwd=work_dir)
        self.txt_info.config(state=tk.NORMAL)
        self.txt_info.delete("1.0", tk.END)
        while p.returncode is None:
            if io == "stdout":
                line = p.stdout.readline()
            else:
                line = p.stderr.readline()
            if any(sub in str(line) for sub in ["error:", "verification error"]):
                run_ok = False
            self.txt_info.config(state=tk.NORMAL)
            self.txt_info.insert(tk.END, line)
            self.txt_info.config(state=tk.DISABLED)
            self.txt_info.see(tk.END)
            p.poll()
            root.update()
        return run_ok

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

    def _compile_bootloader(self):
        _id = int(self.spinbox_id.get())
        make = "make "\
               "ENV=sloeber BAUD_RATE=38400 LED=D2 LED_START_FLASHES=5 "\
               "SN_MAJOR={} SN_MINOR={} pro8".format(_id // 0xff, _id % 0xff)
        cp = "cp {} {}".format(MAKEDIR+BOOTLOADER, BASEDIR)
        self._run("{}; {}".format(make, cp), io="stdout", work_dir=MAKEDIR)

    def flash_bootloader(self):
        self._compile_bootloader()

        if self._run(AVRCMD + "-u -U flash:w:\"{}\":i".format(BOOTLOADER)):
            self.number.set(int(self.number.get()) + 1)
            with open("backup.cfg", "w") as f:
                f.write(self.number.get())
            self.spinbox_id.update()

    def upload_domuino(self):
        ser = rs485.RS485('/dev/ttyUSB2', baudrate=38400, timeout=2)
        dude = SimpleDude(ser, hexfile= DOMUINO, mode485=True)

        self.txt_info.config(state=tk.NORMAL)
        self.txt_info.delete("1.0", tk.END)
        for progress in dude.program():
            self.txt_info.config(state=tk.NORMAL)
            self.txt_info.insert(tk.END, progress + "\n")
            self.txt_info.config(state=tk.DISABLED)
            self.txt_info.update()
            self.txt_info.see(tk.END)
        print("Program RS485")


if __name__ == '__main__':
    root = tk.Tk()
    root.title("Domuino programmer")

    avr = AvrDuino(root)

    root.mainloop()

