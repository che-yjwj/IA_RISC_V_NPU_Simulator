import numpy as np


class TimingHookSystem:
    ICACHE_HIT_LATENCY = 1
    ICACHE_MISS_LATENCY = 10
    MEMORY_ACCESS_LATENCY = 2

    def __init__(self, buffer_size: int = 10000, miss_period: int = 0) -> None:
        self.buffer_size = buffer_size
        self._miss_period = max(0, miss_period)
        self.fetch_stats = np.zeros(
            buffer_size,
            dtype=[("pc", "u8"), ("latency", "i4"), ("cache_miss", "?")],
        )
        self.memory_stats = np.zeros(
            buffer_size,
            dtype=[("latency", "i4"), ("address", "u8"), ("size", "i4"), ("is_write", "?")],
        )
        self.counters = {"fetch": 0, "memory": 0}
        self.random_choices = self._build_miss_pattern(buffer_size)
        self.fetch_miss_count = 0
        self.total_fetch_latency = 0
        self.total_fetch_penalty = 0

    def _build_miss_pattern(self, buffer_size: int) -> np.ndarray:
        pattern = np.zeros(buffer_size, dtype=np.bool_)
        if self._miss_period > 0:
            pattern[:: self._miss_period] = True
        return pattern

    def fetch_hook(self, pc: int, inst_bits: int) -> int:
        idx = self.counters["fetch"]
        cache_miss = bool(self.random_choices[idx % self.buffer_size])
        latency = self.ICACHE_MISS_LATENCY if cache_miss else self.ICACHE_HIT_LATENCY

        if idx < self.buffer_size:
            self.fetch_stats[idx] = (pc, latency, cache_miss)

        self.total_fetch_latency += latency
        if cache_miss:
            self.fetch_miss_count += 1
            self.total_fetch_penalty += max(0, latency - self.ICACHE_HIT_LATENCY)

        self.counters["fetch"] += 1
        return latency

    def decode_hook(self, inst) -> None:  # noqa: D401 - placeholder
        """디코드 훅 자리표시자."""

    def execute_hook(self, op) -> None:  # noqa: D401 - placeholder
        """실행 훅 자리표시자."""

    def memory_hook(self, address: int, size: int, is_write: bool) -> int:
        idx = self.counters["memory"]

        if idx < self.buffer_size:
            self.memory_stats[idx] = (
                self.MEMORY_ACCESS_LATENCY,
                address,
                size,
                is_write,
            )

        self.counters["memory"] += 1
        return self.MEMORY_ACCESS_LATENCY

    def metrics(self) -> dict[str, float | int]:
        total_fetches = self.counters.get("fetch", 0)
        misses = self.fetch_miss_count
        miss_rate = (misses / total_fetches) if total_fetches else 0.0
        hit_rate = 1.0 - miss_rate if total_fetches else 0.0
        average_latency = (self.total_fetch_latency / total_fetches) if total_fetches else 0.0
        return {
            "fetches": total_fetches,
            "misses": misses,
            "hit_rate": hit_rate,
            "miss_rate": miss_rate,
            "average_latency": average_latency,
            "miss_penalty_cycles": self.total_fetch_penalty,
        }
