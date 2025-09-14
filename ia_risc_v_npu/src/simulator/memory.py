class SPM:
    """Scratchpad Memory (SPM)"""
    def __init__(self, size_kb):
        self.size = size_kb * 1024
        self.memory = bytearray(self.size)

    def read(self, address, size):
        return self.memory[address:address+size]

    def write(self, address, data):
        self.memory[address:address+len(data)] = data

class Bus:
    """A simple memory bus that routes requests to the appropriate device."""
    def __init__(self):
        self.devices = {}

    def add_device(self, name, device, start_addr, end_addr):
        self.devices[name] = {
            "device": device,
            "start_addr": start_addr,
            "end_addr": end_addr
        }

    def _find_device(self, address):
        for name, info in self.devices.items():
            if info["start_addr"] <= address <= info["end_addr"]:
                return info["device"], address - info["start_addr"]
        return None, None

    def read(self, address, size):
        device, local_addr = self._find_device(address)
        if device:
            return device.read(local_addr, size)
        else:
            raise MemoryError(f"No device found at address {address}")

    def write(self, address, data):
        device, local_addr = self._find_device(address)
        if device:
            device.write(local_addr, data)
        else:
            raise MemoryError(f"No device found at address {address}")
