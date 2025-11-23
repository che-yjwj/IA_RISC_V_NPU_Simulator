import json
from pathlib import Path

import numpy as np

from src.cq import (
    CommandQueue,
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
    assert plan.summary() == {"dma": 2, "gemm": 1, "vector": 0, "fence": 0}
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
    assert outcome.stats.total_queue_wait >= 0
    assert outcome.stats.max_queue_wait >= outcome.stats.average_queue_wait
    assert outcome.stats.lane_totals == {"dma": 2, "te": 1}
    assert outcome.stats.lane_max_concurrency["dma"] == 1
    assert outcome.stats.lane_max_concurrency["te"] == 1


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

    assert summary["plan_summary"] == {
        "dma": 2,
        "gemm": 1,
        "vector": 0,
        "fence": 0,
    }
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
    assert summary["dispatch"]["lane_usage"]["totals"] == {"dma": 2, "te": 1}
    assert summary["dispatch"]["lane_usage"]["max_concurrency"]["dma"] == 1

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


def test_cq_dma_contention_roundtrip():
    data = np.arange(1024, dtype=np.float32).reshape((32, 32))
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "dma_stage",
                "opcode": "DMA_2D",
                "operands": {
                    "src": "dram://weights",
                    "dst": "spm://tile0",
                    "shape": [32, 32],
                    "strides": [32, 1],
                },
                "trace": {"isa_idx": 0, "ir_operation": "load_weights"},
            },
            {
                "cmd_id": "dma_store",
                "opcode": "DMA_2D",
                "deps": ["dma_stage"],
                "operands": {
                    "src": "spm://tile0",
                    "dst": "dram://outputs",
                    "shape": [32, 32],
                    "strides": [32, 1],
                },
                "trace": {"isa_idx": 1, "ir_operation": "store_outputs"},
            },
        ],
        strict=True,
    )

    simulator = AdaptiveSimulator()
    simulator.load_cq_tensors({"dram://weights": data})

    summary = simulator.run_cq_trace(queue)

    assert summary["dispatch"]["executed"] == len(queue)
    assert summary["execution"]["count"]["dma"] == 2
    assert summary["execution"]["dma_cycles"] > 0
    assert summary["execution"]["dma_bytes"] == data.size * data.itemsize * 2

    outputs_entry = simulator._cq_dram_allocations["outputs"]
    out_bytes = simulator.bus.read(outputs_entry["base"], outputs_entry["size"])
    out = np.frombuffer(out_bytes, dtype=np.float32).reshape(data.shape)
    np.testing.assert_allclose(out, data, rtol=1e-5, atol=1e-6)


def test_cq_interleaved_gemm_dma_with_fence():
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "dma_a",
                "opcode": "DMA_2D",
                "operands": {
                    "src": "dram://inputs_a",
                    "dst": "spm://tile_a",
                    "shape": [32, 16],
                    "strides": [16, 1],
                },
                "trace": {"isa_idx": 0, "ir_operation": "load_a"},
            },
            {
                "cmd_id": "dma_b",
                "opcode": "DMA_2D",
                "operands": {
                    "src": "dram://inputs_b",
                    "dst": "spm://tile_b",
                    "shape": [16, 8],
                    "strides": [8, 1],
                },
                "trace": {"isa_idx": 1, "ir_operation": "load_b"},
            },
            {
                "cmd_id": "gemm_main",
                "opcode": "TE_GEMM",
                "deps": ["dma_a", "dma_b"],
                "operands": {
                    "m": 32,
                    "n": 8,
                    "k": 16,
                    "a": "spm://tile_a",
                    "b": "spm://tile_b",
                    "c": "dram://outputs",
                },
                "trace": {"isa_idx": 2, "ir_operation": "matmul"},
            },
            {
                "cmd_id": "fence_flush",
                "opcode": "FENCE_SPM",
                "deps": ["gemm_main"],
                "operands": {},
                "trace": {"isa_idx": 3, "ir_operation": "fence"},
            },
            {
                "cmd_id": "dma_out",
                "opcode": "DMA_2D",
                "deps": ["fence_flush"],
                "operands": {
                    "src": "dram://outputs",
                    "dst": "dram://final",
                    "shape": [32, 8],
                    "strides": [8, 1],
                },
                "trace": {"isa_idx": 4, "ir_operation": "store"},
            },
        ],
        strict=True,
    )

    m, n, k = 32, 8, 16
    inputs_a = np.arange(m * k, dtype=np.float32).reshape((m, k))
    inputs_b = np.linspace(1, 2, num=k * n, dtype=np.float32).reshape((k, n))

    simulator = AdaptiveSimulator()
    simulator.load_cq_tensors(
        {
            "dram://inputs_a": inputs_a,
            "dram://inputs_b": inputs_b,
        }
    )

    summary = simulator.run_cq_trace(queue)

    assert summary["dispatch"]["executed"] == len(queue)
    counts = summary["execution"]["count"]
    assert counts["dma"] == 3  # two loads + store
    assert counts["gemm"] == 1
    assert counts["fence"] == 1

    final_entry = simulator._cq_dram_allocations["final"]
    final_bytes = simulator.bus.read(final_entry["base"], final_entry["size"])
    final = np.frombuffer(final_bytes, dtype=np.float32).reshape((m, n))
    np.testing.assert_allclose(final, inputs_a @ inputs_b, rtol=1e-5, atol=1e-6)


def test_cq_multi_gemm_with_repeated_fence():
    queue = CommandQueue.from_iterable(
        [
            {
                "cmd_id": "dma_tile0_a",
                "opcode": "DMA_2D",
                "operands": {
                    "src": "dram://inputs0_a",
                    "dst": "spm://tile0_a",
                    "shape": [16, 16],
                    "strides": [16, 1],
                },
                "trace": {"isa_idx": 0, "ir_operation": "load0_a"},
            },
            {
                "cmd_id": "dma_tile0_b",
                "opcode": "DMA_2D",
                "operands": {
                    "src": "dram://inputs0_b",
                    "dst": "spm://tile0_b",
                    "shape": [16, 16],
                    "strides": [16, 1],
                },
                "trace": {"isa_idx": 1, "ir_operation": "load0_b"},
            },
            {
                "cmd_id": "gemm_tile0",
                "opcode": "TE_GEMM",
                "deps": ["dma_tile0_a", "dma_tile0_b"],
                "operands": {
                    "m": 16,
                    "n": 16,
                    "k": 16,
                    "a": "spm://tile0_a",
                    "b": "spm://tile0_b",
                    "c": "dram://accum",
                },
                "trace": {"isa_idx": 2, "ir_operation": "gemm0"},
            },
            {
                "cmd_id": "fence_tile0",
                "opcode": "FENCE_SPM",
                "deps": ["gemm_tile0"],
                "operands": {},
                "trace": {"isa_idx": 3, "ir_operation": "fence0"},
            },
            {
                "cmd_id": "dma_tile1_a",
                "opcode": "DMA_2D",
                "deps": ["fence_tile0"],
                "operands": {
                    "src": "dram://inputs1_a",
                    "dst": "spm://tile1_a",
                    "shape": [16, 16],
                    "strides": [16, 1],
                },
                "trace": {"isa_idx": 4, "ir_operation": "load1_a"},
            },
            {
                "cmd_id": "dma_tile1_b",
                "opcode": "DMA_2D",
                "deps": ["fence_tile0"],
                "operands": {
                    "src": "dram://inputs1_b",
                    "dst": "spm://tile1_b",
                    "shape": [16, 16],
                    "strides": [16, 1],
                },
                "trace": {"isa_idx": 5, "ir_operation": "load1_b"},
            },
            {
                "cmd_id": "gemm_tile1",
                "opcode": "TE_GEMM",
                "deps": ["dma_tile1_a", "dma_tile1_b"],
                "operands": {
                    "m": 16,
                    "n": 16,
                    "k": 16,
                    "a": "spm://tile1_a",
                    "b": "spm://tile1_b",
                    "c": "dram://accum",
                },
                "trace": {"isa_idx": 6, "ir_operation": "gemm1"},
            },
            {
                "cmd_id": "fence_tile1",
                "opcode": "FENCE_SPM",
                "deps": ["gemm_tile1"],
                "operands": {},
                "trace": {"isa_idx": 7, "ir_operation": "fence1"},
            },
            {
                "cmd_id": "dma_flush",
                "opcode": "DMA_2D",
                "deps": ["fence_tile1"],
                "operands": {
                    "src": "dram://accum",
                    "dst": "dram://output",
                    "shape": [16, 16],
                    "strides": [16, 1],
                },
                "trace": {"isa_idx": 8, "ir_operation": "flush"},
            },
        ],
        strict=True,
    )

    tile_shape = (16, 16)
    inputs0_a = np.random.default_rng(0).standard_normal(tile_shape).astype(np.float32)
    inputs0_b = np.random.default_rng(1).standard_normal(tile_shape).astype(np.float32)
    inputs1_a = np.random.default_rng(2).standard_normal(tile_shape).astype(np.float32)
    inputs1_b = np.random.default_rng(3).standard_normal(tile_shape).astype(np.float32)

    simulator = AdaptiveSimulator()
    simulator.load_cq_tensors(
        {
            "dram://inputs0_a": inputs0_a,
            "dram://inputs0_b": inputs0_b,
            "dram://inputs1_a": inputs1_a,
            "dram://inputs1_b": inputs1_b,
            "dram://accum": np.zeros(tile_shape, dtype=np.float32),
        }
    )

    summary = simulator.run_cq_trace(queue)

    assert summary["dispatch"]["executed"] == len(queue)
    counts = summary["execution"]["count"]
    assert counts["gemm"] == 2
    assert counts["fence"] == 2
    assert counts["dma"] == 5

    output_entry = simulator._cq_dram_allocations["output"]
    output_bytes = simulator.bus.read(output_entry["base"], output_entry["size"])
    output = np.frombuffer(output_bytes, dtype=np.float32).reshape(tile_shape)
    expected_last = inputs1_a @ inputs1_b
    np.testing.assert_allclose(output, expected_last, rtol=1e-5, atol=1e-6)

    accum_entry = simulator._cq_dram_allocations["accum"]
    accum_bytes = simulator.bus.read(accum_entry["base"], accum_entry["size"])
    accum = np.frombuffer(accum_bytes, dtype=np.float32).reshape(tile_shape)
    np.testing.assert_allclose(accum, expected_last, rtol=1e-5, atol=1e-6)


def test_vector_sample_queue_matches_golden_trace():
    root = Path(__file__).resolve().parents[3]
    trace_path = root / "workloads" / "cq" / "sample_vector_add.jsonl"
    golden_path = Path(__file__).parent / "golden" / "sample_vector_dispatch.json"

    queue = load_cq_trace(trace_path)
    dispatcher = CQDispatcher()
    outcome = dispatcher.run(queue)

    with golden_path.open("r", encoding="utf-8") as handle:
        golden = json.load(handle)

    assert outcome.trace.scheduled == golden["scheduled"]
    assert outcome.trace.completed == golden["completed"]
    assert outcome.stats.lane_totals == golden["lane_totals"]
    assert outcome.stats.lane_max_concurrency == golden["lane_max_concurrency"]
    assert outcome.stats.lane_max_queue_wait == golden["lane_max_queue_wait"]
    assert outcome.stats.lane_average_queue_wait == golden["lane_average_queue_wait"]
