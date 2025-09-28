import numpy as np

def ld(bus, address):
    return int.from_bytes(bus.read(address, 8), 'little')

def sd(bus, address, value):
    bus.write(address, value.to_bytes(8, 'little'))

def lw(bus, address):
    word = int.from_bytes(bus.read(address, 4), 'little')
    if word & 0x80000000:
        return word - (1 << 32)
    return word

def sw(bus, address, value):
    if isinstance(value, np.uint32):
        bus.write(address, value.tobytes())
    else:
        bus.write(address, value.to_bytes(4, 'little'))
