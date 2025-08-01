#! /usr/bin/env python
"""\
Scan for serial ports.
Part of pySerial (http://pyserial.sf.net)
(C) 2002-2003 <cliechti@gmx.net>

The scan function of this module tries to open each port number
from 0 to 255 and it builds a list of those ports where this was
successful.
"""

import os

import serial


def scan():
    """scan for available ports. return a list of tuples (num, name)"""
    available = []
    n = 0
    for i in range(256):
        try:
            s = serial.Serial(i)
            available.append((i, s.portstr))
            n = i
            s.close()  # explicit close 'cause of delayed GC in java
        except serial.SerialException:
            pass

    if os.name == "posix":
        print("Linux")
        for dev in os.listdir("/dev"):
            if dev[0:6] == "ttyACM":
                n += 1
                available.append((n, "/dev/{0}".format(dev)))

    return available


if __name__ == "__main__":
    print("Found ports:")
    for n, s in scan():
        print("(%d) %s" % (n, s))
