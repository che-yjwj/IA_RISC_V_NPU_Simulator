"""Validation helpers for simulator configuration files.

This module centralises schema validation for the JSON configuration that the
CLI accepts.  It intentionally keeps the representation JSON-friendly so that
callers can continue to treat the result as a nested dictionary while still
benefiting from type and range checks.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, Dict

from src.npu.cluster import ClusterPolicy
from src.risc_v.engine import BranchPredictorConfig, ExecutionTimingConfig
from src.simulator.memory import CacheConfig, DRAMConfig

SUPPORTED_SCHEMA_VERSION = 1


DEFAULT_L1_CONFIG = CacheConfig(
    name="L1",
    size_bytes=32 * 1024,
    line_size=64,
    associativity=4,
    hit_latency=4,
)

DEFAULT_L2_CONFIG = CacheConfig(
    name="L2",
    size_bytes=256 * 1024,
    line_size=64,
    associativity=8,
    hit_latency=12,
)


class ConfigValidationError(ValueError):
    """Raised when a simulator configuration fails schema validation."""


def default_simulator_config() -> Dict[str, Any]:
    """Return a deep copy of the baseline simulator configuration."""

    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "max_cycles": 0,
        "cpu": {
            "execution": asdict(ExecutionTimingConfig()),
            "branch": asdict(BranchPredictorConfig()),
        },
        "cache": {
            "l1": asdict(DEFAULT_L1_CONFIG),
            "l2": asdict(DEFAULT_L2_CONFIG),
        },
        "bus": {
            "slice_bytes": DEFAULT_L1_CONFIG.line_size // 2,
            "bandwidth_bytes_per_cycle": 16,
            "grant_latency": 1,
        },
        "dram": asdict(DRAMConfig()),
        "npu": {
            "cores": 2,
            "policy": ClusterPolicy.MIN_FINISH_TIME.value,
        },
        "determinism": {
            "seed": 0,
            "blas_threads": 1,
        },
        "accuracy_guard": {
            "enabled": False,
            "golds_path": None,
            "max_average_deviation": 0.15,
            "max_single_deviation": 0.2,
        },
        "logging": {
            "level": "INFO",
            "path": None,
            "trace_components": [],
        },
    }


def _validate_int(name: str, value: Any, *, minimum: int | None = None) -> int:
    if not isinstance(value, int):
        raise ConfigValidationError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ConfigValidationError(f"{name} must be >= {minimum}")
    return value


def _validate_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ConfigValidationError(f"{name} must be a boolean")
    return value


def _validate_float(name: str, value: Any, *, minimum: float | None = None) -> float:
    if not isinstance(value, (int, float)):
        raise ConfigValidationError(f"{name} must be a number")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ConfigValidationError(f"{name} must be >= {minimum}")
    return numeric


def _validate_cpu_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("cpu section must be an object")
    result = deepcopy(defaults)

    if "execution" in data:
        exec_data = data["execution"]
        if not isinstance(exec_data, dict):
            raise ConfigValidationError("cpu.execution must be an object")
        execution = deepcopy(result["execution"])
        for key in ("alu_latency", "load_use_stall", "mul_latency", "div_latency"):
            if key in exec_data:
                execution[key] = _validate_int(
                    f"cpu.execution.{key}", exec_data[key], minimum=0
                )
        result["execution"] = execution

    if "branch" in data:
        branch_data = data["branch"]
        if not isinstance(branch_data, dict):
            raise ConfigValidationError("cpu.branch must be an object")
        branch = deepcopy(result["branch"])
        if "mispredict_penalty" in branch_data:
            branch["mispredict_penalty"] = _validate_int(
                "cpu.branch.mispredict_penalty",
                branch_data["mispredict_penalty"],
                minimum=0,
            )
        if "static_backwards_taken" in branch_data:
            branch["static_backwards_taken"] = _validate_bool(
                "cpu.branch.static_backwards_taken",
                branch_data["static_backwards_taken"],
            )
        result["branch"] = branch

    return result


def _validate_cache_level(
    name: str, data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError(f"cache.{name} must be an object")
    result = deepcopy(defaults)
    for key in ("size_bytes", "line_size", "associativity", "hit_latency"):
        if key in data:
            result[key] = _validate_int(f"cache.{name}.{key}", data[key], minimum=1)
    for key in ("write_back", "write_allocate"):
        if key in data:
            result[key] = _validate_bool(f"cache.{name}.{key}", data[key])
    return result


def _validate_cache_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("cache section must be an object")
    result = deepcopy(defaults)
    if "l1" in data:
        result["l1"] = _validate_cache_level("l1", data["l1"], defaults["l1"])
    if "l2" in data:
        result["l2"] = _validate_cache_level("l2", data["l2"], defaults["l2"])
    return result


def _validate_bus_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("bus section must be an object")
    result = deepcopy(defaults)
    for key in ("slice_bytes", "bandwidth_bytes_per_cycle", "grant_latency"):
        if key in data:
            minimum = 0 if key == "grant_latency" else 1
            result[key] = _validate_int(f"bus.{key}", data[key], minimum=minimum)
    return result


def _validate_dram_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("dram section must be an object")
    result = deepcopy(defaults)
    for key in (
        "banks",
        "row_size",
        "line_size",
        "t_rp",
        "t_rcd",
        "t_cas",
        "data_bytes_per_cycle",
    ):
        if key in data:
            minimum = 0 if key.startswith("t_") else 1
            result[key] = _validate_int(f"dram.{key}", data[key], minimum=minimum)
    return result


def _validate_npu_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("npu section must be an object")
    result = deepcopy(defaults)
    if "cores" in data:
        result["cores"] = _validate_int("npu.cores", data["cores"], minimum=1)
    if "policy" in data:
        if not isinstance(data["policy"], str):
            raise ConfigValidationError("npu.policy must be a string")
        normalised = data["policy"].lower()
        valid = {policy.value: policy for policy in ClusterPolicy}
        if normalised not in valid:
            raise ConfigValidationError(f"npu.policy must be one of {sorted(valid)}")
        result["policy"] = normalised
    return result


def _validate_determinism_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("determinism section must be an object")
    result = deepcopy(defaults)
    if "seed" in data:
        result["seed"] = _validate_int("determinism.seed", data["seed"], minimum=0)
    if "blas_threads" in data:
        result["blas_threads"] = _validate_int(
            "determinism.blas_threads", data["blas_threads"], minimum=1
        )
    return result


def _validate_accuracy_guard_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("accuracy_guard section must be an object")
    result = deepcopy(defaults)
    if "enabled" in data:
        result["enabled"] = _validate_bool("accuracy_guard.enabled", data["enabled"])
    if "golds_path" in data:
        path_value = data["golds_path"]
        if path_value is not None and not isinstance(path_value, str):
            raise ConfigValidationError(
                "accuracy_guard.golds_path must be null or string"
            )
        result["golds_path"] = path_value
    if "max_average_deviation" in data:
        result["max_average_deviation"] = _validate_float(
            "accuracy_guard.max_average_deviation",
            data["max_average_deviation"],
            minimum=0.0,
        )
    if "max_single_deviation" in data:
        result["max_single_deviation"] = _validate_float(
            "accuracy_guard.max_single_deviation",
            data["max_single_deviation"],
            minimum=0.0,
        )
    return result


_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _validate_logging_section(
    data: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigValidationError("logging section must be an object")
    result = deepcopy(defaults)
    if "level" in data:
        level = data["level"]
        if not isinstance(level, str):
            raise ConfigValidationError("logging.level must be a string")
        if level.upper() not in _ALLOWED_LOG_LEVELS:
            raise ConfigValidationError(
                f"logging.level must be one of {sorted(_ALLOWED_LOG_LEVELS)}"
            )
        result["level"] = level.upper()

    if "path" in data:
        path = data["path"]
        if path is not None and not isinstance(path, str):
            raise ConfigValidationError("logging.path must be a string or null")
        result["path"] = path

    if "trace_components" in data:
        components = data["trace_components"]
        if not isinstance(components, list) or not all(
            isinstance(c, str) for c in components
        ):
            raise ConfigValidationError(
                "logging.trace_components must be a list of strings"
            )
        result["trace_components"] = components

    return result


def validate_simulator_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate ``raw`` and return a sanitised simulator configuration.

    The returned dictionary always contains defaults for omitted sections so the
    rest of the code base can rely on keys being present.
    """

    defaults = default_simulator_config()

    if not raw:
        return defaults
    if not isinstance(raw, dict):
        raise ConfigValidationError("Config file must contain a JSON object")

    schema_version = raw.get("schema_version", defaults["schema_version"])
    schema_version = _validate_int("schema_version", schema_version, minimum=1)
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ConfigValidationError(
            f"Unsupported schema_version={schema_version}; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )
    defaults["schema_version"] = schema_version

    if "max_cycles" in raw:
        defaults["max_cycles"] = _validate_int(
            "max_cycles", raw["max_cycles"], minimum=0
        )

    if "cpu" in raw:
        defaults["cpu"] = _validate_cpu_section(raw["cpu"], defaults["cpu"])

    if "cache" in raw:
        defaults["cache"] = _validate_cache_section(raw["cache"], defaults["cache"])

    if "bus" in raw:
        defaults["bus"] = _validate_bus_section(raw["bus"], defaults["bus"])

    if "dram" in raw:
        defaults["dram"] = _validate_dram_section(raw["dram"], defaults["dram"])

    if "npu" in raw:
        defaults["npu"] = _validate_npu_section(raw["npu"], defaults["npu"])

    if "determinism" in raw:
        defaults["determinism"] = _validate_determinism_section(
            raw["determinism"], defaults["determinism"]
        )

    if "accuracy_guard" in raw:
        defaults["accuracy_guard"] = _validate_accuracy_guard_section(
            raw["accuracy_guard"], defaults["accuracy_guard"]
        )

    if "logging" in raw:
        defaults["logging"] = _validate_logging_section(
            raw["logging"], defaults["logging"]
        )

    return defaults


__all__ = [
    "ConfigValidationError",
    "SUPPORTED_SCHEMA_VERSION",
    "default_simulator_config",
    "validate_simulator_config",
]
