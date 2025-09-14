import time
import numpy as np

# This is for line_profiler
# from line_profiler import profile

class TimingHookSystem:
    def __init__(self, buffer_size=10000):
        self.buffer_size = buffer_size
        self.hook_stats = {
            'fetch': np.zeros(buffer_size, dtype=[('timestamp', 'f8'), ('latency', 'i4'), ('cache_miss', '?')]),
            'decode': [],
            'execute': [],
            'memory': np.zeros(buffer_size, dtype=[('timestamp', 'f8'), ('latency', 'i4'), ('address', 'u8'), ('size', 'i4'), ('is_write', '?')])
        }
        self.counters = {'fetch': 0, 'memory': 0}
        # Pre-generate random choices for performance
        self.random_choices = np.random.choice([True, False], size=buffer_size)

    def _check_icache_miss(self, pc):
        # Use pre-generated random numbers instead of calling random.choice repeatedly
        if self.counters['fetch'] < self.buffer_size:
            return self.random_choices[self.counters['fetch']]
        return np.random.choice([True, False]) # Fallback

    # @profile
    def fetch_hook(self, pc, inst_bits):
        idx = self.counters['fetch']
        if idx >= self.buffer_size:
            # Buffer full, handle appropriately (e.g., flush to disk, resize)
            return 1 # Default latency
        
        timestamp = time.time()
        cache_miss = self._check_icache_miss(pc)
        latency = 1 if not cache_miss else 10
        
        self.hook_stats['fetch'][idx] = (timestamp, latency, cache_miss)
        self.counters['fetch'] += 1
        
        return latency

    def decode_hook(self, inst):
        pass

    def execute_hook(self, op):
        pass

    def memory_hook(self, address, size, is_write):
        idx = self.counters['memory']
        if idx >= self.buffer_size:
            return 2 # Default latency

        timestamp = time.time()
        latency = 2
        
        self.hook_stats['memory'][idx] = (timestamp, latency, address, size, is_write)
        self.counters['memory'] += 1
        
        return latency