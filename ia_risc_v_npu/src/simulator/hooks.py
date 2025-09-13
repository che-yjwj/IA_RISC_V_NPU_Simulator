import time
import random

class TimingHookSystem:
    def __init__(self):
        self.hook_stats = {
            'fetch': [],
            'decode': [],
            'execute': [],
            'memory': []
        }

    def _check_icache_miss(self, pc):
        return random.choice([True, False])

    def fetch_hook(self, pc, inst_bits):
        timestamp = time.time()
        cache_miss = self._check_icache_miss(pc)
        latency = 1 if not cache_miss else 10
        self.hook_stats['fetch'].append({
            'timestamp': timestamp,
            'latency': latency,
            'cache_miss': cache_miss
        })
        return latency

    def decode_hook(self, inst):
        pass

    def execute_hook(self, op):
        pass