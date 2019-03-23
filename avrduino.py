#!venv/bin/python3

import subprocess
import tkinter as tk
import os
import logging

from serial import rs485
from simpledude import SimpleDude
from domuino import Domuino, QUERIES

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


class TextHandler(logging.Handler):
    # This class allows you to log to a Tkinter Text or ScrolledText widget
    # Adapted from Moshe Kaplan: https://gist.github.com/moshekaplan/c425f861de7bbf28ef06

    def __init__(self, text):
        # run the regular Handler __init__
        logging.Handler.__init__(self)
        # Store a reference to the Text it will log to
        self.text = text

    def emit(self, record):
        msg = self.format(record)

        def append():
            self.text.configure(state='normal')
            self.text.insert(tk.END, msg + '\n')
            self.text.configure(state='disabled')
            # Autoscroll to the bottom
            self.text.yview(tk.END)
        # This is necessary because we can't modify the Text from other threads
        self.text.after(0, append)


class AvrDuino(object):
    def __init__(self, root):
        self.txt_avr = tk.Text(root, width=50)
        self.txt_domuino = tk.Text(root, width=50)
        btn_getinfo = tk.Button(root, text="AVR Info", width=25, command=self.get_info)
        btn_fuses = tk.Button(root, text="Set fuses", width=25, command=self.update_fuses)
        btn_bootloader = tk.Button(root, text="Flash Bootloader RS485", width=25, command=self.flash_bootloader)
        btn_program = tk.Button(root, text="Program Domuino", width=25, command=self.program_domuino)
        btn_update = tk.Button(root, text="Update Domuino", width=25, command=self.update_domuino)
        btn_start = tk.Button(root, text="Start Domuino", width=25, command=self.start_domuino)
        btn_stop = tk.Button(root, text="Cancel", width=25, command=root.destroy)
        btn_clear_avr = tk.Button(root, text="Clear AVR", width=25, command=self.clear_avr)
        btn_clear_dom = tk.Button(root, text="Clear Domuino", width=25, command=self.clear_dom)
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
        btn_update.grid(row=4, columnspan=2, padx=5)
        btn_start.grid(row=5, columnspan=2, padx=5)
        btn_stop.grid(row=6, columnspan=2, padx=5)
        label_id.grid(row=7, column=0, padx=5)
        self.spinbox_id.grid(row=7, column=1, padx=5)
        chk_dry.grid(row=8, columnspan=2, padx=5)

        self.txt_avr.grid(row=0, column=2, rowspan=9, padx=5, pady=5)
        btn_clear_avr.grid(row=9, column=2, padx=5, pady=5)
        self.txt_domuino.grid(row=0, column=3, rowspan=9, padx=3, pady=5)
        btn_clear_dom.grid(row=9, column=3, padx=5, pady=5)

        self.ser = rs485.RS485('/dev/ttyUSB2', baudrate=38400, timeout=2)
        n = int(self.number.get())
        self.avr_handler = TextHandler(self.txt_avr)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(self.avr_handler)

        self.domuino = Domuino(1, self.ser)
        self.domuino.hexfile = DOMUINO
        self.dom_handler = TextHandler(self.txt_domuino)
        self.domuino.log_handler(self.dom_handler)
        self.domuino.daemon = True
        self.domuino.start()

    # def _show_info(self, infos):
    #     self.avr_info.config(state=tk.NORMAL)
    #     self.avr_info.delete("1.0", tk.END)
    #     self.avr_info.insert(tk.END, infos)
    #     self.avr_info.config(state=tk.DISABLED)
    #     self.avr_info.pack()

    def clear_avr(self):
        self.txt_avr.config(state=tk.NORMAL)
        self.txt_avr.delete("1.0", tk.END)
        self.txt_avr.config(state=tk.DISABLED)

    def clear_dom(self):
        self.txt_domuino.config(state=tk.NORMAL)
        self.txt_domuino.delete("1.0", tk.END)
        self.txt_domuino.config(state=tk.DISABLED)

    def _run(self, command, io="stderr", work_dir=BASEDIR):
        run_ok = True
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             shell=True,
                             cwd=work_dir)
        while p.returncode is None:
            if io == "stdout":
                line = p.stdout.readline()
            else:
                line = p.stderr.readline()
            if any(sub in str(line) for sub in ["error:", "verification error"]):
                run_ok = False
            self.logger.info(line)
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
            self.logger.error("\n".join(errors))
        else:
            info.extend(self._find_info(full, "Reading"))
            info.extend(self._find_info(full, "Device signature"))
            info.extend(self._find_info(full, "input file 0x"))
            self.logger.info("\n".join(info))

    def _compile_bootloader(self):
        _id = int(self.spinbox_id.get())
        make = "make "\
               "ENV=sloeber BAUD_RATE=38400 LED=D2 LED_START_FLASHES=5 "\
               "SN_MAJOR={} SN_MINOR={} pro8".format(_id // 0xff, _id % 0xff)
        cp = "cp {} {}".format(MAKEDIR+BOOTLOADER, BASEDIR)
        self._run("{}; {}".format(make, cp), io="stdout", work_dir=MAKEDIR)

    def inc_number(self):
        self.number.set(int(self.number.get()) + 1)
        with open("backup.cfg", "w") as f:
            f.write(self.number.get())
        self.spinbox_id.update()

    def flash_bootloader(self):
        self._compile_bootloader()

        self._run(AVRCMD + "-u -U flash:w:\"{}\":i".format(BOOTLOADER))

    def start_domuino(self):
        n = int(self.number.get())

        self.domuino.send(n, bytearray((QUERIES["RUN"], )))

    def update_domuino(self):
        n = int(self.number.get())
        self.domuino.send(n, bytearray((QUERIES["RESET"], )))

    def program_domuino(self):
        dude = SimpleDude(self.ser, hexfile=DOMUINO, mode485=True)
        dude.program()


if __name__ == '__main__':
    root = tk.Tk()
    root.title("Domuino programmer")

    avr = AvrDuino(root)

    root.mainloop()

