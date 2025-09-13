class MMIO:
    def __init__(self, npu):
        self.npu = npu

    def read(self, address):
        # This is a simplified MMIO read for now.
        # In a real implementation, this would be more complex.
        if address in self.npu.internal_registers:
            return self.npu.internal_registers[address]
        return 0

    def write(self, address, value):
        # This is a simplified MMIO write for now.
        self.npu.internal_registers[address] = value
