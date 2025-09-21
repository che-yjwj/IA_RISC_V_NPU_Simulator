import numpy as np

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


def test_adaptive_simulator_produces_repeatable_random_choices():
    # Force deterministic baseline before constructing the simulators.
    configure_deterministic_environment(force=True, seed=42)

    sim_a = AdaptiveSimulator()
    choices_a = np.copy(sim_a.timing_hooks.random_choices)

    # Force re-configuration to reset the RNG state for a true apples-to-apples comparison
    configure_deterministic_environment(force=True, seed=42)
    sim_b = AdaptiveSimulator()
    choices_b = np.copy(sim_b.timing_hooks.random_choices)

    assert np.array_equal(choices_a, choices_b)
