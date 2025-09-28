import copy

import pytest

from src.simulator.config import (
    ConfigValidationError,
    default_simulator_config,
    validate_simulator_config,
)


def test_validate_simulator_config_returns_defaults_when_empty():
    defaults = default_simulator_config()
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
