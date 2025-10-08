import copy
import logging
from argparse import Namespace

import pytest

from src.cq import SchedulingPolicy
from src.simulator import cli


def _mock_args(**overrides):
    base = {
        "config": None,
        "verbose": False,
        "log_level": None,
        "log_path": None,
        "trace": [],
        "scheduler_policy": None,
        "cq_policy": None,
        "cq_lane_limit": None,
        "simulate": False,
    }
    base.update(overrides)
    return Namespace(**base)


def test_setup_environment_applies_cq_overrides(monkeypatch):
    template = cli.default_simulator_config()
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: copy.deepcopy(template),
    )
    monkeypatch.setattr(
        cli,
        "configure_logging",
        lambda *args, **kwargs: logging.getLogger("simulator"),
    )

    args = _mock_args(
        cq_policy=SchedulingPolicy.EARLIEST_DEADLINE_FIRST.value,
        cq_lane_limit=["dma=3", "te=2"],
    )

    config, _ = cli._setup_environment(args)
    dispatcher = config["cq"]["dispatcher"]
    assert dispatcher["policy"] == SchedulingPolicy.EARLIEST_DEADLINE_FIRST.value
    assert dispatcher["lane_limits"]["dma"] == 3
    assert dispatcher["lane_limits"]["te"] == 2


def test_setup_environment_rejects_invalid_lane(monkeypatch):
    template = cli.default_simulator_config()
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: copy.deepcopy(template),
    )
    monkeypatch.setattr(
        cli,
        "configure_logging",
        lambda *args, **kwargs: logging.getLogger("simulator"),
    )

    args = _mock_args(cq_lane_limit=["dma=0"])
    with pytest.raises(cli.CLIError):
        cli._setup_environment(args)
