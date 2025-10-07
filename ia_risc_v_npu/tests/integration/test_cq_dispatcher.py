from pathlib import Path

import numpy as np

from src.cq import (
    CQDispatcher,
    build_execution_plan,
    load_cq_trace,
    load_isa_spec,
)
from src.simulator.identifiers import SPM as SPM_REGION
from src.simulator.main import AdaptiveSimulator


def test_sample_gemm_dispatch_flow(tmp_path):
    root = Path(__file__).resolve().parents[3]
    trace_path = root / "workloads" / "cq" / "sample_gemm.jsonl"

    queue = load_cq_trace(trace_path)
    spec = load_isa_spec()

    plan = build_execution_plan(queue, spec)
    dispatcher = CQDispatcher()
    outcome = dispatcher.run(queue)

    # All commands should be scheduled and completed because dependencies form a chain.
    assert outcome.commands_executed == len(queue)
    assert outcome.trace.scheduled == list(queue.command_ids())
    assert outcome.trace.rejected == []

    # The execution plan should mirror the dispatcher order (load -> compute -> store).
    assert plan.summary() == {"dma": 2, "gemm": 1, "fence": 0}
    # Validate dispatcher processed the same set of command IDs recorded in the plan.
    plan_command_ids = {op.cmd_id for op in plan.dma_ops}
    plan_command_ids.update(op.cmd_id for op in plan.gemm_ops)
    plan_command_ids.update(op.cmd_id for op in plan.fence_ops)
    assert plan_command_ids == set(outcome.trace.completed)

    # Each command should have a full lifecycle of queued → scheduled → completed.
    for cmd_id in queue.command_ids():
        assert outcome.trace.states(cmd_id) == ("queued", "scheduled", "completed")

    # Trace metadata should expose the original trace payload (e.g., `ir_operation`).
    assert outcome.trace.trace_ids("gemm_0")["ir_operation"] == "matmul"

    # Basic queue statistics should be populated.
    assert outcome.stats.total_queue_wait > 0
    assert outcome.stats.max_queue_wait >= outcome.stats.average_queue_wait


def test_adaptive_simulator_cq_summary(tmp_path):
    root = Path(__file__).resolve().parents[3]
    trace_path = root / "workloads" / "cq" / "sample_gemm.jsonl"

    queue = load_cq_trace(trace_path)
    simulator = AdaptiveSimulator()
    m = n = k = 64
    inputs = np.eye(m, dtype=np.float32)
    weights = np.ones((k, n), dtype=np.float32)
    simulator.load_cq_tensors(
        {
            "dram://inputs": inputs,
            "dram://weights": weights,
        }
    )

    summary = simulator.run_cq_trace(queue)

    assert summary["plan_summary"] == {"dma": 2, "gemm": 1, "fence": 0}
    assert summary["dispatch"]["executed"] == len(queue)
    assert (
        summary["dispatch"]["queue_wait"]["max"]
        >= summary["dispatch"]["queue_wait"]["average"]
    )
    assert summary["status"] == "cq_actions_executed"
    assert {action["type"] for action in summary["actions"]} == {"dma", "gemm"}
    assert summary["execution"]["count"]["dma"] == 2
    assert summary["execution"]["count"]["gemm"] == 1
    assert summary["execution"]["dma_cycles"] > 0
    assert set(summary["execution"]["executed"]) == set(
        summary["dispatch"]["completed"]
    )
    assert summary["execution"]["skipped"] == []

    weights_entry = simulator._cq_dram_allocations["weights"]
    weights_bytes = simulator.bus.read(weights_entry["base"], weights_entry["size"])
    loaded_weights = np.frombuffer(weights_bytes, dtype=np.float32).reshape((k, n))
    np.testing.assert_allclose(loaded_weights, weights, rtol=1e-5, atol=1e-6)

    spm_entry = simulator._cq_spm_allocations["tile0"]
    spm_bytes = simulator.bus.read(
        SPM_REGION.base + spm_entry["offset"], spm_entry["size"]
    )
    spm_tensor = np.frombuffer(spm_bytes, dtype=np.float32).reshape((m, n))

    outputs_entry = simulator._cq_dram_allocations["outputs"]
    out_bytes = simulator.bus.read(outputs_entry["base"], outputs_entry["size"])
    out = np.frombuffer(out_bytes, dtype=np.float32).reshape((m, n))
    expected = inputs @ weights
    np.testing.assert_allclose(spm_tensor, expected, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out, expected, rtol=1e-5, atol=1e-6)
