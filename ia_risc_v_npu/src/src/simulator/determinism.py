"""Utilities for configuring deterministic runtime behaviour."""

from __future__ import annotations

import logging
import os
import random
import threading
from dataclasses import dataclass
from typing import MutableMapping, Optional

try:  # pragma: no cover - dependency already required elsewhere but guard for safety
    import numpy as np
except ImportError:  # pragma: no cover - numpy is required in normal operation
    np = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)
_CONFIG_LOCK = threading.Lock()


@dataclass(frozen=True)
class DeterminismConfig:
    seed: int = 0
    thread_env_vars: tuple[str, ...] = (
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OMP_NUM_THREADS",
    )
    env_thread_value: str = "1"
    set_python_hash_seed: bool = True


_CONFIGURED = False


def _set_env_targets(
    *,
    env: MutableMapping[str, str],
    config: DeterminismConfig,
    logger: logging.Logger,
) -> None:
    for var in config.thread_env_vars:
        previous = env.get(var)
        if previous == config.env_thread_value:
            continue
        env[var] = config.env_thread_value
        logger.debug("Set %s=%s (previous=%s)", var, config.env_thread_value, previous)

    if config.set_python_hash_seed and "PYTHONHASHSEED" not in env:
        env["PYTHONHASHSEED"] = str(config.seed)
        logger.debug("Set PYTHONHASHSEED=%s", config.seed)
    elif config.set_python_hash_seed:
        logger.debug(
            "PYTHONHASHSEED already set to %s; leaving unchanged",
            env.get("PYTHONHASHSEED"),
        )


def configure_deterministic_environment(
    seed: int = 0,
    *,
    logger: Optional[logging.Logger] = None,
    env: Optional[MutableMapping[str, str]] = None,
    reset_rng: bool = True,
    force: bool = False,
    config: Optional[DeterminismConfig] = None,
) -> None:
    """Apply process-wide knobs to reduce nondeterminism.

    Args:
        seed: Seed used for Python's ``random`` module and NumPy.
        logger: Optional logger used for debug output.
        env: Mapping that receives environment updates. Defaults to ``os.environ``.
        reset_rng: Reseed PRNGs even if configuration already applied.
        force: If ``True``, re-apply environment settings even when previously
            configured.
        config: Override the default configuration bundle.
    """

    global _CONFIGURED
    target_env = env if env is not None else os.environ
    logger = logger or LOGGER
    active_config = config or DeterminismConfig(seed=seed)

    with _CONFIG_LOCK:
        if _CONFIGURED and not force:
            logger.debug("Environment already configured for determinism; skipping.")
            return

        if force:
            _CONFIGURED = False

        if not _CONFIGURED:
            _set_env_targets(env=target_env, config=active_config, logger=logger)
            _CONFIGURED = True

    if reset_rng:
        random.seed(active_config.seed)
        logger.debug("Seeded python random RNG with %s", active_config.seed)
        if np is not None:
            np.random.seed(active_config.seed)
            logger.debug("Seeded NumPy RNG with %s", active_config.seed)
        else:  # pragma: no cover - NumPy is expected to be present
            logger.warning("NumPy not available; skipping RNG seed")


__all__ = ["configure_deterministic_environment", "DeterminismConfig"]
