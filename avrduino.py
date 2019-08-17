#!venv/bin/python3

import subprocess
import tkinter as tk
from tkinter import ttk
import os
import logging
import pyudev
from configparser import ConfigParser
import pexpect

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
        self.config = ConfigParser()
        self.config.read(BASEDIR + "/config.ini")

        btns = tk.Frame(root)

        self.number = tk.StringVar()
        self.new_number = tk.StringVar()
        self.usb_selected = tk.StringVar()
        if len(self.config.sections()):
            self.number.set(self.config["config"]["number"])
            self.usb_selected.set(self.config["config"]["usb"])

        usb_ports = tk.Frame(btns)
        lbl_port = tk.Label(usb_ports, text="Port")
        lst_usb_ports = ttk.Combobox(usb_ports,
                                     values=[p["DEVNAME"] for p in self._get_usb_list()],
                                     textvariable=self.usb_selected)
        lbl_port.pack(side=tk.LEFT, padx=5)
        lst_usb_ports.pack(fill=tk.X, expand=True)
        self.usb_selected.trace("w", self.set_config)

        btn_getinfo = tk.Button(btns, text="AVR Info", width=25, command=self.get_info)

        osccal = tk.Frame(btns)
        self.osccal = tk.StringVar()
        label_osccal = tk.Label(osccal, text="OSCCAL")
        self.spinbox_osccal = tk.Spinbox(osccal, from_=0, to=255, textvariable=self.osccal)
        self.set_osccal = tk.BooleanVar()
        chk_osccal = tk.Checkbutton(osccal, text="", variable=self.set_osccal)
        label_osccal.pack(side=tk.LEFT, padx=5)
        self.spinbox_osccal.pack(side=tk.LEFT, padx=5)
        chk_osccal.pack()

        btn_oscout = tk.Button(btns, text="Set OscOut", width=25, command=self.set_oscout)
        btn_clkin = tk.Button(btns, text="Set CLK INT", width=25, command=self.set_clkin)
        btn_clkout = tk.Button(btns, text="Set CLK OUT", width=25, command=self.set_clkout)
        btn_bootloader = tk.Button(btns, text="Flash Bootloader RS485", width=25, command=self.flash_bootloader)
        btn_program = tk.Button(btns, text="Program Domuino", width=25, command=self.program_domuino)
        btn_getosccal = tk.Button(btns, text="Get OSCCAL", width=25, command=self.get_osccal)
        btn_update = tk.Button(btns, text="Update Domuino", width=25, command=self.update_domuino)
        btn_setid = tk.Button(btns, text="Set ID", width=25, command=self.set_id)
        btn_start = tk.Button(btns, text="Start Domuino", width=25, command=self.start_domuino)
        btn_stop = tk.Button(btns, text="Close", width=25, command=root.destroy)
        self.dry_run = tk.BooleanVar()
        chk_dry = tk.Checkbutton(btns, text="Dry run", variable=self.dry_run)

        number = tk.Frame(btns)
        label_id = tk.Label(number, text="ID")
        self.spinbox_id = tk.Spinbox(number, from_=0, to=65535, textvariable=self.number)
        label_id.pack(side=tk.LEFT, padx=5)
        self.spinbox_id.pack()
        self.number.trace("w", self.set_config)

        new_number = tk.Frame(btns)
        label_new_id = tk.Label(new_number, text="New ID")
        self.spinbox_new_id = tk.Spinbox(new_number, from_=0, to=65535, textvariable=self.new_number)
        label_new_id.pack(side=tk.LEFT, padx=5)
        self.spinbox_new_id.pack()

        usb_ports.pack(fill=tk.X, pady=5)
        btn_getinfo.pack(fill=tk.X, pady=5)
        btn_oscout.pack(fill=tk.X, pady=5)
        btn_clkin.pack(fill=tk.X, pady=5)
        btn_clkout.pack(fill=tk.X, pady=5)
        btn_getosccal.pack(fill=tk.X, pady=5)
        osccal.pack(fill=tk.X, pady=5)
        btn_bootloader.pack(fill=tk.X, pady=5)
        btn_program.pack(fill=tk.X, pady=5)
        btn_update.pack(fill=tk.X, pady=5)
        btn_setid.pack(fill=tk.X, pady=5)
        btn_start.pack(fill=tk.X, pady=5)
        btn_stop.pack(fill=tk.X, pady=5)
        number.pack(fill=tk.X, pady=5)
        new_number.pack(fill=tk.X, pady=5)
        chk_dry.pack(fill=tk.X, pady=5)

        txts1 = tk.Frame(root)
        self.txt_avr = tk.Text(txts1, width=50)
        btn_clear_avr = tk.Button(txts1, text="Clear AVR", width=25, command=self.clear_avr)
        self.txt_avr.pack(padx=5, pady=5)
        btn_clear_avr.pack(side=tk.BOTTOM, padx=5, pady=5)

        txts2 = tk.Frame(root)
        self.txt_domuino = tk.Text(txts2, width=50)
        btn_clear_dom = tk.Button(txts2, text="Clear Domuino", width=25, command=self.clear_dom)
        self.txt_domuino.pack(padx=3, pady=5)
        btn_clear_dom.pack(side=tk.BOTTOM, padx=5, pady=5)


        n = int(self.number.get())
        self.avr_handler = TextHandler(self.txt_avr)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(self.avr_handler)

        btns.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=5, pady=5)
        txts1.pack(side=tk.LEFT)
        txts2.pack(side=tk.RIGHT)

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, self._monitor_event)
        observer.start()
        self._start_daemon(self.usb_selected.get())

    def _start_daemon(self, port):
        try:
            self.ser = rs485.RS485(port, baudrate=38400, timeout=2)
            self.domuino = Domuino(1, self.ser)
            self.domuino.hexfile = DOMUINO
            self.dom_handler = TextHandler(self.txt_domuino)
            self.domuino.log_handler(self.dom_handler)
            self.domuino.daemon = True
            self.domuino.start()
        except Exception as e:
            self.logger.error(e)

    def _monitor_event(self, action, device):
        if device.device_node == self.usb_selected.get():
            print(action + " " + (device.device_node or ""))
            if action == "remove":
                self.domuino.stop()
            if action == "add":
                self._start_daemon(self.usb_selected.get())

    def _get_usb_list(self):
        context = pyudev.Context()

        tty = [dict(p) for p in context.list_devices(subsystem="tty")]
        return [p for p in filter(lambda p: "USB" in p["DEVNAME"], tty)]

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
        command += " -n" if self.dry_run.get() else ""

        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             shell=True,
                             cwd=work_dir)
        while True:
            if io == "stdout":
                line = p.stdout.readline().decode("utf-8")
            else:
                line = p.stderr.readline().decode("utf-8")
            if any(sub in str(line) for sub in ["error:", "verification error"]):
                run_ok = False
            self.logger.info(line)
            p.poll()
            root.update()
            if line == "" and p.returncode is not None:
                break
        return run_ok

    @staticmethod
    def _find_info(infos, substring):
        if infos and substring:
            return [s for s in infos if substring in s]

    def get_info(self):
        full = self._run(AVRCMD)
#        info = self._find_info(full, "Version")
#        info.extend(self._find_info(full, "Reading"))
#        info.extend(self._find_info(full, "Device signature"))
#        info.extend(self._find_info(full, "Fuses OK"))
#        self._show_info("\n".join(info))

    def set_oscout(self):
        cmd = AVRCMD + " -U lfuse:w:0xA2:m"
        full = self._run(cmd)

    def set_clkin(self):
        info = ["Clock interno 8Mhz con tempo avvio Ck/14Ck+65ms",
                "Serial program downloading (SPI) enabled; [SPIEN=0]",
                "Boot flash section size 512 words Boot start address=$1E00 [BOOTSZ=01]",
                "Brounout VCC=4.3V; [BODLEVEL=100]"]
        cmd = AVRCMD + " -U lfuse:w:0xE2:m -U hfuse:w:0xDC:m -U efuse:w:0xFA:m"
        full = self._run(cmd)
        # errors = self._find_info(full, "error:")
        # if errors:
        #     self.logger.error("\n".join(errors))
        # else:
        #     info.extend(self._find_info(full, "Reading"))
        #     info.extend(self._find_info(full, "Device signature"))
        #     info.extend(self._find_info(full, "input file 0x"))
        #     self.logger.info("\n".join(info))

    def set_clkout(self):
        info = ["Clock esterno 8Mhz con tempo avvio Ck/14Ck+65ms",
                "Serial program downloading (SPI) enabled; [SPIEN=0]",
                "Boot flash section size 512 words Boot start address=$1E00 [BOOTSZ=01]",
                "Brounout VCC=4.3V; [BODLEVEL=100]"]
        cmd = AVRCMD + " -U lfuse:w:0x9E:m -U hfuse:w:0xDC:m -U efuse:w:0xFA:m"
        full = self._run(cmd)

    def get_osccal(self):
        try:
            child = pexpect.spawn(AVRCMD + " -t")
            child.expect("avrdude>")
            child.sendline("dump calibration")
            child.expect("avrdude>")
            self.osccal.set(child.before.split(b"0000")[1][:4].strip().decode("utf-8"))
        except Exception as e:
            print(e)

    def _compile_bootloader(self):
        _id = int(self.spinbox_id.get())
        osccal = "" if not self.set_osccal.get() else "CALIBRATION={}".format(int(self.osccal.get(), base=16))
        make = "make "\
               "ENV=sloeber BAUD_RATE=38400 LED=D2 LED_START_FLASHES=5 "\
               "SN_MAJOR={} SN_MINOR={} {} pro8".format(_id // 0xff, _id % 0xff, osccal)
        cp = "cp {} {}".format(MAKEDIR+BOOTLOADER, BASEDIR)
        self._run("{}; {}".format(make, cp), io="stdout", work_dir=MAKEDIR)

    def set_config(self, *args):
        self.config["config"]["number"] = self.number.get()
        self.config["config"]["usb"] = self.usb_selected.get()
        with open("config.ini", "w") as f:
            self.config.write(f)
        self._start_daemon(self.usb_selected.get())

    def flash_bootloader(self):
        self._compile_bootloader()

        self._run(AVRCMD + "-u -U flash:w:\"{}\":i".format(BOOTLOADER))

    def start_domuino(self):
        if self.domuino:
            n = int(self.number.get())
            self.domuino.send(n, bytearray((QUERIES["RUN"], )))

    def update_domuino(self):
        if self.domuino:
            n = int(self.number.get())
            self.domuino.send(n, bytearray((QUERIES["RESET"], )))

    def program_domuino(self):
        dude = SimpleDude(self.ser, hexfile=DOMUINO, mode485=True)
        dude.program()

    def set_id(self):
        if self.domuino:
            n = int(self.number.get())
            new_id = int(self.new_number.get())
            self.domuino.send(n, bytearray((QUERIES["SETID"], new_id)))
            self.number.set(new_id)


if __name__ == '__main__':
    root = tk.Tk()
    root.title("Domuino programmer")

    avr = AvrDuino(root)

    root.mainloop()
