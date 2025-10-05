import asyncio

from src.simulator.cli import prepare_summary
from src.simulator.determinism import configure_deterministic_environment
from src.simulator.main import AdaptiveSimulator


def test_configure_deterministic_environment_sets_env():
    env: dict[str, str] = {}
    configure_deterministic_environment(seed=123, env=env, force=True)

    expected_vars = {
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "PYTHONHASHSEED": "123",
    }
    for key, value in expected_vars.items():
        assert env.get(key) == value


def _run_fetch_summary(seed: int) -> dict:
    configure_deterministic_environment(force=True, seed=seed)
    simulator = AdaptiveSimulator()
    program = [0x003100B3] * 8
    simulator.load_program(program)

    async def scenario() -> dict:
        report = await simulator.run_simulation(max_cycles=16)
        return prepare_summary(report, simulator.risc_v_engine.instruction_count)[
            "fetch_metrics"
        ]

    return asyncio.run(scenario())


def test_adaptive_simulator_fetch_metrics_repeatable():
    metrics_a = _run_fetch_summary(seed=7)
    metrics_b = _run_fetch_summary(seed=7)
    assert metrics_a == metrics_b
