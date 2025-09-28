import asyncio
import hashlib
import json

from src.simulator.cli import prepare_summary
from src.simulator.main import AdaptiveSimulator


def _hash_summary(summary: dict) -> str:
    canonical = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _run_add_workload() -> dict:
    simulator = AdaptiveSimulator()
    # Simple ADD stream followed by implicit halt sentinel.
    add_instruction = 0x003100B3
    program = [add_instruction] * 16
    simulator.load_program(program)
    report = asyncio.run(simulator.run_simulation(max_cycles=64))
    summary = prepare_summary(report, simulator.risc_v_engine.instruction_count)
    summary.pop("elapsed_seconds", None)
    summary.pop("mips", None)
    return summary


def test_simulation_is_deterministic_across_runs() -> None:
    first = _hash_summary(_run_add_workload())
    second = _hash_summary(_run_add_workload())
    assert first == second
