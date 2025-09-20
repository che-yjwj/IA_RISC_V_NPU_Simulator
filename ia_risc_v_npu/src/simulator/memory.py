class SPM:
    """Scratchpad Memory (SPM)"""
    def __init__(self, size_kb):
        self.size = size_kb * 1024
        self.memory = bytearray(self.size)

    def read(self, address, size):
        if not (0 <= address < self.size and 0 <= address + size <= self.size):
            raise IndexError(f"SPM read out of bounds: address={address}, size={size}, SPM size={self.size}")
        return self.memory[address:address+size]

    def write(self, address, data):
        if not (0 <= address < self.size and 0 <= address + len(data) <= self.size):
            raise IndexError(f"SPM write out of bounds: address={address}, data_len={len(data)}, SPM size={self.size}")
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

    def _find_device(self, address, size):
        for name, info in self.devices.items():
            if info["start_addr"] <= address and address + size - 1 <= info["end_addr"]:
                return info["device"], address - info["start_addr"]
        return None, None

    def read(self, address, size):
        device, local_addr = self._find_device(address, size)
        if device:
            if hasattr(device, 'read'):
                return device.read(local_addr, size)
            else:
                return device[local_addr:local_addr+size]
        else:
            raise MemoryError(f"No device found or access out of bounds for address {address} with size {size}")

    def write(self, address, data):
        device, local_addr = self._find_device(address, len(data))
        if device:
            if hasattr(device, 'write'):
                device.write(local_addr, data)
            else:
                device[local_addr:local_addr+len(data)] = data
        else:
            raise MemoryError(f"No device found or access out of bounds for address {address} with size {len(data)}")
