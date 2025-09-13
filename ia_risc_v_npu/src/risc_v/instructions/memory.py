def ld(memory, address):
    return int.from_bytes(memory[address:address+8], 'little')

def sd(memory, address, value):
    memory[address:address+8] = value.to_bytes(8, 'little')

def lw(memory, address):
    return int.from_bytes(memory[address:address+4], 'little')

def sw(memory, address, value):
    memory[address:address+4] = value.to_bytes(4, 'little')