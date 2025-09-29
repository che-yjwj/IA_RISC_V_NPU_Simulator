import copy

import pytest

from src.simulator.config import (
    ConfigValidationError,
    default_simulator_config,
    validate_simulator_config,
)
from src.simulator.main import AdaptiveSimulator


def _clone_config() -> dict:
    """Return a writable copy of the default simulator config."""

    return copy.deepcopy(default_simulator_config())


def test_validate_simulator_config_returns_defaults_when_empty():
    defaults = _clone_config()
    validated = validate_simulator_config({})
    assert validated == defaults
    # ensure callers receive independent copies
    validated["cpu"]["execution"]["alu_latency"] = 99
    assert default_simulator_config()["cpu"]["execution"]["alu_latency"] == 1


def test_validate_simulator_config_applies_overrides():
    overrides = {
        "cpu": {"execution": {"alu_latency": 2}},
        "cache": {"l1": {"line_size": 128}},
        "bus": {"bandwidth_bytes_per_cycle": 32},
        "dram": {"t_cas": 14},
        "npu": {"policy": "rr", "cores": 4},
        "determinism": {"seed": 7, "blas_threads": 2},
    }
    validated = validate_simulator_config(overrides)
    assert validated["cpu"]["execution"]["alu_latency"] == 2
    assert validated["cache"]["l1"]["line_size"] == 128
    assert validated["bus"]["bandwidth_bytes_per_cycle"] == 32
    assert validated["dram"]["t_cas"] == 14
    assert validated["npu"]["policy"] == "rr"
    assert validated["npu"]["cores"] == 4
    assert validated["determinism"]["seed"] == 7
    assert validated["determinism"]["blas_threads"] == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 0},
        {"bus": {"slice_bytes": 0}},
        {"cpu": {"execution": {"mul_latency": -1}}},
        {"npu": {"policy": "invalid"}},
        {"determinism": {"blas_threads": 0}},
        {"accuracy_guard": {"max_single_deviation": -0.1}},
    ],
)
def test_validate_simulator_config_rejects_invalid(payload):
    with pytest.raises(ConfigValidationError):
        validate_simulator_config(copy.deepcopy(payload))


def test_adaptive_simulator_applies_validated_config(monkeypatch):
    config = _clone_config()
    config["determinism"]["seed"] = 123
    config["determinism"]["blas_threads"] = 4
    config["bus"].update({
        "slice_bytes": 48,
        "bandwidth_bytes_per_cycle": 24,
        "grant_latency": 3,
    })
    config["cache"]["l1"].update({"hit_latency": 6, "size_bytes": 16 * 1024})
    config["cache"]["l2"].update({"associativity": 16})
    config["dram"].update({"t_cas": 18, "banks": 4})
    config["cpu"]["execution"].update({"alu_latency": 5, "div_latency": 20})
    config["cpu"]["branch"].update({"mispredict_penalty": 7, "static_backwards_taken": False})
    config["npu"].update({"cores": 3, "policy": "rr"})

    captured = {}

    def fake_configure(seed, **kwargs):
        captured["seed"] = seed
        captured["config"] = kwargs.get("config")
        captured["logger"] = kwargs.get("logger")

    monkeypatch.setattr(
        "src.simulator.main.configure_deterministic_environment",
        fake_configure,
    )

    simulator = AdaptiveSimulator(config=config)

    assert captured["seed"] == 123
    assert captured["config"].env_thread_value == "4"
    assert simulator.bus.slice_bytes == 48
    assert simulator.bus.bandwidth_bytes_per_cycle == 24
    assert simulator.bus.grant_latency == 3
    assert simulator.memory_system.dram.config.t_cas == 18
    assert simulator.memory_system.dram.config.banks == 4
    l1_config = simulator.memory_system._caches[0].config
    l2_config = simulator.memory_system._caches[1].config
    assert l1_config.hit_latency == 6
    assert l1_config.size_bytes == 16 * 1024
    assert l2_config.associativity == 16
    assert simulator.risc_v_engine.exec_timing.alu_latency == 5
    assert simulator.risc_v_engine.exec_timing.div_latency == 20
    assert simulator.risc_v_engine.branch_config.mispredict_penalty == 7
    assert simulator.risc_v_engine.branch_config.static_backwards_taken is False
    assert simulator.npu_cluster.cores == 3
    assert simulator.npu_cluster.policy.value == "rr"
