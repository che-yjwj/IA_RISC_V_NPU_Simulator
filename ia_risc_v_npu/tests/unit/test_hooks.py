from src.simulator.hooks import TimingHookSystem


def test_timing_hook_metrics_reports_rates() -> None:
    hooks = TimingHookSystem(buffer_size=16, miss_period=2)

    for idx in range(8):
        hooks.fetch_hook(idx, 0)

    metrics = hooks.metrics()
    assert metrics["fetches"] == 8
    assert metrics["misses"] >= 0
    assert metrics["miss_rate"] >= 0.0
    assert metrics["average_latency"] >= 0.0
    assert metrics["miss_penalty_cycles"] >= 0
