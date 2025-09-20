def ld(bus, address):
    return int.from_bytes(bus.read(address, 8), 'little')

def sd(bus, address, value):
    bus.write(address, value.to_bytes(8, 'little'))

def lw(bus, address):
    return int.from_bytes(bus.read(address, 4), 'little')

def sw(bus, address, value):
    bus.write(address, value.to_bytes(4, 'little'))